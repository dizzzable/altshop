from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from aiogram import Bot
from pydantic import SecretStr
from starlette.requests import Request

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    RobokassaGatewaySettingsDto,
)
from src.infrastructure.payment_gateways.robokassa import RobokassaGateway


def _build_gateway() -> RobokassaGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.ROBOKASSA,
        currency=Currency.RUB,
        is_active=True,
        settings=RobokassaGatewaySettingsDto(
            shop_id="merchant-login",
            api_key=SecretStr("password1"),
            secret_key=SecretStr("password2"),
        ),
    )
    return RobokassaGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def _build_request(body: str) -> Request:
    body_bytes = body.encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    return Request(scope, receive)


def test_handle_create_payment_builds_hosted_payment_url() -> None:
    gateway = _build_gateway()

    result = asyncio.run(gateway.handle_create_payment(amount=Decimal("12.30"), details="order"))

    assert result.url is not None
    parsed = urlparse(result.url)
    params = parse_qs(parsed.query)
    assert parsed.netloc == "auth.robokassa.ru"
    assert params["MerchantLogin"] == ["merchant-login"]
    assert params["OutSum"] == ["12.30"]
    assert params["Shp_payment_id"] == [str(result.id)]


def test_handle_webhook_accepts_result_url_signature() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    out_sum = "12.30"
    inv_id = payment_id.hex
    shp_params = {"Shp_payment_id": str(payment_id)}
    signature = gateway._calculate_result_signature(out_sum, inv_id, shp_params)
    request = _build_request(
        f"OutSum={out_sum}&InvId={inv_id}&SignatureValue={signature}&Shp_payment_id={payment_id}"
    )

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_build_webhook_response_returns_ok_inv_id() -> None:
    gateway = _build_gateway()
    request = _build_request("InvId=test-invoice")

    response = asyncio.run(gateway.build_webhook_response(request))

    assert response.body == b"OKtest-invoice"


def test_handle_webhook_rejects_invalid_signature() -> None:
    gateway = _build_gateway()
    request = _build_request(
        "OutSum=12.30&InvId=test&SignatureValue=wrong&Shp_payment_id=00000000-0000-0000-0000-000000000123"
    )

    with pytest.raises(PermissionError, match="Invalid Robokassa webhook signature"):
        asyncio.run(gateway.handle_webhook(request))
