from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID

import orjson
import pytest
from aiogram import Bot
from httpx import HTTPStatusError, Request, Response
from pydantic import SecretStr

from src.core.enums import CryptoAsset, Currency, PaymentGatewayType
from src.infrastructure.database.models.dto import (
    HeleketGatewaySettingsDto,
    PaymentGatewayDto,
)
from src.infrastructure.payment_gateways.heleket import HeleketGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.content = orjson.dumps(payload)
        self.status_code = status_code
        self.text = self.content.decode()

    def raise_for_status(self) -> None:
        return None


def _build_gateway() -> HeleketGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.HELEKET,
        currency=Currency.USD,
        is_active=True,
        settings=HeleketGatewaySettingsDto(
            merchant_id="merchant-1",
            api_key=SecretStr("secret-key"),
        ),
    )
    return HeleketGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def _build_not_found_error(*, method: str, path: str) -> HTTPStatusError:
    request = Request(method, f"https://api.heleket.com{path}")
    response = Response(404, request=request, text="Route not found")
    return HTTPStatusError("route missing", request=request, response=response)


def test_handle_create_payment_uses_v1_payload_and_emits_v1_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _build_gateway()
    create_payment_v1 = AsyncMock(
        return_value=(
            200,
            {"result": {"url": "https://pay.example/invoice"}},
            '{"result":{"url":"https://pay.example/invoice"}}',
        )
    )
    setattr(gateway, "_create_payment_v1", create_payment_v1)

    metrics: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "src.infrastructure.payment_gateways.heleket.emit_counter",
        lambda name, /, **labels: metrics.append((name, labels)),
    )

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("9.99"),
            details="order",
            payment_asset=CryptoAsset.USDT,
            success_redirect_url="https://example.com/success",
            fail_redirect_url="https://example.com/fail",
        )
    )

    assert result.url == "https://pay.example/invoice"
    assert (
        "payment_gateway_request_mode_total",
        {
            "gateway_type": PaymentGatewayType.HELEKET.value,
            "operation": "create_payment",
            "mode": "v1",
        },
    ) in metrics
    assert create_payment_v1.await_args is not None
    payload = create_payment_v1.await_args.args[0]
    assert payload["url_success"] == "https://example.com/success"
    assert payload["url_return"] == "https://example.com/fail"
    assert "success_url" not in payload
    assert "fail_url" not in payload
    assert payload["to_currency"] == CryptoAsset.USDT.value


def test_get_invoice_info_emits_v1_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = _build_gateway()
    setattr(
        gateway,
        "_client",
        cast(
            Any,
            SimpleNamespace(
                post=AsyncMock(return_value=_FakeHttpResponse({"uuid": "inv-1"})),
            ),
        ),
    )

    metrics: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "src.infrastructure.payment_gateways.heleket.emit_counter",
        lambda name, /, **labels: metrics.append((name, labels)),
    )

    result = asyncio.run(gateway.get_invoice_info("inv-1"))

    assert result == {"uuid": "inv-1"}
    assert (
        "payment_gateway_request_mode_total",
        {
            "gateway_type": PaymentGatewayType.HELEKET.value,
            "operation": "payment_info",
            "mode": "v1",
        },
    ) in metrics


def test_create_payment_v1_signs_exact_request_body() -> None:
    gateway = _build_gateway()
    post = AsyncMock(return_value=_FakeHttpResponse({"result": {"url": "https://pay.example"}}))
    gateway._client = cast(Any, SimpleNamespace(post=post))
    payload = {
        "amount": "5.00",
        "currency": "USD",
        "order_id": "fd43d8fc-fee9-4c9c-861d-2ec93ee3828e",
        "description": "Покупка подписки 🌓 test",
        "url_success": "https://example.com/success",
        "url_return": "https://example.com/fail",
        "to_currency": CryptoAsset.USDT.value,
    }

    asyncio.run(gateway._create_payment_v1(payload))

    kwargs = post.await_args.kwargs
    body = kwargs["content"]
    assert "json" not in kwargs
    assert body == orjson.dumps(payload)
    assert kwargs["headers"]["merchant"] == "merchant-1"
    assert kwargs["headers"]["sign"] == gateway._calculate_v1_sign_from_body(body, "secret-key")


def test_get_invoice_info_signs_exact_request_body() -> None:
    gateway = _build_gateway()
    post = AsyncMock(return_value=_FakeHttpResponse({"uuid": "inv-1"}))
    gateway._client = cast(Any, SimpleNamespace(post=post))

    asyncio.run(gateway.get_invoice_info("inv-1"))

    kwargs = post.await_args.kwargs
    body = kwargs["content"]
    assert "json" not in kwargs
    assert body == orjson.dumps({"uuid": "inv-1"})
    assert kwargs["headers"]["sign"] == gateway._calculate_v1_sign_from_body(body, "secret-key")


def test_verify_webhook_signature_emits_v1_signature_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = _build_gateway()
    body = orjson.dumps({"order_id": str(UUID(int=1)), "status": "paid"})
    signature = gateway._calculate_v1_sign_from_body(body, "secret-key")

    metrics: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "src.infrastructure.payment_gateways.heleket.emit_counter",
        lambda name, /, **labels: metrics.append((name, labels)),
    )

    gateway._verify_webhook_signature(body, signature)

    assert (
        "payment_gateway_webhook_signature_mode_total",
        {
            "gateway_type": PaymentGatewayType.HELEKET.value,
            "mode": "v1",
        },
    ) in metrics


def test_handle_create_payment_propagates_v1_http_errors() -> None:
    gateway = _build_gateway()
    create_payment_v1 = AsyncMock(
        side_effect=_build_not_found_error(method="POST", path="/v1/payment")
    )
    setattr(gateway, "_create_payment_v1", create_payment_v1)

    with pytest.raises(HTTPStatusError):
        asyncio.run(
            gateway.handle_create_payment(
                amount=Decimal("9.99"),
                details="order",
            )
        )

    assert create_payment_v1.await_count == 1


def test_verify_webhook_signature_rejects_legacy_signature() -> None:
    gateway = _build_gateway()
    body = orjson.dumps({"order_id": str(UUID(int=1)), "status": "paid"})
    legacy_signature = hashlib.sha256(body + b"secret-key").hexdigest()

    with pytest.raises(PermissionError, match="Invalid Heleket webhook signature"):
        gateway._verify_webhook_signature(body, legacy_signature)
