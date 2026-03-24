from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

from src.core.config import AppConfig
from src.core.enums import UserRole
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
