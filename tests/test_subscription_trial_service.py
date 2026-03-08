from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.enums import PlanAvailability, PlanType, SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanDurationDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)
from src.services.subscription_trial import (
    TRIAL_REASON_PLAN_NOT_TRIAL,
    TRIAL_REASON_TELEGRAM_LINK_REQUIRED,
    SubscriptionTrialError,
    SubscriptionTrialService,
)


def _build_user(*, telegram_id: int = 1001) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        referral_code=f"ref{telegram_id or 'web'}",
        name=f"User {telegram_id or 'web'}",
    )


def _build_trial_plan(
    *,
    plan_id: int = 99,
    availability: PlanAvailability = PlanAvailability.TRIAL,
    is_active: bool = True,
) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=f"Plan {plan_id}",
        type=PlanType.UNLIMITED,
        availability=availability,
        is_active=is_active,
        traffic_limit=-1,
        device_limit=-1,
        subscription_count=1,
        durations=[PlanDurationDto(days=30, prices=[])],
        internal_squads=[],
    )


def _build_service(
    *,
    trial_plan: PlanDto | None,
    selected_plan: PlanDto | None = None,
    existing_subscriptions: list[SubscriptionDto] | None = None,
) -> tuple[SubscriptionTrialService, SimpleNamespace, SimpleNamespace]:
    plan_service = SimpleNamespace(
        get_trial_plan=AsyncMock(return_value=trial_plan),
        get=AsyncMock(return_value=selected_plan),
    )
    subscription_service = SimpleNamespace(
        has_used_trial=AsyncMock(return_value=False),
        get_all_by_user=AsyncMock(return_value=existing_subscriptions or []),
        create=AsyncMock(),
    )
    remnawave_service = SimpleNamespace(
        create_user=AsyncMock(),
        get_subscription_url=AsyncMock(),
    )
    service = SubscriptionTrialService(
        plan_service=plan_service,
        purchase_access_service=SimpleNamespace(assert_can_purchase=AsyncMock()),
        remnawave_service=remnawave_service,
        subscription_service=subscription_service,
    )
    return service, subscription_service, remnawave_service


def test_get_eligibility_requires_linked_telegram_identity() -> None:
    service, _, _ = _build_service(trial_plan=_build_trial_plan())

    snapshot = asyncio.run(service.get_eligibility(_build_user(telegram_id=0)))

    assert snapshot.eligible is False
    assert snapshot.reason_code == TRIAL_REASON_TELEGRAM_LINK_REQUIRED
    assert snapshot.requires_telegram_link is True


def test_get_eligibility_returns_trial_plan_id_for_eligible_user() -> None:
    service, _, _ = _build_service(trial_plan=_build_trial_plan(plan_id=77))

    snapshot = asyncio.run(service.get_eligibility(_build_user()))

    assert snapshot.eligible is True
    assert snapshot.trial_plan_id == 77


def test_create_trial_subscription_rejects_non_trial_selected_plan() -> None:
    selected_plan = _build_trial_plan(
        plan_id=50,
        availability=PlanAvailability.ALL,
    )
    service, _, _ = _build_service(
        trial_plan=_build_trial_plan(),
        selected_plan=selected_plan,
    )

    with pytest.raises(SubscriptionTrialError) as exc_info:
        asyncio.run(
            service.create_trial_subscription(
                current_user=_build_user(),
                plan_id=50,
            )
    )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == TRIAL_REASON_PLAN_NOT_TRIAL


def test_create_trial_subscription_persists_created_trial() -> None:
    trial_plan = _build_trial_plan(plan_id=77)
    service, subscription_service, remnawave_service = _build_service(trial_plan=trial_plan)
    created_subscription = SubscriptionDto(
        id=5,
        user_remna_id=uuid4(),
        user_telegram_id=1001,
        status=SubscriptionStatus.ACTIVE,
        is_trial=True,
        traffic_limit=-1,
        device_limit=-1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/sub",
        plan=PlanSnapshotDto.from_plan(trial_plan, 30),
    )
    remnawave_service.create_user = AsyncMock(
        return_value=SimpleNamespace(
            uuid=uuid4(),
            status=SubscriptionStatus.ACTIVE,
            expire_at=datetime_now() + timedelta(days=30),
            subscription_url="https://example.test/sub",
        )
    )
    subscription_service.create = AsyncMock(return_value=created_subscription)

    result = asyncio.run(
        service.create_trial_subscription(
            current_user=_build_user(),
            plan_id=None,
        )
    )

    assert result.id == 5
    created_arg = subscription_service.create.await_args.args[1]
    assert created_arg.is_trial is True
    assert created_arg.plan.id == 77
