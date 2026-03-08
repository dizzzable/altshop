from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import orjson
from aiogram import Bot
from pydantic import SecretStr
from starlette.requests import Request

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    MulenpayGatewaySettingsDto,
    PaymentGatewayDto,
)
from src.infrastructure.payment_gateways.mulenpay import MulenpayGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.content = orjson.dumps(payload)

    def raise_for_status(self) -> None:
        return None


def _build_gateway() -> MulenpayGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.MULENPAY,
        currency=Currency.RUB,
        is_active=True,
        settings=MulenpayGatewaySettingsDto(api_key=SecretStr("mulenpay-secret")),
    )
    return MulenpayGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
        config=SimpleNamespace(get_webhook=lambda _gateway_type: "https://example.com/webhook"),
    )


def _build_request(payload: dict[str, object]) -> Request:
    body = orjson.dumps(payload)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_handle_create_payment_uses_provider_uuid_and_url() -> None:
    gateway = _build_gateway()
    provider_uuid = UUID("00000000-0000-0000-0000-000000000123")
    fake_client = SimpleNamespace(
        post=AsyncMock(
            return_value=_FakeHttpResponse(
                {"uuid": str(provider_uuid), "paymentUrl": "https://mulenpay.test/pay/1"}
            )
        )
    )
    setattr(gateway, "_client", cast(Any, fake_client))

    result = asyncio.run(gateway.handle_create_payment(amount=Decimal("15.00"), details="order"))

    assert result.id == provider_uuid
    assert result.url == "https://mulenpay.test/pay/1"


def test_handle_webhook_maps_success_status() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    request = _build_request({"uuid": str(payment_id), "payment_status": "success"})

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED
