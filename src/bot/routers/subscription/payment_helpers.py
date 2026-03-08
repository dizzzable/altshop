from __future__ import annotations

from src.core.crypto_assets import is_crypto_payment_gateway
from src.core.enums import Currency, DeviceType, PaymentGatewayType, PurchaseType
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    UserDto,
)
from src.services.plan import PlanService
from src.services.subscription import SubscriptionService


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
    gateway_type: PaymentGatewayType,
    purchase_type: PurchaseType,
    renew_ids: list[int],
    payment_asset: str | None,
    device_types: list[DeviceType] | None,
) -> str:
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
            purchase_type.value,
            gateway_type.value,
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
    purchase_type: PurchaseType,
    renew_subscription_id: int | None,
    renew_subscription_ids: list[int] | tuple[int, ...] | None,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
) -> list[PlanDurationDto]:
    renew_ids = collect_renew_ids(
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
    )
    is_multi_renew = purchase_type == PurchaseType.RENEW and len(renew_ids) > 1

    if not is_multi_renew:
        duration = plan.get_duration(duration_days)
        return [duration] if duration is not None else []

    available_plans = await plan_service.get_available_plans(user)
    selected_durations: list[PlanDurationDto] = []

    for renew_id in renew_ids:
        subscription = await subscription_service.get(renew_id)
        if not subscription:
            continue

        matched_plan = subscription.find_matching_plan(available_plans)
        if not matched_plan:
            continue

        renew_duration = matched_plan.get_duration(duration_days)
        if renew_duration is not None:
            selected_durations.append(renew_duration)

    return selected_durations
