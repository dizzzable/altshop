import traceback
from decimal import Decimal
from typing import Optional, TypedDict, cast
from uuid import UUID

from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Text
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import AsyncContainer, FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.bot.routers.subscription.payment_helpers import (
    build_payment_cache_key,
    collect_renew_ids,
    filter_gateways_for_durations,
    normalize_gateway_type,
    normalize_purchase_type,
    resolve_purchase_durations,
    resolve_subscription_renewable_plan,
    select_auto_gateway,
)
from src.bot.states import Subscription
from src.core.constants import PURCHASE_PREFIX, USER_KEY
from src.core.crypto_assets import get_supported_payment_assets
from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    PaymentGatewayType,
    PaymentSource,
    PromocodeRewardType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
)
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PriceDetailsDto,
    PromocodeDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.pricing import PricingService
from src.services.promocode import PromocodeService
from src.services.purchase_gateway_policy import filter_gateways_by_channel
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_purchase import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseService,
)
from src.services.user import UserService

PAYMENT_CACHE_KEY = "payment_cache"
CURRENT_DURATION_KEY = "selected_duration"
CURRENT_METHOD_KEY = "selected_payment_method"
CURRENT_PAYMENT_ASSET_KEY = "selected_payment_asset"
CURRENT_DEVICE_TYPE_KEY = "selected_device_type"
SELECTED_DEVICE_TYPES_KEY = "selected_device_types"
SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY = "selected_subscriptions_for_renew"
PAYMENT_GATEWAY_AUTO_SELECTED_KEY = "payment_gateway_auto_selected"
FINAL_QUOTE_KEY = "final_quote"
ALLOWED_PURCHASE_PLAN_IDS_KEY = "allowed_purchase_plan_ids"

BOT_FALLBACK_CURRENCY_ORDER: tuple[Currency, ...] = (
    Currency.USD,
    Currency.RUB,
    Currency.XTR,
)


class CachedPaymentData(TypedDict):
    payment_id: str
    payment_url: Optional[str]
    final_quote: dict[str, object]


def _serialize_final_quote(quote: object) -> dict[str, object]:
    return {
        "price": cast(object, getattr(quote, "price")),
        "original_price": cast(object, getattr(quote, "original_price")),
        "currency": cast(object, getattr(quote, "currency")),
        "settlement_price": cast(object, getattr(quote, "settlement_price")),
        "settlement_original_price": cast(object, getattr(quote, "settlement_original_price")),
        "settlement_currency": cast(object, getattr(quote, "settlement_currency")),
        "discount_percent": cast(object, getattr(quote, "discount_percent")),
        "discount_source": cast(object, getattr(quote, "discount_source")),
        "payment_asset": cast(object, getattr(quote, "payment_asset")),
        "quote_source": cast(object, getattr(quote, "quote_source")),
        "quote_expires_at": cast(object, getattr(quote, "quote_expires_at")),
        "quote_provider_count": cast(object, getattr(quote, "quote_provider_count")),
    }


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


def _resolve_duration_currency(duration: PlanDurationDto, preferred_currency: Currency) -> Currency:
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


def _load_payment_data(dialog_manager: DialogManager) -> dict[str, CachedPaymentData]:
    if PAYMENT_CACHE_KEY not in dialog_manager.dialog_data:
        dialog_manager.dialog_data[PAYMENT_CACHE_KEY] = {}
    return cast(dict[str, CachedPaymentData], dialog_manager.dialog_data[PAYMENT_CACHE_KEY])


def _save_payment_data(dialog_manager: DialogManager, payment_data: CachedPaymentData) -> None:
    dialog_manager.dialog_data["payment_id"] = payment_data["payment_id"]
    dialog_manager.dialog_data["payment_url"] = payment_data["payment_url"]
    dialog_manager.dialog_data[FINAL_QUOTE_KEY] = payment_data["final_quote"]


def _clear_finalized_payment_state(dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data.pop("payment_id", None)
    dialog_manager.dialog_data.pop("payment_url", None)
    dialog_manager.dialog_data.pop(FINAL_QUOTE_KEY, None)


def _clear_payment_selection_state(
    dialog_manager: DialogManager,
    *,
    clear_cache: bool = False,
) -> None:
    dialog_manager.dialog_data.pop(CURRENT_METHOD_KEY, None)
    dialog_manager.dialog_data.pop(CURRENT_PAYMENT_ASSET_KEY, None)
    dialog_manager.dialog_data.pop(PAYMENT_GATEWAY_AUTO_SELECTED_KEY, None)
    _clear_finalized_payment_state(dialog_manager)
    if clear_cache:
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)


def _clear_allowed_purchase_plan_ids(dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data.pop(ALLOWED_PURCHASE_PLAN_IDS_KEY, None)


def _get_selected_device_types(dialog_manager: DialogManager) -> list[DeviceType] | None:
    selected_devices = cast(
        list[str], dialog_manager.dialog_data.get(SELECTED_DEVICE_TYPES_KEY, [])
    )
    if not selected_devices:
        return None
    return [DeviceType(device_type) for device_type in selected_devices]


def _build_cache_key(
    *,
    dialog_manager: DialogManager,
    plan: PlanDto,
    duration_days: int,
    gateway_type: PaymentGatewayType,
    payment_asset: CryptoAsset | None = None,
    device_types: list[DeviceType] | None = None,
) -> str:
    purchase_type, renew_subscription_id, renew_subscription_ids = _get_purchase_state(
        dialog_manager
    )
    renew_ids = collect_renew_ids(
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
    )
    return build_payment_cache_key(
        plan_id=plan.id,
        duration_days=duration_days,
        gateway_type=gateway_type,
        purchase_type=purchase_type,
        renew_ids=renew_ids,
        payment_asset=payment_asset.value if payment_asset else None,
        device_types=device_types,
    )


async def _notify_user(
    *,
    user: UserDto,
    notification_service: NotificationService,
    i18n_key: str,
    i18n_kwargs: dict[str, object] | None = None,
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key=i18n_key,
            i18n_kwargs=i18n_kwargs,
        ),
    )


def _get_purchase_state(
    dialog_manager: DialogManager,
) -> tuple[PurchaseType, int | None, list[int] | None]:
    renew_subscription_id = cast(
        Optional[int],
        dialog_manager.dialog_data.get("renew_subscription_id"),
    )
    renew_subscription_ids = cast(
        Optional[list[int]],
        dialog_manager.dialog_data.get("renew_subscription_ids"),
    )
    inferred_purchase_type = (
        PurchaseType.RENEW
        if collect_renew_ids(
            renew_subscription_id=renew_subscription_id,
            renew_subscription_ids=renew_subscription_ids,
        )
        else PurchaseType.NEW
    )
    raw_purchase_type = dialog_manager.dialog_data.get("purchase_type")

    try:
        purchase_type = normalize_purchase_type(
            cast(PurchaseType | str, raw_purchase_type or inferred_purchase_type)
        )
    except Exception:
        purchase_type = inferred_purchase_type
        logger.warning(
            "Recovered invalid purchase_type from dialog state. inferred='{}' raw='{}'",
            purchase_type.value,
            raw_purchase_type,
        )
    else:
        if raw_purchase_type is None:
            logger.warning(
                "Recovered missing purchase_type from dialog state. inferred='{}'",
                purchase_type.value,
            )

    dialog_manager.dialog_data["purchase_type"] = purchase_type
    return purchase_type, renew_subscription_id, renew_subscription_ids


async def _get_settings_service(dialog_manager: DialogManager) -> SettingsService:
    container: AsyncContainer = dialog_manager.middleware_data["dishka_container"]
    return await container.get(SettingsService)


async def _ensure_new_purchase_limit(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plan: PlanDto,
    purchase_type: PurchaseType,
    subscription_service: SubscriptionService | None,
    notification_service: NotificationService,
) -> bool:
    if purchase_type != PurchaseType.NEW or not subscription_service:
        return True

    existing_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_count = len(
        [
            subscription
            for subscription in existing_subscriptions
            if subscription.status != SubscriptionStatus.DELETED
        ]
    )
    settings_service = await _get_settings_service(dialog_manager)
    max_subscriptions = await settings_service.get_max_subscriptions_for_user(user)

    if max_subscriptions == -1:
        return True

    requested_subscription_count = 1
    if active_count + requested_subscription_count <= max_subscriptions:
        return True

    logger.warning(
        f"{log(user)} Would exceed max subscriptions limit. "
        f"Current: {active_count}, Requested: {requested_subscription_count}, "
        f"Max: {max_subscriptions}"
    )
    await _notify_user(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-subscription-limit-exceeded",
        i18n_kwargs={
            "current": str(active_count),
            "max": str(max_subscriptions),
        },
    )
    return False


async def _calculate_multi_renew_total_price(
    *,
    user: UserDto,
    renew_subscription_ids: list[int],
    duration_days: int,
    currency: Currency,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
) -> Decimal:
    total_price = Decimal(0)

    for sub_id in renew_subscription_ids:
        subscription = await subscription_service.get(sub_id)
        if not subscription:
            continue

        matched_plan = await resolve_subscription_renewable_plan(
            subscription=subscription,
            plan_service=plan_service,
        )
        if not matched_plan:
            continue

        sub_duration = matched_plan.get_duration(duration_days)
        if sub_duration:
            total_price += sub_duration.get_price(currency)

    return total_price


async def _build_payment_pricing(
    *,
    user: UserDto,
    duration: PlanDurationDto,
    duration_days: int,
    payment_gateway: PaymentGatewayDto,
    purchase_type: PurchaseType,
    renew_subscription_ids: list[int] | None,
    pricing_service: PricingService,
    subscription_service: SubscriptionService | None,
    plan_service: PlanService | None,
) -> PriceDetailsDto:
    should_sum_renewals = (
        purchase_type == PurchaseType.RENEW
        and renew_subscription_ids is not None
        and len(renew_subscription_ids) > 1
        and subscription_service is not None
        and plan_service is not None
    )
    if not should_sum_renewals:
        return pricing_service.calculate(
            user=user,
            price=duration.get_price(payment_gateway.currency),
            currency=payment_gateway.currency,
        )

    total_price = await _calculate_multi_renew_total_price(
        user=user,
        renew_subscription_ids=renew_subscription_ids,
        duration_days=duration_days,
        currency=payment_gateway.currency,
        subscription_service=subscription_service,
        plan_service=plan_service,
    )
    logger.info(
        f"{log(user)} Calculated total price for {len(renew_subscription_ids)} "
        f"subscriptions: {total_price}"
    )
    return pricing_service.calculate(user, total_price, payment_gateway.currency)


async def _handle_payment_creation_failure(
    *,
    user: UserDto,
    exception: Exception,
    notification_service: NotificationService,
) -> None:
    logger.error(f"{log(user)} Failed to create payment: {exception}")
    traceback_str = traceback.format_exc()
    error_type_name = type(exception).__name__
    error_message = Text(str(exception)[:512])

    await send_error_notification_task.kiq(
        error_id=user.telegram_id,
        traceback_str=traceback_str,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-event-error",
            i18n_kwargs={
                "user": True,
                "user_id": str(user.telegram_id),
                "user_name": user.name,
                "username": user.username or False,
                "error": (
                    f"{error_type_name}: Failed to create payment "
                    f"check due to error: {error_message.as_html()}"
                ),
            },
            reply_markup=get_user_keyboard(user.telegram_id),
        ),
    )
    await _notify_user(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-subscription-payment-creation-failed",
    )


def _select_single_renewable_subscription(
    *,
    dialog_manager: DialogManager,
    adapter: DialogDataAdapter,
    subscription: SubscriptionDto,
    matched_plan: PlanDto,
) -> None:
    _clear_allowed_purchase_plan_ids(dialog_manager)
    adapter.save(matched_plan)
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data["only_single_plan"] = True
    dialog_manager.dialog_data["renew_subscription_id"] = subscription.id
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [subscription.id]
    dialog_manager.dialog_data["renew_single_select_mode"] = True
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)


def _prepare_renew_selection(
    dialog_manager: DialogManager,
    *,
    single_select_mode: bool,
) -> None:
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = []
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data["renew_subscription_id"] = None
    _clear_allowed_purchase_plan_ids(dialog_manager)
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
    dialog_manager.dialog_data["renew_single_select_mode"] = single_select_mode


def _save_single_plan(
    dialog_manager: DialogManager,
    adapter: DialogDataAdapter,
    plan: PlanDto,
) -> None:
    _clear_allowed_purchase_plan_ids(dialog_manager)
    adapter.save(plan)
    dialog_manager.dialog_data["only_single_plan"] = True


def _save_single_duration(dialog_manager: DialogManager, duration_days: int) -> None:
    dialog_manager.dialog_data[CURRENT_DURATION_KEY] = duration_days
    dialog_manager.dialog_data["only_single_duration"] = True


async def _get_available_purchase_gateways(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plan: PlanDto,
    duration_days: int,
    payment_gateway_service: PaymentGatewayService,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
) -> list[PaymentGatewayDto]:
    gateways = filter_gateways_by_channel(
        await payment_gateway_service.filter_active(),
        channel=PurchaseChannel.TELEGRAM,
    )
    purchase_type, renew_subscription_id, renew_subscription_ids = _get_purchase_state(
        dialog_manager
    )
    selected_durations = await resolve_purchase_durations(
        user=user,
        plan=plan,
        duration_days=duration_days,
        purchase_type=purchase_type,
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
        subscription_service=subscription_service,
        plan_service=plan_service,
    )
    return filter_gateways_for_durations(gateways, selected_durations)


async def _start_single_subscription_renew_flow(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    subscription: SubscriptionDto,
    plan_service: PlanService,
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
) -> bool:
    subscription_id = subscription.id
    if subscription_id is None:
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-renew-plan-unavailable",
        )
        return False

    try:
        purchase_options = await subscription_purchase_service.get_purchase_options(
            subscription_id=subscription_id,
            purchase_type=PurchaseType.RENEW,
            current_user=user,
            channel=PurchaseChannel.TELEGRAM,
        )
    except SubscriptionPurchaseError:
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-renew-plan-unavailable",
        )
        return False

    if not purchase_options.plans:
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-renew-plan-unavailable",
        )
        return False

    if purchase_options.selection_locked and len(purchase_options.plans) == 1:
        matched_plan = await plan_service.get(purchase_options.plans[0].id)
        if not matched_plan:
            await _notify_user(
                user=user,
                notification_service=notification_service,
                i18n_key="ntf-subscription-renew-plan-unavailable",
            )
            return False

        adapter = DialogDataAdapter(dialog_manager)
        _select_single_renewable_subscription(
            dialog_manager=dialog_manager,
            adapter=adapter,
            subscription=subscription,
            matched_plan=matched_plan,
        )
        await dialog_manager.switch_to(state=Subscription.DURATION)
        return True

    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data["only_single_plan"] = False
    dialog_manager.dialog_data["renew_subscription_id"] = subscription_id
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [subscription_id]
    dialog_manager.dialog_data["renew_single_select_mode"] = True
    dialog_manager.dialog_data[ALLOWED_PURCHASE_PLAN_IDS_KEY] = [
        plan.id for plan in purchase_options.plans
    ]
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
    await dialog_manager.switch_to(state=Subscription.PLANS)
    return True


def _set_selected_gateway(
    dialog_manager: DialogManager,
    *,
    gateway_type: PaymentGatewayType,
    auto_selected: bool,
) -> None:
    dialog_manager.dialog_data[CURRENT_METHOD_KEY] = gateway_type
    dialog_manager.dialog_data[PAYMENT_GATEWAY_AUTO_SELECTED_KEY] = auto_selected


async def _finalize_gateway_selection(
    *,
    dialog_manager: DialogManager,
    plan: PlanDto,
    duration_days: int,
    gateway_type: PaymentGatewayType,
    auto_selected: bool,
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
    subscription_service: SubscriptionService,
    payment_asset: CryptoAsset | None = None,
    device_types: list[DeviceType] | None = None,
) -> bool:
    gateway_type = normalize_gateway_type(gateway_type)
    _set_selected_gateway(
        dialog_manager,
        gateway_type=gateway_type,
        auto_selected=auto_selected,
    )
    if payment_asset is None:
        dialog_manager.dialog_data.pop(CURRENT_PAYMENT_ASSET_KEY, None)
    else:
        dialog_manager.dialog_data[CURRENT_PAYMENT_ASSET_KEY] = payment_asset.value

    cache = _load_payment_data(dialog_manager)
    cache_key = _build_cache_key(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=duration_days,
        gateway_type=gateway_type,
        payment_asset=payment_asset,
        device_types=device_types,
    )

    if cache_key in cache:
        logger.info(
            f"{log(cast(UserDto, dialog_manager.middleware_data[USER_KEY]))} "
            f"Using cached payment for gateway '{gateway_type.value}' "
            f"asset='{payment_asset.value if payment_asset else None}'"
        )
        _save_payment_data(dialog_manager, cache[cache_key])
        await dialog_manager.switch_to(state=Subscription.CONFIRM)
        return True

    payment_data = await _create_payment_and_get_data(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=duration_days,
        gateway_type=gateway_type,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
        device_types=device_types,
        payment_asset=payment_asset,
    )
    if not payment_data:
        return False

    cache[cache_key] = payment_data
    _save_payment_data(dialog_manager, payment_data)
    await dialog_manager.switch_to(state=Subscription.CONFIRM)
    return True


async def _handle_gateway_selection(
    *,
    dialog_manager: DialogManager,
    plan: PlanDto,
    duration_days: int,
    gateway_type: PaymentGatewayType,
    auto_selected: bool,
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
    subscription_service: SubscriptionService,
    device_types: list[DeviceType] | None = None,
) -> bool:
    gateway_type = normalize_gateway_type(gateway_type)
    _set_selected_gateway(
        dialog_manager,
        gateway_type=gateway_type,
        auto_selected=auto_selected,
    )
    _clear_finalized_payment_state(dialog_manager)

    supported_assets = get_supported_payment_assets(gateway_type)
    if not supported_assets:
        dialog_manager.dialog_data.pop(CURRENT_PAYMENT_ASSET_KEY, None)
        return await _finalize_gateway_selection(
            dialog_manager=dialog_manager,
            plan=plan,
            duration_days=duration_days,
            gateway_type=gateway_type,
            auto_selected=auto_selected,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
            subscription_service=subscription_service,
            payment_asset=None,
            device_types=device_types,
        )

    if len(supported_assets) == 1:
        return await _finalize_gateway_selection(
            dialog_manager=dialog_manager,
            plan=plan,
            duration_days=duration_days,
            gateway_type=gateway_type,
            auto_selected=auto_selected,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
            subscription_service=subscription_service,
            payment_asset=supported_assets[0],
            device_types=device_types,
        )

    dialog_manager.dialog_data.pop(CURRENT_PAYMENT_ASSET_KEY, None)
    await dialog_manager.switch_to(state=Subscription.PAYMENT_ASSET)
    return True


async def _handle_single_duration_purchase_flow(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plan: PlanDto,
    duration_days: int,
    purchase_type: PurchaseType,
    gateways: list[PaymentGatewayDto],
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
    subscription_service: SubscriptionService,
) -> None:
    if purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        dialog_manager.dialog_data.pop(SELECTED_DEVICE_TYPES_KEY, None)
        await dialog_manager.switch_to(state=Subscription.DEVICE_TYPE)
        return

    if len(gateways) != 1:
        await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)
        return

    logger.info(f"{log(user)} Auto-selected payment method '{gateways[0].type}'")
    dialog_manager.dialog_data["only_single_payment_method"] = True

    await _handle_gateway_selection(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=duration_days,
        gateway_type=gateways[0].type,
        auto_selected=True,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
    )


async def _handle_single_plan_purchase_path(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plans: list[PlanDto],
    gateways: list[PaymentGatewayDto],
    purchase_type: PurchaseType,
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
    subscription_service: SubscriptionService,
) -> bool:
    if len(plans) != 1:
        return False

    plan = plans[0]
    logger.info(f"{log(user)} Auto-selected single plan '{plan.id}'")
    adapter = DialogDataAdapter(dialog_manager)
    _save_single_plan(dialog_manager, adapter, plan)

    if len(plan.durations) != 1:
        await dialog_manager.switch_to(state=Subscription.DURATION)
        return True

    logger.info(f"{log(user)} Auto-selected duration '{plan.durations[0].days}'")
    _save_single_duration(dialog_manager, plan.durations[0].days)
    await _handle_single_duration_purchase_flow(
        dialog_manager=dialog_manager,
        user=user,
        plan=plan,
        duration_days=plan.durations[0].days,
        purchase_type=purchase_type,
        gateways=gateways,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
    )
    return True


async def _ensure_plans_and_gateways(
    *,
    user: UserDto,
    plans: list[PlanDto],
    gateways: list[PaymentGatewayDto],
    notification_service: NotificationService,
) -> bool:
    if not plans:
        logger.warning(f"{log(user)} No available subscription plans")
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-plans-not-available",
        )
        return False

    if not gateways:
        logger.warning(f"{log(user)} No active payment gateways")
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-gateways-not-available",
        )
        return False

    return True


async def _handle_renew_purchase_type(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plan_service: PlanService,
    subscription_service: SubscriptionService,
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
) -> bool:
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    renewable_subscriptions: list[SubscriptionDto] = []
    can_multi_renew_all = True

    for subscription in all_subscriptions:
        if subscription.status not in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.LIMITED,
        ):
            continue
        if subscription.is_unlimited:
            continue

        action_policy = await subscription_purchase_service.get_action_policy(
            current_user=user,
            subscription=subscription,
        )
        if not action_policy.can_renew:
            continue

        renewable_subscriptions.append(subscription)
        can_multi_renew_all = can_multi_renew_all and action_policy.can_multi_renew

    if not renewable_subscriptions:
        logger.warning(f"{log(user)} No renewable subscriptions found")
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-renew-plan-unavailable",
        )
        return True

    if len(renewable_subscriptions) == 1:
        return await _start_single_subscription_renew_flow(
            dialog_manager=dialog_manager,
            user=user,
            subscription=renewable_subscriptions[0],
            plan_service=plan_service,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
        )

    _prepare_renew_selection(
        dialog_manager,
        single_select_mode=not can_multi_renew_all,
    )
    await dialog_manager.switch_to(state=Subscription.SELECT_SUBSCRIPTION_FOR_RENEW)
    return True


async def _calculate_selected_duration_pricing(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plan: PlanDto,
    selected_duration: int,
    pricing_service: PricingService,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
    currency: Currency,
) -> PriceDetailsDto:
    purchase_type, _, renew_subscription_ids = _get_purchase_state(dialog_manager)
    is_multi_renew = (
        purchase_type == PurchaseType.RENEW
        and renew_subscription_ids is not None
        and len(renew_subscription_ids) > 1
    )
    if is_multi_renew:
        selected_durations: list[PlanDurationDto] = []
        for sub_id in renew_subscription_ids:
            subscription = await subscription_service.get(sub_id)
            if not subscription:
                continue
            matched_plan = await resolve_subscription_renewable_plan(
                subscription=subscription,
                plan_service=plan_service,
            )
            if not matched_plan:
                continue
            sub_duration = matched_plan.get_duration(selected_duration)
            if sub_duration:
                selected_durations.append(sub_duration)

        pricing_currency = _resolve_common_duration_currency(selected_durations, currency)
        total_price = await _calculate_multi_renew_total_price(
            user=user,
            renew_subscription_ids=renew_subscription_ids,
            duration_days=selected_duration,
            currency=pricing_currency,
            subscription_service=subscription_service,
            plan_service=plan_service,
        )
        logger.info(
            f"{log(user)} Calculated total price for {len(renew_subscription_ids)} "
            f"subscriptions: {total_price}"
        )
        return pricing_service.calculate(user, total_price, pricing_currency)

    duration = plan.get_duration(selected_duration)
    if not duration:
        raise ValueError(f"Duration '{selected_duration}' not found for plan '{plan.id}'")

    pricing_currency = _resolve_duration_currency(duration, currency)
    return pricing_service.calculate(
        user=user,
        price=duration.get_price(pricing_currency),
        currency=pricing_currency,
    )


async def _try_auto_select_payment_after_duration(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    plan: PlanDto,
    selected_duration: int,
    price: PriceDetailsDto,
    gateways: list[PaymentGatewayDto],
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
    subscription_service: SubscriptionService,
) -> bool:
    selected_gateway = select_auto_gateway(gateways, is_free=price.is_free)
    if selected_gateway is None:
        return False

    logger.info(f"{log(user)} Auto-selected gateway '{selected_gateway.type}'")
    return await _handle_gateway_selection(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=selected_duration,
        gateway_type=selected_gateway.type,
        auto_selected=True,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
    )


def _get_active_promocode_subscriptions(
    subscriptions: list[SubscriptionDto],
) -> list[SubscriptionDto]:
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


def _store_pending_promocode_state(
    dialog_manager: DialogManager,
    *,
    code: str,
    reward_type: PromocodeRewardType,
    days: int,
    plan_name: str | None = None,
) -> None:
    dialog_manager.dialog_data["pending_promocode_code"] = code
    dialog_manager.dialog_data["pending_promocode_days"] = days
    dialog_manager.dialog_data["pending_promocode_reward_type"] = reward_type.value
    if plan_name is None:
        dialog_manager.dialog_data.pop("pending_promocode_plan_name", None)
        return

    dialog_manager.dialog_data["pending_promocode_plan_name"] = plan_name


async def _validate_promocode_for_input(
    *,
    code: str,
    user: UserDto,
    promocode_service: PromocodeService,
    notification_service: NotificationService,
) -> PromocodeDto | None:
    validation_result = await promocode_service.validate_promocode(code, user)
    if not validation_result.success:
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key=validation_result.message_key or "ntf-promocode-error",
        )
        return None

    promocode = validation_result.promocode
    if promocode:
        return promocode

    await _notify_user(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-promocode-not-found",
    )
    return None


async def _handle_subscription_reward_promocode(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    code: str,
    promocode: PromocodeDto,
    subscription_service: SubscriptionService,
) -> bool:
    if promocode.reward_type != PromocodeRewardType.SUBSCRIPTION:
        return False

    active_subscriptions = _get_active_promocode_subscriptions(
        await subscription_service.get_all_by_user(user.telegram_id)
    )
    if active_subscriptions:
        _store_pending_promocode_state(
            dialog_manager,
            code=code,
            reward_type=promocode.reward_type,
            days=promocode.plan.duration if promocode.plan else 30,
        )
        await dialog_manager.switch_to(Subscription.PROMOCODE_SELECT_SUBSCRIPTION)
        return True

    _store_pending_promocode_state(
        dialog_manager,
        code=code,
        reward_type=promocode.reward_type,
        days=promocode.plan.duration if promocode.plan else 30,
        plan_name=promocode.plan.name if promocode.plan else "Подписка",
    )
    await dialog_manager.switch_to(Subscription.PROMOCODE_CONFIRM_NEW)
    return True


async def _handle_duration_reward_promocode(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    code: str,
    promocode: PromocodeDto,
    subscription_service: SubscriptionService,
    notification_service: NotificationService,
) -> bool:
    if promocode.reward_type != PromocodeRewardType.DURATION:
        return False

    active_subscriptions = _get_active_promocode_subscriptions(
        await subscription_service.get_all_by_user(user.telegram_id)
    )
    if not active_subscriptions:
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-promocode-no-subscription-for-duration",
        )
        return True

    if len(active_subscriptions) > 1:
        _store_pending_promocode_state(
            dialog_manager,
            code=code,
            reward_type=promocode.reward_type,
            days=promocode.reward or 0,
        )
        await dialog_manager.switch_to(Subscription.PROMOCODE_SELECT_SUBSCRIPTION)
        return True

    return False


def _format_promocode_reward_info(promocode: PromocodeDto) -> str:
    if promocode.reward_type == PromocodeRewardType.DURATION:
        return f"{promocode.reward} дней"
    if promocode.reward_type == PromocodeRewardType.TRAFFIC:
        return f"{promocode.reward} ГБ трафика"
    if promocode.reward_type == PromocodeRewardType.DEVICES:
        return f"{promocode.reward} устройств"
    if promocode.reward_type == PromocodeRewardType.PERSONAL_DISCOUNT:
        return f"{promocode.reward}% персональная скидка"
    if promocode.reward_type == PromocodeRewardType.PURCHASE_DISCOUNT:
        return f"{promocode.reward}% скидка на покупку"
    return ""


async def _notify_promocode_activation_result(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    result_success: bool,
    result_message_key: str | None,
    promocode: PromocodeDto | None,
    notification_service: NotificationService,
) -> None:
    if not result_success or not promocode:
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key=result_message_key or "ntf-promocode-error",
        )
        return

    await _notify_user(
        user=user,
        notification_service=notification_service,
        i18n_key=result_message_key or "ntf-promocode-activated",
        i18n_kwargs={
            "code": promocode.code,
            "reward_type": promocode.reward_type.value,
            "reward": _format_promocode_reward_info(promocode),
        },
    )
    await dialog_manager.switch_to(Subscription.MAIN)


async def _create_payment_and_get_data(
    dialog_manager: DialogManager,
    plan: PlanDto,
    duration_days: int,
    gateway_type: PaymentGatewayType,
    subscription_purchase_service: SubscriptionPurchaseService,
    notification_service: NotificationService,
    subscription_service: Optional[SubscriptionService] = None,
    device_types: Optional[list[DeviceType]] = None,
    payment_asset: CryptoAsset | None = None,
) -> Optional[CachedPaymentData]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    duration = plan.get_duration(duration_days)
    purchase_type, renew_subscription_id, renew_subscription_ids = _get_purchase_state(
        dialog_manager
    )

    if not duration:
        logger.error(f"{log(user)} Failed to find duration for payment creation")
        return None

    if not await _ensure_new_purchase_limit(
        dialog_manager=dialog_manager,
        user=user,
        plan=plan,
        purchase_type=purchase_type,
        subscription_service=subscription_service,
        notification_service=notification_service,
    ):
        return None

    request = SubscriptionPurchaseRequest(
        purchase_type=purchase_type,
        payment_source=PaymentSource.EXTERNAL,
        channel=PurchaseChannel.TELEGRAM,
        plan_id=plan.id,
        duration_days=duration_days,
        gateway_type=gateway_type.value,
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=tuple(renew_subscription_ids) if renew_subscription_ids else None,
        device_types=tuple(device_types) if device_types else None,
        payment_asset=payment_asset,
    )

    try:
        quote = await subscription_purchase_service.quote(
            request=request,
            current_user=user,
        )
        result = await subscription_purchase_service.execute(
            request=request,
            current_user=user,
        )
    except SubscriptionPurchaseError as exception:
        logger.warning(f"{log(user)} Purchase quote/execute failed: {exception.detail}")
        await _notify_user(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-subscription-payment-creation-failed",
        )
        return None
    except Exception as exception:
        await _handle_payment_creation_failure(
            user=user,
            exception=exception,
            notification_service=notification_service,
        )
        return None

    return CachedPaymentData(
        payment_id=result.transaction_id,
        payment_url=result.payment_url,
        final_quote=_serialize_final_quote(quote),
    )


@inject
async def on_purchase_type_select(
    purchase_type: PurchaseType,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = filter_gateways_by_channel(
        await payment_gateway_service.filter_active(),
        channel=PurchaseChannel.TELEGRAM,
    )
    dialog_manager.dialog_data["purchase_type"] = purchase_type
    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)
    dialog_manager.dialog_data.pop(SELECTED_DEVICE_TYPES_KEY, None)
    _clear_allowed_purchase_plan_ids(dialog_manager)
    _clear_payment_selection_state(dialog_manager, clear_cache=True)

    if purchase_type == PurchaseType.RENEW and user.current_subscription:
        if not gateways:
            await _notify_user(
                user=user,
                notification_service=notification_service,
                i18n_key="ntf-subscription-gateways-not-available",
            )
            return

        handled = await _start_single_subscription_renew_flow(
            dialog_manager=dialog_manager,
            user=user,
            subscription=user.current_subscription,
            plan_service=plan_service,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
        )
        if handled:
            return
        return

    if not await _ensure_plans_and_gateways(
        user=user,
        plans=plans,
        gateways=gateways,
        notification_service=notification_service,
    ):
        return

    adapter = DialogDataAdapter(dialog_manager)
    if len(plans) == 1:
        logger.info(f"{log(user)} Auto-selected single plan '{plans[0].id}'")
        adapter.save(plans[0])
        dialog_manager.dialog_data["only_single_plan"] = True
        await dialog_manager.switch_to(state=Subscription.DURATION)
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_subscription_plans(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    subscription_service: FromDishka[SubscriptionService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Opened subscription plans menu")

    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = filter_gateways_by_channel(
        await payment_gateway_service.filter_active(),
        channel=PurchaseChannel.TELEGRAM,
    )

    if not callback.data:
        raise ValueError("Callback data is empty")

    purchase_type = PurchaseType(callback.data.removeprefix(PURCHASE_PREFIX))
    dialog_manager.dialog_data["purchase_type"] = purchase_type
    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)
    dialog_manager.dialog_data.pop(SELECTED_DEVICE_TYPES_KEY, None)
    _clear_allowed_purchase_plan_ids(dialog_manager)
    _clear_payment_selection_state(dialog_manager, clear_cache=True)

    if purchase_type == PurchaseType.RENEW:
        if not gateways:
            await _notify_user(
                user=user,
                notification_service=notification_service,
                i18n_key="ntf-subscription-gateways-not-available",
            )
            return
        handled = await _handle_renew_purchase_type(
            dialog_manager=dialog_manager,
            user=user,
            plan_service=plan_service,
            subscription_service=subscription_service,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
        )
        if handled:
            return

    if not await _ensure_plans_and_gateways(
        user=user,
        plans=plans,
        gateways=gateways,
        notification_service=notification_service,
    ):
        return

    handled_single_plan = await _handle_single_plan_purchase_path(
        dialog_manager=dialog_manager,
        user=user,
        plans=plans,
        gateways=gateways,
        purchase_type=purchase_type,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
    )
    if handled_single_plan:
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    dialog_manager.dialog_data["only_single_duration"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan: int,
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    allowed_plan_ids = dialog_manager.dialog_data.get(ALLOWED_PURCHASE_PLAN_IDS_KEY)
    if isinstance(allowed_plan_ids, list) and allowed_plan_ids:
        allowed_plan_id_set = {int(plan_id) for plan_id in allowed_plan_ids}
        if selected_plan not in allowed_plan_id_set:
            await _notify_user(
                user=user,
                notification_service=notification_service,
                i18n_key="ntf-subscription-renew-plan-unavailable",
            )
            return

    plan = await plan_service.get(plan_id=selected_plan)

    if not plan:
        raise ValueError(f"Selected plan '{selected_plan}' not found")

    logger.info(f"{log(user)} Selected plan '{plan.id}'")
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(plan)

    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)
    dialog_manager.dialog_data.pop(SELECTED_DEVICE_TYPES_KEY, None)
    _clear_payment_selection_state(dialog_manager, clear_cache=True)

    if len(plan.durations) == 1:
        logger.info(f"{log(user)} Auto-selected single duration '{plan.durations[0].days}'")
        dialog_manager.dialog_data["only_single_duration"] = True
        await on_duration_select(callback, widget, dialog_manager, plan.durations[0].days)
        return

    await dialog_manager.switch_to(state=Subscription.DURATION)


@inject
async def on_duration_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_duration: int,
    settings_service: FromDishka[SettingsService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription duration '{selected_duration}' days")
    dialog_manager.dialog_data[CURRENT_DURATION_KEY] = selected_duration
    _clear_payment_selection_state(dialog_manager)

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)
    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    currency = await settings_service.get_default_currency()
    price = await _calculate_selected_duration_pricing(
        dialog_manager=dialog_manager,
        user=user,
        plan=plan,
        selected_duration=selected_duration,
        pricing_service=pricing_service,
        subscription_service=subscription_service,
        plan_service=plan_service,
        currency=currency,
    )
    dialog_manager.dialog_data["is_free"] = price.is_free
    gateways = await _get_available_purchase_gateways(
        dialog_manager=dialog_manager,
        user=user,
        plan=plan,
        duration_days=selected_duration,
        payment_gateway_service=payment_gateway_service,
        subscription_service=subscription_service,
        plan_service=plan_service,
    )

    purchase_type, _, _ = _get_purchase_state(dialog_manager)
    if purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        dialog_manager.dialog_data.pop(SELECTED_DEVICE_TYPES_KEY, None)
        await dialog_manager.switch_to(state=Subscription.DEVICE_TYPE)
        return

    if await _try_auto_select_payment_after_duration(
        dialog_manager=dialog_manager,
        user=user,
        plan=plan,
        selected_duration=selected_duration,
        price=price,
        gateways=gateways,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
    ):
        return

    await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)


@inject
async def on_payment_method_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_payment_method: PaymentGatewayType,
    notification_service: FromDishka[NotificationService],
    subscription_service: FromDishka[SubscriptionService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected payment method '{selected_payment_method}'")

    selected_duration = dialog_manager.dialog_data[CURRENT_DURATION_KEY]

    logger.info(f"{log(user)} New combination. Creating new payment")

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    # Получаем выбранные устройства для новых подписок
    await _handle_gateway_selection(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=selected_duration,
        gateway_type=selected_payment_method,
        auto_selected=False,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
        device_types=_get_selected_device_types(dialog_manager),
    )

    # Переходим к подтверждению (выбор устройства уже был сделан ранее для NEW)


@inject
async def on_get_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    payment_id = dialog_manager.dialog_data["payment_id"]
    logger.info(f"{log(user)} Getted free subscription '{payment_id}'")
    await payment_gateway_service.handle_payment_succeeded(UUID(str(payment_id)))


@inject
async def on_payment_asset_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_payment_asset: CryptoAsset,
    notification_service: FromDishka[NotificationService],
    subscription_service: FromDishka[SubscriptionService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected payment asset '{selected_payment_asset.value}'")

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)
    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    selected_duration = dialog_manager.dialog_data[CURRENT_DURATION_KEY]
    selected_payment_method = normalize_gateway_type(
        cast(PaymentGatewayType | str, dialog_manager.dialog_data[CURRENT_METHOD_KEY])
    )

    await _finalize_gateway_selection(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=selected_duration,
        gateway_type=selected_payment_method,
        auto_selected=bool(
            dialog_manager.dialog_data.get(PAYMENT_GATEWAY_AUTO_SELECTED_KEY, False)
        ),
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
        subscription_service=subscription_service,
        payment_asset=selected_payment_asset,
        device_types=_get_selected_device_types(dialog_manager),
    )


@inject
async def on_payment_asset_back(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    _clear_finalized_payment_state(dialog_manager)
    dialog_manager.dialog_data.pop(CURRENT_PAYMENT_ASSET_KEY, None)

    if dialog_manager.dialog_data.get(PAYMENT_GATEWAY_AUTO_SELECTED_KEY, False):
        purchase_type, _, _ = _get_purchase_state(dialog_manager)
        if purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
            await dialog_manager.switch_to(Subscription.DEVICE_TYPE)
            return

        await dialog_manager.switch_to(Subscription.DURATION)
        return

    await dialog_manager.switch_to(Subscription.PAYMENT_METHOD)


@inject
async def on_subscription_confirm_back(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(Subscription.PAYMENT_ASSET)


@inject
async def on_promocode_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    if not message.text:
        return

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    code = message.text.strip().upper()
    logger.info(f"{log(user)} Attempting to activate promocode '{code}'")

    promocode = await _validate_promocode_for_input(
        code=code,
        user=user,
        promocode_service=promocode_service,
        notification_service=notification_service,
    )
    if not promocode:
        return

    if await _handle_subscription_reward_promocode(
        dialog_manager=dialog_manager,
        user=user,
        code=code,
        promocode=promocode,
        subscription_service=subscription_service,
    ):
        return

    if await _handle_duration_reward_promocode(
        dialog_manager=dialog_manager,
        user=user,
        code=code,
        promocode=promocode,
        subscription_service=subscription_service,
        notification_service=notification_service,
    ):
        return

    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
    )
    await _notify_promocode_activation_result(
        dialog_manager=dialog_manager,
        user=user,
        result_success=result.success,
        result_message_key=result.message_key,
        promocode=result.promocode,
        notification_service=notification_service,
    )


@inject
async def on_promocode_select_subscription(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка выбора подписки для добавления дней от промокода (SUBSCRIPTION или DURATION)"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    code = dialog_manager.dialog_data.get("pending_promocode_code")
    reward_type_str = dialog_manager.dialog_data.get("pending_promocode_reward_type")

    if not code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        await dialog_manager.switch_to(Subscription.MAIN)
        return

    logger.info(
        f"{log(user)} Selected subscription '{selected_subscription}' "
        f"for promocode '{code}' (type: {reward_type_str})"
    )
    # Активируем промокод с указанием подписки для добавления дней
    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
        target_subscription_id=selected_subscription,
    )

    # Очищаем временные данные
    dialog_manager.dialog_data.pop("pending_promocode_code", None)
    dialog_manager.dialog_data.pop("pending_promocode_days", None)
    dialog_manager.dialog_data.pop("pending_promocode_reward_type", None)

    if result.success and result.promocode:
        promocode = result.promocode

        # Определяем количество дней в зависимости от типа промокода
        if promocode.reward_type == PromocodeRewardType.DURATION:
            days = promocode.reward or 0
        else:
            # SUBSCRIPTION type
            days = promocode.plan.duration if promocode.plan else 0

        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-promocode-activated-subscription-extended",
                i18n_kwargs={
                    "code": promocode.code,
                    "days": str(days),
                },
            ),
        )

        await dialog_manager.switch_to(Subscription.MAIN)
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=result.message_key or "ntf-promocode-error",
            ),
        )


@inject
async def on_promocode_create_new_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Подтверждение создания новой подписки от промокода"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    code = dialog_manager.dialog_data.get("pending_promocode_code")

    if not code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        await dialog_manager.switch_to(Subscription.MAIN)
        return

    logger.info(f"{log(user)} Confirmed creating new subscription from promocode '{code}'")

    # Активируем промокод (создаст новую подписку)
    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
    )

    # Очищаем временные данные
    dialog_manager.dialog_data.pop("pending_promocode_code", None)
    dialog_manager.dialog_data.pop("pending_promocode_plan_name", None)
    dialog_manager.dialog_data.pop("pending_promocode_days", None)

    if result.success and result.promocode:
        promocode = result.promocode

        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-promocode-activated-subscription",
                i18n_kwargs={
                    "code": promocode.code,
                    "plan_name": promocode.plan.name if promocode.plan else "Подписка",
                },
            ),
        )

        await dialog_manager.switch_to(Subscription.SUCCESS)
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=result.message_key or "ntf-promocode-error",
            ),
        )


@inject
async def on_subscription_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
) -> None:
    """Обработка выбора подписки из списка"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription '{selected_subscription}'")

    # Get the index from items
    items = dialog_manager.dialog_data.get("_subscriptions_items", [])
    subscription_index = 1
    for idx, item in enumerate(items):
        if item.get("id") == selected_subscription:
            subscription_index = idx + 1
            break

    dialog_manager.dialog_data["selected_subscription_id"] = selected_subscription
    dialog_manager.dialog_data["selected_subscription_index"] = subscription_index
    await dialog_manager.switch_to(Subscription.SUBSCRIPTION_DETAILS)


@inject
async def on_renew_selected_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    subscription_service: FromDishka[SubscriptionService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    """Продление выбранной подписки"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("selected_subscription_id")

    if not subscription_id:
        return

    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return

    # Найти план для продления
    matched_plan = None
    await _start_single_subscription_renew_flow(
        dialog_manager=dialog_manager,
        user=user,
        subscription=subscription,
        plan_service=plan_service,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
    )
    return

    if not matched_plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
        )
        return

    # Сохраняем план и переходим к выбору длительности
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(matched_plan)
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data["only_single_plan"] = True
    dialog_manager.dialog_data["renew_subscription_id"] = subscription_id
    # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [subscription_id]
    # Очищаем кэш платежей для новой подписки
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)

    await dialog_manager.switch_to(Subscription.DURATION)


@inject
async def on_delete_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переход на окно подтверждения удаления подписки"""
    await dialog_manager.switch_to(Subscription.CONFIRM_DELETE)


@inject
async def on_confirm_delete_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение удаления подписки"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("selected_subscription_id")

    if not subscription_id:
        return

    from src.services.remnawave import RemnawaveService  # noqa: PLC0415

    container: AsyncContainer = dialog_manager.middleware_data["dishka_container"]
    remnawave_service = await container.get(RemnawaveService)

    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return

    # Удаляем пользователя из Remnawave
    if subscription.user_remna_id:
        try:
            await remnawave_service.remnawave.users.delete_user(
                uuid=str(subscription.user_remna_id)
            )
            logger.info(f"{log(user)} Deleted RemnaUser '{subscription.user_remna_id}' from panel")
        except Exception as e:
            logger.error(f"{log(user)} Failed to delete RemnaUser from panel: {e}")

    # Помечаем подписку как удаленную
    result = await subscription_service.delete_subscription(subscription_id)

    if result:
        logger.info(f"{log(user)} Deleted subscription '{subscription_id}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-deleted"),
        )

        # Если это была текущая подписка, нужно обновить current_subscription
        if user.current_subscription and user.current_subscription.id == subscription_id:
            # Найти другую активную подписку
            all_subs = await subscription_service.get_all_by_user(user.telegram_id)
            active_subs = [
                s
                for s in all_subs
                if s.status != SubscriptionStatus.DELETED and s.id != subscription_id
            ]

            from src.services.user import UserService  # noqa: PLC0415

            user_service = await container.get(UserService)

            if active_subs:
                await user_service.set_current_subscription(user.telegram_id, active_subs[0].id)
            else:
                await user_service.set_current_subscription(user.telegram_id, None)
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )

    # Возвращаемся к списку подписок
    await dialog_manager.switch_to(Subscription.MY_SUBSCRIPTIONS)


@inject
async def on_cancel_delete_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Отмена удаления подписки - возврат к деталям"""
    await dialog_manager.switch_to(Subscription.SUBSCRIPTION_DETAILS)


@inject
async def on_subscription_for_renew_toggle(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    plan_service: FromDishka[PlanService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    """Обработка переключения выбора подписки для продления (множественный или одиночный выбор)"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    # Проверяем режим одиночного выбора
    single_select_mode = dialog_manager.dialog_data.get("renew_single_select_mode", False)

    if single_select_mode:
        # Режим одиночного выбора - сразу переходим к продлению выбранной подписки
        logger.info(
            f"{log(user)} Selected single subscription for renewal '{selected_subscription}'"
        )

        subscription = await subscription_service.get(selected_subscription)
        if not subscription:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
            )
            return
        await _start_single_subscription_renew_flow(
            dialog_manager=dialog_manager,
            user=user,
            subscription=subscription,
            plan_service=plan_service,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
        )
        return

        # Найти план для продления
        plans = await plan_service.get_available_plans(user)
        matched_plan = subscription.find_matching_plan(plans)

        if not matched_plan:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
            )
            return

        # Сохраняем план и переходим к выбору длительности
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(matched_plan)
        dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
        dialog_manager.dialog_data["only_single_plan"] = True
        dialog_manager.dialog_data["renew_subscription_id"] = selected_subscription
        # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
        dialog_manager.dialog_data["renew_subscription_ids"] = None
        dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [selected_subscription]
        # Очищаем кэш платежей, так как выбрана новая подписка для продления
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)

        await dialog_manager.switch_to(Subscription.DURATION)
        return

    # Режим множественного выбора (toggle)
    # Получаем текущий список выбранных подписок
    selected_subscriptions = dialog_manager.dialog_data.get(
        SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY, []
    )

    if selected_subscription in selected_subscriptions:
        # Убираем из выбора
        selected_subscriptions.remove(selected_subscription)
        logger.info(f"{log(user)} Deselected subscription for renewal '{selected_subscription}'")
    else:
        # Добавляем в выбор
        selected_subscriptions.append(selected_subscription)
        logger.info(f"{log(user)} Selected subscription for renewal '{selected_subscription}'")

    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = selected_subscriptions


@inject
async def on_confirm_renew_selection(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение выбора подписок для продления"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    selected_subscriptions = dialog_manager.dialog_data.get(
        SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY, []
    )

    if not selected_subscriptions:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-select-at-least-one"),
        )
        return

    logger.info(f"{log(user)} Confirmed renewal for subscriptions: {selected_subscriptions}")
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW

    # Получаем все выбранные подписки и их планы
    subscriptions_with_plans = []

    for sub_id in selected_subscriptions:
        subscription = await subscription_service.get(sub_id)
        if subscription:
            matched_plan = await resolve_subscription_renewable_plan(
                subscription=subscription,
                plan_service=plan_service,
            )
            if matched_plan:
                subscriptions_with_plans.append((subscription, matched_plan))

    if not subscriptions_with_plans:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
        )
        return

    # Сохраняем информацию о выбранных подписках
    dialog_manager.dialog_data["subscriptions_for_renew"] = [
        {"id": sub.id, "plan_id": plan.id} for sub, plan in subscriptions_with_plans
    ]

    # Если все подписки имеют одинаковый план, используем его
    # Иначе нужно будет обрабатывать каждую подписку отдельно
    unique_plans = list({plan.id for _, plan in subscriptions_with_plans})

    if len(unique_plans) == 1:
        # Все подписки имеют одинаковый план
        _, matched_plan = subscriptions_with_plans[0]
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(matched_plan)
        dialog_manager.dialog_data["only_single_plan"] = True
        dialog_manager.dialog_data["renew_subscription_ids"] = selected_subscriptions
        # Для обратной совместимости сохраняем первую подписку
        dialog_manager.dialog_data["renew_subscription_id"] = selected_subscriptions[0]
        # Очищаем кэш платежей для новых подписок
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
        await dialog_manager.switch_to(Subscription.DURATION)
    else:
        # Разные планы - используем первый план как базовый, но цена будет суммироваться
        # при создании платежа на основе плана каждой подписки
        _, first_plan = subscriptions_with_plans[0]
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(first_plan)
        dialog_manager.dialog_data["only_single_plan"] = True  # Скрываем выбор плана
        dialog_manager.dialog_data["renew_subscription_ids"] = selected_subscriptions
        dialog_manager.dialog_data["renew_subscription_id"] = selected_subscriptions[0]
        # Очищаем кэш платежей для новых подписок
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
        # Переходим к выбору длительности - цена будет рассчитана с учётом всех планов
        await dialog_manager.switch_to(Subscription.DURATION)


@inject
async def on_subscription_for_renew_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Обработка выбора подписки для продления (одиночный выбор - для обратной совместимости)"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription for renewal '{selected_subscription}'")

    subscription = await subscription_service.get(selected_subscription)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return

    # Найти план для продления
    await _start_single_subscription_renew_flow(
        dialog_manager=dialog_manager,
        user=user,
        subscription=subscription,
        plan_service=plan_service,
        subscription_purchase_service=subscription_purchase_service,
        notification_service=notification_service,
    )
    return

    plans = await plan_service.get_available_plans(user)
    matched_plan = subscription.find_matching_plan(plans)

    if not matched_plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
        )
        return

    # Сохраняем план и переходим к выбору длительности
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(matched_plan)
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data["only_single_plan"] = True
    dialog_manager.dialog_data["renew_subscription_id"] = selected_subscription
    # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [selected_subscription]
    # Очищаем кэш платежей для новой подписки
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)

    await dialog_manager.switch_to(Subscription.DURATION)


@inject
async def on_device_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_device_type: DeviceType,
    settings_service: FromDishka[SettingsService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected device type '{selected_device_type}'")

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)
    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    selected_devices = cast(
        list[str],
        dialog_manager.dialog_data.get(SELECTED_DEVICE_TYPES_KEY, []),
    )
    selected_devices.append(selected_device_type.value)
    dialog_manager.dialog_data[SELECTED_DEVICE_TYPES_KEY] = selected_devices
    _clear_payment_selection_state(dialog_manager)

    if len(selected_devices) < 1:
        return

    selected_duration = dialog_manager.dialog_data[CURRENT_DURATION_KEY]
    currency = await settings_service.get_default_currency()
    selected_duration_obj = plan.get_duration(selected_duration)
    if not selected_duration_obj:
        raise ValueError(f"Duration '{selected_duration}' not found for plan '{plan.id}'")

    pricing_currency = _resolve_duration_currency(selected_duration_obj, currency)
    price = pricing_service.calculate(
        user=user,
        price=selected_duration_obj.get_price(pricing_currency),
        currency=pricing_currency,
    )
    dialog_manager.dialog_data["is_free"] = price.is_free
    gateways = await _get_available_purchase_gateways(
        dialog_manager=dialog_manager,
        user=user,
        plan=plan,
        duration_days=selected_duration,
        payment_gateway_service=payment_gateway_service,
        subscription_service=subscription_service,
        plan_service=plan_service,
    )

    selected_gateway = select_auto_gateway(gateways, is_free=price.is_free)
    if selected_gateway is not None:
        logger.info(f"{log(user)} Auto-selected gateway '{selected_gateway.type}'")
        await _handle_gateway_selection(
            dialog_manager=dialog_manager,
            plan=plan,
            duration_days=selected_duration,
            gateway_type=selected_gateway.type,
            auto_selected=True,
            subscription_purchase_service=subscription_purchase_service,
            notification_service=notification_service,
            subscription_service=subscription_service,
            device_types=_get_selected_device_types(dialog_manager),
        )
        return

    await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)
