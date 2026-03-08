from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from aiogram import Bot
from starlette.requests import Request

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlategaGatewaySettingsDto,
)
from src.infrastructure.payment_gateways.platega import PlategaGateway


def _build_gateway() -> PlategaGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=True,
        settings=PlategaGatewaySettingsDto(
            merchant_id="merchant-1",
            secret="secret-key",
        ),
    )
    return PlategaGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def _build_request(payload: dict[str, object], headers: dict[str, str] | None = None) -> Request:
    body = json.dumps(payload).encode()
    raw_headers = [
        (name.lower().encode(), value.encode()) for name, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": raw_headers,
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_handle_create_payment_accepts_redirect_field() -> None:
    gateway = _build_gateway()
    setattr(
        gateway,
        "_create_transaction",
        AsyncMock(
            return_value={
                "redirect": "https://pay.platega.io/checkout",
                "transactionId": "tx-1",
                "status": "PENDING",
            }
        ),
    )

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("120"),
            details="test order",
            success_redirect_url="https://example.com/success",
            fail_redirect_url="https://example.com/fail",
        )
    )

    assert result.url == "https://pay.platega.io/checkout"


def test_handle_webhook_accepts_current_callback_shape_and_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    request = _build_request(
        {
            "id": str(payment_id),
            "amount": 1000,
            "currency": "RUB",
            "status": "CONFIRMED",
            "paymentMethod": 2,
        },
        headers={
            "X-MerchantId": "merchant-1",
            "X-Secret": "secret-key",
            "Content-Type": "application/json",
        },
    )

    metrics: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "src.infrastructure.payment_gateways.platega.emit_counter",
        lambda name, /, **labels: metrics.append((name, labels)),
    )

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED
    assert (
        "payment_gateway_webhook_mode_total",
        {
            "gateway_type": PaymentGatewayType.PLATEGA.value,
            "mode": "official_callback",
            "auth_mode": "callback_headers",
        },
    ) in metrics


def test_handle_webhook_rejects_invalid_callback_secret() -> None:
    gateway = _build_gateway()
    request = _build_request(
        {
            "id": "00000000-0000-0000-0000-000000000123",
            "amount": 1000,
            "currency": "RUB",
            "status": "CONFIRMED",
            "paymentMethod": 2,
        },
        headers={
            "X-MerchantId": "merchant-1",
            "X-Secret": "wrong-secret",
            "Content-Type": "application/json",
        },
    )

    with pytest.raises(PermissionError, match="Invalid Platega webhook secret"):
        asyncio.run(gateway.handle_webhook(request))


def test_handle_webhook_rejects_legacy_payload_contract() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000321")
    request = _build_request({"payload": str(payment_id), "status": "success"})

    with pytest.raises(PermissionError, match="Missing Platega webhook auth headers"):
        asyncio.run(gateway.handle_webhook(request))
