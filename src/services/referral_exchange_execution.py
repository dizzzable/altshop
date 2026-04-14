from __future__ import annotations

import secrets
import string
from datetime import timedelta
from typing import TYPE_CHECKING

from src.core.enums import (
    PointsExchangeType,
    PromocodeAvailability,
    PromocodeRewardType,
    SubscriptionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanSnapshotDto, PromocodeDto

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import SubscriptionDto, UserDto

    from .referral_exchange import ReferralExchangeExecutionResult, ReferralExchangeService


async def execute(
    service: ReferralExchangeService,
    *,
    user_telegram_id: int,
    exchange_type: PointsExchangeType,
    subscription_id: int | None = None,
    gift_plan_id: int | None = None,
) -> ReferralExchangeExecutionResult:
    referral_settings = await service.settings_service.get_referral_settings()
    exchange_settings = referral_settings.points_exchange

    if not exchange_settings.exchange_enabled:
        raise service._exchange_error(
            code="EXCHANGE_DISABLED",
            message="Points exchange is disabled",
        )
    if not exchange_settings.is_type_enabled(exchange_type):
        raise service._exchange_error(
            code="EXCHANGE_TYPE_DISABLED",
            message=f"Exchange type '{exchange_type.value}' is disabled",
        )

    db_user = await service.uow.repository.users.get_for_update(user_telegram_id)
    if not db_user:
        raise service._exchange_error(code="USER_NOT_FOUND", message="User not found")
    user = service._user_dto_from_model(db_user)
    if user is None:
        raise service._exchange_error(code="USER_NOT_FOUND", message="User not found")

    type_settings = exchange_settings.get_settings_for_type(exchange_type)
    effective_points = service._get_effective_points(
        user_points=user.points,
        max_points=type_settings.max_points,
    )
    if effective_points < type_settings.min_points:
        raise service._exchange_error(
            code="NOT_ENOUGH_POINTS",
            message=f"Minimum points required: {type_settings.min_points}",
        )

    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        result = await service._execute_subscription_days(
            user=user,
            effective_points=effective_points,
            points_cost=type_settings.points_cost,
            subscription_id=subscription_id,
        )
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        result = await service._execute_gift_subscription(
            user=user,
            points_cost=type_settings.points_cost,
            configured_plan_id=type_settings.gift_plan_id,
            requested_plan_id=gift_plan_id,
            duration_days=type_settings.gift_duration_days,
        )
    elif exchange_type == PointsExchangeType.DISCOUNT:
        result = await service._execute_discount(
            user_telegram_id=user.telegram_id,
            current_points=user.points,
            current_discount=user.purchase_discount,
            effective_points=effective_points,
            points_cost=type_settings.points_cost,
            max_discount_percent=type_settings.max_discount_percent,
        )
    elif exchange_type == PointsExchangeType.TRAFFIC:
        result = await service._execute_traffic(
            user=user,
            effective_points=effective_points,
            points_cost=type_settings.points_cost,
            max_traffic_gb=type_settings.max_traffic_gb,
            subscription_id=subscription_id,
        )
    else:
        raise service._exchange_error(
            code="UNSUPPORTED_EXCHANGE_TYPE",
            message=f"Unsupported exchange type '{exchange_type.value}'",
        )

    await service.user_service.clear_user_cache(user.telegram_id)
    return result


async def execute_subscription_days(
    service: ReferralExchangeService,
    *,
    user: UserDto,
    effective_points: int,
    points_cost: int,
    subscription_id: int | None,
) -> ReferralExchangeExecutionResult:
    if not subscription_id:
        raise service._exchange_error(
            code="SUBSCRIPTION_REQUIRED",
            message="Subscription ID is required for this exchange type",
        )
    if points_cost <= 0:
        raise service._exchange_error(
            code="INVALID_POINTS_COST",
            message="Points cost must be greater than zero",
        )

    subscription = await service._get_exchangeable_subscription(
        user_telegram_id=user.telegram_id,
        subscription_id=subscription_id,
    )
    days_to_add = effective_points // points_cost
    points_spent = days_to_add * points_cost
    if days_to_add <= 0 or points_spent <= 0:
        raise service._exchange_error(
            code="NOT_ENOUGH_POINTS",
            message="Not enough points for exchange",
        )

    base_expire_at = max(subscription.expire_at, datetime_now())
    subscription.expire_at = base_expire_at + timedelta(days=days_to_add)
    await service.subscription_service.update(subscription, auto_commit=False)

    points_after = user.points - points_spent
    await service.uow.repository.users.update(user.telegram_id, points=points_after)
    await service.remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    return service._execution_result(
        exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
        points_spent=points_spent,
        points_balance_after=points_after,
        result=service._result_payload(days_added=days_to_add),
    )


async def execute_gift_subscription(
    service: ReferralExchangeService,
    *,
    user: UserDto,
    points_cost: int,
    configured_plan_id: int | None,
    requested_plan_id: int | None,
    duration_days: int,
) -> ReferralExchangeExecutionResult:
    if points_cost <= 0:
        raise service._exchange_error(
            code="INVALID_POINTS_COST",
            message="Points cost must be greater than zero",
        )
    if user.points < points_cost:
        raise service._exchange_error(
            code="NOT_ENOUGH_POINTS",
            message="Not enough points for exchange",
        )

    selected_plan_id = requested_plan_id or configured_plan_id
    if not selected_plan_id:
        raise service._exchange_error(
            code="PLAN_REQUIRED",
            message="Gift plan is required for this exchange type",
        )

    plan = await service.plan_service.get(selected_plan_id)
    if not plan or not plan.is_active:
        raise service._exchange_error(
            code="PLAN_NOT_FOUND",
            message="Selected gift plan not found",
        )

    safe_duration_days = max(duration_days, 1)
    promocode_code = await service._generate_gift_promocode_code()
    plan_snapshot = PlanSnapshotDto.from_plan(plan, safe_duration_days)
    promocode = PromocodeDto(
        code=promocode_code,
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        availability=PromocodeAvailability.ALL,
        reward=safe_duration_days,
        plan=plan_snapshot,
        lifetime=-1,
        max_activations=1,
        is_active=True,
    )
    await service.promocode_service.create(promocode, auto_commit=False)

    points_after = user.points - points_cost
    await service.uow.repository.users.update(user.telegram_id, points=points_after)

    return service._execution_result(
        exchange_type=PointsExchangeType.GIFT_SUBSCRIPTION,
        points_spent=points_cost,
        points_balance_after=points_after,
        result=service._result_payload(
            gift_promocode=promocode_code,
            gift_plan_name=plan.name,
            gift_duration_days=safe_duration_days,
        ),
    )


async def execute_discount(
    service: ReferralExchangeService,
    *,
    user_telegram_id: int,
    current_points: int,
    current_discount: int,
    effective_points: int,
    points_cost: int,
    max_discount_percent: int,
) -> ReferralExchangeExecutionResult:
    if points_cost <= 0:
        raise service._exchange_error(
            code="INVALID_POINTS_COST",
            message="Points cost must be greater than zero",
        )

    discount_percent = effective_points // points_cost
    if max_discount_percent > 0:
        discount_percent = min(discount_percent, max_discount_percent)
    points_spent = discount_percent * points_cost
    if discount_percent <= 0 or points_spent <= 0:
        raise service._exchange_error(
            code="NOT_ENOUGH_POINTS",
            message="Not enough points for exchange",
        )

    points_after = current_points - points_spent
    purchase_discount_after = min(max(current_discount, 0) + discount_percent, 100)
    await service.uow.repository.users.update(
        user_telegram_id,
        points=points_after,
        purchase_discount=purchase_discount_after,
    )

    return service._execution_result(
        exchange_type=PointsExchangeType.DISCOUNT,
        points_spent=points_spent,
        points_balance_after=points_after,
        result=service._result_payload(discount_percent_added=discount_percent),
    )


async def execute_traffic(
    service: ReferralExchangeService,
    *,
    user: UserDto,
    effective_points: int,
    points_cost: int,
    max_traffic_gb: int,
    subscription_id: int | None,
) -> ReferralExchangeExecutionResult:
    if not subscription_id:
        raise service._exchange_error(
            code="SUBSCRIPTION_REQUIRED",
            message="Subscription ID is required for this exchange type",
        )
    if points_cost <= 0:
        raise service._exchange_error(
            code="INVALID_POINTS_COST",
            message="Points cost must be greater than zero",
        )

    subscription = await service._get_exchangeable_subscription(
        user_telegram_id=user.telegram_id,
        subscription_id=subscription_id,
    )
    traffic_gb = effective_points // points_cost
    if max_traffic_gb > 0:
        traffic_gb = min(traffic_gb, max_traffic_gb)
    points_spent = traffic_gb * points_cost
    if traffic_gb <= 0 or points_spent <= 0:
        raise service._exchange_error(
            code="NOT_ENOUGH_POINTS",
            message="Not enough points for exchange",
        )

    subscription.traffic_limit = (subscription.traffic_limit or 0) + traffic_gb
    await service.subscription_service.update(subscription, auto_commit=False)

    points_after = user.points - points_spent
    await service.uow.repository.users.update(user.telegram_id, points=points_after)
    await service.remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    return service._execution_result(
        exchange_type=PointsExchangeType.TRAFFIC,
        points_spent=points_spent,
        points_balance_after=points_after,
        result=service._result_payload(traffic_gb_added=traffic_gb),
    )


async def get_exchangeable_subscription(
    service: ReferralExchangeService,
    *,
    user_telegram_id: int,
    subscription_id: int,
) -> SubscriptionDto:
    subscription = await service.subscription_service.get(subscription_id)
    if not subscription or subscription.user_telegram_id != user_telegram_id:
        raise service._exchange_error(
            code="SUBSCRIPTION_NOT_FOUND",
            message="Subscription not found",
        )
    if (
        subscription.status
        not in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.LIMITED,
        )
        or subscription.is_unlimited
    ):
        raise service._exchange_error(
            code="SUBSCRIPTION_NOT_ELIGIBLE",
            message="Subscription is not eligible for this exchange",
        )
    return subscription


async def generate_gift_promocode_code(service: ReferralExchangeService) -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "GIFT_" + "".join(secrets.choice(alphabet) for _ in range(8))
        exists = await service.promocode_service.get_by_code(code)
        if not exists:
            return code
    raise service._exchange_error(
        code="PROMOCODE_GENERATION_FAILED",
        message="Could not generate unique promocode",
    )
