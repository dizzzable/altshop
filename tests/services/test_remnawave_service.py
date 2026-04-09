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


def test_get_external_squads_safe_falls_back_to_raw_http_on_validation_error() -> None:
    remnawave = SimpleNamespace(
        external_squads=SimpleNamespace(
            get_external_squads=AsyncMock(side_effect=_build_validation_error())
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
    service._get_external_squads_raw = AsyncMock(  # type: ignore[method-assign]
        return_value=[{"uuid": UUID("00000000-0000-0000-0000-000000000001"), "name": "Team"}]
    )

    result = run_async(service.get_external_squads_safe())

    assert result == [{"uuid": UUID("00000000-0000-0000-0000-000000000001"), "name": "Team"}]
    service._get_external_squads_raw.assert_awaited_once()


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


def test_sync_user_rebinds_existing_subscription_owner_by_remna_id() -> None:
    remnawave = SimpleNamespace()
    user = SimpleNamespace(telegram_id=605)
    existing_subscription = SimpleNamespace(
        id=10,
        user_telegram_id=8,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000010"),
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=SimpleNamespace(
            get_by_remna_id=AsyncMock(return_value=existing_subscription),
            get_current=AsyncMock(return_value=None),
            rebind_user=AsyncMock(return_value=existing_subscription),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._resolve_matched_plan_for_sync = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._hydrate_panel_subscription_url = AsyncMock()  # type: ignore[method-assign]
    service._update_subscription_from_sync = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(
        uuid=UUID("00000000-0000-0000-0000-000000000010"),
        telegram_id=605,
        model_dump=lambda: {
            "uuid": UUID("00000000-0000-0000-0000-000000000010"),
            "status": SubscriptionStatus.ACTIVE,
            "expire_at": datetime.now(timezone.utc) + timedelta(days=30),
            "subscription_url": "https://example.com/sub",
            "traffic_limit_bytes": 100 * 1024 * 1024 * 1024,
            "hwid_device_limit": 1,
            "active_internal_squads": [],
            "external_squad_uuid": None,
            "traffic_limit_strategy": None,
            "tag": "starter",
        },
    )

    run_async(service.sync_user(remna_user, creating=True))

    service.subscription_service.rebind_user.assert_awaited_once_with(
        subscription_id=10,
        user_telegram_id=605,
        previous_user_telegram_id=8,
        auto_commit=False,
    )
