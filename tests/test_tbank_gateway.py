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
from src.infrastructure.database.models.dto import PaymentGatewayDto, TbankGatewaySettingsDto
from src.infrastructure.payment_gateways.tbank import TbankGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.content = orjson.dumps(payload)
        self.status_code = status_code
        self.text = self.content.decode()

    def raise_for_status(self) -> None:
        return None


def _build_gateway() -> TbankGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.TBANK,
        currency=Currency.RUB,
        is_active=True,
        settings=TbankGatewaySettingsDto(
            terminal_key="terminal-key",
            password=SecretStr("terminal-password"),
        ),
    )
    return TbankGateway(
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


def test_handle_create_payment_extracts_payment_url_and_signs_payload() -> None:
    gateway = _build_gateway()
    post = AsyncMock(
        return_value=_FakeHttpResponse(
            {
                "Success": True,
                "PaymentURL": "https://securepay.tinkoff.ru/pay/1",
            }
        )
    )
    gateway._client = cast(object, SimpleNamespace(post=post))

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("10.50"),
            details="order",
            success_redirect_url="https://example.com/success",
            fail_redirect_url="https://example.com/fail",
        )
    )

    assert result.url == "https://securepay.tinkoff.ru/pay/1"
    payload = orjson.loads(post.await_args.kwargs["content"])
    assert payload["TerminalKey"] == "terminal-key"
    assert payload["Amount"] == 1050
    assert payload["NotificationURL"] == "https://example.com/webhook"
    assert payload["SuccessURL"] == "https://example.com/success"
    assert payload["FailURL"] == "https://example.com/fail"
    assert UUID(payload["OrderId"])
    assert payload["Token"] == gateway._generate_token(payload)


def test_handle_webhook_validates_token_and_maps_status() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000321")
    payload = {
        "TerminalKey": "terminal-key",
        "OrderId": str(payment_id),
        "Status": "CONFIRMED",
    }
    payload["Token"] = gateway._generate_token(payload)
    request = _build_request(payload)

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_handle_webhook_rejects_invalid_token() -> None:
    gateway = _build_gateway()
    request = _build_request(
        {
            "TerminalKey": "terminal-key",
            "OrderId": "00000000-0000-0000-0000-000000000321",
            "Status": "CONFIRMED",
            "Token": "wrong-token",
        }
    )

    with pytest.raises(PermissionError, match="Invalid T-Bank webhook token"):
        asyncio.run(gateway.handle_webhook(request))


def test_get_state_uses_signed_payload() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000999")
    post = AsyncMock(
        return_value=_FakeHttpResponse(
            {
                "Success": True,
                "Status": "NEW",
            }
        )
    )
    gateway._client = cast(object, SimpleNamespace(post=post))

    payload = asyncio.run(gateway.get_state(payment_id))

    assert payload["Status"] == "NEW"
    request_payload = orjson.loads(post.await_args.kwargs["content"])
    assert request_payload["OrderId"] == str(payment_id)
    assert request_payload["Token"] == gateway._generate_token(request_payload)


def test_build_webhook_response_returns_provider_ack() -> None:
    gateway = _build_gateway()
    response = asyncio.run(gateway.build_webhook_response(_build_request({})))

    assert response.body == b"OK"
