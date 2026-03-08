from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import orjson
import pytest
from aiogram import Bot
from pydantic import SecretStr
from starlette.requests import Request

from src.core.enums import CryptoAsset, Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    CryptomusGatewaySettingsDto,
    PaymentGatewayDto,
)
from src.infrastructure.payment_gateways.cryptomus import CryptomusGateway


def _build_gateway() -> CryptomusGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.CRYPTOMUS,
        currency=Currency.USD,
        is_active=True,
        settings=CryptomusGatewaySettingsDto(
            merchant_id="merchant-1",
            api_key=SecretStr("secret-key"),
        ),
    )
    return CryptomusGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
        config=SimpleNamespace(get_webhook=lambda _gateway_type: "https://example.com/webhook"),
    )


def _build_request(payload: dict[str, object], signature: str) -> Request:
    body = orjson.dumps(payload)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"sign", signature.encode()), (b"content-type", b"application/json")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_handle_create_payment_extracts_checkout_url() -> None:
    gateway = _build_gateway()
    create_payment = AsyncMock(
        return_value=(
            200,
            {"result": {"url": "https://cryptomus.test/pay/1"}},
            '{"result":{"url":"https://cryptomus.test/pay/1"}}',
        )
    )
    setattr(gateway, "_create_payment", create_payment)

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("10.50"),
            details="order",
            payment_asset=CryptoAsset.USDT,
        )
    )

    assert result.url == "https://cryptomus.test/pay/1"
    assert create_payment.await_count == 1
    payload = create_payment.await_args.args[0]
    assert payload["to_currency"] == CryptoAsset.USDT.value


def test_handle_webhook_accepts_signed_payload() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    payload = {"order_id": str(payment_id), "status": "paid"}
    signature = gateway._calculate_sign(orjson.dumps(payload))
    request = _build_request(payload, signature)

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_handle_webhook_rejects_invalid_signature() -> None:
    gateway = _build_gateway()
    request = _build_request(
        {"order_id": "00000000-0000-0000-0000-000000000123", "status": "paid"},
        "wrong-signature",
    )

    with pytest.raises(PermissionError, match="Invalid Cryptomus webhook signature"):
        asyncio.run(gateway.handle_webhook(request))
