from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.states import Notification
from src.core.enums import Locale, UserNotificationType
from src.core.utils.message_payload import MessagePayload
from src.services.notification import NotificationService

_NOTIFICATION_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "bot" / "routers" / "extra" / "notification.py"
)
_spec = importlib.util.spec_from_file_location(
    "test_notification_router_module",
    _NOTIFICATION_MODULE_PATH,
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Failed to load notification router module for tests")
_notification_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_notification_module)
on_close_notification = _notification_module.on_close_notification


class _FakeDishkaContainer:
    def __init__(self, dependency: object) -> None:
        self._dependency = dependency

    async def get(self, _type_hint: object, component: object | None = None) -> object:
        _ = component
        return self._dependency


def _build_notification_service(
    *,
    settings_enabled: bool,
    sent_message_id: int | None = 777,
    event_id: int = 55,
) -> tuple[NotificationService, SimpleNamespace, SimpleNamespace]:
    settings_service = SimpleNamespace(
        is_notification_enabled=AsyncMock(return_value=settings_enabled),
    )
    user_notification_event_service = SimpleNamespace(
        create_event=AsyncMock(return_value=SimpleNamespace(id=event_id)),
        set_bot_delivery_meta=AsyncMock(return_value=True),
    )

    service = NotificationService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        user_service=SimpleNamespace(),
        settings_service=settings_service,
        user_notification_event_service=user_notification_event_service,
    )
    service._get_translated_text = lambda **_: "Rendered text"  # type: ignore[method-assign]
    service._send_message = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            SimpleNamespace(message_id=sent_message_id) if sent_message_id is not None else None
        )
    )

    return service, settings_service, user_notification_event_service


def test_notify_user_creates_history_event_when_notification_enabled() -> None:
    service, _settings_service, event_service = _build_notification_service(settings_enabled=True)
    user = SimpleNamespace(telegram_id=123456, language=Locale.EN)

    asyncio.run(
        service.notify_user(
            user=user,
            payload=MessagePayload.not_deleted(i18n_key="ntf-event-partner-earning"),
            ntf_type=UserNotificationType.PARTNER_EARNING,
        )
    )

    assert event_service.create_event.await_count == 1
    assert service._send_message.await_args.kwargs["close_notification_id"] == 55  # type: ignore[attr-defined]
    assert event_service.set_bot_delivery_meta.await_count == 1


def test_notify_user_skips_send_and_history_when_notification_disabled() -> None:
    service, settings_service, event_service = _build_notification_service(settings_enabled=False)
    user = SimpleNamespace(telegram_id=123456, language=Locale.EN)

    result = asyncio.run(
        service.notify_user(
            user=user,
            payload=MessagePayload.not_deleted(i18n_key="ntf-event-partner-earning"),
            ntf_type=UserNotificationType.PARTNER_EARNING,
        )
    )

    assert result is None
    assert settings_service.is_notification_enabled.await_count == 1
    assert event_service.create_event.await_count == 0
    assert service._send_message.await_count == 0  # type: ignore[attr-defined]


def test_close_notification_with_event_id_marks_history_as_read() -> None:
    notification_message = SimpleNamespace(
        message_id=901,
        chat=SimpleNamespace(id=7777),
        delete=AsyncMock(),
    )
    callback = SimpleNamespace(
        data=f"{Notification.CLOSE.state}:42",
        message=notification_message,
        answer=AsyncMock(),
    )
    bot = SimpleNamespace(edit_message_reply_markup=AsyncMock())
    user = SimpleNamespace(telegram_id=123456, role="user", name="Tester")
    event_service = SimpleNamespace(mark_read_by_id=AsyncMock(return_value=True))
    dishka_container = _FakeDishkaContainer(event_service)

    asyncio.run(
        on_close_notification(
            callback=callback,
            bot=bot,
            user=user,
            dishka_container=dishka_container,
        )
    )

    assert event_service.mark_read_by_id.await_count == 1
    assert event_service.mark_read_by_id.await_args.kwargs["notification_id"] == 42
    assert event_service.mark_read_by_id.await_args.kwargs["read_source"] == "BOT"
    assert notification_message.delete.await_count == 1
    assert callback.answer.await_count == 1


def test_close_notification_without_event_id_keeps_backward_behavior() -> None:
    notification_message = SimpleNamespace(
        message_id=902,
        chat=SimpleNamespace(id=7777),
        delete=AsyncMock(),
    )
    callback = SimpleNamespace(
        data=Notification.CLOSE.state,
        message=notification_message,
        answer=AsyncMock(),
    )
    bot = SimpleNamespace(edit_message_reply_markup=AsyncMock())
    user = SimpleNamespace(telegram_id=123456, role="user", name="Tester")
    event_service = SimpleNamespace(mark_read_by_id=AsyncMock(return_value=True))
    dishka_container = _FakeDishkaContainer(event_service)

    asyncio.run(
        on_close_notification(
            callback=callback,
            bot=bot,
            user=user,
            dishka_container=dishka_container,
        )
    )

    assert event_service.mark_read_by_id.await_count == 0
    assert notification_message.delete.await_count == 1
    assert callback.answer.await_count == 1
