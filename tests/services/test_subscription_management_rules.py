from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from remnawave.exceptions import NotFoundError
from remnawave.exceptions.general import ApiErrorResponse

from src.core.enums import SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)
from src.services.plan import PlanDeletionBlockedError, PlanService
from src.services.subscription import SubscriptionService
from src.services.subscription_portal import SubscriptionPortalService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(telegram_id=telegram_id, name="Test User")


def build_plan(*, plan_id: int, name: str = "Plan") -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name,
        is_active=True,
        durations=[],
        allowed_user_ids=[],
        internal_squads=[],
    )


def build_subscription(
    *,
    subscription_id: int,
    plan: PlanDto,
    user_telegram_id: int = 100,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=status,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/subscription",
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )


def build_subscription_service(*, uow) -> SubscriptionService:
    return SubscriptionService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=uow,
        user_service=MagicMock(),
    )


def build_plan_service(*, uow) -> PlanService:
    return PlanService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=uow,
    )


def test_has_used_trial_checks_historical_trial_records() -> None:
    captured = {}

    async def fake_count(model, conditions):
        captured["model"] = model
        captured["conditions"] = conditions
        return 1

    subscriptions_repo = SimpleNamespace(_count=AsyncMock(side_effect=fake_count))
    uow = SimpleNamespace(repository=SimpleNamespace(subscriptions=subscriptions_repo))
    service = build_subscription_service(uow=uow)

    result = run_async(service.has_used_trial(build_user()))

    assert result is True
    assert "is_trial" in str(captured["conditions"]).lower()
    assert "status" not in str(captured["conditions"]).lower()


def test_delete_plan_is_blocked_when_transition_rules_reference_it() -> None:
    plans_repo = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(id=7)),
        get_transition_references=AsyncMock(return_value=[SimpleNamespace(id=99)]),
        delete=AsyncMock(return_value=True),
    )
    subscriptions_repo = SimpleNamespace(filter_by_plan_id=AsyncMock(return_value=[]))
    uow = SimpleNamespace(
        repository=SimpleNamespace(
            plans=plans_repo,
            subscriptions=subscriptions_repo,
        )
    )
    service = build_plan_service(uow=uow)

    with pytest.raises(PlanDeletionBlockedError):
        run_async(service.delete(7))

    plans_repo.delete.assert_not_awaited()


def test_delete_subscription_treats_missing_remnawave_profile_as_success() -> None:
    current_user = build_user()
    plan = build_plan(plan_id=1, name="Standard")
    deleted_subscription = build_subscription(
        subscription_id=11,
        plan=plan,
        user_telegram_id=current_user.telegram_id,
    )
    next_subscription = build_subscription(
        subscription_id=12,
        plan=plan,
        user_telegram_id=current_user.telegram_id,
    )

    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=deleted_subscription),
        delete_subscription=AsyncMock(return_value=True),
        get_all_by_user=AsyncMock(return_value=[deleted_subscription, next_subscription]),
    )
    user_service = SimpleNamespace(
        set_current_subscription=AsyncMock(),
        delete_current_subscription=AsyncMock(),
        uow=SimpleNamespace(commit=AsyncMock()),
    )
    remnawave_service = SimpleNamespace(
        delete_user=AsyncMock(
            side_effect=NotFoundError(
                404,
                ApiErrorResponse(message="Not found"),
            )
        )
    )

    service = SubscriptionPortalService(
        subscription_service=subscription_service,
        subscription_runtime_service=MagicMock(),
        plan_service=MagicMock(),
        remnawave_service=remnawave_service,
        user_service=user_service,
    )

    result = run_async(
        service.delete_subscription(
            subscription_id=deleted_subscription.id or 0,
            current_user=current_user,
        )
    )

    assert result.success is True
    subscription_service.delete_subscription.assert_awaited_once_with(deleted_subscription.id)
    user_service.set_current_subscription.assert_awaited_once_with(
        telegram_id=current_user.telegram_id,
        subscription_id=next_subscription.id,
    )
    user_service.delete_current_subscription.assert_not_awaited()
    user_service.uow.commit.assert_awaited_once()
