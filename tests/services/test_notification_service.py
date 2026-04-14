from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.states import Notification
from src.core.config import AppConfig
from src.core.enums import Locale, SystemNotificationType, UserNotificationType, UserRole
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto.user import UserDto
from src.services.notification import NotificationService


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_send_message_marks_user_blocked_for_chat_not_found() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(
        side_effect=TelegramBadRequest(
            method=SendMessage(chat_id=123, text=""),
            message="Bad Request: chat not found",
        )
    )
    user = UserDto(
        telegram_id=123,
        name="Test User",
        role=UserRole.USER,
    )
    user_service = MagicMock()
    user_service.get = AsyncMock(return_value=user)
    user_service.set_bot_blocked = AsyncMock()

    service = NotificationService(
        config=AppConfig.get(),
        bot=bot,
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=user_service,
        settings_service=MagicMock(),
        user_notification_event_service=MagicMock(),
    )

    result = run_async(service._send_message(user=user, payload=MessagePayload(i18n_key="")))

    assert result is None
    user_service.set_bot_blocked.assert_awaited_once_with(user=user, blocked=True)


def test_send_text_message_truncates_oversized_html_payload() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    user = UserDto(
        telegram_id=123,
        name="Test User",
        role=UserRole.USER,
    )

    service = NotificationService(
        config=AppConfig.get(),
        bot=bot,
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=MagicMock(),
        settings_service=MagicMock(),
        user_notification_event_service=MagicMock(),
    )
    service._get_translated_text = MagicMock(return_value=f"<i>{'x' * 5000}</i>")  # type: ignore[method-assign]

    run_async(
        service._send_text_message(
            user=user,
            payload=MessagePayload(i18n_key=""),
            reply_markup=None,
        )
    )

    sent_text = bot.send_message.await_args.kwargs["text"]
    assert len(sent_text) == service.TELEGRAM_TEXT_LIMIT
    assert "<i>" not in sent_text
    assert sent_text.endswith("...")


def test_system_notify_skips_duplicate_event_payloads() -> None:
    bot = MagicMock()
    user_service = MagicMock()
    user_service.get_by_role = AsyncMock(
        return_value=[UserDto(telegram_id=123, name="Dev", role=UserRole.DEV)]
    )
    settings_service = MagicMock()
    settings_service.is_notification_enabled = AsyncMock(return_value=True)
    redis_client = MagicMock()
    redis_client.set = AsyncMock(return_value=False)

    service = NotificationService(
        config=AppConfig.get(),
        bot=bot,
        redis_client=redis_client,
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=user_service,
        settings_service=settings_service,
        user_notification_event_service=MagicMock(),
    )
    service._send_message = AsyncMock()  # type: ignore[method-assign]

    results = run_async(
        service.system_notify(
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={"error": "RuntimeError: boom"},
                dedupe_key="event|duplicate",
                dedupe_ttl_seconds=300,
            ),
            ntf_type=SystemNotificationType.BOT_LIFETIME,
        )
    )

    assert results == []
    service._send_message.assert_not_awaited()


def test_acquire_system_event_dedupe_degrades_open_when_redis_is_unavailable() -> None:
    service = NotificationService(
        config=AppConfig.get(),
        bot=MagicMock(),
        redis_client=MagicMock(set=AsyncMock(side_effect=RuntimeError("redis down"))),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=MagicMock(),
        settings_service=MagicMock(),
        user_notification_event_service=MagicMock(),
    )

    result = run_async(
        service._acquire_system_event_dedupe(dedupe_key="event|boom", ttl_seconds=300)
    )

    assert result is True


def test_notify_user_persists_delivery_meta_after_successful_send() -> None:
    user = UserDto(telegram_id=123, name="Test User", role=UserRole.USER, language=Locale.EN)
    user_service = MagicMock()
    settings_service = MagicMock()
    settings_service.is_notification_enabled = AsyncMock(return_value=True)
    user_notification_event_service = MagicMock()
    user_notification_event_service.create_event = AsyncMock(return_value=MagicMock(id=77))
    user_notification_event_service.set_bot_delivery_meta = AsyncMock()

    service = NotificationService(
        config=AppConfig.get(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=user_service,
        settings_service=settings_service,
        user_notification_event_service=user_notification_event_service,
    )
    service._get_translated_text = MagicMock(return_value="Delivered text")  # type: ignore[method-assign]
    service._send_message = AsyncMock(return_value=MagicMock(spec=Message, message_id=555))  # type: ignore[method-assign]

    result = run_async(
        service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user"),
            ntf_type=UserNotificationType.EXPIRED,
        )
    )

    assert result is not None
    user_notification_event_service.create_event.assert_awaited_once()
    user_notification_event_service.set_bot_delivery_meta.assert_awaited_once_with(
        notification_id=77,
        bot_chat_id=123,
        bot_message_id=555,
    )


def test_prepare_reply_markup_adds_close_button_for_inline_markup() -> None:
    service = NotificationService(
        config=AppConfig.get(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=MagicMock(),
        settings_service=MagicMock(),
        user_notification_event_service=MagicMock(),
    )
    original_markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="btn-existing", callback_data="keep")]]
    )
    close_button = InlineKeyboardButton(text="Close", callback_data=Notification.CLOSE.state)
    service._translate_keyboard_texts = MagicMock(return_value=original_markup)  # type: ignore[method-assign]
    service._get_close_notification_button = MagicMock(return_value=close_button)  # type: ignore[method-assign]

    result = service._prepare_reply_markup(
        reply_markup=original_markup,
        add_close_button=True,
        auto_delete_after=None,
        locale=Locale.EN,
        chat_id=123,
        close_notification_id=77,
    )

    assert isinstance(result, InlineKeyboardMarkup)
    assert result.inline_keyboard[-1][0].text == "Close"
    assert result.inline_keyboard[-1][0].callback_data == Notification.CLOSE.state


def test_translate_button_text_falls_back_to_original_text_on_translation_error() -> None:
    service = NotificationService(
        config=AppConfig.get(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        user_service=MagicMock(),
        settings_service=MagicMock(),
        user_notification_event_service=MagicMock(),
    )
    service._get_translated_text = MagicMock(side_effect=RuntimeError("translator failed"))  # type: ignore[method-assign]

    result = service._translate_button_text(Locale.EN, "btn-existing")

    assert result == "btn-existing"
