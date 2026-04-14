from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, SubscriptionDto
from src.infrastructure.taskiq.tasks.notifications import _build_expiry_summary_lines


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_subscription(
    subscription_id: int,
    owner_telegram_id: int,
    plan_name: str,
) -> SubscriptionDto:
    plan = PlanDto(
        id=subscription_id,
        name=plan_name,
        durations=[],
        allowed_user_ids=[],
        internal_squads=[],
    )
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=owner_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now(),
        url="https://example.test/sub",
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )


def test_build_expiry_summary_lines_prefers_batched_remnawave_profile_map() -> None:
    subscriptions = [
        build_subscription(1, 12, "Starter"),
        build_subscription(2, 12, "Family"),
    ]
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(
            return_value={
                subscriptions[0].user_remna_id: SimpleNamespace(username="starter_profile"),
                subscriptions[1].user_remna_id: SimpleNamespace(username="family_profile"),
            }
        ),
        get_user=AsyncMock(),
    )

    summary = run_async(
        _build_expiry_summary_lines(
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        )
    )

    assert "starter_profile" in summary
    assert "family_profile" in summary
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(12)
    remnawave_service.get_user.assert_not_awaited()


def test_build_expiry_summary_lines_falls_back_to_direct_lookup_on_batch_miss() -> None:
    subscriptions = [build_subscription(1, 12, "Starter")]
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(return_value={}),
        get_user=AsyncMock(return_value=SimpleNamespace(username="fallback_profile")),
    )

    summary = run_async(
        _build_expiry_summary_lines(
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        )
    )

    assert "fallback_profile" in summary
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(12)
    remnawave_service.get_user.assert_awaited_once_with(subscriptions[0].user_remna_id)


def test_build_expiry_summary_lines_falls_back_to_direct_lookup_on_batch_failure() -> None:
    subscriptions = [
        build_subscription(1, 12, "Starter"),
        build_subscription(2, 12, "Family"),
    ]
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(side_effect=RuntimeError("boom")),
        get_user=AsyncMock(
            side_effect=[
                SimpleNamespace(username="starter_profile"),
                SimpleNamespace(username="family_profile"),
            ]
        ),
    )

    summary = run_async(
        _build_expiry_summary_lines(
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        )
    )

    assert "starter_profile" in summary
    assert "family_profile" in summary
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(12)
    assert remnawave_service.get_user.await_count == 2
