from decimal import Decimal
from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.bot.routers.subscription.payment_helpers import (
    collect_renew_ids,
    filter_gateways_for_durations,
    normalize_gateway_type,
    normalize_purchase_type,
    resolve_purchase_durations,
    resolve_subscription_renewable_plan,
)
from src.core.config import AppConfig
from src.core.crypto_assets import get_supported_payment_assets
from src.core.enums import (
    Currency,
    DeviceType,
    PaymentGatewayType,
    PromocodeRewardType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
)
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanDurationDto,
    UserDto,
)
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.pricing import PricingService
from src.services.purchase_gateway_policy import filter_gateways_by_channel
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_purchase import SubscriptionPurchaseService

DEVICE_TYPE_EMOJIS = {
    DeviceType.ANDROID: "📱",
    DeviceType.IPHONE: "🍏",
    DeviceType.WINDOWS: "🖥",
    DeviceType.MAC: "💻",
    DeviceType.OTHER: "🛩️",
}

DEVICE_TYPE_NAMES = {
    DeviceType.ANDROID: "Android",
    DeviceType.IPHONE: "iPhone",
    DeviceType.WINDOWS: "Windows",
    DeviceType.MAC: "Mac",
    DeviceType.OTHER: "Other",
}

BOT_FALLBACK_CURRENCY_ORDER: tuple[Currency, ...] = (
    Currency.USD,
    Currency.RUB,
    Currency.XTR,
)


def _resolve_device_type_meta(device_type: DeviceType | None) -> tuple[str, str]:
    if device_type is None:
        return DEVICE_TYPE_EMOJIS[DeviceType.OTHER], DEVICE_TYPE_NAMES[DeviceType.OTHER]

    return (
        DEVICE_TYPE_EMOJIS.get(device_type, DEVICE_TYPE_EMOJIS[DeviceType.OTHER]),
        DEVICE_TYPE_NAMES.get(device_type, DEVICE_TYPE_NAMES[DeviceType.OTHER]),
    )


def _format_subscription_title(plan_name: str, device_type: DeviceType | None) -> str:
    emoji, device_name = _resolve_device_type_meta(device_type)
    return f"{emoji} {device_name} - {plan_name}"


def _resolve_mini_app_entry_url(config: AppConfig) -> str | None:
    mini_app_url = config.bot.mini_app_url
    if isinstance(mini_app_url, str) and mini_app_url.strip():
        return mini_app_url.rstrip("/")
    return None


def _resolve_available_currency(
    *,
    available_currencies: set[Currency],
    preferred_currency: Currency,
) -> Currency:
    if preferred_currency in available_currencies:
        return preferred_currency

    for fallback_currency in BOT_FALLBACK_CURRENCY_ORDER:
        if fallback_currency in available_currencies:
            return fallback_currency

    if not available_currencies:
        raise ValueError("No prices available for duration")

    return next(iter(available_currencies))


def _resolve_duration_currency(
    duration: PlanDurationDto,
    preferred_currency: Currency,
) -> Currency:
    return _resolve_available_currency(
        available_currencies={price.currency for price in duration.prices},
        preferred_currency=preferred_currency,
    )


def _resolve_common_duration_currency(
    durations: list[PlanDurationDto],
    preferred_currency: Currency,
) -> Currency:
    if not durations:
        return preferred_currency

    common_currencies = {price.currency for price in durations[0].prices}
    for duration in durations[1:]:
        common_currencies &= {price.currency for price in duration.prices}

    if common_currencies:
        return _resolve_available_currency(
            available_currencies=common_currencies,
            preferred_currency=preferred_currency,
        )

    return _resolve_duration_currency(durations[0], preferred_currency)


def _resolve_currency_symbol(currency_code: str) -> str:
    try:
        return Currency(currency_code).symbol
    except ValueError:
        return currency_code


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    has_active = bool(user.current_subscription and not user.current_subscription.is_trial)
    is_unlimited = user.current_subscription.is_unlimited if user.current_subscription else False

    # Get all user subscriptions count
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions if s.status not in (SubscriptionStatus.DELETED,)
    ]
    active_count = len(active_subscriptions)

    # Get max subscriptions for this specific user (respects individual settings)
    max_subscriptions = await settings_service.get_max_subscriptions_for_user(user)

    # Check if user can add more subscriptions
    # -1 means unlimited
    if max_subscriptions == -1:
        can_add_subscription = True
    else:
        can_add_subscription = active_count < max_subscriptions

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
    active_subscriptions = [s for s in all_subscriptions if s.status != SubscriptionStatus.DELETED]

    formatted_subscriptions = []
    for idx, sub in enumerate(active_subscriptions):
        expire_parts = i18n_format_expire_time(sub.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
        plan_name = sub.plan.name if sub.plan else "—"
        device_name = _format_subscription_title(plan_name=plan_name, device_type=sub.device_type)

        formatted_subscriptions.append(
            {
                "id": sub.id,
                "index": idx + 1,
                "status": sub.status.value,
                "device_name": device_name,
                "plan_name": plan_name,
                "device_type": sub.device_type.value if sub.device_type else None,
                "expire_time": expire_time_str,
            }
        )

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
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
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
    if subscription.status in (
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.EXPIRED,
        SubscriptionStatus.LIMITED,
    ):
        action_policy = await subscription_purchase_service.get_action_policy(
            current_user=user,
            subscription=subscription,
        )
        can_renew = action_policy.can_renew and not subscription.is_unlimited
    mini_app_url = _resolve_mini_app_entry_url(config)
    is_app_enabled = config.bot.has_configured_mini_app_url and bool(mini_app_url)

    return {
        "subscription_index": subscription_index,
        "status": subscription.status.value,
        "plan_name": subscription.plan.name,
        "device_type": subscription.device_type.value if subscription.device_type else 0,
        "traffic_limit": i18n.get(traffic_key, **traffic_kw) if traffic_kw else traffic_key,
        "device_limit": i18n.get(device_key, **device_kw) if device_kw else device_key,
        "expire_time": expire_time_str,
        "paid_at": paid_at_str,
        "url": mini_app_url or subscription.url,
        "is_app": is_app_enabled,
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
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter for selecting subscriptions to renew (single or multiple selection)."""
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    currency = await settings_service.get_default_currency()

    single_select_mode = dialog_manager.dialog_data.get("renew_single_select_mode", False)
    selected_subscription_ids = dialog_manager.dialog_data.get(
        "selected_subscriptions_for_renew", []
    )

    renewable_subscriptions = []
    for sub in all_subscriptions:
        if sub.status in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.LIMITED,
        ):
            action_policy = await subscription_purchase_service.get_action_policy(
                current_user=user,
                subscription=sub,
            )
            can_select = (
                action_policy.can_renew if single_select_mode else action_policy.can_multi_renew
            )
            matched_plan = await resolve_subscription_renewable_plan(
                subscription=sub,
                plan_service=plan_service,
            )
            display_plan_name = matched_plan.name if matched_plan else sub.plan.name
            if can_select and not sub.is_unlimited:
                expire_parts = i18n_format_expire_time(sub.expire_at)
                expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
                is_selected = sub.id in selected_subscription_ids

                renewable_subscriptions.append(
                    {
                        "id": sub.id,
                        "status": sub.status.value,
                        "plan_name": _format_subscription_title(
                            plan_name=display_plan_name,
                            device_type=sub.device_type,
                        ),
                        "device_type": sub.device_type.value if sub.device_type else None,
                        "expire_time": expire_time_str,
                        "is_selected": is_selected,
                        "plan_id": matched_plan.id if matched_plan else getattr(sub.plan, "id", 0),
                    }
                )

    dialog_manager.dialog_data["_renewable_subscriptions"] = renewable_subscriptions
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
    """Getter for confirming selected subscriptions for renewal."""
    selected_subscription_ids = dialog_manager.dialog_data.get(
        "selected_subscriptions_for_renew", []
    )
    selected_duration = dialog_manager.dialog_data.get("selected_duration", 30)
    currency = await settings_service.get_default_currency()

    selected_subscription_entries = []
    for sub_id in selected_subscription_ids:
        subscription = await subscription_service.get(sub_id)
        if not subscription:
            continue
        matched_plan = await resolve_subscription_renewable_plan(
            subscription=subscription,
            plan_service=plan_service,
        )
        if not matched_plan:
            continue
        duration = matched_plan.get_duration(selected_duration)
        if duration:
            selected_subscription_entries.append((subscription, matched_plan, duration))

    pricing_currency = _resolve_common_duration_currency(
        [duration for _, _, duration in selected_subscription_entries],
        currency,
    )
    selected_subscriptions_info = []
    total_original_price = Decimal(0)

    for subscription, matched_plan, duration in selected_subscription_entries:
        original_price = duration.get_price(pricing_currency)
        total_original_price += original_price

        expire_parts = i18n_format_expire_time(subscription.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)

        selected_subscriptions_info.append(
            {
                "id": subscription.id,
                "plan_name": _format_subscription_title(
                    plan_name=matched_plan.name,
                    device_type=subscription.device_type,
                ),
                "expire_time": expire_time_str,
                "plan_id": matched_plan.id,
                "price": original_price,
            }
        )

    pricing = pricing_service.calculate(user, total_original_price, pricing_currency)

    return {
        "selected_subscriptions": selected_subscriptions_info,
        "selected_count": len(selected_subscriptions_info),
        "total_original_price": total_original_price,
        "final_amount": pricing.final_amount,
        "discount_percent": pricing.discount_percent,
        "currency": pricing_currency.symbol,
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
        "total_count": 1,
        "is_multiple": False,
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
    allowed_plan_ids = dialog_manager.dialog_data.get("allowed_purchase_plan_ids")
    if isinstance(allowed_plan_ids, list) and allowed_plan_ids:
        allowed_plan_id_set = {int(plan_id) for plan_id in allowed_plan_ids}
        plans = [plan for plan in plans if (plan.id or 0) in allowed_plan_id_set]

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
    purchase_type = normalize_purchase_type(
        cast(PurchaseType | str, dialog_manager.dialog_data.get("purchase_type", PurchaseType.NEW))
    )
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    renew_subscription_id = dialog_manager.dialog_data.get("renew_subscription_id")
    renew_ids = collect_renew_ids(
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
    )
    is_multi_renew = purchase_type == PurchaseType.RENEW and len(renew_ids) > 1
    renew_count = len(renew_ids) if renew_ids else 1

    for duration in plan.durations:
        key, kw = i18n_format_days(duration.days)

        if is_multi_renew:
            selected_durations = await resolve_purchase_durations(
                user=user,
                plan=plan,
                duration_days=duration.days,
                purchase_type=purchase_type,
                renew_subscription_id=renew_subscription_id,
                renew_subscription_ids=renew_subscription_ids,
                subscription_service=subscription_service,
                plan_service=plan_service,
            )
            if len(selected_durations) != renew_count:
                continue
            pricing_currency = _resolve_common_duration_currency(selected_durations, currency)
            total_price = sum(
                (
                    selected_duration.get_price(pricing_currency)
                    for selected_duration in selected_durations
                ),
                Decimal(0),
            )
            price = pricing_service.calculate(user, total_price, pricing_currency)
        else:
            pricing_currency = _resolve_duration_currency(duration, currency)
            price = pricing_service.calculate(
                user,
                duration.get_price(pricing_currency),
                pricing_currency,
            )

        durations.append(
            {
                "days": duration.days,
                "period": i18n.get(key, **kw),
                "final_amount": price.final_amount,
                "discount_percent": price.discount_percent,
                "original_amount": price.original_amount,
                "currency": pricing_currency.symbol,
            }
        )

    return {
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": 1,
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

    gateways = filter_gateways_by_channel(
        await payment_gateway_service.filter_active(),
        channel=PurchaseChannel.TELEGRAM,
    )
    selected_duration = dialog_manager.dialog_data["selected_duration"]
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    purchase_type = normalize_purchase_type(
        cast(PurchaseType | str, dialog_manager.dialog_data.get("purchase_type", PurchaseType.NEW))
    )
    is_new_purchase = purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL)
    duration = plan.get_duration(selected_duration)

    # Проверяем множественное продление
    renew_subscription_id = dialog_manager.dialog_data.get("renew_subscription_id")
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    renew_ids = collect_renew_ids(
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
    )
    is_multi_renew = purchase_type == PurchaseType.RENEW and len(renew_ids) > 1

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    selected_durations = await resolve_purchase_durations(
        user=user,
        plan=plan,
        duration_days=selected_duration,
        purchase_type=purchase_type,
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
        subscription_service=subscription_service,
        plan_service=plan_service,
    )
    gateways = filter_gateways_for_durations(gateways, selected_durations)

    payment_methods = []

    for gateway in gateways:
        # Для множественного продления суммируем цены всех подписок
        if is_multi_renew:
            total_price = sum(
                (
                    selected_duration_item.get_price(gateway.currency)
                    for selected_duration_item in selected_durations
                ),
                Decimal(0),
            )
            pricing = pricing_service.calculate(user, total_price, gateway.currency)
        else:
            pricing = pricing_service.calculate(
                user=user,
                price=duration.get_price(gateway.currency),
                currency=gateway.currency,
            )

        payment_methods.append(
            {
                "gateway_type": gateway.type,
                "price": pricing.final_amount,
                "currency": gateway.currency.symbol,
            }
        )

    key, kw = i18n_format_days(duration.days)
    renew_count = len(renew_ids) if renew_ids else 1

    return {
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": 1,
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
async def payment_asset_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    selected_duration = dialog_manager.dialog_data["selected_duration"]
    selected_payment_method = normalize_gateway_type(
        cast(PaymentGatewayType | str, dialog_manager.dialog_data["selected_payment_method"])
    )
    selected_payment_asset = dialog_manager.dialog_data.get("selected_payment_asset")
    purchase_type = normalize_purchase_type(
        cast(PurchaseType | str, dialog_manager.dialog_data["purchase_type"])
    )
    renew_ids = collect_renew_ids(
        renew_subscription_id=dialog_manager.dialog_data.get("renew_subscription_id"),
        renew_subscription_ids=dialog_manager.dialog_data.get("renew_subscription_ids"),
    )
    duration = plan.get_duration(selected_duration)

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    payment_assets = [
        {
            "asset": asset.value,
            "label": f"{_resolve_currency_symbol(asset.value)} {asset.value}",
        }
        for asset in get_supported_payment_assets(selected_payment_method)
    ]
    key, kw = i18n_format_days(duration.days)

    return {
        "purchase_type": purchase_type,
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": 1,
        "period": i18n.get(key, **kw),
        "payment_method": selected_payment_method,
        "payment_assets": payment_assets,
        "selected_payment_asset": selected_payment_asset or False,
        "gateway_auto_selected": dialog_manager.dialog_data.get(
            "payment_gateway_auto_selected",
            False,
        ),
        "is_new_purchase": purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL),
        "only_single_duration": dialog_manager.dialog_data.get("only_single_duration", False),
        "is_multi_renew": purchase_type == PurchaseType.RENEW and len(renew_ids) > 1,
        "renew_count": len(renew_ids) if renew_ids else 1,
    }


@inject
async def confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    selected_duration = dialog_manager.dialog_data["selected_duration"]
    only_single_duration = dialog_manager.dialog_data.get("only_single_duration", False)
    is_free = dialog_manager.dialog_data.get("is_free", False)
    selected_payment_method = normalize_gateway_type(
        cast(PaymentGatewayType | str, dialog_manager.dialog_data["selected_payment_method"])
    )
    selected_payment_asset = dialog_manager.dialog_data.get("selected_payment_asset")
    purchase_type = normalize_purchase_type(
        cast(PurchaseType | str, dialog_manager.dialog_data["purchase_type"])
    )
    duration = plan.get_duration(selected_duration)

    # Проверяем множественное продление
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    renew_subscription_id = dialog_manager.dialog_data.get("renew_subscription_id")
    renew_ids = collect_renew_ids(
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
    )
    is_multi_renew = purchase_type == PurchaseType.RENEW and len(renew_ids) > 1
    renew_count = len(renew_ids) if renew_ids else 1

    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found in plan '{plan.name}'")

    result_url = dialog_manager.dialog_data["payment_url"]
    quote = cast(dict[str, Any], dialog_manager.dialog_data["final_quote"])

    key, kw = i18n_format_days(duration.days)
    gateways = filter_gateways_by_channel(
        await payment_gateway_service.filter_active(),
        channel=PurchaseChannel.TELEGRAM,
    )
    selected_durations = await resolve_purchase_durations(
        user=user,
        plan=plan,
        duration_days=selected_duration,
        purchase_type=purchase_type,
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
        subscription_service=subscription_service,
        plan_service=plan_service,
    )
    gateways = filter_gateways_for_durations(gateways, selected_durations)
    show_payment_asset_back = len(
        get_supported_payment_assets(selected_payment_method)
    ) > 1 and bool(selected_payment_asset)

    return {
        "purchase_type": purchase_type,
        "plan": plan.name,
        "description": plan.description or False,
        "type": plan.type,
        "devices": i18n_format_device_limit(plan.device_limit),
        "traffic": i18n_format_traffic_limit(plan.traffic_limit),
        "subscription_count": 1,
        "period": i18n.get(key, **kw),
        "payment_method": selected_payment_method,
        "final_amount": quote["price"],
        "discount_percent": quote["discount_percent"],
        "original_amount": quote["original_price"],
        "currency": _resolve_currency_symbol(str(quote["currency"])),
        "url": result_url,
        "only_single_gateway": len(gateways) == 1,
        "only_single_duration": only_single_duration,
        "is_free": is_free,
        "is_multi_renew": is_multi_renew,
        "renew_count": renew_count,
        "show_payment_asset_back": show_payment_asset_back,
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
    mini_app_url = _resolve_mini_app_entry_url(config)
    is_app_enabled = config.bot.has_configured_mini_app_url and bool(mini_app_url)

    return {
        "is_app": is_app_enabled,
        "url": mini_app_url or user.current_subscription.url,
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
    purchase_type = normalize_purchase_type(cast(PurchaseType | str, start_data["purchase_type"]))
    subscription = user.current_subscription

    if not subscription:
        raise ValueError(f"User '{user.telegram_id}' has no active subscription after purchase")

    # Get all user subscriptions count for frg-subscription template
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s for s in all_subscriptions if s.status not in (SubscriptionStatus.DELETED,)
    ]
    subscriptions_count = len(active_subscriptions)
    mini_app_url = _resolve_mini_app_entry_url(config)
    is_app_enabled = config.bot.has_configured_mini_app_url and bool(mini_app_url)

    return {
        "purchase_type": purchase_type,
        "plan_name": subscription.plan.name,
        "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        "added_duration": i18n_format_days(subscription.plan.duration),
        "subscriptions_count": subscriptions_count,
        "is_app": is_app_enabled,
        "url": mini_app_url or subscription.url,
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
    """Getter for selecting a subscription when activating SUBSCRIPTION or DURATION promocodes."""
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)

    active_subscriptions = [
        s
        for s in all_subscriptions
        if s.status
        in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]

    promocode_days = dialog_manager.dialog_data.get("pending_promocode_days", 30)
    reward_type_str = dialog_manager.dialog_data.get("pending_promocode_reward_type", "")
    is_duration_promocode = reward_type_str == PromocodeRewardType.DURATION.value

    formatted_subscriptions = []
    for idx, sub in enumerate(active_subscriptions):
        expire_parts = i18n_format_expire_time(sub.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
        plan_name = sub.plan.name if sub.plan else "—"
        title = _format_subscription_title(plan_name=plan_name, device_type=sub.device_type)

        formatted_subscriptions.append(
            {
                "id": sub.id,
                "index": idx + 1,
                "status": sub.status.value,
                "device_name": title,
                "plan_name": title,
                "device_type": sub.device_type.value if sub.device_type else None,
                "expire_time": expire_time_str,
            }
        )

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
