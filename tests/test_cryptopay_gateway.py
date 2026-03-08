from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import orjson
from aiogram import Bot
from pydantic import SecretStr

from src.core.enums import CryptoAsset, Currency, PaymentGatewayType
from src.infrastructure.database.models.dto import (
    CryptopayGatewaySettingsDto,
    PaymentGatewayDto,
)
from src.infrastructure.payment_gateways.cryptopay import CryptopayGateway


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.content = orjson.dumps(payload)
        self.status_code = status_code
        self.text = self.content.decode()

    def raise_for_status(self) -> None:
        return None


def _build_gateway() -> CryptopayGateway:
    gateway = PaymentGatewayDto(
        id=1,
        order_index=1,
        type=PaymentGatewayType.CRYPTOPAY,
        currency=Currency.USD,
        is_active=True,
        settings=CryptopayGatewaySettingsDto(
            api_key=SecretStr("secret-key"),
        ),
    )
    return CryptopayGateway(
        gateway=gateway,
        bot=cast(Bot, SimpleNamespace(get_me=AsyncMock())),
    )


def test_handle_create_payment_uses_fiat_invoice_mode_with_selected_asset() -> None:
    gateway = _build_gateway()
    post = AsyncMock(
        return_value=_FakeHttpResponse(
            {
                "ok": True,
                "result": {
                    "invoice_id": 101,
                    "bot_invoice_url": "https://pay.crypt.bot/invoice/101",
                },
            }
        )
    )
    gateway._client = cast(object, SimpleNamespace(post=post))

    result = asyncio.run(
        gateway.handle_create_payment(
            amount=Decimal("10.50"),
            details="order",
            payment_asset=CryptoAsset.USDC,
            success_redirect_url="https://example.com/success",
        )
    )

    assert result.url == "https://pay.crypt.bot/invoice/101"
    payload = post.await_args.kwargs["json"]
    assert payload["currency_type"] == "fiat"
    assert payload["fiat"] == Currency.USD.value
    assert payload["amount"] == "10.50"
    assert payload["accepted_assets"] == CryptoAsset.USDC.value
    assert payload["paid_btn_name"] == "callback"
    assert payload["paid_btn_url"] == "https://example.com/success"
