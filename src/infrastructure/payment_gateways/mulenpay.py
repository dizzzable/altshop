"""MulenPay payment gateway implementation."""

import hashlib
import hmac
from decimal import Decimal
from typing import Any, Final
from uuid import UUID, uuid4

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    MulenpayGatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class MulenpayGateway(BasePaymentGateway):
    """MulenPay redirect checkout gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://mulenpay.ru/api"
    DEFAULT_CURRENCY: Final[str] = "rub"

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, MulenpayGatewaySettingsDto):
            raise TypeError("MulenpayGateway requires MulenpayGatewaySettingsDto")

        api_key = self._get_api_key()
        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def handle_create_payment(
        self,
        amount: Decimal,
        details: str,
        payment_id: UUID | None = None,
        payment_asset: CryptoAsset | None = None,
        success_redirect_url: str | None = None,
        fail_redirect_url: str | None = None,
        is_test_payment: bool = False,
    ) -> PaymentResult:
        default_redirect_url = await self._get_bot_redirect_url()
        if self.config is not None:
            self._get_webhook_secret()

        payment_id = payment_id or uuid4()
        payload = self._build_create_payment_payload(
            payment_id=payment_id,
            amount=amount,
            details=details,
            website_url=success_redirect_url or fail_redirect_url or default_redirect_url,
        )

        try:
            response = await self._client.post("/v2/payments", content=orjson.dumps(payload))
            response.raise_for_status()
            data = orjson.loads(response.content)
        except HTTPStatusError as exception:
            logger.error(
                "MulenPay create payment failed. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise

        payment_url = data.get("paymentUrl") or data.get("url")
        if not payment_url:
            raise KeyError("Invalid response from MulenPay API")

        logger.debug(
            "MulenPay payment created. payment_id='{}' external_id='{}'",
            payment_id,
            data.get("id"),
        )

        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        body = await request.body()
        self._verify_webhook_secret(request)
        try:
            payload = orjson.loads(body)
        except orjson.JSONDecodeError as exception:
            raise ValueError("Invalid MulenPay webhook payload") from exception

        if not isinstance(payload, dict):
            raise ValueError("Invalid MulenPay webhook payload")

        raw_payment_id = payload.get("uuid") or payload.get("payment_uuid")
        status = payload.get("payment_status") or payload.get("status")
        if not raw_payment_id or not status:
            raise ValueError("Missing MulenPay webhook fields")

        try:
            payment_id = UUID(str(raw_payment_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format for MulenPay payment") from exception

        return payment_id, self._map_status(status)

    def _get_api_key(self) -> str:
        api_key = self.gateway.settings.api_key
        secret = api_key.get_secret_value().strip() if api_key else ""
        if not secret:
            raise ValueError("MulenPay api_key is required")
        return secret

    def _get_shop_id(self) -> int:
        shop_id = (self.gateway.settings.shop_id or "").strip()
        if not shop_id:
            raise ValueError("MulenPay shop_id is required")

        try:
            return int(shop_id)
        except ValueError as exception:
            raise ValueError("MulenPay shop_id must be an integer") from exception

    def _get_secret_key(self) -> str:
        secret_key = self.gateway.settings.secret_key
        secret = secret_key.get_secret_value().strip() if secret_key else ""
        if not secret:
            raise ValueError("MulenPay secret_key is required")
        return secret

    def _get_webhook_secret(self) -> str:
        webhook_secret = self.gateway.settings.webhook_secret
        secret = webhook_secret.get_secret_value().strip() if webhook_secret else ""
        if not secret:
            raise ValueError("MulenPay webhook_secret is required")
        return secret

    def _verify_webhook_secret(self, request: Request) -> None:
        request_secret = str(getattr(request, "path_params", {}).get("webhook_secret") or "")
        configured_secret = self._get_webhook_secret()
        if not request_secret or not hmac.compare_digest(request_secret, configured_secret):
            raise PermissionError("Invalid MulenPay webhook secret")

    def _build_create_payment_payload(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        details: str,
        website_url: str | None,
    ) -> dict[str, Any]:
        currency = self.DEFAULT_CURRENCY
        amount_value = self._format_amount(amount)
        shop_id = self._get_shop_id()
        payload: dict[str, Any] = {
            "currency": currency,
            "amount": amount_value,
            "uuid": str(payment_id),
            "shopId": shop_id,
            "description": details[:255],
            "items": [self._build_item(amount=amount, details=details)],
            "sign": self._build_signature(
                currency=currency,
                amount=amount_value,
                shop_id=shop_id,
            ),
        }
        if website_url:
            payload["website_url"] = website_url
        return payload

    def _build_signature(self, *, currency: str, amount: str, shop_id: int) -> str:
        signature_payload = f"{currency}{amount}{shop_id}{self._get_secret_key()}"
        return hashlib.sha1(signature_payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_item(*, amount: Decimal, details: str) -> dict[str, Any]:
        return {
            "description": details[:255],
            "quantity": 1,
            "price": float(amount.quantize(Decimal("0.01"))),
            "vat_code": 0,
            "payment_subject": 4,
            "payment_mode": 4,
        }

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")

    @staticmethod
    def _map_status(status: object) -> TransactionStatus:
        normalized = str(status or "").lower()
        if normalized in {"paid", "success", "completed", "succeeded"}:
            return TransactionStatus.COMPLETED
        if normalized in {"pending", "processing", "waiting"}:
            return TransactionStatus.PENDING
        if normalized in {"failed", "cancel", "canceled", "cancelled", "expired"}:
            return TransactionStatus.CANCELED
        raise ValueError(f"Unsupported MulenPay status: {status}")
