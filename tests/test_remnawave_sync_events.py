from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.enums import RemnaUserEvent, SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto, UserDto
from src.infrastructure.taskiq.tasks import subscriptions as subscriptions_tasks
from src.services import remnawave as remnawave_module
from src.services.remnawave import RemnawaveService


class _FakeRemnaUser(SimpleNamespace):
    def model_dump(self) -> dict[str, object]:
        return {"uuid": self.uuid}


def _build_user() -> UserDto:
    return UserDto(
        telegram_id=1001,
        referral_code="ref1001",
        name="Sync User",
        username="sync",
    )


def _build_subscription(*, user: UserDto) -> SubscriptionDto:
    plan = PlanSnapshotDto.test()
    return SubscriptionDto(
        id=777,
        user_remna_id=uuid4(),
        user_telegram_id=user.telegram_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://sub.local/current",
        plan=plan,
    )


def _build_remna_user(*, telegram_id: int, expire_at=None) -> _FakeRemnaUser:
    if expire_at is None:
        expire_at = datetime_now() + timedelta(days=7)

    return _FakeRemnaUser(
        telegram_id=telegram_id,
        username="panel-user",
        tag="IMPORTED",
        uuid=uuid4(),
        status=SubscriptionStatus.ACTIVE.value,
        used_traffic_bytes=1024,
        traffic_limit_bytes=2048,
        hwid_device_limit=3,
        expire_at=expire_at,
    )


def _build_service() -> RemnawaveService:
    service = object.__new__(RemnawaveService)
    service.user_service = SimpleNamespace(
        get=AsyncMock(),
        set_current_subscription=AsyncMock(return_value=True),
    )
    service.subscription_service = SimpleNamespace(
        get_by_remna_id=AsyncMock(return_value=None),
        get_current=AsyncMock(return_value=None),
    )
    service._resolve_matched_plan_for_sync = AsyncMock(return_value=None)
    service._hydrate_panel_subscription_url = AsyncMock(return_value=None)
    service._create_subscription_from_sync = AsyncMock(return_value=None)
    service._update_subscription_from_sync = AsyncMock(return_value=None)
    return service


def test_sync_user_uses_current_subscription_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()
    user = _build_user()
    current_subscription = _build_subscription(user=user)
    remna_user = _build_remna_user(telegram_id=user.telegram_id)

    service.user_service.get = AsyncMock(return_value=user)
    service.subscription_service.get_by_remna_id = AsyncMock(return_value=None)
    service.subscription_service.get_current = AsyncMock(return_value=current_subscription)

    dummy_remna_subscription = SimpleNamespace(
        tag="TAG",
        url="https://sub.local/panel",
        traffic_limit=50,
        device_limit=3,
        internal_squads=[],
        external_squad=None,
        traffic_limit_strategy=None,
    )
    monkeypatch.setattr(
        remnawave_module.RemnaSubscriptionDto,
        "from_remna_user",
        staticmethod(lambda _payload: dummy_remna_subscription),
    )

    asyncio.run(
        service.sync_user(
            remna_user=remna_user,
            creating=True,
            use_current_subscription_fallback=True,
        )
    )

    service.subscription_service.get_current.assert_awaited_once()
    service._update_subscription_from_sync.assert_awaited_once()
    service._create_subscription_from_sync.assert_not_awaited()


def test_sync_user_creates_subscription_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()
    user = _build_user()
    remna_user = _build_remna_user(telegram_id=user.telegram_id)

    service.user_service.get = AsyncMock(return_value=user)
    service.subscription_service.get_by_remna_id = AsyncMock(return_value=None)
    service.subscription_service.get_current = AsyncMock(return_value=None)

    dummy_remna_subscription = SimpleNamespace(
        tag="TAG",
        url="https://sub.local/panel",
        traffic_limit=50,
        device_limit=3,
        internal_squads=[],
        external_squad=None,
        traffic_limit_strategy=None,
    )
    monkeypatch.setattr(
        remnawave_module.RemnaSubscriptionDto,
        "from_remna_user",
        staticmethod(lambda _payload: dummy_remna_subscription),
    )

    asyncio.run(
        service.sync_user(
            remna_user=remna_user,
            creating=True,
            use_current_subscription_fallback=False,
        )
    )

    service._create_subscription_from_sync.assert_awaited_once()
    service._update_subscription_from_sync.assert_not_awaited()


def test_handle_user_event_created_delegates_to_created_handler() -> None:
    service = _build_service()
    remna_user = _build_remna_user(telegram_id=1001)
    remna_user.tag = "IMPORTED"
    service._handle_created_user_event = AsyncMock(return_value=None)

    asyncio.run(service.handle_user_event(RemnaUserEvent.CREATED, remna_user))

    service._handle_created_user_event.assert_awaited_once_with(remna_user)


def test_handle_user_event_deleted_enqueues_delete_task(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()
    user = _build_user()
    remna_user = _build_remna_user(telegram_id=user.telegram_id)
    delete_task = SimpleNamespace(kiq=AsyncMock(return_value=None))
    status_task = SimpleNamespace(kiq=AsyncMock(return_value=None))

    service.user_service.get = AsyncMock(return_value=user)
    monkeypatch.setattr(subscriptions_tasks, "delete_current_subscription_task", delete_task)
    monkeypatch.setattr(subscriptions_tasks, "update_status_current_subscription_task", status_task)

    asyncio.run(service.handle_user_event(RemnaUserEvent.DELETED, remna_user))

    delete_task.kiq.assert_awaited_once_with(
        user_telegram_id=user.telegram_id,
        user_remna_id=remna_user.uuid,
    )
    status_task.kiq.assert_not_awaited()
