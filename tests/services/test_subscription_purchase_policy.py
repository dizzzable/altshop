from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

from src.core.enums import (
    ArchivedPlanRenewMode,
    PlanAvailability,
    PurchaseChannel,
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
from src.services.plan_catalog import PlanCatalogItemSnapshot
from src.services.subscription_purchase_policy import (
    ARCHIVED_REPLACEMENT_WARNING_CODE,
    UPGRADE_WARNING_CODE,
    SubscriptionPurchasePolicyService,
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
    availability: PlanAvailability = PlanAvailability.ALL,
    archived_renew_mode: ArchivedPlanRenewMode = ArchivedPlanRenewMode.SELF_RENEW,
    replacement_plan_ids: list[int] | None = None,
    upgrade_to_plan_ids: list[int] | None = None,
    traffic_limit: int = 100,
    device_limit: int = 1,
) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name,
        is_active=is_active,
        is_archived=is_archived,
        availability=availability,
        archived_renew_mode=archived_renew_mode,
        replacement_plan_ids=replacement_plan_ids or [],
        upgrade_to_plan_ids=upgrade_to_plan_ids or [],
        traffic_limit=traffic_limit,
        device_limit=device_limit,
        durations=[],
        allowed_user_ids=[],
        internal_squads=[],
    )


def build_subscription(
    plan: PlanDto,
    *,
    subscription_id: int = 1,
    user_telegram_id: int = 100,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    is_trial: bool = False,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=status,
        is_trial=is_trial,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://example.test/subscription",
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )


class FakePlanService:
    def __init__(self, plans: list[PlanDto]) -> None:
        self.plans = {plan.id: plan for plan in plans}

    async def get(self, plan_id: int) -> PlanDto | None:
        return self.plans.get(plan_id)

    async def get_purchase_available_plans_by_ids(
        self,
        *,
        user: UserDto,
        plan_ids: list[int],
    ) -> list[PlanDto]:
        del user
        return [
            plan
            for plan_id in plan_ids
            if (plan := self.plans.get(plan_id)) is not None and plan.is_publicly_purchasable
        ]

    async def get_transition_available_plans_by_ids(
        self,
        *,
        plan_ids: list[int],
    ) -> list[PlanDto]:
        return [
            plan
            for plan_id in plan_ids
            if (plan := self.plans.get(plan_id)) is not None
            and plan.is_active
            and not plan.is_archived
        ]


class FakePlanCatalogService:
    async def build_items_from_plans(
        self,
        *,
        current_user: UserDto,
        channel: PurchaseChannel,
        plans: list[PlanDto],
    ) -> list[PlanCatalogItemSnapshot]:
        del current_user, channel
        return [
            PlanCatalogItemSnapshot(
                id=plan.id or 0,
                name=plan.name,
                description=plan.description,
                tag=plan.tag,
                type=plan.type.value,
                availability=plan.availability.value,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                order_index=plan.order_index,
                is_active=plan.is_active,
                allowed_user_ids=plan.allowed_user_ids,
                internal_squads=[],
                external_squad=None,
                durations=[],
                created_at="",
                updated_at="",
            )
            for plan in plans
        ]


def build_policy_service(*plans: PlanDto) -> SubscriptionPurchasePolicyService:
    return SubscriptionPurchasePolicyService(
        plan_service=FakePlanService(list(plans)),
        plan_catalog_service=FakePlanCatalogService(),
    )


def test_archived_self_renew_returns_only_source_plan() -> None:
    user = build_user()
    source_plan = build_plan(
        plan_id=1,
        name="Legacy",
        is_archived=True,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
    )
    subscription = build_subscription(source_plan, subscription_id=11)
    service = build_policy_service(source_plan)

    action_policy = run_async(
        service.get_action_policy(current_user=user, subscription=subscription)
    )
    purchase_options = run_async(
        service.get_purchase_options(
            current_user=user,
            subscription=subscription,
            purchase_type=PurchaseType.RENEW,
            channel=PurchaseChannel.WEB,
        )
    )

    assert action_policy.can_renew is True
    assert action_policy.can_upgrade is False
    assert action_policy.can_multi_renew is True
    assert action_policy.renew_mode == SubscriptionRenewMode.SELF_RENEW
    assert purchase_options.selection_locked is True
    assert purchase_options.warning_code is None
    assert [plan.id for plan in purchase_options.plans] == [source_plan.id]


def test_archived_replace_on_renew_returns_only_configured_replacements() -> None:
    user = build_user()
    replacement_a = build_plan(plan_id=2, name="Fresh Start")
    replacement_b = build_plan(
        plan_id=3,
        name="Bigger Plan",
        device_limit=2,
        availability=PlanAvailability.NEW,
    )
    source_plan = build_plan(
        plan_id=1,
        name="Old Plan",
        is_archived=True,
        archived_renew_mode=ArchivedPlanRenewMode.REPLACE_ON_RENEW,
        replacement_plan_ids=[replacement_a.id, replacement_b.id],
    )
    subscription = build_subscription(source_plan, subscription_id=12)
    service = build_policy_service(source_plan, replacement_a, replacement_b)

    action_policy = run_async(
        service.get_action_policy(current_user=user, subscription=subscription)
    )
    purchase_options = run_async(
        service.get_purchase_options(
            current_user=user,
            subscription=subscription,
            purchase_type=PurchaseType.RENEW,
            channel=PurchaseChannel.WEB,
        )
    )

    assert action_policy.can_renew is True
    assert action_policy.can_multi_renew is False
    assert action_policy.renew_mode == SubscriptionRenewMode.REPLACE_ON_RENEW
    assert purchase_options.selection_locked is False
    assert purchase_options.warning_code == ARCHIVED_REPLACEMENT_WARNING_CODE
    assert [plan.id for plan in purchase_options.plans] == [replacement_a.id, replacement_b.id]


def test_upgrade_options_return_all_explicit_transition_targets() -> None:
    user = build_user()
    better_plan = build_plan(plan_id=2, name="More Devices", device_limit=3)
    worse_plan = build_plan(plan_id=3, name="Less Traffic", traffic_limit=50)
    same_plan_limits = build_plan(plan_id=4, name="Same Limits", traffic_limit=100, device_limit=1)
    source_plan = build_plan(
        plan_id=1,
        name="Starter",
        upgrade_to_plan_ids=[better_plan.id, worse_plan.id, same_plan_limits.id],
        traffic_limit=100,
        device_limit=1,
    )
    subscription = build_subscription(source_plan, subscription_id=13)
    service = build_policy_service(source_plan, better_plan, worse_plan, same_plan_limits)

    action_policy = run_async(
        service.get_action_policy(current_user=user, subscription=subscription)
    )
    purchase_options = run_async(
        service.get_purchase_options(
            current_user=user,
            subscription=subscription,
            purchase_type=PurchaseType.UPGRADE,
            channel=PurchaseChannel.WEB,
        )
    )

    assert action_policy.can_renew is True
    assert action_policy.can_upgrade is True
    assert action_policy.can_multi_renew is True
    assert purchase_options.warning_code == UPGRADE_WARNING_CODE
    assert [plan.id for plan in purchase_options.plans] == [
        better_plan.id,
        worse_plan.id,
        same_plan_limits.id,
    ]


def test_upgrade_options_ignore_catalog_availability_for_explicit_targets() -> None:
    user = build_user()
    existing_only_plan = build_plan(
        plan_id=2,
        name="Existing Only",
        availability=PlanAvailability.EXISTING,
    )
    new_only_plan = build_plan(
        plan_id=3,
        name="New Only",
        availability=PlanAvailability.NEW,
    )
    inactive_plan = build_plan(plan_id=4, name="Inactive", is_active=False)
    archived_plan = build_plan(plan_id=5, name="Archived", is_archived=True)
    source_plan = build_plan(
        plan_id=1,
        name="Trial",
        availability=PlanAvailability.TRIAL,
        upgrade_to_plan_ids=[
            existing_only_plan.id,
            new_only_plan.id,
            inactive_plan.id,
            archived_plan.id,
            1,
        ],
    )
    subscription = build_subscription(source_plan, subscription_id=15, is_trial=True)
    service = build_policy_service(
        source_plan,
        existing_only_plan,
        new_only_plan,
        inactive_plan,
        archived_plan,
    )

    purchase_options = run_async(
        service.get_purchase_options(
            current_user=user,
            subscription=subscription,
            purchase_type=PurchaseType.UPGRADE,
            channel=PurchaseChannel.WEB,
        )
    )

    assert [plan.id for plan in purchase_options.plans] == [
        existing_only_plan.id,
        new_only_plan.id,
    ]


def test_trial_subscription_can_only_upgrade() -> None:
    user = build_user()
    paid_plan = build_plan(plan_id=2, name="Paid", device_limit=2)
    same_limits_paid_plan = build_plan(plan_id=3, name="Same Limits Paid")
    trial_plan = build_plan(
        plan_id=1,
        name="Trial",
        availability=PlanAvailability.TRIAL,
        upgrade_to_plan_ids=[paid_plan.id, same_limits_paid_plan.id],
    )
    subscription = build_subscription(trial_plan, subscription_id=14, is_trial=True)
    service = build_policy_service(trial_plan, paid_plan, same_limits_paid_plan)

    action_policy = run_async(
        service.get_action_policy(current_user=user, subscription=subscription)
    )
    renew_options = run_async(
        service.get_purchase_options(
            current_user=user,
            subscription=subscription,
            purchase_type=PurchaseType.RENEW,
            channel=PurchaseChannel.WEB,
        )
    )
    upgrade_options = run_async(
        service.get_purchase_options(
            current_user=user,
            subscription=subscription,
            purchase_type=PurchaseType.UPGRADE,
            channel=PurchaseChannel.WEB,
        )
    )

    assert action_policy.can_renew is False
    assert action_policy.can_multi_renew is False
    assert action_policy.can_upgrade is True
    assert renew_options.plans == []
    assert [plan.id for plan in upgrade_options.plans] == [
        paid_plan.id,
        same_limits_paid_plan.id,
    ]
    assert upgrade_options.warning_code == UPGRADE_WARNING_CODE
