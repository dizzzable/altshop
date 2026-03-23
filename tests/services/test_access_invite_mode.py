from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import CallbackQuery, Message

from src.core.enums import AccessMode, Locale
from src.infrastructure.database.models.dto import SettingsDto, UserDto
from src.services.access import AccessService
from src.services.access_policy import AccessModePolicyService


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


def build_access_service(settings: SettingsDto | None = None) -> AccessService:
    current_settings = settings or SettingsDto()
    translator = SimpleNamespace(get=lambda key, **kwargs: key)
    translator_hub = SimpleNamespace(
        get_translator_by_locale=MagicMock(return_value=translator)
    )

    return AccessService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=SimpleNamespace(set=AsyncMock(return_value=True)),
        redis_repository=SimpleNamespace(
            collection_is_member=AsyncMock(return_value=False),
            collection_add=AsyncMock(return_value=1),
            collection_members=AsyncMock(return_value=[]),
            delete=AsyncMock(),
        ),
        translator_hub=translator_hub,
        settings_service=SimpleNamespace(
            get=AsyncMock(return_value=current_settings),
            get_access_mode=AsyncMock(return_value=current_settings.access_mode),
            set_access_mode=AsyncMock(),
        ),
        user_service=SimpleNamespace(
            get=AsyncMock(),
            get_recent_activity_users=AsyncMock(return_value=[]),
        ),
        referral_service=SimpleNamespace(is_referral_event=AsyncMock(return_value=False)),
        access_mode_policy_service=AccessModePolicyService(),
    )


def build_user(*, telegram_id: int, created_at: datetime | None = None) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Guest",
        language=Locale.RU,
        created_at=created_at,
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


def test_existing_locked_user_can_open_safe_start_event() -> None:
    started_at = datetime.now(timezone.utc)
    settings = SettingsDto(
        access_mode=AccessMode.INVITED,
        invite_mode_started_at=started_at,
    )
    service = build_access_service(settings)
    user = build_user(telegram_id=501, created_at=started_at + timedelta(minutes=1))

    result = run_async(
        service._handle_existing_user_access(
            user=user,
            mode=AccessMode.INVITED,
            event=build_message("/start"),
        )
    )

    assert result is True


def test_existing_locked_user_gets_callback_alert_without_redirect(monkeypatch) -> None:
    started_at = datetime.now(timezone.utc)
    settings = SettingsDto(
        access_mode=AccessMode.INVITED,
        invite_mode_started_at=started_at,
    )
    service = build_access_service(settings)
    user = build_user(telegram_id=502, created_at=started_at + timedelta(minutes=1))
    callback = build_callback("open_subscriptions")
    answer_mock = AsyncMock()
    object.__setattr__(callback, "answer", answer_mock)
    notify_mock = AsyncMock()

    monkeypatch.setattr(
        "src.services.access.send_access_denied_notification_task.kiq",
        notify_mock,
    )
    monkeypatch.setattr(
        service,
        "_render_plain_i18n",
        lambda **kwargs: "Access denied",
    )

    result = run_async(
        service._handle_existing_user_access(
            user=user,
            mode=AccessMode.INVITED,
            event=callback,
        )
    )

    assert result is False
    answer_mock.assert_awaited_once_with(text="Access denied", show_alert=True)
    notify_mock.assert_not_awaited()


def test_purchase_blocked_message_event_sends_notice_without_redirect(monkeypatch) -> None:
    settings = SettingsDto(access_mode=AccessMode.PURCHASE_BLOCKED)
    service = build_access_service(settings)
    user = build_user(telegram_id=503)
    notify_mock = AsyncMock()

    monkeypatch.setattr(
        "src.services.access.send_access_denied_notification_task.kiq",
        notify_mock,
    )

    result = run_async(
        service._handle_existing_user_access(
            user=user,
            mode=AccessMode.PURCHASE_BLOCKED,
            event=build_callback("purchase_new"),
        )
    )

    assert result is False
    notify_mock.assert_not_awaited()


def test_public_mode_never_marks_user_as_invite_locked() -> None:
    service = build_access_service(SettingsDto(access_mode=AccessMode.PUBLIC))
    user = build_user(telegram_id=504)

    result = run_async(service.is_invite_locked(user, mode=AccessMode.PUBLIC))

    assert result is False


def test_invited_mode_grandfathers_existing_users() -> None:
    started_at = datetime.now(timezone.utc)
    service = build_access_service(
        SettingsDto(
            access_mode=AccessMode.INVITED,
            invite_mode_started_at=started_at,
        )
    )
    user = build_user(telegram_id=505, created_at=started_at - timedelta(minutes=1))

    result = run_async(service.is_invite_locked(user, mode=AccessMode.INVITED))

    assert result is False


def test_set_mode_applies_lazily_without_refreshing_recent_users(monkeypatch) -> None:
    settings = SettingsDto(access_mode=AccessMode.PUBLIC)
    service = build_access_service(settings)
    access_opened_mock = AsyncMock()
    service.get_all_waiting_users = AsyncMock(return_value=[])
    service.clear_all_waiting_users = AsyncMock()

    monkeypatch.setattr(
        "src.services.access.send_access_opened_notifications_task.kiq",
        access_opened_mock,
    )

    run_async(service.set_mode(AccessMode.PUBLIC))

    service.settings_service.set_access_mode.assert_awaited_once_with(AccessMode.PUBLIC)
    service.user_service.get_recent_activity_users.assert_not_awaited()
    access_opened_mock.assert_not_awaited()
    service.clear_all_waiting_users.assert_awaited_once()


def test_set_mode_still_notifies_waitlist_users(monkeypatch) -> None:
    settings = SettingsDto(access_mode=AccessMode.PURCHASE_BLOCKED)
    service = build_access_service(settings)
    access_opened_mock = AsyncMock()
    waiting_users = [700, 701]
    service.get_all_waiting_users = AsyncMock(return_value=waiting_users)
    service.clear_all_waiting_users = AsyncMock()

    monkeypatch.setattr(
        "src.services.access.send_access_opened_notifications_task.kiq",
        access_opened_mock,
    )

    run_async(service.set_mode(AccessMode.PUBLIC))

    service.settings_service.set_access_mode.assert_awaited_once_with(AccessMode.PUBLIC)
    access_opened_mock.assert_awaited_once_with(waiting_users)
    service.clear_all_waiting_users.assert_awaited_once()
