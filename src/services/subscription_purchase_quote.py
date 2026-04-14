from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    DiscountSource,
    PaymentSource,
    PurchaseType,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionRenewItemDto,
    UserDto,
)

from .market_quote import CurrencyConversionQuote
from .subscription_purchase_models import (
    ResolvedRenewItemContext,
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    ValidatedPurchaseContext,
)

if TYPE_CHECKING:
    from .subscription_purchase import SubscriptionPurchaseService


def _resolve_purchase_duration(
    _service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    plan: PlanDto,
) -> tuple[int, PlanDurationDto]:
    duration_days = request.duration_days
    if not duration_days:
        if not plan.durations:
            raise SubscriptionPurchaseError(
                status_code=400,
                detail="No durations available for this plan",
            )
        duration_days = plan.durations[0].days

    duration = next((item for item in plan.durations if item.days == duration_days), None)
    if not duration:
        raise SubscriptionPurchaseError(
            status_code=400,
            detail=f"Duration {duration_days} days not available for this plan",
        )

    return duration_days, duration


def _resolve_effective_subscription_count(
    _service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
) -> tuple[int, int]:
    if request.purchase_type in (PurchaseType.RENEW, PurchaseType.UPGRADE) and request.quantity > 1:
        raise SubscriptionPurchaseError(
            status_code=400,
            detail="Quantity greater than 1 is not supported for renew or upgrade purchases",
        )

    effective_multiplier = (
        request.quantity
        if request.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL)
        else 1
    )
    return effective_multiplier, effective_multiplier


def _resolve_gateway_price(
    _service: SubscriptionPurchaseService,
    *,
    duration: PlanDurationDto,
    gateway: PaymentGatewayDto,
) -> PlanPriceDto:
    price_obj = next(
        (price for price in duration.prices if price.currency == gateway.currency),
        None,
    )
    if not price_obj:
        raise SubscriptionPurchaseError(
            status_code=400,
            detail=f"Price not found for gateway currency {gateway.currency.value}",
        )
    return price_obj


def _calculate_final_purchase_price(
    service: SubscriptionPurchaseService,
    *,
    current_user: UserDto,
    gateway: PaymentGatewayDto,
    price_obj: PlanPriceDto,
    effective_multiplier: int,
) -> PriceDetailsDto:
    price_for_calculation = Decimal(price_obj.price) * Decimal(effective_multiplier)
    return service.pricing_service.calculate(
        user=current_user,
        price=price_for_calculation,
        currency=gateway.currency,
    )


async def _calculate_settlement_pricing(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    validated_context: ValidatedPurchaseContext,
    duration: PlanDurationDto,
    gateway: PaymentGatewayDto,
    effective_multiplier: int,
) -> tuple[PriceDetailsDto, tuple[TransactionRenewItemDto, ...]]:
    if request.purchase_type == PurchaseType.RENEW and validated_context.renew_items:
        renew_items, total_base_price = service._build_renew_transaction_items(
            renew_item_contexts=validated_context.renew_items,
            duration_days=duration.days,
            gateway=gateway,
        )
        settlement_pricing = service.pricing_service.calculate(
            user=current_user,
            price=total_base_price,
            currency=gateway.currency,
        )
        return settlement_pricing, renew_items

    price_obj = service._resolve_gateway_price(duration=duration, gateway=gateway)
    settlement_pricing = service._calculate_final_purchase_price(
        current_user=current_user,
        gateway=gateway,
        price_obj=price_obj,
        effective_multiplier=effective_multiplier,
    )
    return settlement_pricing, ()


def _build_renew_transaction_items(
    service: SubscriptionPurchaseService,
    *,
    duration_days: int,
    gateway: PaymentGatewayDto,
    renew_item_contexts: tuple[ResolvedRenewItemContext, ...],
) -> tuple[tuple[TransactionRenewItemDto, ...], Decimal]:
    renew_items: list[TransactionRenewItemDto] = []
    total_price = Decimal("0")

    for renew_item_context in renew_item_contexts:
        renew_duration = renew_item_context.target_plan.get_duration(duration_days)
        if not renew_duration:
            raise SubscriptionPurchaseError(
                status_code=400,
                detail=(
                    f"Duration {duration_days} days not available for subscription "
                    f"{renew_item_context.subscription_id}"
                ),
            )

        renew_price = service._resolve_gateway_price(duration=renew_duration, gateway=gateway)
        item_amount = Decimal(renew_price.price)
        total_price += item_amount
        renew_items.append(
            TransactionRenewItemDto(
                subscription_id=renew_item_context.subscription_id,
                renew_mode=renew_item_context.renew_mode,
                plan=PlanSnapshotDto.from_plan(
                    renew_item_context.target_plan,
                    duration_days,
                ),
                pricing=PriceDetailsDto(
                    original_amount=item_amount,
                    discount_percent=0,
                    discount_source=DiscountSource.NONE,
                    final_amount=item_amount,
                ),
            )
        )

    return tuple(renew_items), total_price


async def _build_display_quote(
    service: SubscriptionPurchaseService,
    *,
    current_user: UserDto,
    request: SubscriptionPurchaseRequest,
    gateway: PaymentGatewayDto,
    settlement_amount: Decimal,
    payment_asset: CryptoAsset | None,
) -> CurrencyConversionQuote:
    if request.payment_source == PaymentSource.PARTNER_BALANCE:
        effective_currency = await service.settings_service.resolve_partner_balance_currency(
            current_user
        )
        return await service.market_quote_service.convert_from_rub(
            amount_rub=settlement_amount,
            target_currency=effective_currency,
        )

    if payment_asset is not None:
        if gateway.currency != Currency.USD:
            raise SubscriptionPurchaseError(
                status_code=400,
                detail=(
                    f"Gateway {gateway.type.value} must use USD settlement "
                    "for crypto payment quotes"
                ),
            )
        return await service.market_quote_service.convert_from_usd(
            amount_usd=settlement_amount,
            target_currency=Currency(payment_asset.value),
        )

    return service._build_static_display_quote(
        amount=settlement_amount,
        currency=gateway.currency,
    )


def _build_static_display_quote(
    service: SubscriptionPurchaseService,
    *,
    amount: Decimal,
    currency: Currency,
) -> CurrencyConversionQuote:
    if amount <= 0:
        normalized_amount = Decimal(0)
    else:
        normalized_amount = service.pricing_service.apply_currency_rules(amount, currency)
    return CurrencyConversionQuote(
        amount=normalized_amount,
        currency=currency,
        quote_rate=Decimal("1"),
        quote_source="STATIC",
        quote_provider_count=0,
        quote_expires_at=datetime_now().replace(microsecond=0).isoformat(),
    )


def _resolve_purchase_device_types(
    _service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    effective_subscription_count: int,
) -> list[DeviceType] | None:
    raw_device_types = list(request.device_types or ())
    if request.device_type and not raw_device_types:
        raw_device_types = [request.device_type] * effective_subscription_count

    if request.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL) and raw_device_types:
        if len(raw_device_types) != effective_subscription_count:
            raise SubscriptionPurchaseError(
                status_code=400,
                detail=(
                    "Device types count does not match requested subscriptions count: "
                    f"{len(raw_device_types)} != {effective_subscription_count}"
                ),
            )

    return raw_device_types or None
