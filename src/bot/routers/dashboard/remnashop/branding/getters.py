from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.services.settings import SettingsService

FIELD_LABEL_KEYS: dict[str, str] = {
    "project_name": "msg-branding-field-project-name",
    "web_title": "msg-branding-field-web-title",
    "bot_menu_button_text": "msg-branding-field-bot-menu-button",
    "telegram_template": "msg-branding-field-telegram-template",
    "password_reset_telegram_template": "msg-branding-field-password-reset-template",
    "web_request_delivered": "msg-branding-field-web-request-delivered",
    "web_request_open_bot": "msg-branding-field-web-request-open-bot",
    "web_confirm_success": "msg-branding-field-web-confirm-success",
}

LOCALIZED_FIELDS: set[str] = {
    "telegram_template",
    "password_reset_telegram_template",
    "web_request_delivered",
    "web_request_open_bot",
    "web_confirm_success",
}


def _is_localized(field: str) -> bool:
    return field in LOCALIZED_FIELDS


def _field_label(field: str, i18n: TranslatorRunner) -> str:
    return i18n.get(FIELD_LABEL_KEYS.get(field, "msg-common-empty-value"))


def _get_localized_field(branding: Any, field: str) -> Any:
    if field == "telegram_template":
        return branding.verification.telegram_template
    if field == "password_reset_telegram_template":
        return branding.verification.password_reset_telegram_template
    if field == "web_request_delivered":
        return branding.verification.web_request_delivered
    if field == "web_request_open_bot":
        return branding.verification.web_request_open_bot
    if field == "web_confirm_success":
        return branding.verification.web_confirm_success
    return None


def _get_field_value(branding: Any, field: str, locale: str = "en") -> str:
    if field == "project_name":
        return branding.project_name
    if field == "web_title":
        return branding.web_title
    if field == "bot_menu_button_text":
        return branding.bot_menu_button_text

    localized_value = _get_localized_field(branding, field)
    if not localized_value:
        return ""

    if locale == "ru":
        return str(localized_value.ru or "")
    return str(localized_value.en or "")


def _render_localized_preview(
    *,
    settings_service: SettingsService,
    localized_text: Any,
    language: str,
    placeholders: dict[str, object],
) -> str:
    template = settings_service.resolve_localized_branding_text(
        localized_text,
        language=language,
    )
    return settings_service.render_branding_text(template, placeholders=placeholders)


def _compact_preview(value: str) -> str:
    return " ".join(value.split())


def _truncate_preview(value: str, *, max_length: int) -> str:
    compact = _compact_preview(value)
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


@inject
async def branding_main_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    branding = await settings_service.get_branding_settings()

    sample_code = "123456"
    tg_placeholders = {
        "project_name": branding.project_name,
        "code": sample_code,
    }
    web_placeholders = {"project_name": branding.project_name}

    return {
        "project_name_label": _field_label("project_name", i18n),
        "web_title_label": _field_label("web_title", i18n),
        "bot_menu_button_text_label": _field_label("bot_menu_button_text", i18n),
        "telegram_template_label": _field_label("telegram_template", i18n),
        "password_reset_telegram_template_label": _field_label(
            "password_reset_telegram_template",
            i18n,
        ),
        "web_request_delivered_label": _field_label("web_request_delivered", i18n),
        "web_request_open_bot_label": _field_label("web_request_open_bot", i18n),
        "web_confirm_success_label": _field_label("web_confirm_success", i18n),
        "project_name": _truncate_preview(str(branding.project_name), max_length=32),
        "web_title": _truncate_preview(str(branding.web_title), max_length=32),
        "bot_menu_button_text": _truncate_preview(
            str(branding.bot_menu_button_text), max_length=32
        ),
        "tg_preview_ru": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.telegram_template,
                language="ru",
                placeholders=tg_placeholders,
            ),
            max_length=40,
        ),
        "tg_preview_en": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.telegram_template,
                language="en",
                placeholders=tg_placeholders,
            ),
            max_length=40,
        ),
        "password_reset_tg_preview_ru": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.password_reset_telegram_template,
                language="ru",
                placeholders=tg_placeholders,
            ),
            max_length=40,
        ),
        "password_reset_tg_preview_en": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.password_reset_telegram_template,
                language="en",
                placeholders=tg_placeholders,
            ),
            max_length=40,
        ),
        "web_request_delivered_ru": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.web_request_delivered,
                language="ru",
                placeholders=web_placeholders,
            ),
            max_length=40,
        ),
        "web_request_delivered_en": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.web_request_delivered,
                language="en",
                placeholders=web_placeholders,
            ),
            max_length=40,
        ),
        "web_request_open_bot_ru": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.web_request_open_bot,
                language="ru",
                placeholders=web_placeholders,
            ),
            max_length=40,
        ),
        "web_request_open_bot_en": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.web_request_open_bot,
                language="en",
                placeholders=web_placeholders,
            ),
            max_length=40,
        ),
        "web_confirm_success_ru": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.web_confirm_success,
                language="ru",
                placeholders=web_placeholders,
            ),
            max_length=40,
        ),
        "web_confirm_success_en": _truncate_preview(
            _render_localized_preview(
                settings_service=settings_service,
                localized_text=branding.verification.web_confirm_success,
                language="en",
                placeholders=web_placeholders,
            ),
            max_length=40,
        ),
    }


@inject
async def branding_edit_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    branding = await settings_service.get_branding_settings()
    selected_field = str(dialog_manager.dialog_data.get("branding_field", "project_name"))
    is_localized = _is_localized(selected_field)

    selected_locale = str(dialog_manager.dialog_data.get("branding_locale", "en")).lower()
    if not is_localized:
        selected_locale = "global"
    elif selected_locale not in {"en", "ru"}:
        selected_locale = "en"

    if is_localized and selected_locale == "ru":
        field_label = i18n.get(
            "msg-branding-field-label-ru-override",
            label=_field_label(selected_field, i18n),
        )
    elif is_localized:
        field_label = i18n.get(
            "msg-branding-field-label-en-base",
            label=_field_label(selected_field, i18n),
        )
    else:
        field_label = _field_label(selected_field, i18n)

    current_value = _get_field_value(
        branding,
        selected_field,
        locale=("en" if selected_locale == "global" else selected_locale),
    )
    if is_localized and selected_locale == "ru" and not current_value:
        current_value = i18n.get("msg-branding-field-empty-uses-en")

    return {
        "field_id": selected_field,
        "field_label": field_label,
        "current_value": current_value,
        "is_localized": is_localized,
        "edit_locale_en_label": i18n.get("msg-branding-edit-locale-en"),
        "edit_locale_ru_label": i18n.get("msg-branding-edit-locale-ru"),
    }
