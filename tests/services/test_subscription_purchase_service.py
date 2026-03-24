from __future__ import annotations

import asyncio
from typing import Any, cast

from src.core.enums import ArchivedPlanRenewMode, PlanAvailability
from src.infrastructure.database.models.dto import PlanDto, UserDto
from src.services.subscription_purchase import (
    ARCHIVED_PLAN_NOT_PURCHASABLE_CODE,
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseService,
)


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


def build_service(plan_service: FakePlanService) -> SubscriptionPurchaseService:
    return SubscriptionPurchaseService(
        config=cast(Any, object()),
        plan_service=cast(Any, plan_service),
        pricing_service=cast(Any, object()),
        purchase_access_service=cast(Any, object()),
        subscription_service=cast(Any, object()),
        subscription_purchase_policy_service=cast(Any, object()),
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
