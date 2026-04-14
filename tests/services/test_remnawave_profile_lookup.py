from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, SubscriptionDto
from src.services.remnawave_profile_lookup import (
    load_owner_remna_users_by_uuid,
    resolve_subscription_profile_name,
    resolve_subscription_remna_user,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_subscription() -> SubscriptionDto:
    plan = PlanDto(
        id=1,
        name="Starter",
        durations=[],
        allowed_user_ids=[],
        internal_squads=[],
    )
    return SubscriptionDto(
        id=1,
        user_remna_id=uuid4(),
        user_telegram_id=12,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now(),
        url="https://example.test/sub",
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )


def test_load_owner_remna_users_by_uuid_returns_none_without_owner_id() -> None:
    remnawave_service = SimpleNamespace(get_users_map_by_telegram_id=AsyncMock())

    result = run_async(
        load_owner_remna_users_by_uuid(
            owner_telegram_id=None,
            remnawave_service=remnawave_service,
        )
    )

    assert result is None
    remnawave_service.get_users_map_by_telegram_id.assert_not_awaited()


def test_resolve_subscription_remna_user_uses_batch_hit_without_direct_lookup() -> None:
    subscription = build_subscription()
    remna_user = SimpleNamespace(username="batch-hit")
    remnawave_service = SimpleNamespace(get_user=AsyncMock())

    result = run_async(
        resolve_subscription_remna_user(
            subscription=subscription,
            remna_users_by_uuid={subscription.user_remna_id: remna_user},
            remnawave_service=remnawave_service,
        )
    )

    assert result is remna_user
    remnawave_service.get_user.assert_not_awaited()


def test_resolve_subscription_remna_user_falls_back_to_direct_lookup_on_batch_miss() -> None:
    subscription = build_subscription()
    remna_user = SimpleNamespace(username="fallback")
    remnawave_service = SimpleNamespace(get_user=AsyncMock(return_value=remna_user))

    result = run_async(
        resolve_subscription_remna_user(
            subscription=subscription,
            remna_users_by_uuid={},
            remnawave_service=remnawave_service,
        )
    )

    assert result is remna_user
    remnawave_service.get_user.assert_awaited_once_with(subscription.user_remna_id)


def test_load_owner_remna_users_by_uuid_returns_none_on_batch_failure() -> None:
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(side_effect=RuntimeError("boom"))
    )

    result = run_async(
        load_owner_remna_users_by_uuid(
            owner_telegram_id=12,
            remnawave_service=remnawave_service,
        )
    )

    assert result is None
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(12)


def test_resolve_subscription_profile_name_returns_none_when_username_missing() -> None:
    subscription = build_subscription()
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=SimpleNamespace(username=None))
    )

    result = run_async(
        resolve_subscription_profile_name(
            subscription=subscription,
            remna_users_by_uuid=None,
            remnawave_service=remnawave_service,
        )
    )

    assert result is None
    remnawave_service.get_user.assert_awaited_once_with(subscription.user_remna_id)
