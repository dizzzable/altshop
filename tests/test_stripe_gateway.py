from __future__ import annotations

import asyncio
import hmac
import time
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import orjson
import pytest
from aiogram import Bot
from pydantic import SecretStr
from starlette.requests import Request

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    StripeGatewaySettingsDto,
)
from src.infrastructure.payment_gateways.stripe import StripeGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.content = orjson.dumps(payload)

    def raise_for_status(self) -> None:
        return None


def _build_gateway() -> StripeGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.STRIPE,
        currency=Currency.USD,
        is_active=True,
        settings=StripeGatewaySettingsDto(
            secret_key=SecretStr("sk_test_123"),
            webhook_secret=SecretStr("whsec_test_123"),
        ),
    )
    return StripeGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def _build_request(payload: dict[str, Any], webhook_secret: str) -> Request:
    body = orjson.dumps(payload)
    timestamp = str(int(time.time()))
    signature = hmac.new(
        webhook_secret.encode(),
        f"{timestamp}.".encode() + body,
        "sha256",
    ).hexdigest()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [
            (b"stripe-signature", f"t={timestamp},v1={signature}".encode()),
            (b"content-type", b"application/json"),
        ],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_handle_create_payment_uses_hosted_checkout_session() -> None:
    gateway = _build_gateway()
    fake_client = SimpleNamespace(post=AsyncMock(return_value=_FakeHttpResponse({"url": "https://checkout.stripe.test/1"})))
    setattr(gateway, "_client", cast(Any, fake_client))

    result = asyncio.run(gateway.handle_create_payment(amount=Decimal("19.99"), details="order"))

    assert result.url == "https://checkout.stripe.test/1"
    assert fake_client.post.await_count == 1


def test_handle_webhook_accepts_signed_checkout_completed_event() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    request = _build_request(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"payment_id": str(payment_id)},
                }
            },
        },
        "whsec_test_123",
    )

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_handle_webhook_rejects_invalid_signature() -> None:
    gateway = _build_gateway()
    body = orjson.dumps(
        {
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"payment_id": str(UUID(int=1))}}},
        }
    )
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"stripe-signature", b"t=1,v1=bad"), (b"content-type", b"application/json")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive)

    with pytest.raises(PermissionError):
        asyncio.run(gateway.handle_webhook(request))
