from __future__ import annotations

from uuid import uuid4

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode, SubManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.states import RemnashopBotMenu
from src.core.config import AppConfig
from src.core.constants import USER_KEY
from src.core.enums import BotMenuCustomButtonKind
from src.core.utils.bot_menu import (
    BOT_MENU_MAX_CUSTOM_BUTTONS,
    is_valid_bot_menu_web_app_url,
    resolve_bot_menu_web_app_url,
)
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.validators import is_double_click
from src.infrastructure.database.models.dto import BotMenuCustomButtonDto, SettingsDto, UserDto
from src.services.notification import NotificationService
from src.services.settings import SettingsService

BUTTON_CLEAR_COMMANDS = {"/clear", "clear", "-"}


def _sorted_buttons(buttons: list[BotMenuCustomButtonDto]) -> list[BotMenuCustomButtonDto]:
    return sorted(buttons, key=lambda item: (item.order, item.id))


def _normalize_buttons(buttons: list[BotMenuCustomButtonDto]) -> list[BotMenuCustomButtonDto]:
    normalized: list[BotMenuCustomButtonDto] = []
    for order, button in enumerate(_sorted_buttons(buttons)):
        normalized.append(
            BotMenuCustomButtonDto.model_validate({**button.model_dump(), "order": order})
        )
    return normalized


def _assign_buttons(settings: SettingsDto, buttons: list[BotMenuCustomButtonDto]) -> None:
    settings.bot_menu.custom_buttons = _normalize_buttons(buttons)


def _find_selected_button(
    dialog_manager: DialogManager,
    settings: SettingsDto,
) -> tuple[list[BotMenuCustomButtonDto], int, BotMenuCustomButtonDto] | None:
    selected_button_id = str(dialog_manager.dialog_data.get("bot_menu_button_id", "")).strip()
    custom_buttons = _normalize_buttons(settings.bot_menu.custom_buttons)
    for index, button in enumerate(custom_buttons):
        if button.id == selected_button_id:
            return custom_buttons, index, button
    return None


async def _notify(
    *,
    user: UserDto,
    notification_service: NotificationService,
    i18n_key: str,
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key=i18n_key),
    )


@inject
async def on_bot_menu_mode_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()

    if settings.bot_menu.miniapp_only_enabled:
        settings.bot_menu.miniapp_only_enabled = False
        await settings_service.update(settings)
        logger.info(f"{log(user)} Disabled mini app-first menu mode")
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-mode-disabled",
        )
        return

    resolved_url, _ = resolve_bot_menu_web_app_url(bot_menu=settings.bot_menu, config=config)
    if not resolved_url:
        logger.warning(f"{log(user)} Failed to enable mini app-first mode: no URL configured")
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-mode-missing-url",
        )
        return

    settings.bot_menu.miniapp_only_enabled = True
    await settings_service.update(settings)
    logger.info(f"{log(user)} Enabled mini app-first menu mode")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-mode-enabled",
    )


@inject
async def on_mini_app_url_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    if not message.text:
        return

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    normalized = message.text.strip()

    if normalized.lower() in BUTTON_CLEAR_COMMANDS:
        settings.bot_menu.mini_app_url = None
        resolved_url, _ = resolve_bot_menu_web_app_url(bot_menu=settings.bot_menu, config=config)
        if settings.bot_menu.miniapp_only_enabled and not resolved_url:
            settings.bot_menu.miniapp_only_enabled = False
            await settings_service.update(settings)
            logger.info(f"{log(user)} Cleared mini app URL and auto-disabled mini app-first mode")
            await _notify(
                user=user,
                notification_service=notification_service,
                i18n_key="ntf-bot-menu-url-cleared-disabled",
            )
        else:
            await settings_service.update(settings)
            logger.info(f"{log(user)} Cleared stored mini app URL")
            await _notify(
                user=user,
                notification_service=notification_service,
                i18n_key="ntf-bot-menu-url-cleared",
            )
        await dialog_manager.switch_to(state=RemnashopBotMenu.MAIN)
        return

    if not is_valid_bot_menu_web_app_url(normalized):
        logger.warning(
            f"{log(user)} Rejected mini app URL incompatible with Telegram WebApp buttons: "
            f"'{normalized}'"
        )
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-invalid-url",
        )
        return

    settings.bot_menu.mini_app_url = normalized
    try:
        await settings_service.update(settings)
    except Exception as exc:
        logger.warning(f"{log(user)} Invalid mini app URL '{normalized}': {exc}")
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-invalid-url",
        )
        return

    logger.info(f"{log(user)} Saved mini app URL for bot menu")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-url-saved",
    )
    await dialog_manager.switch_to(state=RemnashopBotMenu.MAIN)


@inject
async def on_custom_button_add(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    custom_buttons = _normalize_buttons(settings.bot_menu.custom_buttons)

    if len(custom_buttons) >= BOT_MENU_MAX_CUSTOM_BUTTONS:
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-button-limit",
        )
        return

    new_button = BotMenuCustomButtonDto(
        id=uuid4().hex,
        label=i18n.get("msg-bot-menu-new-button-label"),
        kind=BotMenuCustomButtonKind.URL,
        url="https://example.com",
        enabled=False,
        order=len(custom_buttons),
    )
    custom_buttons.append(new_button)
    _assign_buttons(settings, custom_buttons)
    await settings_service.update(settings)

    dialog_manager.dialog_data["bot_menu_button_id"] = new_button.id
    logger.info(f"{log(user)} Created bot menu custom button '{new_button.id}'")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-button-created",
    )
    await dialog_manager.switch_to(state=RemnashopBotMenu.BUTTON)


async def on_custom_button_select(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
) -> None:
    sub_manager.manager.dialog_data["bot_menu_button_id"] = str(sub_manager.item_id)
    await sub_manager.manager.switch_to(state=RemnashopBotMenu.BUTTON)


@inject
async def on_custom_button_toggle_enabled(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-button-not-found",
        )
        await dialog_manager.start(RemnashopBotMenu.MAIN, mode=StartMode.RESET_STACK)
        return

    buttons, index, button = selected
    buttons[index] = BotMenuCustomButtonDto.model_validate(
        {**button.model_dump(), "enabled": not button.enabled}
    )
    _assign_buttons(settings, buttons)
    await settings_service.update(settings)
    logger.info(f"{log(user)} Toggled custom button '{button.id}' enabled state")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-button-updated",
    )


@inject
async def on_custom_button_kind_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-button-not-found",
        )
        await dialog_manager.start(RemnashopBotMenu.MAIN, mode=StartMode.RESET_STACK)
        return

    buttons, index, button = selected
    next_kind = (
        BotMenuCustomButtonKind.WEB_APP
        if button.kind == BotMenuCustomButtonKind.URL
        else BotMenuCustomButtonKind.URL
    )
    if next_kind == BotMenuCustomButtonKind.WEB_APP and not is_valid_bot_menu_web_app_url(
        button.url
    ):
        logger.warning(
            f"{log(user)} Rejected custom button '{button.id}' WEB_APP toggle due to "
            f"incompatible URL '{button.url}'"
        )
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-invalid-url",
        )
        return

    buttons[index] = BotMenuCustomButtonDto.model_validate(
        {**button.model_dump(), "kind": next_kind}
    )
    _assign_buttons(settings, buttons)
    await settings_service.update(settings)
    logger.info(f"{log(user)} Toggled custom button '{button.id}' kind to '{next_kind}'")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-button-updated",
    )


@inject
async def on_custom_button_move_up(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        return

    buttons, index, button = selected
    if index <= 0:
        return

    buttons[index - 1], buttons[index] = buttons[index], buttons[index - 1]
    _assign_buttons(settings, buttons)
    await settings_service.update(settings)
    logger.info(f"{log(user)} Moved custom button '{button.id}' up")


@inject
async def on_custom_button_move_down(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        return

    buttons, index, button = selected
    if index >= len(buttons) - 1:
        return

    buttons[index], buttons[index + 1] = buttons[index + 1], buttons[index]
    _assign_buttons(settings, buttons)
    await settings_service.update(settings)
    logger.info(f"{log(user)} Moved custom button '{button.id}' down")


@inject
async def on_custom_button_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-button-not-found",
        )
        await dialog_manager.start(RemnashopBotMenu.MAIN, mode=StartMode.RESET_STACK)
        return

    buttons, _, button = selected
    if not is_double_click(dialog_manager, f"delete_bot_menu_button_{button.id}", cooldown=10):
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-double-click-confirm",
        )
        return

    settings.bot_menu.custom_buttons = [
        custom_button for custom_button in buttons if custom_button.id != button.id
    ]
    _assign_buttons(settings, settings.bot_menu.custom_buttons)
    await settings_service.update(settings)
    dialog_manager.dialog_data.pop("bot_menu_button_id", None)
    logger.info(f"{log(user)} Deleted custom button '{button.id}'")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-button-deleted",
    )
    await dialog_manager.start(RemnashopBotMenu.MAIN, mode=StartMode.RESET_STACK)


@inject
async def on_custom_button_label_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    if not message.text:
        return

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-button-not-found",
        )
        await dialog_manager.start(RemnashopBotMenu.MAIN, mode=StartMode.RESET_STACK)
        return

    buttons, index, button = selected
    try:
        buttons[index] = BotMenuCustomButtonDto.model_validate(
            {**button.model_dump(), "label": message.text}
        )
        _assign_buttons(settings, buttons)
        await settings_service.update(settings)
    except Exception as exc:
        logger.warning(f"{log(user)} Invalid custom button label: {exc}")
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-invalid-label",
        )
        return

    logger.info(f"{log(user)} Updated custom button '{button.id}' label")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-button-updated",
    )
    await dialog_manager.switch_to(state=RemnashopBotMenu.BUTTON)


@inject
async def on_custom_button_url_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    if not message.text:
        return

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    selected = _find_selected_button(dialog_manager, settings)
    if selected is None:
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-button-not-found",
        )
        await dialog_manager.start(RemnashopBotMenu.MAIN, mode=StartMode.RESET_STACK)
        return

    buttons, index, button = selected
    normalized = message.text.strip()
    if button.kind == BotMenuCustomButtonKind.WEB_APP and not is_valid_bot_menu_web_app_url(
        normalized
    ):
        logger.warning(
            f"{log(user)} Rejected WEB_APP custom button URL for '{button.id}': '{normalized}'"
        )
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-invalid-url",
        )
        return

    try:
        buttons[index] = BotMenuCustomButtonDto.model_validate(
            {**button.model_dump(), "url": normalized}
        )
        _assign_buttons(settings, buttons)
        await settings_service.update(settings)
    except Exception as exc:
        logger.warning(f"{log(user)} Invalid custom button URL: {exc}")
        await _notify(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-bot-menu-invalid-url",
        )
        return

    logger.info(f"{log(user)} Updated custom button '{button.id}' URL")
    await _notify(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-bot-menu-button-updated",
    )
    await dialog_manager.switch_to(state=RemnashopBotMenu.BUTTON)
