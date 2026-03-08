"""Platega payment gateway implementation."""

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
from src.core.observability import emit_counter
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    PlategaGatewaySettingsDto,
    normalize_platega_payment_method,
)

from .base import BasePaymentGateway


class PlategaGateway(BasePaymentGateway):
    """Platega payment gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://app.platega.io"
    DEFAULT_CURRENCY: Final[str] = "RUB"
    DEFAULT_PAYMENT_METHOD: Final[int] = 2
    DESCRIPTION_MAX_LENGTH: Final[int] = 64

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, PlategaGatewaySettingsDto):
            raise TypeError("PlategaGateway requires PlategaGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "X-MerchantId": self.gateway.settings.merchant_id or "",
                "X-Secret": self.gateway.settings.secret.get_secret_value()
                if self.gateway.settings.secret
                else "",
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
        payment_id = uuid.uuid4()
        default_redirect_url = await self._get_bot_redirect_url()
        resolved_success_url = success_redirect_url or default_redirect_url
        resolved_fail_url = fail_redirect_url or resolved_success_url
        sanitized_description = self._sanitize_description(details, self.DESCRIPTION_MAX_LENGTH)

        configured_method_raw = (
            self.gateway.settings.payment_method
            if isinstance(self.gateway.settings, PlategaGatewaySettingsDto)
            else self.DEFAULT_PAYMENT_METHOD
        )
        configured_method = normalize_platega_payment_method(
            configured_method_raw,
            strict=False,
            default=self.DEFAULT_PAYMENT_METHOD,
        )
        payload = self._build_payload(
            payment_id=payment_id,
            amount=amount,
            payment_method=configured_method,
            description=sanitized_description,
            success_url=resolved_success_url,
            fail_url=resolved_fail_url,
        )

        try:
            data = await self._create_transaction(payload)
        except HTTPStatusError as exception:
            if not self._is_payment_method_error(exception):
                logger.error(
                    "Platega create payment failed. status='{}' body='{}'",
                    exception.response.status_code,
                    exception.response.text,
                )
                raise

            logger.warning(
                "Platega rejected paymentMethod. configured='{}' resolved='{}' test='{}' body='{}'",
                configured_method_raw,
                configured_method,
                is_test_payment,
                exception.response.text,
            )

            if not is_test_payment:
                raise ValueError(
                    "Invalid Platega payment_method configuration. Use 1 (CARD) or 2 (SBP)."
                ) from exception

            fallback_method = self.DEFAULT_PAYMENT_METHOD
            if configured_method == fallback_method:
                raise ValueError(
                    "Platega test payment failed: paymentMethod was rejected even after fallback."
                ) from exception

            payload["paymentMethod"] = fallback_method
            logger.warning(
                "Retrying Platega test payment with fallback method='{}'", fallback_method
            )
            data = await self._create_transaction(payload)

        payment_url = data.get("redirect") or data.get("paymentUrl") or data.get("url")
        if not payment_url:
            raise KeyError("Invalid response from Platega API: missing payment URL")

        logger.info(
            "Platega transaction created. transaction_id='{}' payment_id='{}' method='{}'",
            data.get("transactionId"),
            payment_id,
            payload["paymentMethod"],
        )
        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"Platega webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            status = webhook_data.get("status")
            auth_mode = self._verify_webhook_headers(request)
            payment_id, mode = self._extract_payment_id(webhook_data)
            self._emit_webhook_mode(mode=mode, auth_mode=auth_mode)

            match str(status or "").upper():
                case "CONFIRMED" | "COMPLETED" | "SUCCESS":
                    transaction_status = TransactionStatus.COMPLETED
                case "CANCELED" | "CANCELLED" | "CHARGEBACK" | "FAILED" | "EXPIRED":
                    transaction_status = TransactionStatus.CANCELED
                case "PENDING" | "PROCESSING":
                    transaction_status = TransactionStatus.PENDING
                case _:
                    logger.info(f"Ignoring Platega webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate Platega webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(f"/transaction/{transaction_id}")
            response.raise_for_status()
            return orjson.loads(response.content)
        except Exception as exception:
            logger.error(f"Failed to get Platega transaction info: {exception}")
            raise

    async def _create_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/transaction/process", json=payload)
        response.raise_for_status()
        return orjson.loads(response.content)

    def _build_payload(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        payment_method: int,
        description: str,
        success_url: str,
        fail_url: str,
    ) -> dict[str, Any]:
        return {
            "paymentMethod": payment_method,
            "paymentDetails": {
                "amount": float(amount),
                "currency": self.DEFAULT_CURRENCY,
            },
            "description": description,
            "payload": str(payment_id),
            "return": success_url,
            "failedUrl": fail_url,
        }

    @staticmethod
    def _is_payment_method_error(exception: HTTPStatusError) -> bool:
        if exception.response.status_code != 400:
            return False

        body = exception.response.text.lower()
        return "paymentmethod" in body or "val_0001" in body

    def _verify_webhook_headers(self, request: Request) -> str:
        merchant_header = request.headers.get("X-MerchantId")
        secret_header = request.headers.get("X-Secret")
        if merchant_header is None and secret_header is None:
            raise PermissionError("Missing Platega webhook auth headers")

        if not isinstance(self.gateway.settings, PlategaGatewaySettingsDto):
            raise PermissionError("Platega settings are not configured")

        expected_merchant_id = (self.gateway.settings.merchant_id or "").strip()
        expected_secret = (
            self.gateway.settings.secret.get_secret_value().strip()
            if self.gateway.settings.secret
            else ""
        )
        provided_merchant_id = (merchant_header or "").strip()
        provided_secret = (secret_header or "").strip()

        if not provided_merchant_id or not provided_secret:
            raise PermissionError("Missing Platega webhook auth headers")
        if expected_merchant_id and provided_merchant_id != expected_merchant_id:
            raise PermissionError("Invalid Platega webhook merchant id")
        if expected_secret and provided_secret != expected_secret:
            raise PermissionError("Invalid Platega webhook secret")
        return "callback_headers"

    def _extract_payment_id(self, webhook_data: dict[str, Any]) -> tuple[UUID, str]:
        raw_payment_id = webhook_data.get("id")
        try:
            return UUID(str(raw_payment_id)), "official_callback"
        except ValueError as exception:
            raise ValueError("Invalid UUID format for id") from exception

    def _emit_webhook_mode(self, *, mode: str, auth_mode: str) -> None:
        emit_counter(
            "payment_gateway_webhook_mode_total",
            gateway_type=self.gateway.type.value,
            mode=mode,
            auth_mode=auth_mode,
        )

    @staticmethod
    def _sanitize_description(description: str, max_bytes: int) -> str:
        cleaned = (description or "").strip()
        if not max_bytes:
            return cleaned

        encoded = cleaned.encode("utf-8")
        if len(encoded) <= max_bytes:
            return cleaned

        logger.debug(f"Platega description trimmed from {len(encoded)} to {max_bytes} bytes")

        trimmed_bytes = encoded[:max_bytes]
        while True:
            try:
                return trimmed_bytes.decode("utf-8")
            except UnicodeDecodeError:
                trimmed_bytes = trimmed_bytes[:-1]
