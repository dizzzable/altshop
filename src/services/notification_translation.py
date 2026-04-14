from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from src.bot.states import Notification
from src.core.enums import Locale
from src.core.i18n.translator import get_translated_kwargs, safe_i18n_get
from src.core.utils.formatters import i18n_postprocess_text
from src.core.utils.system_events import normalize_system_event_kwargs, render_system_event_blocks
from src.core.utils.types import AnyKeyboard

if TYPE_CHECKING:
    from .notification import NotificationService


def prepare_reply_markup(
    service: NotificationService,
    reply_markup: Optional[AnyKeyboard],
    add_close_button: bool,
    auto_delete_after: Optional[int],
    locale: Locale,
    chat_id: int,
    close_notification_id: Optional[int] = None,
) -> Optional[AnyKeyboard]:
    if reply_markup is None:
        if add_close_button and auto_delete_after is None:
            close_button = service._get_close_notification_button(
                locale=locale,
                close_notification_id=close_notification_id,
            )
            return service._get_close_notification_keyboard(close_button)
        return None

    if not add_close_button or auto_delete_after is not None:
        return service._translate_keyboard_texts(reply_markup, locale)

    close_button = service._get_close_notification_button(
        locale=locale,
        close_notification_id=close_notification_id,
    )

    if isinstance(reply_markup, InlineKeyboardMarkup):
        translated_markup = service._translate_keyboard_texts(reply_markup, locale)
        translated_markup = cast(InlineKeyboardMarkup, translated_markup)
        builder = InlineKeyboardBuilder.from_markup(translated_markup)
        builder.row(close_button)
        return builder.as_markup()

    if isinstance(reply_markup, ReplyKeyboardMarkup):
        return service._translate_keyboard_texts(reply_markup, locale)

    logger.warning(
        "Unsupported reply_markup type '{}' for chat '{}'. Close button will not be added",
        type(reply_markup).__name__,
        chat_id,
    )
    return reply_markup


def get_close_notification_button(
    service: NotificationService,
    locale: Locale,
    close_notification_id: Optional[int] = None,
) -> InlineKeyboardButton:
    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    button_text = i18n.get("btn-notification-close")
    callback_data = Notification.CLOSE.state
    if close_notification_id is not None:
        callback_data = f"{Notification.CLOSE.state}:{close_notification_id}"
    return InlineKeyboardButton(text=button_text, callback_data=callback_data)


def get_close_notification_keyboard(
    service: NotificationService,
    button: InlineKeyboardButton,
) -> InlineKeyboardMarkup:
    del service
    builder = InlineKeyboardBuilder()
    builder.row(button)
    return builder.as_markup()


def get_translated_text(
    service: NotificationService,
    locale: Locale,
    i18n_key: str,
    i18n_kwargs: dict[str, Any] = {},
) -> str:
    if not i18n_key:
        return i18n_key

    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    if i18n_key.startswith("ntf-event-"):
        enriched_kwargs = normalize_system_event_kwargs(i18n_kwargs)
        enriched_kwargs.update(render_system_event_blocks(locale, enriched_kwargs))
    else:
        enriched_kwargs = i18n_kwargs
    kwargs = get_translated_kwargs(i18n, enriched_kwargs)
    return i18n_postprocess_text(safe_i18n_get(i18n, i18n_key, **kwargs))


def translate_keyboard_texts(
    service: NotificationService,
    keyboard: AnyKeyboard,
    locale: Locale,
) -> AnyKeyboard:
    if isinstance(keyboard, InlineKeyboardMarkup):
        return service._translate_inline_keyboard(keyboard, locale)
    if isinstance(keyboard, ReplyKeyboardMarkup):
        return service._translate_reply_keyboard(keyboard, locale)
    return keyboard


def translate_inline_keyboard(
    service: NotificationService,
    keyboard: InlineKeyboardMarkup,
    locale: Locale,
) -> InlineKeyboardMarkup:
    new_inline_keyboard = []
    for row_inline in keyboard.inline_keyboard:
        new_row_inline = []
        for button_inline in row_inline:
            button_inline.text = service._translate_button_text(locale, button_inline.text)
            new_row_inline.append(button_inline)
        new_inline_keyboard.append(new_row_inline)
    return InlineKeyboardMarkup(inline_keyboard=new_inline_keyboard)


def translate_reply_keyboard(
    service: NotificationService,
    keyboard: ReplyKeyboardMarkup,
    locale: Locale,
) -> ReplyKeyboardMarkup:
    new_keyboard = []
    for row in keyboard.keyboard:
        new_row = []
        for button in row:
            button.text = service._translate_button_text(locale, button.text)
            new_row.append(button)
        new_keyboard.append(new_row)

    return ReplyKeyboardMarkup(
        keyboard=new_keyboard,
        **keyboard.model_dump(exclude={"keyboard"}),
    )


def translate_button_text(
    service: NotificationService,
    locale: Locale,
    text: Optional[str],
) -> str:
    if not text:
        return ""

    try:
        return service._get_translated_text(locale, text)
    except Exception:
        return text
