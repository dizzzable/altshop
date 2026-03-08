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

from src.api.endpoints.payments import yoomoney_redirect
from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    PartnerSettingsDto,
    PaymentGatewayDto,
    YoomoneyGatewaySettingsDto,
)
from src.infrastructure.payment_gateways.yoomoney import (
    YoomoneyGateway,
    parse_yoomoney_redirect_token,
)


def _build_gateway() -> YoomoneyGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.YOOMONEY,
        currency=Currency.RUB,
        is_active=True,
        settings=YoomoneyGatewaySettingsDto(
            wallet_id="4100111111111111",
            secret_key=SecretStr("wallet-secret"),
        ),
    )
    config = SimpleNamespace(
        domain=SecretStr("example.test"),
        crypt_key=SecretStr("redirect-signature-secret"),
    )
    return YoomoneyGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
        config=config,
    )


def _build_request(
    *,
    body: bytes = b"",
    method: str = "POST",
    token_secret: str = "redirect-signature-secret",
) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": "/api/v1/payments/yoomoney/redirect",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
        "app": SimpleNamespace(
            state=SimpleNamespace(config=SimpleNamespace(crypt_key=SecretStr(token_secret)))
        ),
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def test_handle_create_payment_builds_signed_local_redirect_url() -> None:
    gateway = _build_gateway()

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("12.30"),
            details="VPN subscription",
            success_redirect_url="https://example.test/webapp/dashboard/subscription?payment=success",
        )
    )

    assert result.url is not None
    parsed = urlparse(result.url)
    assert parsed.netloc == "example.test"
    assert parsed.path == "/api/v1/payments/yoomoney/redirect"

    token = parse_qs(parsed.query)["token"][0]
    form_fields = parse_yoomoney_redirect_token(
        token=token,
        signing_secret="redirect-signature-secret",
    )

    assert form_fields["receiver"] == "4100111111111111"
    assert form_fields["quickpay-form"] == YoomoneyGateway.QUICKPAY_FORM
    assert form_fields["paymentType"] == YoomoneyGateway.DEFAULT_PAYMENT_TYPE
    assert form_fields["sum"] == "12.30"
    assert form_fields["label"] == str(result.id)
    assert form_fields["targets"] == "VPN subscription"
    assert (
        form_fields["successURL"]
        == "https://example.test/webapp/dashboard/subscription?payment=success"
    )


def test_yoomoney_redirect_endpoint_renders_auto_submit_form() -> None:
    token = parse_qs(
        urlparse(
            asyncio.run(
                _build_gateway().handle_create_payment(
                    amount=Decimal("9.99"),
                    details="order",
                    success_redirect_url="https://example.test/success",
                )
            ).url
        ).query
    )["token"][0]
    request = _build_request(method="GET")

    response = asyncio.run(yoomoney_redirect(token=token, request=request))

    assert response.status_code == 200
    assert b"https://yoomoney.ru/quickpay/confirm" in response.body
    assert b'name="receiver"' in response.body
    assert b'name="label"' in response.body
    assert b"redirect-form" in response.body


def test_yoomoney_redirect_endpoint_rejects_invalid_token() -> None:
    response = asyncio.run(
        yoomoney_redirect(token="bad-token", request=_build_request(method="GET"))
    )

    assert response.status_code == 400


def test_handle_webhook_accepts_signed_yoomoney_notification() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    payload = {
        "notification_type": "p2p-in",
        "operation_id": "5555",
        "amount": "12.30",
        "currency": "643",
        "datetime": "2026-03-07T14:00:00Z",
        "sender": "4100111111111111",
        "codepro": "false",
        "label": str(payment_id),
    }
    payload["sha1_hash"] = gateway._calculate_webhook_signature(payload)
    body = "&".join(f"{key}={value}" for key, value in payload.items()).encode()

    resolved_payment_id, status = asyncio.run(gateway.handle_webhook(_build_request(body=body)))

    assert resolved_payment_id == payment_id
    assert status == TransactionStatus.COMPLETED


def test_handle_webhook_maps_codepro_notification_to_pending() -> None:
    gateway = _build_gateway()
    payment_id = UUID("00000000-0000-0000-0000-000000000123")
    payload = {
        "notification_type": "card-in",
        "operation_id": "5555",
        "amount": "12.30",
        "currency": "643",
        "datetime": "2026-03-07T14:00:00Z",
        "sender": "4100111111111111",
        "codepro": "true",
        "label": str(payment_id),
    }
    payload["sha1_hash"] = gateway._calculate_webhook_signature(payload)
    body = "&".join(f"{key}={value}" for key, value in payload.items()).encode()

    _, status = asyncio.run(gateway.handle_webhook(_build_request(body=body)))

    assert status == TransactionStatus.PENDING


def test_handle_webhook_rejects_invalid_signature() -> None:
    gateway = _build_gateway()
    body = (
        "notification_type=p2p-in&operation_id=5555&amount=12.30&currency=643&"
        "datetime=2026-03-07T14:00:00Z&sender=4100111111111111&codepro=false&"
        "label=00000000-0000-0000-0000-000000000123&sha1_hash=bad"
    ).encode()

    with pytest.raises(PermissionError, match="Invalid YooMoney webhook signature"):
        asyncio.run(gateway.handle_webhook(_build_request(body=body)))


def test_partner_settings_expose_yoomoney_commission() -> None:
    settings = PartnerSettingsDto()

    assert settings.get_gateway_commission("YOOMONEY") == settings.yoomoney_commission
