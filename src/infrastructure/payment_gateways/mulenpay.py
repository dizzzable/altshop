"""MulenPay payment gateway implementation."""

from decimal import Decimal
from typing import Any, Final
from uuid import UUID

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

    API_BASE: Final[str] = "https://mulenpay.ru"
    DEFAULT_CURRENCY: Final[str] = "RUB"

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
                "Content-Type": "application/json",
                "api-key": api_key,
                "X-API-Key": api_key,
            },
        )

    async def handle_create_payment(
        self,
        amount: Decimal,
        details: str,
        payment_asset: CryptoAsset | None = None,
        success_redirect_url: str | None = None,
        fail_redirect_url: str | None = None,
        is_test_payment: bool = False,
    ) -> PaymentResult:
        default_redirect_url = await self._get_bot_redirect_url()
        payload: dict[str, Any] = {
            "amount": self._format_amount(amount),
            "currency": self.DEFAULT_CURRENCY,
            "description": details[:255],
        }
        if success_redirect_url or default_redirect_url:
            payload["successUrl"] = success_redirect_url or default_redirect_url
        if fail_redirect_url:
            payload["failUrl"] = fail_redirect_url
        if self.config is not None:
            payload["callbackUrl"] = self.config.get_webhook(self.gateway.type)

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

        raw_payment_id = data.get("uuid") or data.get("id")
        payment_url = data.get("paymentUrl") or data.get("url")
        if not raw_payment_id or not payment_url:
            raise KeyError("Invalid response from MulenPay API")

        try:
            payment_id = UUID(str(raw_payment_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format returned by MulenPay") from exception

        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        body = await request.body()
        try:
            payload = orjson.loads(body)
        except orjson.JSONDecodeError as exception:
            raise ValueError("Invalid MulenPay webhook payload") from exception

        if not isinstance(payload, dict):
            raise ValueError("Invalid MulenPay webhook payload")

        raw_payment_id = payload.get("uuid") or payload.get("payment_uuid") or payload.get("id")
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
        if normalized in {"failed", "canceled", "cancelled", "expired"}:
            return TransactionStatus.CANCELED
        raise ValueError(f"Unsupported MulenPay status: {status}")
