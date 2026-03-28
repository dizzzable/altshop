"""Cryptomus payment gateway implementation."""

import base64
import hashlib
import hmac
import uuid
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
    CryptomusGatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class CryptomusGateway(BasePaymentGateway):
    """Cryptomus hosted checkout gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://api.cryptomus.com"
    DEFAULT_CURRENCY: Final[str] = "USD"

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, CryptomusGatewaySettingsDto):
            raise TypeError("CryptomusGateway requires CryptomusGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "merchant": self._get_merchant_id(),
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
        payment_id = payment_id or uuid.uuid4()
        default_redirect_url = await self._get_bot_redirect_url()
        redirect_url = success_redirect_url or default_redirect_url
        payload = {
            "amount": self._format_amount(amount),
            "currency": self.DEFAULT_CURRENCY,
            "order_id": str(payment_id),
            "description": details[:255],
            "url_return": fail_redirect_url or redirect_url,
            "url_success": redirect_url,
            "is_payment_multiple": False,
            "lifetime": 3600,
        }
        if payment_asset is not None:
            payload["to_currency"] = payment_asset.value
        if self.config is not None:
            payload["url_callback"] = self.config.get_webhook(self.gateway.type)

        try:
            status_code, data, response_body = await self._create_payment(payload)
        except HTTPStatusError as exception:
            logger.error(
                "Cryptomus create payment failed. payment_id='{}' payment_asset='{}' "
                "status='{}' body='{}'",
                payment_id,
                payment_asset.value if payment_asset else None,
                exception.response.status_code,
                exception.response.text,
            )
            raise

        result = data.get("result", {})
        if not isinstance(result, dict):
            raise ValueError("Invalid response from Cryptomus API")

        payment_url = (
            result.get("url")
            or result.get("payment_url")
            or result.get("address_qr_code")
        )
        if not payment_url:
            raise KeyError("Invalid response from Cryptomus API: missing payment URL")

        logger.info(
            "Cryptomus invoice created. payment_id='{}' payment_asset='{}' "
            "status='{}' body='{}'",
            payment_id,
            payment_asset.value if payment_asset else None,
            status_code,
            response_body,
        )
        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        body = await request.body()
        signature = request.headers.get("sign") or request.headers.get("Sign")
        if not signature:
            raise PermissionError("Missing Cryptomus webhook signature")
        self._verify_signature(body, signature)

        try:
            payload = orjson.loads(body)
        except orjson.JSONDecodeError as exception:
            raise ValueError("Invalid Cryptomus webhook payload") from exception

        if not isinstance(payload, dict):
            raise ValueError("Invalid Cryptomus webhook payload")

        raw_payment_id = payload.get("order_id") or payload.get("orderId")
        status = payload.get("status") or payload.get("payment_status")
        if not raw_payment_id:
            raise ValueError("Missing order_id in Cryptomus webhook")

        try:
            payment_id = UUID(str(raw_payment_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format for order_id") from exception

        return payment_id, self._map_status(status)

    async def _create_payment(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any], str]:
        payload_bytes = orjson.dumps(payload)
        response = await self._client.post(
            "/v1/payment",
            content=payload_bytes,
            headers={"sign": self._calculate_sign(payload_bytes)},
        )
        response.raise_for_status()
        return response.status_code, orjson.loads(response.content), response.text

    def _verify_signature(self, body: bytes, signature: str) -> None:
        expected = self._calculate_sign(body)
        if not hmac.compare_digest(expected.lower(), signature.strip().lower()):
            raise PermissionError("Invalid Cryptomus webhook signature")

    def _calculate_sign(self, body: bytes) -> str:
        encoded_body = base64.b64encode(body).decode()
        secret = self._get_api_key()
        return hashlib.md5(f"{encoded_body}{secret}".encode()).hexdigest()

    def _get_merchant_id(self) -> str:
        merchant_id = (self.gateway.settings.merchant_id or "").strip()
        if not merchant_id:
            raise ValueError("Cryptomus merchant_id is required")
        return merchant_id

    def _get_api_key(self) -> str:
        api_key = self.gateway.settings.api_key
        secret = api_key.get_secret_value().strip() if api_key else ""
        if not secret:
            raise ValueError("Cryptomus api_key is required")
        return secret

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")

    @staticmethod
    def _map_status(status: object) -> TransactionStatus:
        normalized = str(status or "").lower()
        if normalized in {"paid", "paid_over", "success", "succeeded"}:
            return TransactionStatus.COMPLETED
        if normalized in {"check", "process", "confirm_check", "pending", "wrong_amount_waiting"}:
            return TransactionStatus.PENDING
        if normalized in {"cancel", "system_fail", "fail", "failed", "expired", "wrong_amount"}:
            return TransactionStatus.CANCELED
        raise ValueError(f"Unsupported Cryptomus status: {status}")
