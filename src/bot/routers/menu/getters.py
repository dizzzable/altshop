from typing import Any
from uuid import UUID

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.enums import PointsExchangeType, ReferralRewardType, SubscriptionStatus
from src.core.utils.formatters import (
    format_username_to_url,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.partner import PartnerService
from src.services.plan import PlanService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    plan = await plan_service.get_trial_plan()
    has_used_trial = await subscription_service.has_used_trial(user)
    support_username = config.bot.support_username.get_secret_value()
    ref_link = await referral_service.get_ref_link(user.referral_code)
    support_link = format_username_to_url(support_username, i18n.get("contact-support-help"))

    # Get subscriptions count
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [s for s in all_subscriptions if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMITED, SubscriptionStatus.EXPIRED)]
    subscriptions_count = len(active_subscriptions)
    
    # Count subscriptions with device_type for btn-menu-devices
    # Показываем кнопку "Мои устройства" если есть подписки с указанным типом устройства
    subscriptions_with_device_type = [
        s for s in all_subscriptions
        if s.status != SubscriptionStatus.DELETED and s.device_type is not None
    ]
    devices_count = len(subscriptions_with_device_type)
    
    # Показываем кнопку если есть хотя бы одна подписка (даже без device_type)
    has_any_subscription = len([s for s in all_subscriptions if s.status != SubscriptionStatus.DELETED]) > 0

    # Получаем настройки реферальной системы для проверки типа награды
    referral_settings = await settings_service.get_referral_settings()
    is_points_reward = referral_settings.reward.is_points

    # Проверяем, является ли пользователь партнером
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    is_partner = partner is not None and partner.is_active

    base_data = {
        "user_id": str(user.telegram_id),
        "user_name": user.name,
        "personal_discount": user.personal_discount,
        "support": support_link,
        "invite": i18n.get("referral-invite-message", url=ref_link),
        "has_subscription": user.has_subscription,
        "is_app": config.bot.is_mini_app,
        "is_referral_enable": await settings_service.is_referral_enable(),
        "is_points_reward": is_points_reward,
        "subscriptions_count": subscriptions_count,
        "count": devices_count,  # For btn-menu-devices
        "is_partner": is_partner,
    }

    subscription = user.current_subscription

    if not subscription:
        base_data.update(
            {
                "status": None,
                "is_trial": False,
                "trial_available": not has_used_trial and plan,
                "has_device_limit": has_any_subscription,  # Показываем кнопку если есть подписки
                "connectable": False,
            }
        )
        return base_data

    base_data.update(
        {
            "status": subscription.status,
            "type": subscription.get_subscription_type,
            "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
            "device_limit": i18n_format_device_limit(subscription.device_limit),
            "expire_time": i18n_format_expire_time(subscription.expire_at),
            "is_trial": subscription.is_trial,
            "has_device_limit": has_any_subscription,  # Показываем кнопку если есть подписки
            "connectable": subscription.is_active,
            "url": config.bot.mini_app_url or subscription.url,
        }
    )

    return base_data


@inject
async def connect_device_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Получает список подписок пользователя для выбора устройства при подключении.
    Показывает только активные подписки (ACTIVE, LIMITED).
    """
    from src.core.enums import DeviceType
    
    # Get all subscriptions for user
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    
    # Filter only connectable subscriptions (ACTIVE or LIMITED)
    connectable_subscriptions = [
        s for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMITED)
    ]
    
    # Device type emoji mapping
    device_emojis = {
        DeviceType.ANDROID: "📱",
        DeviceType.IPHONE: "🍏",
        DeviceType.WINDOWS: "🖥",
        DeviceType.MAC: "💻",
    }
    
    # Device type name mapping
    device_names = {
        DeviceType.ANDROID: "Android",
        DeviceType.IPHONE: "iPhone",
        DeviceType.WINDOWS: "Windows",
        DeviceType.MAC: "Mac",
    }
    
    formatted_subscriptions = []
    for sub in connectable_subscriptions:
        device_type = sub.device_type
        if device_type:
            emoji = device_emojis.get(device_type, "📦")
            device_name = device_names.get(device_type, device_type.value)
        else:
            emoji = "📦"
            device_name = sub.plan.name if sub.plan else "Подписка"
        
        # Status indicator
        status_emoji = "🟢" if sub.status == SubscriptionStatus.ACTIVE else "🟡"
        
        formatted_subscriptions.append({
            "id": sub.id,
            "display_name": f"{status_emoji} {emoji} {device_name} - {sub.plan.name if sub.plan else '—'}",
            "url": sub.url,
            "device_type": device_type.value if device_type else None,
            "plan_name": sub.plan.name if sub.plan else "—",
        })
    
    return {
        "subscriptions": formatted_subscriptions,
        "subscriptions_empty": len(formatted_subscriptions) == 0,
    }


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Показывает устройства, на которые были приобретены подписки.
    Отображает тип устройства (device_type) из подписки, а не активированные устройства.
    """
    from src.core.enums import DeviceType
    
    # Get all active subscriptions
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions
        if s.status != SubscriptionStatus.DELETED
    ]

    # Device type emoji mapping
    device_emojis = {
        DeviceType.ANDROID: "📱",
        DeviceType.IPHONE: "📱",
        DeviceType.WINDOWS: "💻",
        DeviceType.MAC: "🖥️",
    }
    
    # Device type name mapping
    device_names = {
        DeviceType.ANDROID: "Android",
        DeviceType.IPHONE: "iPhone",
        DeviceType.WINDOWS: "Windows",
        DeviceType.MAC: "Mac",
    }

    formatted_devices = []
    for sub in active_subscriptions:
        # Формируем информацию о подписке с типом устройства
        device_type = sub.device_type
        if device_type:
            emoji = device_emojis.get(device_type, "📦")
            device_name = device_names.get(device_type, device_type.value)
        else:
            emoji = "📦"
            device_name = sub.plan.name if sub.plan else "Подписка"
        
        formatted_devices.append({
            "id": sub.id,
            "device_type": device_type.value if device_type else None,
            "device_name": f"{emoji} {device_name}",
            "plan_name": sub.plan.name if sub.plan else "—",
            "subscription_url": sub.url,
            "status": sub.status.value,
            "is_active": sub.is_active,
        })

    return {
        "devices": formatted_devices,
        "devices_empty": len(formatted_devices) == 0,
        "subscriptions_count": len(active_subscriptions),
    }




@inject
async def invite_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    referrals = await referral_service.get_referral_count(user.telegram_id)
    payments = await referral_service.get_reward_count(user.telegram_id)
    ref_link = await referral_service.get_ref_link(user.referral_code)
    support_username = config.bot.support_username.get_secret_value()
    support_link = format_username_to_url(
        support_username, i18n.get("contact-support-withdraw-points")
    )

    return {
        "reward_type": settings.reward.type,
        "referrals": referrals,
        "payments": payments,
        "points": user.points,
        "is_points_reward": settings.reward.is_points,
        "has_points": True if user.points > 0 else False,
        "referral_link": ref_link,
        "invite": i18n.get("referral-invite-message", url=ref_link),
        "withdraw": support_link,
    }


@inject
async def invite_about_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    reward_config = settings.reward.config

    max_level = settings.level.value
    identical_reward = settings.reward.is_identical

    reward_levels: dict[str, str] = {}
    for lvl, val in reward_config.items():
        if lvl.value <= max_level:
            reward_levels[f"reward_level_{lvl.value}"] = i18n.get(
                "msg-invite-reward",
                value=val,
                reward_strategy_type=settings.reward.strategy,
                reward_type=settings.reward.type,
            )

    return {
        **reward_levels,
        "reward_type": settings.reward.type,
        "reward_strategy_type": settings.reward.strategy,
        "accrual_strategy": settings.accrual_strategy,
        "identical_reward": identical_reward,
        "max_level": max_level,
    }


@inject
async def connect_device_url_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для окна с URL выбранного устройства.
    """
    subscription_url = dialog_manager.dialog_data.get("selected_subscription_url", "")
    plan_name = dialog_manager.dialog_data.get("selected_subscription_plan_name", "Подписка")
    
    return {
        "url": subscription_url,
        "plan_name": plan_name,
        "is_app": config.bot.is_mini_app,
        "connectable": True,
    }


@inject
async def exchange_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для экрана обмена - показывает баллы и доступные типы обмена.
    """
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    referrals = await referral_service.get_referral_count(user.telegram_id)
    payments = await referral_service.get_reward_count(user.telegram_id)
    
    # Получаем подписки для проверки наличия
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]
    
    points = user.points
    # Рассчитываем дни по курсу обмена
    days_available = exchange_settings.calculate_days(points)
    
    # Для типа награды EXTRA_DAYS - показываем накопленные дни (баллы = дни)
    # Для типа награды POINTS - показываем баллы и конвертированные дни
    extra_days = points  # При EXTRA_DAYS баллы = дни
    
    # Получаем включенные типы обмена
    enabled_types = exchange_settings.get_enabled_types()
    has_multiple_types = len(enabled_types) > 1
    
    # Проверяем доступность каждого типа обмена
    subscription_days_available = (
        exchange_settings.is_type_enabled(PointsExchangeType.SUBSCRIPTION_DAYS) and
        points >= exchange_settings.subscription_days.min_points and
        len(active_subscriptions) > 0
    )
    
    gift_subscription_available = (
        exchange_settings.is_type_enabled(PointsExchangeType.GIFT_SUBSCRIPTION) and
        points >= exchange_settings.gift_subscription.min_points and
        exchange_settings.gift_subscription.gift_plan_id is not None
    )
    
    discount_available = (
        exchange_settings.is_type_enabled(PointsExchangeType.DISCOUNT) and
        points >= exchange_settings.discount.min_points
    )
    
    traffic_available = (
        exchange_settings.is_type_enabled(PointsExchangeType.TRAFFIC) and
        points >= exchange_settings.traffic.min_points and
        len(active_subscriptions) > 0
    )
    
    # Рассчитываем значения для каждого типа
    discount_percent = exchange_settings.calculate_discount(points)
    traffic_gb = exchange_settings.calculate_traffic_gb(points)
    
    # Получаем информацию о плане для подарочной подписки
    gift_plan_name = None
    if exchange_settings.gift_subscription.gift_plan_id:
        plan = await plan_service.get(exchange_settings.gift_subscription.gift_plan_id)
        if plan:
            gift_plan_name = plan.name
    
    return {
        "points": points,
        "days_available": days_available,
        "extra_days": extra_days,
        "points_per_day": exchange_settings.subscription_days.points_cost,
        "exchange_enabled": exchange_settings.exchange_enabled,
        "referrals": referrals,
        "payments": payments,
        "has_points": points >= exchange_settings.subscription_days.min_points,
        "has_subscriptions": len(active_subscriptions) > 0,
        "reward_type": settings.reward.type,
        # Новые поля для типов обмена
        "has_multiple_types": has_multiple_types,
        "enabled_types_count": len(enabled_types),
        "subscription_days_available": subscription_days_available,
        "gift_subscription_available": gift_subscription_available,
        "discount_available": discount_available,
        "traffic_available": traffic_available,
        "discount_percent": discount_percent,
        "traffic_gb": traffic_gb,
        "gift_plan_name": gift_plan_name,
        "gift_duration_days": exchange_settings.gift_subscription.gift_duration_days,
        # Стоимости
        "subscription_days_cost": exchange_settings.subscription_days.points_cost,
        "gift_subscription_cost": exchange_settings.gift_subscription.points_cost,
        "discount_cost": exchange_settings.discount.points_cost,
        "traffic_cost": exchange_settings.traffic.points_cost,
    }


@inject
async def exchange_select_type_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для выбора типа обмена баллов.
    """
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    points = user.points
    
    # Получаем подписки
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]
    has_subscriptions = len(active_subscriptions) > 0
    
    # Формируем список доступных типов обмена
    exchange_types = []
    
    if exchange_settings.subscription_days.enabled:
        days = exchange_settings.calculate_days(points)
        available = points >= exchange_settings.subscription_days.min_points and has_subscriptions
        exchange_types.append({
            "type": PointsExchangeType.SUBSCRIPTION_DAYS,
            "available": available,
            "value": days,
            "cost": exchange_settings.subscription_days.points_cost,
            "description": i18n.get("exchange-type-days-value", days=days),
        })
    
    if exchange_settings.gift_subscription.enabled:
        available = (
            points >= exchange_settings.gift_subscription.min_points and
            exchange_settings.gift_subscription.gift_plan_id is not None
        )
        plan_name = None
        if exchange_settings.gift_subscription.gift_plan_id:
            plan = await plan_service.get(exchange_settings.gift_subscription.gift_plan_id)
            if plan:
                plan_name = plan.name
        exchange_types.append({
            "type": PointsExchangeType.GIFT_SUBSCRIPTION,
            "available": available,
            "value": exchange_settings.gift_subscription.gift_duration_days,
            "cost": exchange_settings.gift_subscription.points_cost,
            "plan_name": plan_name,
            "description": i18n.get(
                "exchange-type-gift-value",
                plan_name=plan_name or "—",
                days=exchange_settings.gift_subscription.gift_duration_days,
            ),
        })
    
    if exchange_settings.discount.enabled:
        discount = exchange_settings.calculate_discount(points)
        available = points >= exchange_settings.discount.min_points
        exchange_types.append({
            "type": PointsExchangeType.DISCOUNT,
            "available": available,
            "value": discount,
            "cost": exchange_settings.discount.points_cost,
            "description": i18n.get("exchange-type-discount-value", percent=discount),
        })
    
    if exchange_settings.traffic.enabled:
        traffic = exchange_settings.calculate_traffic_gb(points)
        available = points >= exchange_settings.traffic.min_points and has_subscriptions
        exchange_types.append({
            "type": PointsExchangeType.TRAFFIC,
            "available": available,
            "value": traffic,
            "cost": exchange_settings.traffic.points_cost,
            "description": i18n.get("exchange-type-traffic-value", gb=traffic),
        })
    
    return {
        "points": points,
        "exchange_types": exchange_types,
        "has_available_types": any(t["available"] for t in exchange_types),
    }


@inject
async def exchange_gift_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для обмена на подарочную подписку.
    """
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    gift_settings = exchange_settings.gift_subscription
    
    points = user.points
    
    # Получаем информацию о плане
    plan_name = None
    if gift_settings.gift_plan_id:
        plan = await plan_service.get(gift_settings.gift_plan_id)
        if plan:
            plan_name = plan.name
    
    return {
        "points": points,
        "cost": gift_settings.points_cost,
        "plan_name": plan_name or "—",
        "duration_days": gift_settings.gift_duration_days,
        "can_exchange": points >= gift_settings.min_points,
    }


@inject
async def exchange_gift_select_plan_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для выбора плана при обмене на подарочную подписку.
    Показывает список доступных планов для выбора.
    """
    settings = await settings_service.get_referral_settings()
    gift_settings = settings.points_exchange.gift_subscription
    
    # Получаем все активные планы
    all_plans = await plan_service.get_all()
    active_plans = [p for p in all_plans if p.is_active and p.id is not None]
    
    formatted_plans = []
    for plan in active_plans:
        # Получаем длительности плана
        durations = plan.durations if plan.durations else []
        duration_str = ", ".join([f"{d.days}д" for d in durations[:3]]) if durations else "—"
        
        formatted_plans.append({
            "id": plan.id,
            "name": plan.name,
            "display_name": f"📦 {plan.name}",
            "durations": duration_str,
        })
    
    return {
        "points": user.points,
        "cost": gift_settings.points_cost,
        "plans": formatted_plans,
        "has_plans": len(formatted_plans) > 0,
        "can_exchange": user.points >= gift_settings.min_points,
    }


@inject
async def exchange_gift_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для подтверждения обмена на подарочную подписку.
    """
    settings = await settings_service.get_referral_settings()
    gift_settings = settings.points_exchange.gift_subscription
    
    selected_plan_id = dialog_manager.dialog_data.get("gift_selected_plan_id")
    selected_duration = dialog_manager.dialog_data.get("gift_selected_duration", gift_settings.gift_duration_days)
    
    plan_name = "—"
    if selected_plan_id:
        plan = await plan_service.get(selected_plan_id)
        if plan:
            plan_name = plan.name
    
    return {
        "points": user.points,
        "cost": gift_settings.points_cost,
        "plan_name": plan_name,
        "duration_days": selected_duration,
        "can_exchange": user.points >= gift_settings.min_points and selected_plan_id is not None,
    }


@inject
async def exchange_gift_success_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для успешного обмена на подарочную подписку - показывает промокод.
    """
    promocode = dialog_manager.dialog_data.get("gift_promocode", "")
    plan_name = dialog_manager.dialog_data.get("gift_plan_name", "")
    duration_days = dialog_manager.dialog_data.get("gift_duration_days", 0)
    
    return {
        "promocode": promocode,
        "plan_name": plan_name,
        "duration_days": duration_days,
    }


@inject
async def exchange_discount_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для обмена на скидку.
    """
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    discount_settings = exchange_settings.discount
    
    points = user.points
    discount_percent = exchange_settings.calculate_discount(points)
    
    # Рассчитываем сколько баллов будет потрачено
    points_to_spend = discount_percent * discount_settings.points_cost
    
    return {
        "points": points,
        "cost_per_percent": discount_settings.points_cost,
        "discount_percent": discount_percent,
        "points_to_spend": points_to_spend,
        "max_discount": discount_settings.max_discount_percent,
        "can_exchange": points >= discount_settings.min_points,
    }


@inject
async def exchange_traffic_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для обмена на трафик - выбор подписки.
    """
    from src.core.enums import DeviceType
    
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    traffic_settings = exchange_settings.traffic
    
    points = user.points
    traffic_gb = exchange_settings.calculate_traffic_gb(points)
    
    # Получаем подписки с лимитом трафика
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
        and s.traffic_limit is not None
    ]
    
    # Device type emoji mapping
    device_emojis = {
        DeviceType.ANDROID: "📱",
        DeviceType.IPHONE: "🍏",
        DeviceType.WINDOWS: "🖥",
        DeviceType.MAC: "💻",
    }
    
    formatted_subscriptions = []
    for sub in active_subscriptions:
        device_type = sub.device_type
        if device_type:
            emoji = device_emojis.get(device_type, "📦")
        else:
            emoji = "📦"
        
        formatted_subscriptions.append({
            "id": sub.id,
            "display_name": f"{emoji} {sub.plan.name if sub.plan else 'Подписка'}",
            "traffic_limit": sub.traffic_limit,
            "status": sub.status.value,
        })
    
    return {
        "points": points,
        "cost_per_gb": traffic_settings.points_cost,
        "traffic_gb": traffic_gb,
        "max_traffic": traffic_settings.max_traffic_gb,
        "subscriptions": formatted_subscriptions,
        "has_subscriptions": len(formatted_subscriptions) > 0,
        "can_exchange": points >= traffic_settings.min_points,
    }


@inject
async def exchange_traffic_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для подтверждения обмена на трафик.
    """
    from src.core.enums import DeviceType
    
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    traffic_settings = exchange_settings.traffic
    
    subscription_id = dialog_manager.dialog_data.get("traffic_subscription_id")
    
    if not subscription_id:
        return {"error": True}
    
    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        return {"error": True}
    
    points = user.points
    traffic_gb = exchange_settings.calculate_traffic_gb(points)
    points_to_spend = traffic_gb * traffic_settings.points_cost
    
    # Device type emoji mapping
    device_emojis = {
        DeviceType.ANDROID: "📱",
        DeviceType.IPHONE: "🍏",
        DeviceType.WINDOWS: "🖥",
        DeviceType.MAC: "💻",
    }
    
    device_type = subscription.device_type
    if device_type:
        emoji = device_emojis.get(device_type, "📦")
    else:
        emoji = "📦"
    
    return {
        "points": points,
        "points_to_spend": points_to_spend,
        "traffic_gb": traffic_gb,
        "subscription_name": f"{emoji} {subscription.plan.name if subscription.plan else 'Подписка'}",
        "current_traffic_limit": subscription.traffic_limit,
    }


@inject
async def exchange_points_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для окна обмена баллов на дни подписки.
    Показывает список подписок, на которые можно добавить дни.
    """
    from src.core.enums import DeviceType
    
    # Получаем настройки обмена
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    
    # Получаем все активные подписки пользователя
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]
    
    # Device type emoji mapping
    device_emojis = {
        DeviceType.ANDROID: "📱",
        DeviceType.IPHONE: "🍏",
        DeviceType.WINDOWS: "🖥",
        DeviceType.MAC: "💻",
    }
    
    formatted_subscriptions = []
    for sub in active_subscriptions:
        expire_parts = i18n_format_expire_time(sub.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
        
        device_type = sub.device_type
        if device_type:
            emoji = device_emojis.get(device_type, "📦")
        else:
            emoji = "📦"
        
        formatted_subscriptions.append({
            "id": sub.id,
            "display_name": f"{emoji} {sub.plan.name if sub.plan else 'Подписка'}",
            "expire_time": expire_time_str,
            "status": sub.status.value,
        })
    
    # Рассчитываем сколько дней можно получить по курсу обмена
    points = user.points
    days_available = exchange_settings.calculate_days(points)
    
    return {
        "points": points,
        "days_available": days_available,
        "points_per_day": exchange_settings.points_per_day,
        "subscriptions": formatted_subscriptions,
        "has_subscriptions": len(formatted_subscriptions) > 0,
    }


@inject
async def exchange_points_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для окна подтверждения обмена баллов.
    """
    from src.core.enums import DeviceType
    
    # Получаем настройки обмена
    settings = await settings_service.get_referral_settings()
    exchange_settings = settings.points_exchange
    
    subscription_id = dialog_manager.dialog_data.get("exchange_subscription_id")
    
    if not subscription_id:
        return {
            "points": 0,
            "days_to_add": 0,
            "points_per_day": exchange_settings.points_per_day,
            "subscription_name": "—",
            "expire_time": "—",
        }
    
    subscription = await subscription_service.get(subscription_id)
    
    if not subscription:
        return {
            "points": 0,
            "days_to_add": 0,
            "points_per_day": exchange_settings.points_per_day,
            "subscription_name": "—",
            "expire_time": "—",
        }
    
    # Device type emoji mapping
    device_emojis = {
        DeviceType.ANDROID: "📱",
        DeviceType.IPHONE: "🍏",
        DeviceType.WINDOWS: "🖥",
        DeviceType.MAC: "💻",
    }
    
    device_type = subscription.device_type
    if device_type:
        emoji = device_emojis.get(device_type, "📦")
    else:
        emoji = "📦"
    
    expire_parts = i18n_format_expire_time(subscription.expire_at)
    expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
    
    points = user.points
    
    # Применяем максимальный лимит, если установлен
    points_to_exchange = points
    if exchange_settings.max_exchange_points > 0:
        points_to_exchange = min(points_to_exchange, exchange_settings.max_exchange_points)
    
    # Рассчитываем дни по курсу обмена
    days_to_add = exchange_settings.calculate_days(points_to_exchange)
    # Пересчитываем фактическое количество баллов (кратное курсу)
    points_to_exchange = exchange_settings.calculate_points_needed(days_to_add)
    
    return {
        "points": points_to_exchange,
        "days_to_add": days_to_add,
        "points_per_day": exchange_settings.points_per_day,
        "subscription_name": f"{emoji} {subscription.plan.name if subscription.plan else 'Подписка'}",
        "expire_time": expire_time_str,
    }
