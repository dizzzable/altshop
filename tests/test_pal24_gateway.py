from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from aiogram import Bot
from httpx import HTTPStatusError, Request, Response
from pydantic import SecretStr
from starlette.requests import Request as StarletteRequest

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    Pal24GatewaySettingsDto,
    PaymentGatewayDto,
)
from src.infrastructure.payment_gateways.pal24 import Pal24Gateway


def _build_gateway() -> Pal24Gateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.PAL24,
        currency=Currency.RUB,
        is_active=True,
        settings=Pal24GatewaySettingsDto(
            api_key=SecretStr("secret-key"),
            shop_id="shop-1",
        ),
    )
    return Pal24Gateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def _build_request(body: bytes, content_type: str) -> StarletteRequest:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(b"content-type", content_type.encode())],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return StarletteRequest(scope, receive)


def _build_not_found_error(*, method: str, path: str) -> HTTPStatusError:
    request = Request(method, f"https://pal24.pro/api/v1{path}")
    response = Response(404, request=request, text="Route not found")
    return HTTPStatusError("route missing", request=request, response=response)


def test_handle_create_payment_uses_official_form_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _build_gateway()
    create_bill = AsyncMock(
        return_value={
            "success": True,
            "bill_id": "bill-1",
            "link_page_url": "https://pal24.pro/pay/1",
        }
    )
    setattr(gateway, "_create_bill", create_bill)

    metrics: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "src.infrastructure.payment_gateways.pal24.emit_counter",
        lambda name, /, **labels: metrics.append((name, labels)),
    )

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("99.50"),
            details="order",
        )
    )

    assert result.url == "https://pal24.pro/pay/1"
    assert create_bill.await_args is not None
    payload = create_bill.await_args.args[0]
    assert "apiToken" not in payload
    assert payload["shop_id"] == "shop-1"
    assert payload["currency_in"] == "RUB"
    assert (
        "payment_gateway_request_mode_total",
        {
            "gateway_type": PaymentGatewayType.PAL24.value,
            "operation": "create_payment",
            "mode": "official_form",
        },
    ) in metrics


def test_gateway_client_uses_bearer_authorization_header() -> None:
    gateway = _build_gateway()

    assert gateway._client.headers["Authorization"] == "Bearer secret-key"
    assert gateway._client.headers["Accept"] == "application/json"


def test_handle_webhook_accepts_official_form_postback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    out_sum = "99.50"
    signature = hashlib.md5(f"{out_sum}:{payment_id}:secret-key".encode()).hexdigest().upper()
    request = _build_request(
        (
            f"InvId={payment_id}&OutSum={out_sum}&Status=SUCCESS&SignatureValue={signature}"
        ).encode(),
        "application/x-www-form-urlencoded",
    )

    metrics: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "src.infrastructure.payment_gateways.pal24.emit_counter",
        lambda name, /, **labels: metrics.append((name, labels)),
    )

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED
    assert (
        "payment_gateway_webhook_mode_total",
        {
            "gateway_type": PaymentGatewayType.PAL24.value,
            "mode": "official_form_postback",
        },
    ) in metrics


def test_handle_create_payment_propagates_official_http_errors() -> None:
    gateway = _build_gateway()
    create_bill = AsyncMock(side_effect=_build_not_found_error(method="POST", path="/bill/create"))
    setattr(gateway, "_create_bill", create_bill)

    with pytest.raises(HTTPStatusError):
        asyncio.run(gateway.handle_create_payment(amount=Decimal("25"), details="order"))

    assert create_bill.await_count == 1


def test_get_bill_info_uses_official_status_contract_without_api_token() -> None:
    gateway = _build_gateway()
    client_get = AsyncMock(
        return_value=Response(
            200,
            request=Request("GET", "https://pal24.pro/api/v1/bill/status"),
            content=b'{"success":true,"status":"SUCCESS"}',
        )
    )
    setattr(gateway._client, "get", client_get)

    result = asyncio.run(gateway.get_bill_info("bill-1"))

    assert result["status"] == "SUCCESS"
    assert client_get.await_args is not None
    assert client_get.await_args.kwargs["params"] == {"id": "bill-1"}
    assert "apiToken" not in client_get.await_args.kwargs["params"]


def test_handle_webhook_rejects_legacy_json_contract() -> None:
    gateway = _build_gateway()
    request = _build_request(
        b'{"order_id":"00000000-0000-0000-0000-000000000456","status":"paid"}',
        "application/json",
    )

    with pytest.raises(ValueError, match="Invalid webhook payload"):
        asyncio.run(gateway.handle_webhook(request))
