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

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    YookassaGatewaySettingsDto,
)
from src.infrastructure.payment_gateways.yookassa import YookassaGateway


def _build_gateway(
    *,
    shop_id: str | None = "shop-id",
    api_key: SecretStr | None = SecretStr("secret-key"),
) -> YookassaGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.YOOKASSA,
        currency=Currency.RUB,
        is_active=True,
        settings=YookassaGatewaySettingsDto(
            shop_id=shop_id,
            api_key=api_key,
        ),
    )
    return YookassaGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
        config=SimpleNamespace(domain=SecretStr("example.test")),
    )


def _build_request(*, body: bytes) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/payments/yookassa",
        "headers": [
            (b"content-type", b"application/json"),
            (b"x-forwarded-for", b"185.71.76.5"),
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


def test_handle_webhook_accepts_trusted_ip_without_api_key() -> None:
    gateway = _build_gateway(api_key=None)
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    body = orjson.dumps({"object": {"id": str(payment_id), "status": "succeeded"}})

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(_build_request(body=body)))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_handle_create_payment_requires_api_key() -> None:
    gateway = _build_gateway(api_key=None)

    with pytest.raises(ValueError, match="Yookassa api_key is required"):
        asyncio.run(
            gateway.handle_create_payment(
                amount=Decimal("12.30"),
                details="VPN subscription",
            )
        )
