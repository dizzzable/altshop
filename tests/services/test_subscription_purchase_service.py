from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, cast
from uuid import uuid4

from src.core.enums import (
    ArchivedPlanRenewMode,
    PlanAvailability,
    PurchaseType,
    SubscriptionRenewMode,
    SubscriptionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)
from src.services.subscription_purchase import (
    ARCHIVED_PLAN_NOT_PURCHASABLE_CODE,
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseService,
    ValidatedPurchaseContext,
)
from src.services.subscription_purchase_policy import SubscriptionPurchaseSelection


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(telegram_id=telegram_id, name="Test User")


def build_plan(
    *,
    plan_id: int,
    name: str,
    is_active: bool = True,
    is_archived: bool = False,
) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name,
        is_active=is_active,
        is_archived=is_archived,
        availability=PlanAvailability.ALL,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
        durations=[],
        allowed_user_ids=[],
        internal_squads=[],
    )


class FakePlanService:
    def __init__(self, *, available_plans: list[PlanDto], known_plans: list[PlanDto]) -> None:
        self._available_plans = available_plans
        self._known_plans = {plan.id: plan for plan in known_plans}

    async def get_available_plans(self, user: UserDto) -> list[PlanDto]:
        del user
        return self._available_plans

    async def get(self, plan_id: int) -> PlanDto | None:
        return self._known_plans.get(plan_id)


class FakeSubscriptionService:
    def __init__(self, subscriptions: list[SubscriptionDto]) -> None:
        self._subscriptions = {subscription.id: subscription for subscription in subscriptions}

    async def get(self, subscription_id: int) -> SubscriptionDto | None:
        return self._subscriptions.get(subscription_id)


class FakeSubscriptionPurchasePolicyService:
    def __init__(self, *, source_plan: PlanDto, upgrade_plans: tuple[PlanDto, ...]) -> None:
        self.source_plan = source_plan
        self.upgrade_plans = upgrade_plans

    async def build_selection(
        self,
        *,
        current_user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionPurchaseSelection:
        del current_user
        return SubscriptionPurchaseSelection(
            source_subscription=subscription,
            source_plan=self.source_plan,
            source_plan_missing=False,
            renew_mode=SubscriptionRenewMode.STANDARD,
            renew_plans=(self.source_plan,),
            upgrade_plans=self.upgrade_plans,
        )

    @staticmethod
    def get_purchase_candidates(
        *,
        selection: SubscriptionPurchaseSelection,
        purchase_type: PurchaseType,
    ) -> tuple[PlanDto, ...]:
        if purchase_type == PurchaseType.UPGRADE:
            return selection.upgrade_plans
        return selection.renew_plans


def build_subscription(
    plan: PlanDto,
    *,
    subscription_id: int = 1,
    user_telegram_id: int = 100,
    is_trial: bool = False,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        is_trial=is_trial,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/subscription",
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )


def build_service(
    plan_service: FakePlanService,
    *,
    subscription_service: Any | None = None,
    subscription_purchase_policy_service: Any | None = None,
) -> SubscriptionPurchaseService:
    return SubscriptionPurchaseService(
        config=cast(Any, object()),
        plan_service=cast(Any, plan_service),
        pricing_service=cast(Any, object()),
        purchase_access_service=cast(Any, object()),
        subscription_service=cast(Any, subscription_service or object()),
        subscription_purchase_policy_service=cast(
            Any, subscription_purchase_policy_service or object()
        ),
        settings_service=cast(Any, object()),
        payment_gateway_service=cast(Any, object()),
        partner_service=cast(Any, object()),
        market_quote_service=cast(Any, object()),
    )


def test_get_valid_catalog_purchase_plan_accepts_public_plan() -> None:
    user = build_user()
    public_plan = build_plan(plan_id=1, name="Standard")
    service = build_service(
        FakePlanService(available_plans=[public_plan], known_plans=[public_plan])
    )

    plan = run_async(
        service._get_valid_catalog_purchase_plan(
            request=SubscriptionPurchaseRequest(plan_id=public_plan.id),
            current_user=user,
        )
    )

    assert plan.id == public_plan.id


def test_get_valid_catalog_purchase_plan_rejects_archived_plan_with_explicit_code() -> None:
    user = build_user()
    archived_plan = build_plan(plan_id=7, name="Legacy", is_archived=True)
    service = build_service(
        FakePlanService(available_plans=[], known_plans=[archived_plan])
    )

    try:
        run_async(
            service._get_valid_catalog_purchase_plan(
                request=SubscriptionPurchaseRequest(plan_id=archived_plan.id),
                current_user=user,
            )
        )
    except SubscriptionPurchaseError as error:
        assert error.status_code == 400
        assert error.detail == {
            "code": ARCHIVED_PLAN_NOT_PURCHASABLE_CODE,
            "message": "Archived plans cannot be purchased as a new subscription",
        }
    else:
        raise AssertionError("Expected archived plan purchase to be rejected")


def test_validate_upgrade_purchase_context_accepts_explicit_same_limit_target() -> None:
    user = build_user()
    trial_plan = build_plan(plan_id=1, name="Trial")
    same_limits_target = build_plan(plan_id=2, name="Standard")
    subscription = build_subscription(trial_plan, subscription_id=17, is_trial=True)
    service = build_service(
        FakePlanService(available_plans=[], known_plans=[trial_plan, same_limits_target]),
        subscription_service=FakeSubscriptionService([subscription]),
        subscription_purchase_policy_service=FakeSubscriptionPurchasePolicyService(
            source_plan=trial_plan,
            upgrade_plans=(same_limits_target,),
        ),
    )

    context = run_async(
        service._validate_upgrade_purchase_context(
            request=SubscriptionPurchaseRequest(
                purchase_type=PurchaseType.UPGRADE,
                renew_subscription_id=17,
                plan_id=2,
            ),
            current_user=user,
        )
    )

    assert isinstance(context, ValidatedPurchaseContext)
    assert context.plan.id == 2
