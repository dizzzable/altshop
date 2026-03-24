from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.states import RemnashopBranding
from src.core.constants import USER_KEY
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import BrandingSettingsDto, UserDto
from src.services.settings import SettingsService

LOCALIZED_FIELDS: set[str] = {
    "telegram_template",
    "password_reset_telegram_template",
    "web_request_delivered",
    "web_request_open_bot",
    "web_confirm_success",
}

GLOBAL_FIELD_MAP: dict[str, str] = {
    "project_name": "project_name",
    "web_title": "web_title",
    "bot_menu_button_text": "bot_menu_button_text",
}

LOCALIZED_FIELD_MAP: dict[str, str] = {
    "telegram_template": "telegram_template",
    "password_reset_telegram_template": "password_reset_telegram_template",
    "web_request_delivered": "web_request_delivered",
    "web_request_open_bot": "web_request_open_bot",
    "web_confirm_success": "web_confirm_success",
}


def _resolve_localized_field_locale(locale: str | None) -> str:
    if locale not in {"ru", "en"}:
        raise ValueError("Locale must be 'ru' or 'en' for localized branding fields")
    return locale


def _apply_field_value(
    branding: BrandingSettingsDto,
    field: str,
    value: str,
    *,
    locale: str | None = None,
) -> None:
    global_field = GLOBAL_FIELD_MAP.get(field)
    if global_field:
        setattr(branding, global_field, value)
        return

    localized_field = LOCALIZED_FIELD_MAP.get(field)
    if localized_field is None:
        raise ValueError(f"Unknown branding field: {field}")

    resolved_locale = _resolve_localized_field_locale(locale)
    setattr(getattr(branding.verification, localized_field), resolved_locale, value)


async def on_select_edit_field(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    widget_id = str(getattr(widget, "widget_id", "") or "")
    callback_data = str(callback.data or "")

    selected_field = widget_id or callback_data
    if ":" in selected_field:
        selected_field = selected_field.split(":")[-1]
    if not selected_field:
        selected_field = "project_name"

    dialog_manager.dialog_data["branding_field"] = selected_field
    dialog_manager.dialog_data["branding_locale"] = (
        "en" if selected_field in LOCALIZED_FIELDS else "global"
    )
    await dialog_manager.switch_to(state=RemnashopBranding.EDIT)


async def on_select_edit_locale(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    locale = "en" if widget.widget_id == "edit_locale_en" else "ru"
    dialog_manager.dialog_data["branding_locale"] = locale
    await dialog_manager.switch_to(state=RemnashopBranding.EDIT)


@inject
async def on_branding_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    if not message.text:
        return

    field = str(dialog_manager.dialog_data.get("branding_field", "")).strip()
    if not field:
        await message.answer(i18n.get("ntf-branding-field-not-selected"))
        return
    locale = str(dialog_manager.dialog_data.get("branding_locale", "global")).strip().lower()

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    settings = await settings_service.get()
    value = message.text
    if field in LOCALIZED_FIELDS and locale == "ru":
        normalized = message.text.strip().lower()
        if normalized in {"/clear", "clear", "-"}:
            value = ""

    try:
        _apply_field_value(
            settings.branding,
            field,
            value,
            locale=None if field not in LOCALIZED_FIELDS else locale,
        )
        await settings_service.update(settings)
    except Exception as exc:
        logger.warning(f"{log(user)} Failed to update branding field '{field}': {exc}")
        await message.answer(i18n.get("ntf-branding-save-failed"))
        return

    logger.info(f"{log(user)} Updated branding field '{field}'")
    await dialog_manager.switch_to(state=RemnashopBranding.MAIN)
