from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.constants import MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import DeviceType, PurchaseType, SubscriptionStatus
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import PlanDto, PriceDetailsDto, SubscriptionDto, UserDto
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.pricing import PricingService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    has_active = bool(user.current_subscription and not user.current_subscription.is_trial)
    is_unlimited = user.current_subscription.is_unlimited if user.current_subscription else False
    
    # Get all user subscriptions count
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [s for s in all_subscriptions if s.status not in (SubscriptionStatus.DELETED,)]
    active_count = len(active_subscriptions)
    
    # Check if user can add more subscriptions
    can_add_subscription = active_count < MAX_SUBSCRIPTIONS_PER_USER
    
    return {
        "has_active_subscription": has_active,
        "is_not_unlimited": not is_unlimited,
        "subscriptions_count": active_count,
        "has_subscriptions": active_count > 0,
        "can_add_subscription": can_add_subscription,
    }


@inject
async def my_subscriptions_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    # Filter only relevant subscriptions (not deleted)
    active_subscriptions = [s for s in all_subscriptions if s.status != SubscriptionStatus.DELETED]
    
    formatted_subscriptions = []
    for idx, sub in enumerate(active_subscriptions):
        expire_parts = i18n_format_expire_time(sub.expire_at)
        # i18n_format_expire_time returns a list of tuples, join them
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
        
        # Формируем название устройства для отображения в списке
        device_names = {
            DeviceType.ANDROID: "📱 Android",
            DeviceType.IPHONE: "🍏 iPhone",
            DeviceType.WINDOWS: "🖥 Windows",
            DeviceType.MAC: "💻 Mac",
        }
        device_name = device_names.get(sub.device_type, f"📦 {sub.plan.name}") if sub.device_type else f"📦 {sub.plan.name}"
        
        formatted_subscriptions.append({
            "id": sub.id,
            "index": idx + 1,
            "status": sub.status.value,
            "device_name": device_name,
            "plan_name": sub.plan.name,
            "device_type": sub.device_type.value if sub.device_type else None,
            "expire_time": expire_time_str,
        })
    
    # Save items for use in handlers
    dialog_manager.dialog_data["_subscriptions_items"] = formatted_subscriptions
    
    return {
        "subscriptions": formatted_subscriptions,
        "subscriptions_empty": len(formatted_subscriptions) == 0,
    }


@inject
async def subscription_details_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    subscription_id = dialog_manager.dialog_data.get("selected_subscription_id")
    subscription_index = dialog_manager.dialog_data.get("selected_subscription_index", 1)
    
    if not subscription_id:
        raise ValueError("No subscription selected")
    
    subscription = await subscription_service.get(subscription_id)
    
    if not subscription:
        raise ValueError(f"Subscription {subscription_id} not found")
    
    expire_parts = i18n_format_expire_time(subscription.expire_at)
    expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
    traffic_key, traffic_kw = i18n_format_traffic_limit(subscription.traffic_limit)
    device_key, device_kw = i18n_format_device_limit(subscription.device_limit)
    
    # Форматируем дату оплаты (создания подписки)
    paid_at_str = "—"
    if subscription.created_at:
        paid_at_str = subscription.created_at.strftime("%d.%m.%Y %H:%M")
    
    # Проверяем, можно ли продлить подписку
    can_renew = False
    if subscription.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED):
        plans = await plan_service.get_available_plans(user)
        matched_plan = subscription.find_matching_plan(plans)
        can_renew = matched_plan is not None and not subscription.is_unlimited
    
    return {
        "subscription_index": subscription_index,
        "status": subscription.status.value,
        "plan_name": subscription.plan.name,
        "device_type": subscription.device_type.value if subscription.device_type else 0,
        "traffic_limit": i18n.get(traffic_key, **traffic_kw) if traffic_kw else traffic_key,
        "device_limit": i18n.get(device_key, **device_kw) if device_kw else device_key,
        "expire_time": expire_time_str,
        "paid_at": paid_at_str,
        "url": subscription.url,
        "is_app": config.bot.is_mini_app,
        "connectable": subscription.status == SubscriptionStatus.ACTIVE,
        "can_renew": can_renew,
    }


@inject
async def confirm_delete_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна подтверждения удаления подписки"""
    subscription_id = dialog_manager.dialog_data.get("selected_subscription_id")
    subscription_index = dialog_manager.dialog_data.get("selected_subscription_index", 1)
    
    if not subscription_id:
        raise ValueError("No subscription selected")
    
    subscription = await subscription_service.get(subscription_id)
    
    if not subscription:
        raise ValueError(f"Subscription {subscription_id} not found")
    
    expire_parts = i18n_format_expire_time(subscription.expire_at)
    expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
    
    return {
        "subscription_index": subscription_index,
        "plan_name": subscription.plan.name,
        "expire_time": expire_time_str,
    }


@inject
async def select_subscription_for_renew_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    settings_service: FromDishka[SettingsService],
    pricing_service: FromDishka[PricingService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна выбора подписки при продлении (одиночный или множественный выбор)"""
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    plans = await plan_service.get_available_plans(user)
    currency = await settings_service.get_default_currency()
    
    # Проверяем режим выбора
    single_select_mode = dialog_manager.dialog_data.get("renew_single_select_mode", False)
    
    # Получаем текущий список выбранных подписок
    selected_subscription_ids = dialog_manager.dialog_data.get("selected_subscriptions_for_renew", [])
    
    # Фильтруем подписки, которые можно продлить
    renewable_subscriptions = []
    for sub in all_subscriptions:
        if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED):
            matched_plan = sub.find_matching_plan(plans)
            if matched_plan and not sub.is_unlimited:
                expire_parts = i18n_format_expire_time(sub.expire_at)
                expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
                
                # Формируем название с типом устройства
                device_emoji = ""
                if sub.device_type:
                    device_emojis = {
                        DeviceType.ANDROID: "📱",
                        DeviceType.IPHONE: "🍏",
                        DeviceType.WINDOWS: "🖥",
                        DeviceType.MAC: "💻",
                    }
                    device_emoji = device_emojis.get(sub.device_type, "")
                
                # Проверяем, выбрана ли подписка
                is_selected = sub.id in selected_subscription_ids
                
                renewable_subscriptions.append({
                    "id": sub.id,
                    "status": sub.status.value,
                    "plan_name": f"{device_emoji} {sub.plan.name}" if device_emoji else sub.plan.name,
                    "device_type": sub.device_type.value if sub.device_type else None,
                    "expire_time": expire_time_str,
                    "is_selected": is_selected,
                    "plan_id": matched_plan.id,
                })
    
    # Сохраняем для использования в обработчиках
    dialog_manager.dialog_data["_renewable_subscriptions"] = renewable_subscriptions
    
    # Считаем количество выбранных подписок
    selected_count = len(selected_subscription_ids)
    
    return {
        "subscriptions": renewable_subscriptions,
        "subscriptions_count": len(renewable_subscriptions),
        "has_single_subscription": len(renewable_subscriptions) == 1,
        "selected_count": selected_count,
        "has_selection": selected_count > 0,
        "currency": currency.symbol,
        "single_select_mode": single_select_mode,
    }


@inject
async def confirm_renew_selection_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    settings_service: FromDishka[SettingsService],
    pricing_service: FromDishka[PricingService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна подтверждения выбранных подписок для продления"""
    selected_subscription_ids = dialog_manager.dialog_data.get("selected_subscriptions_for_renew", [])
    selected_duration = dialog_manager.dialog_data.get("selected_duration", 30)  # default 30 days
    plans = await plan_service.get_available_plans(user)
    currency = await settings_service.get_default_currency()
    
    # Собираем информацию о выбранных подписках
    selected_subscriptions_info = []
    total_original_price = 0
    
    for sub_id in selected_subscription_ids:
        subscription = await subscription_service.get(sub_id)
        if subscription:
            matched_plan = subscription.find_matching_plan(plans)
            if matched_plan:
                duration = matched_plan.get_duration(selected_duration)
                if duration:
                    # Рассчитываем цену для этой подписки
                    original_price = duration.get_price(currency)
                    total_original_price += original_price
                    
                    expire_parts = i18n_format_expire_time(subscription.expire_at)
                    expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
                    
                    # Формируем название с типом устройства
                    device_emoji = ""
                    if subscription.device_type:
                        device_emojis = {
                            DeviceType.ANDROID: "📱",
                            DeviceType.IPHONE: "🍏",
                            DeviceType.WINDOWS: "🖥",
                            DeviceType.MAC: "💻",
                        }
                        device_emoji = device_emojis.get(subscription.device_type, "")
                    
                    selected_subscriptions_info.append({
                        "id": subscription.id,
                        "plan_name": f"{device_emoji} {matched_plan.name}" if device_emoji else matched_plan.name,
                        "expire_time": expire_time_str,
                        "plan_id": matched_plan.id,
                        "price": original_price,
                    })
    
    # Рассчитываем итоговую цену со скидками
    pricing = pricing_service.calculate(user, total_original_price, currency)
    
    return {
        "selected_subscriptions": selected_subscriptions_info,
        "selected_count": len(selected_subscriptions_info),
        "total_original_price": total_original_price,
        "final_amount": pricing.final_amount,
        "discount_percent": pricing.discount_percent,
        "currency": currency.symbol,
        "has_discount": pricing.discount_percent > 0,
    }


@inject
async def device_type_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна выбора типа устройства"""
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)
    
    if not plan:
        raise ValueError("PlanDto not found in dialog data")
    
    subscription_count = plan.subscription_count
    selected_devices = dialog_manager.dialog_data.get("selected_device_types", [])
    current_index = len(selected_devices) + 1
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    
    # Формируем список доступных типов устройств
    device_types = [
        {"type": DeviceType.ANDROID.value, "name": DeviceType.ANDROID.value},
        {"type": DeviceType.IPHONE.value, "name": DeviceType.IPHONE.value},
        {"type": DeviceType.WINDOWS.value, "name": DeviceType.WINDOWS.value},
        {"type": DeviceType.MAC.value, "name": DeviceType.MAC.value},
    ]
    
    return {
        "device_types": device_types,
        "current_index": current_index,
        "total_count": subscription_count,
        "is_multiple": subscription_count > 1,
        "only_single_duration": only_single_duration,
    }


@inject
async def plans_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    plans = await plan_service.get_available_plans(user)

    formatted_plans = [
        {
            "id": plan.id,
            "name": plan.name,
        }
        for plan in plans
    ]

    return {
        "plans": formatted_plans,
    }


@inject
async def duration_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    currency = await settings_service.get_default_currency()
    only_single_plan = dialog_manager.dialog_data.get("only_single_plan", False)
    dialog_manager.dialog_data["is_free"] = False
    durations = []
    
    # Проверяем, есть ли множественное продление с разными планами
    purchase_type = dialog_manager.dialog_data.get("purchase_type")
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    is_multi_renew = (
        purchase_type == PurchaseType.RENEW
        and renew_subscription_ids
        and len(renew_subscription_ids) > 1
    )
    
    # Получаем все планы для расчёта суммарной цены при множественном продлении
    all_plans = None
    subscriptions_with_plans = []
    if is_multi_renew:
        all_plans = await plan_service.get_available_plans(user)
        for sub_id in renew_subscription_ids:
            subscription = await subscription_service.get(sub_id)
            if subscription:
                matched_plan = subscription.find_matching_plan(all_plans)
                if matched_plan:
                    subscriptions_with_plans.append((subscription, matched_plan))

    for duration in plan.durations:
        key, kw = i18n_format_days(duration.days)
        
        if is_multi_renew and subscriptions_with_plans:
            # Суммируем цены всех подписок для этой длительности
            total_price = 0
            for sub, matched_plan in subscriptions_with_plans:
                sub_duration = matched_plan.get_duration(duration.days)
                if sub_duration:
                    total_price += sub_duration.get_price(currency)
            price = pricing_service.calculate(user, total_price, currency)
        else:
            price = pricing_service.calculate(user, duration.get_price(currency), currency)
        
        durations.append(
            {
                "days": duration.days,
                "period": i18n.get(key, **kw),
                "final_amount": price.final_amount,
                "discount_percent": price.discount_percent,
                "original_amount": price.original_amount,
                "currency": currency.symbol,
            }
        )
    
    # Информация о количестве продлеваемых подписок
    renew_count = len(renew_subscription_ids) if renew_subscription_ids else 1

    return {
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": plan.subscription_count,
        "durations": durations,
        "period": 0,
        "final_amount": 0,
        "currency": "",
        "only_single_plan": only_single_plan,
        "is_multi_renew": is_multi_renew,
        "renew_count": renew_count,
    }


@inject
async def payment_method_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    pricing_service: FromDishka[PricingService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    gateways = await payment_gateway_service.filter_active()
    selected_duration = dialog_manager.dialog_data["selected_duration"]
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    purchase_type = dialog_manager.dialog_data.get("purchase_type")
    is_new_purchase = purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL)
    duration = plan.get_duration(selected_duration)
    
    # Проверяем множественное продление
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    is_multi_renew = (
        purchase_type == PurchaseType.RENEW
        and renew_subscription_ids
        and len(renew_subscription_ids) > 1
    )

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    payment_methods = []
    
    if is_multi_renew:
        # Для множественного продления суммируем цены всех подписок
        all_plans = await plan_service.get_available_plans(user)
        
        for gateway in gateways:
            total_price = 0
            for sub_id in renew_subscription_ids:
                subscription = await subscription_service.get(sub_id)
                if subscription:
                    matched_plan = subscription.find_matching_plan(all_plans)
                    if matched_plan:
                        sub_duration = matched_plan.get_duration(selected_duration)
                        if sub_duration:
                            total_price += sub_duration.get_price(gateway.currency)
            
            pricing = pricing_service.calculate(user, total_price, gateway.currency)
            payment_methods.append(
                {
                    "gateway_type": gateway.type,
                    "price": pricing.final_amount,
                    "currency": gateway.currency.symbol,
                }
            )
    else:
        for gateway in gateways:
            payment_methods.append(
                {
                    "gateway_type": gateway.type,
                    "price": duration.get_price(gateway.currency),
                    "currency": gateway.currency.symbol,
                }
            )

    key, kw = i18n_format_days(duration.days)
    renew_count = len(renew_subscription_ids) if renew_subscription_ids else 1

    return {
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": plan.subscription_count,
        "period": i18n.get(key, **kw),
        "payment_methods": payment_methods,
        "final_amount": 0,
        "currency": "",
        "only_single_duration": only_single_duration,
        "is_new_purchase": is_new_purchase,
        "is_multi_renew": is_multi_renew,
        "renew_count": renew_count,
    }


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    selected_duration = dialog_manager.dialog_data["selected_duration"]
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    is_free = dialog_manager.dialog_data.get("is_free", False)
    selected_payment_method = dialog_manager.dialog_data["selected_payment_method"]
    purchase_type = dialog_manager.dialog_data["purchase_type"]
    payment_gateway = await payment_gateway_service.get_by_type(selected_payment_method)
    duration = plan.get_duration(selected_duration)
    
    # Проверяем множественное продление
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    is_multi_renew = (
        purchase_type == PurchaseType.RENEW
        and renew_subscription_ids
        and len(renew_subscription_ids) > 1
    )
    renew_count = len(renew_subscription_ids) if renew_subscription_ids else 1

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    if not payment_gateway:
        raise ValueError(f"Not found PaymentGateway by selected type '{selected_payment_method}'")

    result_url = dialog_manager.dialog_data["payment_url"]
    pricing_data = dialog_manager.dialog_data["final_pricing"]
    pricing = PriceDetailsDto.model_validate_json(pricing_data)

    key, kw = i18n_format_days(duration.days)
    gateways = await payment_gateway_service.filter_active()

    return {
        "purchase_type": purchase_type,
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": plan.subscription_count,
        "period": i18n.get(key, **kw),
        "payment_method": selected_payment_method,
        "final_amount": pricing.final_amount,
        "discount_percent": pricing.discount_percent,
        "original_amount": pricing.original_amount,
        "currency": payment_gateway.currency.symbol,
        "url": result_url,
        "only_single_gateway": len(gateways) == 1,
        "only_single_duration": only_single_duration,
        "is_free": is_free,
        "is_multi_renew": is_multi_renew,
        "renew_count": renew_count,
    }


@inject
async def getter_connect(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    **kwargs: Any,
) -> dict[str, Any]:
    if not user.current_subscription:
        raise ValueError(f"User '{user.telegram_id}' has no active subscription after purchase")

    return {
        "is_app": config.bot.is_mini_app,
        "url": config.bot.mini_app_url or user.current_subscription.url,
        "connectable": True,
    }


@inject
async def success_payment_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    purchase_type: PurchaseType = start_data["purchase_type"]
    subscription = user.current_subscription

    if not subscription:
        raise ValueError(f"User '{user.telegram_id}' has no active subscription after purchase")

    # Get all user subscriptions count for frg-subscription template
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [s for s in all_subscriptions if s.status not in (SubscriptionStatus.DELETED,)]
    subscriptions_count = len(active_subscriptions)

    return {
        "purchase_type": purchase_type,
        "plan_name": subscription.plan.name,
        "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        "added_duration": i18n_format_days(subscription.plan.duration),
        "subscriptions_count": subscriptions_count,
        "is_app": config.bot.is_mini_app,
        "url": config.bot.mini_app_url or subscription.url,
        "connectable": True,
    }


@inject
async def promocode_select_subscription_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна выбора подписки при активации промокода типа SUBSCRIPTION или DURATION"""
    from src.core.enums import PromocodeRewardType
    
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    
    # Фильтруем активные подписки (не удаленные и не безлимитные)
    active_subscriptions = [
        s for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]
    
    # Получаем количество дней и тип промокода
    promocode_days = dialog_manager.dialog_data.get("pending_promocode_days", 30)
    reward_type_str = dialog_manager.dialog_data.get("pending_promocode_reward_type", "")
    
    # Определяем тип промокода для отображения правильного сообщения
    is_duration_promocode = reward_type_str == PromocodeRewardType.DURATION.value
    
    formatted_subscriptions = []
    for idx, sub in enumerate(active_subscriptions):
        expire_parts = i18n_format_expire_time(sub.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
        
        # Формируем название с типом устройства
        device_emoji = ""
        if sub.device_type:
            device_emojis = {
                DeviceType.ANDROID: "📱",
                DeviceType.IPHONE: "🍏",
                DeviceType.WINDOWS: "🖥",
                DeviceType.MAC: "💻",
            }
            device_emoji = device_emojis.get(sub.device_type, "")
        
        # Формируем device_name для отображения в кнопке
        device_names = {
            DeviceType.ANDROID: "📱 Android",
            DeviceType.IPHONE: "🍏 iPhone",
            DeviceType.WINDOWS: "🖥 Windows",
            DeviceType.MAC: "💻 Mac",
        }
        device_name = device_names.get(sub.device_type, f"📦 {sub.plan.name}") if sub.device_type else f"📦 {sub.plan.name}"
        
        formatted_subscriptions.append({
            "id": sub.id,
            "index": idx + 1,
            "status": sub.status.value,
            "device_name": device_name,
            "plan_name": f"{device_emoji} {sub.plan.name}" if device_emoji else sub.plan.name,
            "device_type": sub.device_type.value if sub.device_type else None,
            "expire_time": expire_time_str,
        })
    
    return {
        "subscriptions": formatted_subscriptions,
        "subscriptions_count": len(formatted_subscriptions),
        "promocode_days": promocode_days,
        "is_duration_promocode": is_duration_promocode,
    }


@inject
async def promocode_confirm_new_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна подтверждения создания новой подписки от промокода"""
    plan_name = dialog_manager.dialog_data.get("pending_promocode_plan_name", "Подписка")
    promocode_days = dialog_manager.dialog_data.get("pending_promocode_days", 30)
    
    # Форматируем количество дней
    days_key, days_kw = i18n_format_days(promocode_days)
    days_str = i18n.get(days_key, **days_kw)
    
    return {
        "plan_name": plan_name,
        "promocode_days": promocode_days,
        "days_formatted": days_str,
    }
