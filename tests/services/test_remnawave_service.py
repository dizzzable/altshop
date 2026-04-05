from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from pydantic import ValidationError

from src.core.enums import DeviceType, PlanType, SubscriptionStatus
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto
from src.services.remnawave import RemnawaveService


def run_async(coroutine):
    return asyncio.run(coroutine)


def _build_validation_error() -> ValidationError:
    return ValidationError.from_exception_data(
        "GetStatsResponseDto",
        [
            {
                "type": "missing",
                "loc": ("cpu", "physicalCores"),
                "input": {"cores": 1},
            }
        ],
    )


def test_try_connection_falls_back_to_raw_health_check_on_validation_error() -> None:
    remnawave = SimpleNamespace(
        system=SimpleNamespace(
            get_stats=AsyncMock(side_effect=_build_validation_error())
        )
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._try_connection_raw = AsyncMock()  # type: ignore[method-assign]

    run_async(service.try_connection())

    service._try_connection_raw.assert_awaited_once()


def test_pick_group_sync_current_subscription_id_prefers_active_latest_subscription() -> None:
    now = datetime.now(timezone.utc)
    plan = PlanSnapshotDto(
        id=1,
        name="Starter",
        tag="starter",
        type=PlanType.BOTH,
        traffic_limit=100,
        device_limit=1,
        duration=30,
        internal_squads=[],
        external_squad=None,
    )
    active_old = SubscriptionDto(
        id=1,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000001"),
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=now + timedelta(days=5),
        url="https://example.com/1",
        device_type=DeviceType.OTHER,
        plan=plan.model_copy(deep=True),
    )
    active_new = SubscriptionDto(
        id=2,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000002"),
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=now + timedelta(days=30),
        url="https://example.com/2",
        device_type=DeviceType.OTHER,
        plan=plan.model_copy(deep=True),
    )
    deleted = SubscriptionDto(
        id=3,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000003"),
        status=SubscriptionStatus.DELETED,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=now + timedelta(days=40),
        url="https://example.com/3",
        device_type=DeviceType.OTHER,
        plan=plan.model_copy(deep=True),
    )

    selected = RemnawaveService._pick_group_sync_current_subscription_id(
        [active_old, active_new, deleted]
    )

    assert selected == 2
