from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.enums import PaymentSource
from src.infrastructure.database.models.dto import UserDto

from .subscription_purchase_models import (
    SubscriptionPurchaseQuoteResult,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseResult,
)

if TYPE_CHECKING:
    from .subscription_purchase import SubscriptionPurchaseService


async def _execute(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionPurchaseResult:
    await service.purchase_access_service.assert_can_purchase(current_user)
    normalized_request = await service._normalize_trial_catalog_purchase_request(
        request=request,
        current_user=current_user,
    )
    return await service._execute_without_access_assert(
        request=normalized_request,
        current_user=current_user,
    )


async def _quote(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionPurchaseQuoteResult:
    await service.purchase_access_service.assert_can_purchase(current_user)
    normalized_request = await service._normalize_trial_catalog_purchase_request(
        request=request,
        current_user=current_user,
    )
    validated_context = await service._validate_purchase_context(
        request=normalized_request,
        current_user=current_user,
    )
    plan = validated_context.plan
    _, duration = service._resolve_purchase_duration(request=normalized_request, plan=plan)
    effective_multiplier, _ = service._resolve_effective_subscription_count(
        request=normalized_request
    )
    gateway, gateway_type = await service._resolve_purchase_gateway(request=normalized_request)
    payment_asset = service._resolve_payment_asset(
        request=normalized_request,
        gateway_type=gateway_type,
    )
    settlement_pricing, renew_items = await service._calculate_settlement_pricing(
        request=normalized_request,
        current_user=current_user,
        validated_context=validated_context,
        duration=duration,
        gateway=gateway,
        effective_multiplier=effective_multiplier,
    )
    if normalized_request.payment_source == PaymentSource.PARTNER_BALANCE:
        await service._assert_partner_balance_purchase_allowed(
            request=normalized_request,
            current_user=current_user,
            gateway=gateway,
        )

    final_display_quote = await service._build_display_quote(
        current_user=current_user,
        request=normalized_request,
        gateway=gateway,
        settlement_amount=settlement_pricing.final_amount,
        payment_asset=payment_asset,
    )
    original_display_quote = await service._build_display_quote(
        current_user=current_user,
        request=normalized_request,
        gateway=gateway,
        settlement_amount=settlement_pricing.original_amount,
        payment_asset=payment_asset,
    )
    return SubscriptionPurchaseQuoteResult(
        price=float(final_display_quote.amount),
        original_price=float(original_display_quote.amount),
        currency=final_display_quote.currency.value,
        settlement_price=float(settlement_pricing.final_amount),
        settlement_original_price=float(settlement_pricing.original_amount),
        settlement_currency=gateway.currency.value,
        discount_percent=settlement_pricing.discount_percent,
        discount_source=settlement_pricing.discount_source.value,
        payment_asset=payment_asset.value if payment_asset else None,
        quote_source=final_display_quote.quote_source,
        quote_expires_at=final_display_quote.quote_expires_at,
        quote_provider_count=final_display_quote.quote_provider_count,
        renew_items=renew_items,
    )
