from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.enums import CryptoAsset, Currency, PaymentGatewayType, PurchaseChannel
from src.infrastructure.database.models.dto import PaymentGatewayDto
from src.services.subscription_purchase import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
)
from src.services.subscription_purchase_gateway_selection import (
    SubscriptionPurchaseGatewaySelectionService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_gateway(*, gateway_type: PaymentGatewayType) -> PaymentGatewayDto:
    return PaymentGatewayDto(
        order_index=1,
        type=gateway_type,
        currency=Currency.USD
        if gateway_type in {PaymentGatewayType.CRYPTOMUS, PaymentGatewayType.HELEKET}
        else Currency.RUB,
        is_active=True,
    )


def build_service(
    *,
    gateways: list[PaymentGatewayDto],
) -> SubscriptionPurchaseGatewaySelectionService:
    payment_gateway_service = SimpleNamespace(
        filter_active=AsyncMock(return_value=gateways),
        get_by_type=AsyncMock(return_value=None),
    )
    return SubscriptionPurchaseGatewaySelectionService(
        payment_gateway_service=payment_gateway_service,
        error_factory=lambda status_code, detail: SubscriptionPurchaseError(
            status_code=status_code,
            detail=detail,
        ),
    )


def test_resolve_purchase_gateway_prefers_telegram_stars_for_telegram_channel() -> None:
    stars_gateway = build_gateway(gateway_type=PaymentGatewayType.TELEGRAM_STARS)
    fallback_gateway = build_gateway(gateway_type=PaymentGatewayType.PLATEGA)
    service = build_service(gateways=[fallback_gateway, stars_gateway])

    gateway, gateway_type = run_async(
        service.resolve_purchase_gateway(
            request=SubscriptionPurchaseRequest(channel=PurchaseChannel.TELEGRAM)
        )
    )

    assert gateway is stars_gateway
    assert gateway_type == PaymentGatewayType.TELEGRAM_STARS


def test_resolve_purchase_gateway_requires_explicit_type_for_multiple_web_gateways() -> None:
    service = build_service(
        gateways=[
            build_gateway(gateway_type=PaymentGatewayType.PLATEGA),
            build_gateway(gateway_type=PaymentGatewayType.ROBOKASSA),
        ]
    )

    with pytest.raises(SubscriptionPurchaseError) as error:
        run_async(
            service.resolve_purchase_gateway(
                request=SubscriptionPurchaseRequest(channel=PurchaseChannel.WEB)
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Gateway type is required when multiple web gateways are available"


def test_resolve_purchase_gateway_rejects_telegram_only_gateway_for_web_channel() -> None:
    service = build_service(gateways=[])

    with pytest.raises(SubscriptionPurchaseError) as error:
        run_async(
            service.resolve_purchase_gateway(
                request=SubscriptionPurchaseRequest(
                    channel=PurchaseChannel.WEB,
                    gateway_type=PaymentGatewayType.TELEGRAM_STARS.value,
                )
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Gateway TELEGRAM_STARS is not available for web purchases"


def test_resolve_payment_asset_requires_asset_when_gateway_supports_multiple_assets() -> None:
    service = build_service(gateways=[])

    with pytest.raises(SubscriptionPurchaseError) as error:
        service.resolve_payment_asset(
            request=SubscriptionPurchaseRequest(channel=PurchaseChannel.WEB),
            gateway_type=PaymentGatewayType.CRYPTOMUS,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "payment_asset is required for gateway CRYPTOMUS"


def test_resolve_payment_asset_rejects_unsupported_asset() -> None:
    service = build_service(gateways=[])

    with pytest.raises(SubscriptionPurchaseError) as error:
        service.resolve_payment_asset(
            request=SubscriptionPurchaseRequest(
                channel=PurchaseChannel.WEB,
                payment_asset=CryptoAsset.SOL,
            ),
            gateway_type=PaymentGatewayType.CRYPTOPAY,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Unsupported payment_asset 'SOL' for gateway CRYPTOPAY"
