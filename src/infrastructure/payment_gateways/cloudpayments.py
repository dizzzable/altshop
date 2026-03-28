"""CloudPayments payment gateway implementation."""

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
from fastapi.responses import JSONResponse
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    CloudPaymentsGatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class CloudPaymentsGateway(BasePaymentGateway):
    """CloudPayments hosted order checkout gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://api.cloudpayments.ru"
    DEFAULT_CURRENCY: Final[str] = "RUB"

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, CloudPaymentsGatewaySettingsDto):
            raise TypeError("CloudPaymentsGateway requires CloudPaymentsGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            auth=(self._get_public_id(), self._get_api_secret()),
            headers={"Content-Type": "application/json"},
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
        payload: dict[str, Any] = {
            "Amount": float(amount),
            "Currency": self.DEFAULT_CURRENCY,
            "Description": details[:255],
            "InvoiceId": str(payment_id),
        }
        if success_redirect_url:
            payload["SuccessRedirectUrl"] = success_redirect_url
        if fail_redirect_url:
            payload["FailRedirectUrl"] = fail_redirect_url

        try:
            response = await self._client.post("/orders/create", content=orjson.dumps(payload))
            response.raise_for_status()
            data = orjson.loads(response.content)
        except HTTPStatusError as exception:
            logger.error(
                "CloudPayments create order failed. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise

        if not data.get("Success", False):
            raise ValueError(f"CloudPayments API error: {data.get('Message') or 'Unknown error'}")

        model = data.get("Model", {})
        if not isinstance(model, dict):
            raise ValueError("Invalid CloudPayments response payload")

        payment_url = model.get("Url") or model.get("url")
        if not payment_url:
            raise KeyError("Invalid CloudPayments response: missing Url")

        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        body = await request.body()
        self._verify_signature(body, request.headers.get("Content-HMAC"))

        try:
            payload = orjson.loads(body)
        except orjson.JSONDecodeError as exception:
            raise ValueError("Invalid CloudPayments webhook payload") from exception

        if not isinstance(payload, dict):
            raise ValueError("Invalid CloudPayments webhook payload")

        raw_payment_id = payload.get("InvoiceId")
        if raw_payment_id is None and isinstance(payload.get("Data"), dict):
            raw_payment_id = payload["Data"].get("InvoiceId")
        if raw_payment_id is None:
            raise ValueError("Missing InvoiceId in CloudPayments webhook")

        try:
            payment_id = UUID(str(raw_payment_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format for CloudPayments InvoiceId") from exception

        status = (
            payload.get("Status")
            or payload.get("TransactionStatus")
            or payload.get("payment_status")
        )
        if status is None:
            reason_code = payload.get("ReasonCode")
            status = "COMPLETED" if reason_code in (None, 0, "0") else "FAILED"

        return payment_id, self._map_status(status)

    async def build_webhook_response(self, request: Request) -> JSONResponse:
        return JSONResponse({"code": 0})

    def _verify_signature(self, body: bytes, header_signature: str | None) -> None:
        if not header_signature:
            raise PermissionError("Missing CloudPayments Content-HMAC header")
        expected_signature = base64.b64encode(
            hmac.new(self._get_api_secret().encode(), body, hashlib.sha256).digest()
        ).decode()
        if not hmac.compare_digest(expected_signature, header_signature.strip()):
            raise PermissionError("Invalid CloudPayments webhook signature")

    def _get_public_id(self) -> str:
        public_id = (self.gateway.settings.public_id or "").strip()
        if not public_id:
            raise ValueError("CloudPayments public_id is required")
        return public_id

    def _get_api_secret(self) -> str:
        api_secret = self.gateway.settings.api_secret
        secret = api_secret.get_secret_value().strip() if api_secret else ""
        if not secret:
            raise ValueError("CloudPayments api_secret is required")
        return secret

    @staticmethod
    def _map_status(status: object) -> TransactionStatus:
        normalized = str(status or "").upper()
        if normalized in {"COMPLETED", "AUTHORIZED", "CONFIRMED", "SUCCESS", "PAID"}:
            return TransactionStatus.COMPLETED
        if normalized in {"PENDING", "WAITING", "PROCESSING"}:
            return TransactionStatus.PENDING
        if normalized in {"FAILED", "DECLINED", "CANCELED", "CANCELLED", "REJECTED"}:
            return TransactionStatus.CANCELED
        raise ValueError(f"Unsupported CloudPayments status: {status}")
