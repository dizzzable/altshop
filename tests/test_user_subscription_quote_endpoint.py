from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.contracts.user_subscription import PurchaseQuoteRequest
from src.api.endpoints.user_subscription import quote_subscription
from src.core.enums import CryptoAsset, PaymentGatewayType, PurchaseChannel, PurchaseType
from src.services.subscription_purchase import SubscriptionPurchaseQuoteResult

QUOTE_SUBSCRIPTION_ENDPOINT = getattr(
    inspect.unwrap(quote_subscription),
    "__dishka_orig_func__",
    inspect.unwrap(quote_subscription),
)


def test_quote_subscription_delegates_to_purchase_service_and_maps_response() -> None:
    current_user = SimpleNamespace(telegram_id=1001)
    subscription_purchase_service = SimpleNamespace(
        quote=AsyncMock(
            return_value=SubscriptionPurchaseQuoteResult(
                price=14.5,
                original_price=18.0,
                currency="USDT",
                settlement_price=1450.0,
                settlement_original_price=1800.0,
                settlement_currency="RUB",
                discount_percent=20,
                discount_source="PURCHASE",
                payment_asset="USDT",
                quote_source="MARKET_MAX_REAL",
                quote_expires_at="2026-03-08T00:01:00+00:00",
                quote_provider_count=4,
            )
        )
    )

    response = asyncio.run(
        QUOTE_SUBSCRIPTION_ENDPOINT(
            request=PurchaseQuoteRequest(
                purchase_type=PurchaseType.NEW,
                channel=PurchaseChannel.WEB,
                plan_id=11,
                duration_days=30,
                gateway_type=PaymentGatewayType.CRYPTOMUS.value,
                payment_asset=CryptoAsset.USDT,
            ),
            current_user=current_user,
            subscription_purchase_service=subscription_purchase_service,
        )
    )

    request_arg = subscription_purchase_service.quote.await_args.kwargs["request"]
    assert request_arg.gateway_type == PaymentGatewayType.CRYPTOMUS.value
    assert request_arg.payment_asset == CryptoAsset.USDT
    assert response.price == 14.5
    assert response.original_price == 18.0
    assert response.currency == "USDT"
    assert response.settlement_currency == "RUB"
    assert response.payment_asset == "USDT"
    assert response.quote_source == "MARKET_MAX_REAL"
