from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import orjson
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from pydantic import SecretStr

from src.core.enums import Currency, PaymentGatewayType, TransactionStatus
from src.infrastructure.database.models.dto import (
    CryptopayGatewaySettingsDto,
    MulenpayGatewaySettingsDto,
    PaymentGatewayDto,
    WataGatewaySettingsDto,
)
from src.infrastructure.payment_gateways.cryptopay import CryptopayGateway
from src.infrastructure.payment_gateways.mulenpay import MulenpayGateway
from src.infrastructure.payment_gateways.wata import WataGateway


def run_async(coroutine):
    return asyncio.run(coroutine)


class FakeRequest:
    def __init__(
        self,
        *,
        body: bytes,
        headers: dict[str, str] | None = None,
        path_params: dict[str, str] | None = None,
    ) -> None:
        self._body = body
        self.headers = headers or {}
        self.path_params = path_params or {}

    async def body(self) -> bytes:
        return self._body


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.content = orjson.dumps(payload)

    def raise_for_status(self) -> None:
        return None


def build_cryptopay_gateway(*, token: str = "token:secret") -> CryptopayGateway:
    gateway = PaymentGatewayDto(
        order_index=1,
        type=PaymentGatewayType.CRYPTOPAY,
        currency=Currency.USD,
        is_active=True,
        settings=CryptopayGatewaySettingsDto(api_key=SecretStr(token)),
    )
    return CryptopayGateway(
        gateway=gateway,
        bot=SimpleNamespace(),
        config=None,
    )


def build_mulenpay_gateway(
    *,
    shop_id: str | None = "5",
    secret_key: str | None = "mulen-signing-secret",
    webhook_secret: str | None = "mulen-secret",
) -> MulenpayGateway:
    gateway = PaymentGatewayDto(
        order_index=1,
        type=PaymentGatewayType.MULENPAY,
        currency=Currency.RUB,
        is_active=True,
        settings=MulenpayGatewaySettingsDto(
            shop_id=shop_id,
            api_key=SecretStr("mulen-api-key"),
            secret_key=SecretStr(secret_key) if secret_key is not None else None,
            webhook_secret=SecretStr(webhook_secret) if webhook_secret is not None else None,
        ),
    )
    return MulenpayGateway(
        gateway=gateway,
        bot=SimpleNamespace(
            get_me=AsyncMock(return_value=SimpleNamespace(username="altshop_test_bot"))
        ),
        config=SimpleNamespace(
            get_webhook=lambda _gateway_type: "https://example.test/api/v1/payments/mulenpay"
        ),
    )


def build_wata_gateway(*, public_key_pem: str | None = None) -> WataGateway:
    gateway = PaymentGatewayDto(
        order_index=1,
        type=PaymentGatewayType.WATA,
        currency=Currency.RUB,
        is_active=True,
        settings=WataGatewaySettingsDto(access_token=SecretStr("wata-token")),
    )
    wata_gateway = WataGateway(
        gateway=gateway,
        bot=SimpleNamespace(),
        config=None,
    )
    if public_key_pem is not None:
        wata_gateway._public_key_cache = public_key_pem
        wata_gateway._public_key_loaded_at = datetime.now(timezone.utc)
    return wata_gateway


def build_wata_signature(body: bytes) -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    signature = private_key.sign(body, padding.PKCS1v15(), hashes.SHA512())
    return public_key_pem, base64.b64encode(signature).decode("ascii")


@pytest.mark.parametrize(
    ("status", "expected_status"),
    [
        ("paid", TransactionStatus.COMPLETED),
        ("expired", TransactionStatus.CANCELED),
    ],
)
def test_cryptopay_handle_webhook_verifies_signature_and_maps_status(
    status: str,
    expected_status: TransactionStatus,
) -> None:
    gateway = build_cryptopay_gateway()
    payment_id = uuid4()
    body = orjson.dumps(
        {
            "update_type": "invoice_paid",
            "request_date": "2026-03-26T17:00:00+00:00",
            "payload": {
                "payload": str(payment_id),
                "status": status,
            },
        }
    )
    secret = hashlib.sha256("token:secret".encode("utf-8")).digest()
    signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

    resolved_payment_id, resolved_status = run_async(
        gateway.handle_webhook(
            FakeRequest(
                body=body,
                headers={"crypto-pay-api-signature": signature},
            )
        )
    )

    assert resolved_payment_id == payment_id
    assert resolved_status == expected_status


def test_cryptopay_handle_webhook_rejects_invalid_signature() -> None:
    gateway = build_cryptopay_gateway()
    body = orjson.dumps(
        {
            "update_type": "invoice_paid",
            "request_date": "2026-03-26T17:00:00+00:00",
            "payload": {
                "payload": str(uuid4()),
                "status": "paid",
            },
        }
    )

    with pytest.raises(PermissionError, match="Invalid Crypto Pay webhook signature"):
        run_async(
            gateway.handle_webhook(
                FakeRequest(
                    body=body,
                    headers={"crypto-pay-api-signature": "invalid"},
                )
            )
        )


@pytest.mark.parametrize(
    ("status", "expected_status"),
    [
        ("success", TransactionStatus.COMPLETED),
        ("cancel", TransactionStatus.CANCELED),
    ],
)
def test_mulenpay_handle_webhook_requires_secret_path_and_maps_status(
    status: str,
    expected_status: TransactionStatus,
) -> None:
    gateway = build_mulenpay_gateway()
    payment_id = uuid4()
    request = FakeRequest(
        body=orjson.dumps(
            {
                "id": 12345,
                "uuid": str(payment_id),
                "payment_status": status,
            }
        ),
        path_params={"webhook_secret": "mulen-secret"},
    )

    resolved_payment_id, resolved_status = run_async(gateway.handle_webhook(request))

    assert resolved_payment_id == payment_id
    assert resolved_status == expected_status


def test_mulenpay_handle_webhook_rejects_missing_secret_path() -> None:
    gateway = build_mulenpay_gateway()
    request = FakeRequest(
        body=orjson.dumps(
            {
                "id": 12345,
                "uuid": str(uuid4()),
                "payment_status": "success",
            }
        )
    )

    with pytest.raises(PermissionError, match="Invalid MulenPay webhook secret"):
        run_async(gateway.handle_webhook(request))


def test_mulenpay_handle_webhook_requires_internal_uuid() -> None:
    gateway = build_mulenpay_gateway()
    request = FakeRequest(
        body=orjson.dumps(
            {
                "id": 12345,
                "payment_status": "success",
            }
        ),
        path_params={"webhook_secret": "mulen-secret"},
    )

    with pytest.raises(ValueError, match="Missing MulenPay webhook fields"):
        run_async(gateway.handle_webhook(request))


def test_mulenpay_create_payment_uses_documented_request_contract_and_internal_uuid() -> None:
    gateway = build_mulenpay_gateway()
    gateway._client = SimpleNamespace(  # type: ignore[assignment]
        post=AsyncMock(
            return_value=FakeResponse(
                {
                    "id": 12345,
                    "paymentUrl": "https://mulenpay.test/pay",
                }
            )
        )
    )

    result = run_async(
        gateway.handle_create_payment(
            amount=Decimal("99.99"),
            details="VPN subscription",
            success_redirect_url="https://example.test/webapp/payment-success",
            fail_redirect_url="https://example.test/webapp/payment-failed",
        )
    )

    payload = orjson.loads(gateway._client.post.await_args.kwargs["content"])
    assert result.id == UUID(payload["uuid"])
    assert result.url == "https://mulenpay.test/pay"
    assert payload == {
        "currency": "rub",
        "amount": "99.99",
        "uuid": str(result.id),
        "shopId": 5,
        "description": "VPN subscription",
        "website_url": "https://example.test/webapp/payment-success",
        "items": [
            {
                "description": "VPN subscription",
                "quantity": 1,
                "price": 99.99,
                "vat_code": 0,
                "payment_subject": 4,
                "payment_mode": 4,
            }
        ],
        "sign": hashlib.sha1("rub99.995mulen-signing-secret".encode("utf-8")).hexdigest(),
    }
    assert (
        gateway._client.post.await_args.args[0]
        == "/v2/payments"
    )
    assert "successUrl" not in payload
    assert "failUrl" not in payload
    assert "callbackUrl" not in payload


def test_mulenpay_create_payment_requires_webhook_secret_when_security_is_configured() -> None:
    gateway = build_mulenpay_gateway(webhook_secret=None)
    gateway._client = SimpleNamespace(post=AsyncMock())  # type: ignore[assignment]

    with pytest.raises(ValueError, match="MulenPay webhook_secret is required"):
        run_async(
            gateway.handle_create_payment(
                amount=Decimal("10.00"),
                details="VPN subscription",
            )
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"shop_id": None}, "MulenPay shop_id is required"),
        ({"secret_key": None}, "MulenPay secret_key is required"),
    ],
)
def test_mulenpay_create_payment_requires_documented_signing_settings(
    kwargs: dict[str, str | None],
    message: str,
) -> None:
    gateway = build_mulenpay_gateway(**kwargs)
    gateway._client = SimpleNamespace(post=AsyncMock())  # type: ignore[assignment]

    with pytest.raises(ValueError, match=message):
        run_async(
            gateway.handle_create_payment(
                amount=Decimal("10.00"),
                details="VPN subscription",
            )
        )


@pytest.mark.parametrize(
    ("status", "expected_status"),
    [
        ("Paid", TransactionStatus.COMPLETED),
        ("Declined", TransactionStatus.CANCELED),
    ],
)
def test_wata_handle_webhook_requires_signature_and_maps_status(
    status: str,
    expected_status: TransactionStatus,
) -> None:
    payment_id = uuid4()
    body = orjson.dumps(
        {
            "orderId": str(payment_id),
            "transactionStatus": status,
        }
    )
    public_key_pem, signature = build_wata_signature(body)
    gateway = build_wata_gateway(public_key_pem=public_key_pem)

    resolved_payment_id, resolved_status = run_async(
        gateway.handle_webhook(
            FakeRequest(
                body=body,
                headers={"X-Signature": signature},
            )
        )
    )

    assert resolved_payment_id == payment_id
    assert resolved_status == expected_status


def test_wata_handle_webhook_rejects_missing_signature() -> None:
    gateway = build_wata_gateway()
    body = orjson.dumps(
        {
            "orderId": str(uuid4()),
            "transactionStatus": "Paid",
        }
    )

    with pytest.raises(PermissionError, match="Missing WATA webhook signature"):
        run_async(gateway.handle_webhook(FakeRequest(body=body)))


def test_wata_handle_webhook_rejects_invalid_signature_encoding() -> None:
    body = orjson.dumps(
        {
            "orderId": str(uuid4()),
            "transactionStatus": "Paid",
        }
    )
    public_key_pem, _signature = build_wata_signature(body)
    gateway = build_wata_gateway(public_key_pem=public_key_pem)

    with pytest.raises(PermissionError, match="Invalid WATA webhook signature"):
        run_async(
            gateway.handle_webhook(
                FakeRequest(
                    body=body,
                    headers={"X-Signature": "not-valid-base64-or-hex"},
                )
            )
        )
