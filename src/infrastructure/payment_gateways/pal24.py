"""Pal24 (PayPalych) payment gateway implementation."""

import hashlib
import uuid
from decimal import Decimal
from typing import Any, Final
from urllib.parse import parse_qs
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
    Pal24GatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class Pal24Gateway(BasePaymentGateway):
    """Pal24 (PayPalych) payment gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://pal24.pro/api/v1"
    DEFAULT_CURRENCY: Final[str] = "RUB"

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, Pal24GatewaySettingsDto):
            raise TypeError("Pal24Gateway requires Pal24GatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._get_api_token()}",
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
        payload = self._build_official_create_payload(
            payment_id=payment_id,
            amount=amount,
            details=details,
        )

        try:
            data = await self._create_bill(payload)
        except HTTPStatusError as exception:
            logger.error(
                "Pal24 create payment failed. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise
        except Exception as exception:
            logger.error(
                f"An unexpected error occurred while creating Pal24 payment: {exception}"
            )
            raise

        payment_url = self._extract_payment_url(data)
        if not payment_url:
            raise KeyError("Invalid response from Pal24 API: missing payment URL")

        self._emit_request_mode(operation="create_payment", mode="official_form")
        logger.info(
            "Pal24 bill created. mode='official_form' bill_id='{}' payment_id='{}'",
            data.get("bill_id") or data.get("InvId"),
            payment_id,
        )
        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        try:
            body = await request.body()
            official_payload = self._parse_official_webhook(body)
            if official_payload:
                payment_id, transaction_status = self._handle_official_webhook(official_payload)
                self._emit_webhook_mode(mode="official_form_postback")
                return payment_id, transaction_status

            raise ValueError("Unsupported Pal24 webhook payload")

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate Pal24 webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    def _build_official_create_payload(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        details: str,
    ) -> dict[str, str]:
        return {
            "shop_id": self._get_shop_id(),
            "amount": self._format_amount(amount),
            "order_id": str(payment_id),
            "currency_in": self.DEFAULT_CURRENCY,
            "description": details[:255],
            "type": "normal",
        }

    async def _create_bill(self, payload: dict[str, str]) -> dict[str, Any]:
        response = await self._client.post(
            "/bill/create",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return self._parse_api_response(response.content)

    def _parse_api_response(self, content: bytes) -> dict[str, Any]:
        data = orjson.loads(content)
        if not isinstance(data, dict):
            raise ValueError("Invalid Pal24 response payload")
        if not data.get("success", True):
            error_msg = data.get("message", "Unknown error")
            raise ValueError(f"Pal24 API error: {error_msg}")
        return data

    @staticmethod
    def _extract_payment_url(data: dict[str, Any]) -> str | None:
        return data.get("link_page_url") or data.get("link_url") or data.get("url")

    def _parse_official_webhook(self, body: bytes) -> dict[str, str]:
        parsed = {
            key: values[0]
            for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()
            if values
        }
        if not parsed:
            return {}
        if "InvId" not in parsed and "SignatureValue" not in parsed and "Status" not in parsed:
            return {}
        return parsed

    def _handle_official_webhook(
        self,
        webhook_data: dict[str, str],
    ) -> tuple[UUID, TransactionStatus]:
        signature = webhook_data.get("SignatureValue")
        if signature:
            expected_signature = self._calculate_official_signature(webhook_data)
            if signature.upper() != expected_signature.upper():
                logger.warning("Pal24 official webhook signature mismatch")
                raise PermissionError("Invalid Pal24 webhook signature")

        raw_payment_id = webhook_data.get("InvId")
        status = webhook_data.get("Status")
        if not raw_payment_id:
            raise ValueError("Missing InvId in webhook")

        try:
            payment_id = UUID(raw_payment_id)
        except ValueError as exception:
            raise ValueError("Invalid UUID format for InvId") from exception

        return payment_id, self._map_status(status)

    def _calculate_official_signature(self, data: dict[str, str]) -> str:
        sign_string = f"{data.get('OutSum', '')}:{data.get('InvId', '')}:{self._get_api_token()}"
        return hashlib.md5(sign_string.encode()).hexdigest().upper()

    @staticmethod
    def _map_status(status: object) -> TransactionStatus:
        normalized = str(status or "").upper()
        if normalized in {"PAID", "SUCCESS", "OVERPAID"}:
            return TransactionStatus.COMPLETED
        if normalized in {"REJECTED", "EXPIRED", "FAIL", "FAILED", "CANCELED", "CANCELLED"}:
            return TransactionStatus.CANCELED
        if normalized in {"NEW", "PROCESS", "UNDERPAID", "PENDING", "PROCESSING"}:
            return TransactionStatus.PENDING
        logger.info(f"Ignoring Pal24 webhook status: {status}")
        raise ValueError(f"Unsupported status: {status}")

    def _emit_request_mode(self, *, operation: str, mode: str) -> None:
        emit_counter(
            "payment_gateway_request_mode_total",
            gateway_type=self.gateway.type.value,
            operation=operation,
            mode=mode,
        )

    def _emit_webhook_mode(self, *, mode: str) -> None:
        emit_counter(
            "payment_gateway_webhook_mode_total",
            gateway_type=self.gateway.type.value,
            mode=mode,
        )

    def _get_api_token(self) -> str:
        if not isinstance(self.gateway.settings, Pal24GatewaySettingsDto):
            raise ValueError("Pal24 settings are not configured")
        api_key = self.gateway.settings.api_key
        token = api_key.get_secret_value().strip() if api_key else ""
        if not token:
            raise ValueError("Pal24 api_key is required")
        return token

    def _get_shop_id(self) -> str:
        if not isinstance(self.gateway.settings, Pal24GatewaySettingsDto):
            raise ValueError("Pal24 settings are not configured")
        shop_id = (self.gateway.settings.shop_id or "").strip()
        if not shop_id:
            raise ValueError("Pal24 shop_id is required")
        return shop_id

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")

    async def get_bill_info(self, bill_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(
                "/bill/status",
                params={"id": bill_id},
            )
            response.raise_for_status()
            return self._parse_api_response(response.content)
        except HTTPStatusError as exception:
            logger.error(
                "Failed to get Pal24 bill info. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise
        except Exception as exception:
            logger.error(f"Failed to get Pal24 bill info: {exception}")
            raise
