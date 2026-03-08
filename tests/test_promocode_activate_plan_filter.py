from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.enums import PlanType, PromocodeRewardType, SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    PromocodeDto,
    SubscriptionDto,
    UserDto,
)
from src.services.promocode import ActivationResult
from src.services.promocode_portal import PromocodePortalError, PromocodePortalService


def _build_user(telegram_id: int = 1001) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        referral_code=f"ref{telegram_id}",
        name=f"User {telegram_id}",
    )


def _build_plan(plan_id: int, duration: int = 30) -> PlanSnapshotDto:
    return PlanSnapshotDto(
        id=plan_id,
        name=f"Plan {plan_id}",
        type=PlanType.UNLIMITED,
        traffic_limit=-1,
        device_limit=-1,
        duration=duration,
        internal_squads=[],
    )


def _build_active_subscription(
    *,
    subscription_id: int,
    user_telegram_id: int,
    plan_id: int,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=-1,
        device_limit=-1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/sub",
        plan=_build_plan(plan_id),
    )


def _build_promocode(
    *,
    reward_type: PromocodeRewardType,
    allowed_plan_ids: list[int],
    reward: int = 10,
) -> PromocodeDto:
    promocode = PromocodeDto(
        id=1,
        code="PROMO1",
        is_active=True,
        reward_type=reward_type,
        reward=reward,
    )
    promocode.allowed_plan_ids = allowed_plan_ids
    if reward_type == PromocodeRewardType.SUBSCRIPTION:
        promocode.plan = _build_plan(999, duration=30)
    return promocode


def _build_service(
    *,
    promocode: PromocodeDto,
    subscriptions: list[SubscriptionDto],
    target_subscription: SubscriptionDto | None = None,
    activate_result: ActivationResult | None = None,
) -> tuple[PromocodePortalService, SimpleNamespace]:
    promocode_service = SimpleNamespace(
        get_by_code=AsyncMock(return_value=promocode),
        activate=AsyncMock(
            return_value=activate_result
            or ActivationResult(success=True, promocode=promocode, message_key="ok")
        ),
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=subscriptions),
        get=AsyncMock(return_value=target_subscription),
    )
    service = PromocodePortalService(
        promocode_service=promocode_service,
        purchase_access_service=SimpleNamespace(assert_can_purchase=AsyncMock()),
        subscription_service=subscription_service,
        user_service=SimpleNamespace(),
    )
    return service, promocode_service


def test_activate_promocode_normalizes_code_before_lookup_and_activation() -> None:
    user = _build_user()
    promocode = _build_promocode(
        reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
        allowed_plan_ids=[],
        reward=15,
    )
    service, promo_service = _build_service(promocode=promocode, subscriptions=[])

    result = asyncio.run(
        service.activate(
            current_user=user,
            code="  promo1 ",
            subscription_id=None,
            create_new=False,
        )
    )

    assert result.next_step is None
    assert result.message == "Promocode activated successfully"
    promo_service.get_by_code.assert_awaited_once_with("PROMO1")
    assert promo_service.activate.await_args.kwargs["code"] == "PROMO1"


def test_subscription_promocode_without_eligible_active_subscriptions_returns_create_new() -> None:
    user = _build_user()
    promocode = _build_promocode(
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        allowed_plan_ids=[100],
        reward=30,
    )
    ineligible_active_sub = _build_active_subscription(
        subscription_id=10,
        user_telegram_id=user.telegram_id,
        plan_id=200,
    )
    service, promo_service = _build_service(
        promocode=promocode,
        subscriptions=[ineligible_active_sub],
    )

    result = asyncio.run(
        service.activate(
            current_user=user,
            code="promo1",
            subscription_id=None,
            create_new=False,
        )
    )

    assert result.next_step == "CREATE_NEW"
    assert "create a new subscription" in result.message
    promo_service.activate.assert_not_awaited()


def test_duration_promocode_without_eligible_active_subscriptions_returns_400() -> None:
    user = _build_user()
    promocode = _build_promocode(
        reward_type=PromocodeRewardType.DURATION,
        allowed_plan_ids=[100],
        reward=7,
    )
    ineligible_active_sub = _build_active_subscription(
        subscription_id=11,
        user_telegram_id=user.telegram_id,
        plan_id=200,
    )
    service, promo_service = _build_service(
        promocode=promocode,
        subscriptions=[ineligible_active_sub],
    )

    with pytest.raises(PromocodePortalError) as exc_info:
        asyncio.run(
            service.activate(
                current_user=user,
                code="promo1",
                subscription_id=None,
                create_new=False,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "No eligible active subscriptions to apply this promocode"
    promo_service.activate.assert_not_awaited()


def test_subscription_promocode_rejects_ineligible_explicit_subscription() -> None:
    user = _build_user()
    promocode = _build_promocode(
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        allowed_plan_ids=[100],
        reward=30,
    )
    ineligible_active_sub = _build_active_subscription(
        subscription_id=12,
        user_telegram_id=user.telegram_id,
        plan_id=200,
    )
    service, promo_service = _build_service(
        promocode=promocode,
        subscriptions=[ineligible_active_sub],
        target_subscription=ineligible_active_sub,
    )

    with pytest.raises(PromocodePortalError) as exc_info:
        asyncio.run(
            service.activate(
                current_user=user,
                code="promo1",
                subscription_id=12,
                create_new=False,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Subscription plan is not eligible for this promocode"
    promo_service.activate.assert_not_awaited()


def test_subscription_promocode_without_filter_auto_activates_single_active_subscription() -> None:
    user = _build_user()
    promocode = _build_promocode(
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        allowed_plan_ids=[],
        reward=30,
    )
    active_sub = _build_active_subscription(
        subscription_id=13,
        user_telegram_id=user.telegram_id,
        plan_id=200,
    )
    service, promo_service = _build_service(
        promocode=promocode,
        subscriptions=[active_sub],
    )

    result = asyncio.run(
        service.activate(
            current_user=user,
            code="promo1",
            subscription_id=None,
            create_new=False,
        )
    )

    assert result.next_step is None
    assert promo_service.activate.await_args.kwargs["target_subscription_id"] == 13
