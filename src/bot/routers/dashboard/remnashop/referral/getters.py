from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.enums import (
    PointsExchangeType,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from src.services.plan import PlanService
from src.services.settings import SettingsService


@inject
async def referral_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    
    # Get eligible plans info
    eligible_plan_ids = settings.eligible_plan_ids
    eligible_plans_count = len(eligible_plan_ids)
    
    # Get plan names for display
    eligible_plan_names = []
    if eligible_plan_ids:
        all_plans = await plan_service.get_all()
        for plan in all_plans:
            if plan.id in eligible_plan_ids:
                eligible_plan_names.append(plan.name)

    return {
        "is_enable": settings.enable,
        "referral_level": settings.level,
        "reward_type": settings.reward.type,
        "accrual_strategy_type": settings.accrual_strategy,
        "reward_strategy_type": settings.reward.strategy,
        "has_plan_filter": settings.has_plan_filter,
        "eligible_plans_count": eligible_plans_count,
        "eligible_plan_names": ", ".join(eligible_plan_names) if eligible_plan_names else None,
    }


async def level_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"levels": list(ReferralLevel)}


async def reward_type_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"rewards": list(ReferralRewardType)}


async def accrual_strategy_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"strategys": list(ReferralAccrualStrategy)}


async def reward_strategy_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    return {"strategys": list(ReferralRewardStrategy)}


@inject
async def eligible_plans_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    all_plans = await plan_service.get_all()
    settings = await settings_service.get_referral_settings()
    eligible_plan_ids = settings.eligible_plan_ids

    plans_data = [
        {
            "id": plan.id,
            "name": plan.name,
            "is_active": plan.is_active,
            "selected": plan.id in eligible_plan_ids,
        }
        for plan in all_plans
        if plan.id is not None
    ]

    return {
        "plans": plans_data,
        "has_filter": settings.has_plan_filter,
        "eligible_count": len(eligible_plan_ids),
    }


@inject
async def reward_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    reward_config = settings.reward.config

    levels_strings = []
    max_level = settings.level.value
    for lvl, val in reward_config.items():
        if lvl.value <= max_level:
            levels_strings.append(
                i18n.get(
                    "msg-referral-reward-level",
                    level=lvl.value,
                    value=val,
                    reward_type=settings.reward.type,
                    reward_strategy_type=settings.reward.strategy,
                )
            )

    reward_string = "\n".join(levels_strings)

    return {
        "reward": reward_string,
        "reward_type": settings.reward.type,
        "reward_strategy_type": settings.reward.strategy,
    }


@inject
async def points_exchange_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настроек обмена баллов."""
    settings = await settings_service.get_referral_settings()
    exchange = settings.points_exchange

    # Подсчитываем количество включенных типов обмена
    enabled_types = exchange.get_enabled_types()
    enabled_count = len(enabled_types)

    return {
        "exchange_enabled": exchange.exchange_enabled,
        "points_per_day": exchange.subscription_days.points_cost,
        "min_exchange_points": exchange.subscription_days.min_points,
        "max_exchange_points": exchange.subscription_days.max_points,
        "has_max_limit": exchange.subscription_days.max_points > 0,
        # Новые поля для типов обмена
        "enabled_types_count": enabled_count,
        "subscription_days_enabled": exchange.subscription_days.enabled,
        "gift_subscription_enabled": exchange.gift_subscription.enabled,
        "discount_enabled": exchange.discount.enabled,
        "traffic_enabled": exchange.traffic.enabled,
    }


@inject
async def exchange_types_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для списка типов обмена баллов."""
    settings = await settings_service.get_referral_settings()
    exchange = settings.points_exchange

    # Получаем план для подарочной подписки
    gift_plan_name = None
    if exchange.gift_subscription.gift_plan_id:
        plan = await plan_service.get(exchange.gift_subscription.gift_plan_id)
        if plan:
            gift_plan_name = plan.name

    exchange_types = [
        {
            "type": PointsExchangeType.SUBSCRIPTION_DAYS,
            "enabled": exchange.subscription_days.enabled,
            "cost": exchange.subscription_days.points_cost,
            "description": i18n.get("exchange-type-subscription-days-desc"),
        },
        {
            "type": PointsExchangeType.GIFT_SUBSCRIPTION,
            "enabled": exchange.gift_subscription.enabled,
            "cost": exchange.gift_subscription.points_cost,
            "description": i18n.get(
                "exchange-type-gift-subscription-desc",
                plan_name=gift_plan_name or "не выбран",
                days=exchange.gift_subscription.gift_duration_days,
            ),
        },
        {
            "type": PointsExchangeType.DISCOUNT,
            "enabled": exchange.discount.enabled,
            "cost": exchange.discount.points_cost,
            "description": i18n.get(
                "exchange-type-discount-desc",
                max_percent=exchange.discount.max_discount_percent,
            ),
        },
        {
            "type": PointsExchangeType.TRAFFIC,
            "enabled": exchange.traffic.enabled,
            "cost": exchange.traffic.points_cost,
            "description": i18n.get(
                "exchange-type-traffic-desc",
                max_gb=exchange.traffic.max_traffic_gb,
            ),
        },
    ]

    return {
        "exchange_types": exchange_types,
        "exchange_enabled": exchange.exchange_enabled,
    }


@inject
async def exchange_type_settings_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настроек конкретного типа обмена."""
    settings = await settings_service.get_referral_settings()
    exchange = settings.points_exchange
    
    exchange_type_str = dialog_manager.dialog_data.get("selected_exchange_type")
    if not exchange_type_str:
        return {"error": True}
    
    exchange_type = PointsExchangeType(exchange_type_str)
    type_settings = exchange.get_settings_for_type(exchange_type)
    
    # Дополнительные данные в зависимости от типа
    extra_data = {}
    
    if exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        if type_settings.gift_plan_id:
            plan = await plan_service.get(type_settings.gift_plan_id)
            extra_data["gift_plan_name"] = plan.name if plan else "не выбран"
        else:
            extra_data["gift_plan_name"] = "не выбран"
        extra_data["gift_duration_days"] = type_settings.gift_duration_days
    elif exchange_type == PointsExchangeType.DISCOUNT:
        extra_data["max_discount_percent"] = type_settings.max_discount_percent
    elif exchange_type == PointsExchangeType.TRAFFIC:
        extra_data["max_traffic_gb"] = type_settings.max_traffic_gb

    return {
        "exchange_type": exchange_type,
        "enabled": type_settings.enabled,
        "points_cost": type_settings.points_cost,
        "min_points": type_settings.min_points,
        "max_points": type_settings.max_points,
        "has_max_limit": type_settings.max_points > 0,
        **extra_data,
    }


@inject
async def exchange_gift_plan_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для выбора плана подарочной подписки."""
    all_plans = await plan_service.get_all()
    settings = await settings_service.get_referral_settings()
    current_plan_id = settings.points_exchange.gift_subscription.gift_plan_id

    plans_data = [
        {
            "id": plan.id,
            "name": plan.name,
            "is_active": plan.is_active,
            "selected": plan.id == current_plan_id,
        }
        for plan in all_plans
        if plan.id is not None
    ]

    return {
        "plans": plans_data,
        "current_plan_id": current_plan_id,
    }


@inject
async def points_per_day_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для изменения курса обмена баллов."""
    settings = await settings_service.get_referral_settings()
    exchange = settings.points_exchange

    return {
        "points_per_day": exchange.points_per_day,
    }


@inject
async def min_exchange_points_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для изменения минимального количества баллов."""
    settings = await settings_service.get_referral_settings()
    exchange = settings.points_exchange

    return {
        "min_exchange_points": exchange.min_exchange_points,
    }


@inject
async def max_exchange_points_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для изменения максимального количества баллов."""
    settings = await settings_service.get_referral_settings()
    exchange = settings.points_exchange

    return {
        "max_exchange_points": exchange.max_exchange_points,
        "has_limit": exchange.max_exchange_points > 0,
    }
