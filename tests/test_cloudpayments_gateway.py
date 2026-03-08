from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
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
    CloudPaymentsGatewaySettingsDto,
    PaymentGatewayDto,
)
from src.infrastructure.payment_gateways.cloudpayments import CloudPaymentsGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.content = orjson.dumps(payload)

    def raise_for_status(self) -> None:
        return None


def _build_gateway() -> CloudPaymentsGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.CLOUDPAYMENTS,
        currency=Currency.RUB,
        is_active=True,
        settings=CloudPaymentsGatewaySettingsDto(
            public_id="public-id",
            api_secret=SecretStr("cloud-secret"),
        ),
    )
    return CloudPaymentsGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def _build_request(payload: dict[str, object], api_secret: str) -> Request:
    body = orjson.dumps(payload)
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [
            (b"content-hmac", signature.encode()),
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


def test_handle_create_payment_extracts_order_url() -> None:
    gateway = _build_gateway()
    fake_client = SimpleNamespace(
        post=AsyncMock(
            return_value=_FakeHttpResponse(
                {"Success": True, "Model": {"Url": "https://cloudpayments.test/order/1"}}
            )
        )
    )
    setattr(gateway, "_client", cast(Any, fake_client))

    result = asyncio.run(gateway.handle_create_payment(amount=Decimal("25.00"), details="order"))

    assert result.url == "https://cloudpayments.test/order/1"


def test_handle_webhook_accepts_signed_payload() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    request = _build_request({"InvoiceId": str(payment_id), "Status": "Completed"}, "cloud-secret")

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_build_webhook_response_returns_cloudpayments_ack() -> None:
    gateway = _build_gateway()
    request = _build_request({"InvoiceId": str(UUID(int=1)), "Status": "Completed"}, "cloud-secret")

    response = asyncio.run(gateway.build_webhook_response(request))

    assert response.body == b'{"code":0}'


def test_handle_webhook_rejects_invalid_signature() -> None:
    gateway = _build_gateway()
    body = orjson.dumps({"InvoiceId": str(UUID(int=1)), "Status": "Completed"})
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-hmac", b"bad"), (b"content-type", b"application/json")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(scope, receive)

    with pytest.raises(PermissionError, match="Invalid CloudPayments webhook signature"):
        asyncio.run(gateway.handle_webhook(request))
