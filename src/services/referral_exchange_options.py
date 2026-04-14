from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.enums import PointsExchangeType, SubscriptionStatus

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import SubscriptionDto

    from .referral_exchange import (
        ReferralExchangeOptions,
        ReferralExchangeService,
        ReferralExchangeTypeOption,
        ReferralGiftPlanOption,
    )


async def get_options(
    service: ReferralExchangeService,
    *,
    user_telegram_id: int,
) -> ReferralExchangeOptions:
    user = await service.user_service.get(user_telegram_id)
    if not user:
        raise service._exchange_error(code="USER_NOT_FOUND", message="User not found")

    referral_settings = await service.settings_service.get_referral_settings()
    exchange_settings = referral_settings.points_exchange
    subscriptions = await service._get_exchangeable_subscriptions(user.telegram_id)
    has_subscriptions = bool(subscriptions)
    gift_plans = await service._get_active_gift_plans()

    type_options: list[ReferralExchangeTypeOption] = []
    for exchange_type in PointsExchangeType:
        type_settings = exchange_settings.get_settings_for_type(exchange_type)
        effective_points = service._get_effective_points(
            user_points=user.points,
            max_points=type_settings.max_points,
        )
        computed_value = service._compute_value(exchange_type, effective_points, type_settings)
        requires_subscription = exchange_type in (
            PointsExchangeType.SUBSCRIPTION_DAYS,
            PointsExchangeType.TRAFFIC,
        )
        has_plan_for_gift = (
            bool(gift_plans) if exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION else True
        )
        availability_reason = resolve_availability_reason(
            exchange_enabled=exchange_settings.exchange_enabled,
            type_enabled=type_settings.enabled,
            user_points=user.points,
            min_points=type_settings.min_points,
            points_cost=type_settings.points_cost,
            computed_value=computed_value,
            requires_subscription=requires_subscription,
            has_subscriptions=has_subscriptions,
            has_plan_for_gift=has_plan_for_gift,
        )
        available = (
            exchange_settings.exchange_enabled
            and type_settings.enabled
            and availability_reason is None
        )
        type_options.append(
            service._type_option(
                type=exchange_type,
                enabled=exchange_settings.exchange_enabled and type_settings.enabled,
                available=available,
                availability_reason=availability_reason,
                points_cost=type_settings.points_cost,
                min_points=type_settings.min_points,
                max_points=type_settings.max_points,
                computed_value=computed_value,
                requires_subscription=requires_subscription,
                gift_plan_id=type_settings.gift_plan_id,
                gift_duration_days=type_settings.gift_duration_days,
                max_discount_percent=type_settings.max_discount_percent,
                max_traffic_gb=type_settings.max_traffic_gb,
            )
        )

    return service._options(
        exchange_enabled=exchange_settings.exchange_enabled,
        points_balance=user.points,
        types=type_options,
        gift_plans=gift_plans,
    )


def resolve_availability_reason(
    *,
    exchange_enabled: bool,
    type_enabled: bool,
    user_points: int,
    min_points: int,
    points_cost: int,
    computed_value: int,
    requires_subscription: bool,
    has_subscriptions: bool,
    has_plan_for_gift: bool,
) -> str | None:
    if not exchange_enabled:
        return "EXCHANGE_DISABLED_GLOBAL"
    if not type_enabled:
        return "EXCHANGE_TYPE_DISABLED"
    if user_points < max(min_points, points_cost) or computed_value <= 0:
        return "INSUFFICIENT_POINTS"
    if requires_subscription and not has_subscriptions:
        return "SUBSCRIPTION_REQUIRED"
    if not has_plan_for_gift:
        return "GIFT_PLAN_REQUIRED"
    return None


async def get_exchangeable_subscriptions(
    service: ReferralExchangeService,
    user_telegram_id: int,
) -> list[SubscriptionDto]:
    subscriptions = await service.subscription_service.get_all_by_user(user_telegram_id)
    return [
        subscription
        for subscription in subscriptions
        if subscription.status
        in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.LIMITED,
        )
        and not subscription.is_unlimited
    ]


async def get_active_gift_plans(
    service: ReferralExchangeService,
) -> list[ReferralGiftPlanOption]:
    plans = await service.plan_service.get_all()
    return [
        service._gift_plan_option(plan_id=plan.id, plan_name=plan.name)
        for plan in plans
        if plan.id is not None and plan.is_active
    ]
