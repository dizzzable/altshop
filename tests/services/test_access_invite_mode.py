from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CallbackQuery, Message

from src.core.enums import AccessMode, UserRole
from src.infrastructure.database.models.dto import UserDto
from src.services.access import AccessService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_message(text: str) -> Message:
    return Message.model_validate(
        {
            "message_id": 1,
            "date": "2026-03-22T12:00:00+00:00",
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "User"},
            "text": text,
        }
    )


def build_callback(data: str) -> CallbackQuery:
    return CallbackQuery.model_validate(
        {
            "id": "1",
            "from": {"id": 1, "is_bot": False, "first_name": "User"},
            "chat_instance": "1",
            "data": data,
        }
    )


def build_access_service() -> AccessService:
    return AccessService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=SimpleNamespace(
            collection_is_member=AsyncMock(return_value=False),
            collection_add=AsyncMock(return_value=1),
            collection_members=AsyncMock(return_value=[]),
            delete=AsyncMock(),
        ),
        translator_hub=MagicMock(),
        settings_service=SimpleNamespace(
            get_access_mode=AsyncMock(),
            set_access_mode=AsyncMock(),
        ),
        user_service=SimpleNamespace(
            get=AsyncMock(),
            get_recent_activity_users=AsyncMock(return_value=[]),
        ),
        referral_service=SimpleNamespace(is_referral_event=AsyncMock(return_value=False)),
    )


def test_new_user_in_invited_mode_is_soft_allowed() -> None:
    service = build_access_service()
    aiogram_user = SimpleNamespace(
        id=500,
        full_name="Guest User",
        language_code="ru",
    )

    result = run_async(
        service._handle_new_user_access(
            aiogram_user=aiogram_user,
            event=build_message("/start"),
            mode=AccessMode.INVITED,
        )
    )

    assert result is True


def test_existing_uninvited_user_can_open_safe_start_event() -> None:
    service = build_access_service()
    user = UserDto(telegram_id=501, name="Guest")

    result = run_async(
        service._handle_existing_user_access(
            user=user,
            mode=AccessMode.INVITED,
            event=build_message("/start"),
        )
    )

    assert result is True


def test_existing_uninvited_user_is_blocked_on_product_callback(monkeypatch) -> None:
    service = build_access_service()
    user = UserDto(telegram_id=502, name="Guest")
    redirect_mock = AsyncMock()
    notify_mock = AsyncMock()

    monkeypatch.setattr(
        "src.services.access.redirect_to_main_menu_task.kiq",
        redirect_mock,
    )
    monkeypatch.setattr(
        "src.services.access.send_access_denied_notification_task.kiq",
        notify_mock,
    )

    result = run_async(
        service._handle_existing_user_access(
            user=user,
            mode=AccessMode.INVITED,
            event=build_callback("open_subscriptions"),
        )
    )

    assert result is False
    redirect_mock.assert_awaited_once_with(user.telegram_id)
    notify_mock.assert_awaited_once()


def test_public_mode_never_marks_user_as_invite_locked() -> None:
    service = build_access_service()
    user = UserDto(telegram_id=503, name="Guest")

    result = run_async(service.is_invite_locked(user, mode=AccessMode.PUBLIC))

    assert result is False


def test_set_mode_refreshes_recent_non_privileged_users(monkeypatch) -> None:
    service = build_access_service()
    guest = UserDto(telegram_id=600, name="Guest")
    dev = UserDto(telegram_id=601, name="Dev", role=UserRole.DEV)
    blocked = UserDto(telegram_id=602, name="Blocked", is_blocked=True)
    service.user_service.get_recent_activity_users = AsyncMock(
        return_value=[guest, dev, blocked, guest]
    )
    redirect_mock = AsyncMock()
    access_opened_mock = AsyncMock()

    monkeypatch.setattr(
        "src.services.access.redirect_to_main_menu_task.kiq",
        redirect_mock,
    )
    monkeypatch.setattr(
        "src.services.access.send_access_opened_notifications_task.kiq",
        access_opened_mock,
    )

    run_async(service.set_mode(AccessMode.PUBLIC))

    service.settings_service.set_access_mode.assert_awaited_once_with(AccessMode.PUBLIC)
    redirect_mock.assert_awaited_once_with(guest.telegram_id)
    access_opened_mock.assert_not_awaited()
