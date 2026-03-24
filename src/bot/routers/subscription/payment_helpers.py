from __future__ import annotations

from src.core.crypto_assets import is_crypto_payment_gateway
from src.core.enums import (
    ArchivedPlanRenewMode,
    Currency,
    DeviceType,
    PaymentGatewayType,
    PurchaseType,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    SubscriptionDto,
    UserDto,
)
from src.services.plan import PlanService
from src.services.subscription import SubscriptionService


def normalize_purchase_type(purchase_type: PurchaseType | str) -> PurchaseType:
    if isinstance(purchase_type, PurchaseType):
        return purchase_type
    return PurchaseType(str(purchase_type))


def normalize_gateway_type(gateway_type: PaymentGatewayType | str) -> PaymentGatewayType:
    if isinstance(gateway_type, PaymentGatewayType):
        return gateway_type
    return PaymentGatewayType(str(gateway_type))


def collect_renew_ids(
    *,
    renew_subscription_id: int | None,
    renew_subscription_ids: list[int] | tuple[int, ...] | None,
) -> list[int]:
    renew_ids: list[int] = []
    if renew_subscription_id:
        renew_ids.append(renew_subscription_id)
    if renew_subscription_ids:
        renew_ids.extend(renew_subscription_ids)
    return list(dict.fromkeys(renew_ids))


def duration_supports_currency(duration: PlanDurationDto, currency: Currency) -> bool:
    return any(price.currency == currency for price in duration.prices)


def filter_gateways_for_durations(
    gateways: list[PaymentGatewayDto],
    durations: list[PlanDurationDto],
) -> list[PaymentGatewayDto]:
    if not durations:
        return gateways

    return [
        gateway
        for gateway in gateways
        if all(duration_supports_currency(duration, gateway.currency) for duration in durations)
    ]


def select_auto_gateway(
    gateways: list[PaymentGatewayDto],
    *,
    is_free: bool,
) -> PaymentGatewayDto | None:
    if not gateways:
        return None

    if len(gateways) == 1:
        return gateways[0]

    if not is_free:
        return None

    telegram_stars_gateway = next(
        (gateway for gateway in gateways if gateway.type == PaymentGatewayType.TELEGRAM_STARS),
        None,
    )
    if telegram_stars_gateway is not None:
        return telegram_stars_gateway

    non_crypto_gateway = next(
        (gateway for gateway in gateways if not is_crypto_payment_gateway(gateway.type)),
        None,
    )
    if non_crypto_gateway is not None:
        return non_crypto_gateway

    return gateways[0]


def build_payment_cache_key(
    *,
    plan_id: int,
    duration_days: int,
    gateway_type: PaymentGatewayType | str,
    purchase_type: PurchaseType | str,
    renew_ids: list[int],
    payment_asset: str | None,
    device_types: list[DeviceType] | None,
) -> str:
    normalized_purchase_type = normalize_purchase_type(purchase_type)
    normalized_gateway_type = normalize_gateway_type(gateway_type)
    normalized_renew_ids = ",".join(str(item) for item in sorted(set(renew_ids))) or "-"
    normalized_device_types = (
        ",".join(sorted(device_type.value for device_type in device_types))
        if device_types
        else "-"
    )
    normalized_payment_asset = payment_asset or "-"

    return "|".join(
        (
            str(plan_id),
            str(duration_days),
            normalized_purchase_type.value,
            normalized_gateway_type.value,
            normalized_payment_asset,
            normalized_renew_ids,
            normalized_device_types,
        )
    )


async def resolve_purchase_durations(
    *,
    user: UserDto,
    plan: PlanDto,
    duration_days: int,
    purchase_type: PurchaseType | str,
    renew_subscription_id: int | None,
    renew_subscription_ids: list[int] | tuple[int, ...] | None,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
) -> list[PlanDurationDto]:
    normalized_purchase_type = normalize_purchase_type(purchase_type)
    renew_ids = collect_renew_ids(
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
    )
    is_multi_renew = normalized_purchase_type == PurchaseType.RENEW and len(renew_ids) > 1

    if not is_multi_renew:
        duration = plan.get_duration(duration_days)
        return [duration] if duration is not None else []

    selected_durations: list[PlanDurationDto] = []

    for renew_id in renew_ids:
        subscription = await subscription_service.get(renew_id)
        if not subscription:
            continue

        matched_plan = await resolve_subscription_renewable_plan(
            subscription=subscription,
            plan_service=plan_service,
        )
        if not matched_plan:
            continue

        renew_duration = matched_plan.get_duration(duration_days)
        if renew_duration is not None:
            selected_durations.append(renew_duration)

    return selected_durations


async def resolve_subscription_renewable_plan(
    *,
    subscription: SubscriptionDto,
    plan_service: PlanService,
) -> PlanDto | None:
    source_plan_id = getattr(subscription.plan, "id", None)
    if not source_plan_id or source_plan_id <= 0:
        return None

    source_plan = await plan_service.get(source_plan_id)
    if not source_plan:
        return None

    if source_plan.is_archived:
        if source_plan.archived_renew_mode == ArchivedPlanRenewMode.SELF_RENEW:
            return source_plan
        return None

    return source_plan if source_plan.is_publicly_purchasable else None
