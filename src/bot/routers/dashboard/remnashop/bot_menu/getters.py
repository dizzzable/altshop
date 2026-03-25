from __future__ import annotations

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.enums import BotMenuCustomButtonKind
from src.core.utils.bot_menu import (
    BOT_MENU_MAX_CUSTOM_BUTTONS,
    BOT_MENU_SOURCE_CONFIG,
    BOT_MENU_SOURCE_SETTINGS,
    resolve_bot_menu_state,
)
from src.infrastructure.database.models.dto import BotMenuCustomButtonDto
from src.services.settings import SettingsService


def _sorted_buttons(buttons: list[BotMenuCustomButtonDto]) -> list[BotMenuCustomButtonDto]:
    return sorted(buttons, key=lambda item: (item.order, item.id))


def _resolve_source_label(source: str, i18n: TranslatorRunner) -> str:
    if source == BOT_MENU_SOURCE_SETTINGS:
        return i18n.get("msg-bot-menu-source-settings")
    if source == BOT_MENU_SOURCE_CONFIG:
        return i18n.get("msg-bot-menu-source-config")
    return i18n.get("msg-bot-menu-source-missing")


def _resolve_selected_button_data(
    *,
    settings_buttons: list[BotMenuCustomButtonDto],
    selected_button_id: str,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    custom_buttons = _sorted_buttons(settings_buttons)
    selected_index = next(
        (index for index, button in enumerate(custom_buttons) if button.id == selected_button_id),
        -1,
    )
    selected_button = (
        custom_buttons[selected_index]
        if 0 <= selected_index < len(custom_buttons)
        else BotMenuCustomButtonDto(
            id="missing",
            label=i18n.get("msg-common-empty-value"),
            kind=BotMenuCustomButtonKind.URL,
            url="https://example.com",
            enabled=False,
            order=0,
        )
    )

    return {
        "button_label": selected_button.label,
        "button_kind": selected_button.kind.value,
        "button_url": selected_button.url,
        "button_enabled": selected_button.enabled,
        "button_position": selected_index + 1 if selected_index >= 0 else 0,
        "button_count": len(custom_buttons),
        "can_move_up": selected_index > 0,
        "can_move_down": 0 <= selected_index < len(custom_buttons) - 1,
    }


@inject
async def bot_menu_main_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get()
    bot_menu_state = resolve_bot_menu_state(
        bot_menu=settings.bot_menu,
        branding=settings.branding,
        config=config,
    )
    custom_buttons = _sorted_buttons(settings.bot_menu.custom_buttons)

    return {
        "miniapp_only_enabled": settings.bot_menu.miniapp_only_enabled,
        "mini_app_url": settings.bot_menu.mini_app_url or i18n.get("msg-common-empty-value"),
        "resolved_mini_app_url": bot_menu_state.mini_app_url
        or i18n.get("msg-common-empty-value"),
        "resolved_source_label": _resolve_source_label(bot_menu_state.mini_app_source, i18n),
        "custom_button_count": len(custom_buttons),
        "custom_button_limit": BOT_MENU_MAX_CUSTOM_BUTTONS,
        "has_custom_buttons": bool(custom_buttons),
        "custom_buttons": [
            {
                "id": button.id,
                "label": button.label,
                "kind": button.kind.value,
                "enabled": button.enabled,
            }
            for button in custom_buttons
        ],
    }


@inject
async def bot_menu_url_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get()
    bot_menu_state = resolve_bot_menu_state(
        bot_menu=settings.bot_menu,
        branding=settings.branding,
        config=config,
    )

    return {
        "stored_url": settings.bot_menu.mini_app_url or i18n.get("msg-common-empty-value"),
        "resolved_url": bot_menu_state.mini_app_url or i18n.get("msg-common-empty-value"),
        "resolved_source_label": _resolve_source_label(bot_menu_state.mini_app_source, i18n),
    }


@inject
async def bot_menu_button_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get()
    selected_button_id = str(dialog_manager.dialog_data.get("bot_menu_button_id", ""))
    return _resolve_selected_button_data(
        settings_buttons=settings.bot_menu.custom_buttons,
        selected_button_id=selected_button_id,
        i18n=i18n,
    )


@inject
async def bot_menu_button_label_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get()
    data = _resolve_selected_button_data(
        settings_buttons=settings.bot_menu.custom_buttons,
        selected_button_id=str(dialog_manager.dialog_data.get("bot_menu_button_id", "")),
        i18n=i18n,
    )
    return {"current_label": data["button_label"]}


@inject
async def bot_menu_button_url_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get()
    data = _resolve_selected_button_data(
        settings_buttons=settings.bot_menu.custom_buttons,
        selected_button_id=str(dialog_manager.dialog_data.get("bot_menu_button_id", "")),
        i18n=i18n,
    )
    return {"current_url": data["button_url"]}
