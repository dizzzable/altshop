"""Heleket payment gateway implementation."""

import base64
import hashlib
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
    HeleketGatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class HeleketGateway(BasePaymentGateway):
    """Heleket cryptocurrency payment gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://api.heleket.com"
    DEFAULT_CURRENCY: Final[str] = "USD"

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, HeleketGatewaySettingsDto):
            raise TypeError("HeleketGateway requires HeleketGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE.strip().rstrip("/"),
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
        default_redirect_url = await self._get_bot_redirect_url()
        resolved_success_url = success_redirect_url or default_redirect_url
        resolved_fail_url = fail_redirect_url or resolved_success_url

        v1_payload = self._build_v1_payment_payload(
            payment_id=payment_id,
            amount=amount,
            details=details,
            payment_asset=payment_asset,
            success_redirect_url=resolved_success_url,
            return_redirect_url=resolved_fail_url,
        )

        try:
            status_code, data, response_body = await self._create_payment_v1(v1_payload)
        except HTTPStatusError as exception:
            logger.error(
                "Heleket v1 create payment failed. payment_id='{}' payment_asset='{}' "
                "status='{}' body='{}'",
                payment_id,
                payment_asset.value if payment_asset else None,
                exception.response.status_code,
                exception.response.text,
            )
            raise

        payment_url = self._extract_payment_url(data)
        if not payment_url:
            raise KeyError("Invalid response from Heleket API: missing payment URL")

        logger.info(
            "Heleket invoice created. mode='v1' payment_id='{}' payment_asset='{}' "
            "status='{}' body='{}'",
            payment_id,
            payment_asset.value if payment_asset else None,
            status_code,
            response_body,
        )
        self._emit_request_mode(operation="create_payment", mode="v1")
        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"Heleket webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            signature = (
                request.headers.get("sign")
                or request.headers.get("Sign")
                or request.headers.get("X-Signature")
                or request.headers.get("X-Sign")
                or webhook_data.get("sign")
                or webhook_data.get("signature")
            )
            if not signature:
                raise PermissionError("Missing Heleket webhook signature")

            self._verify_webhook_signature(body, signature)

            order_id = (
                webhook_data.get("order_id")
                or webhook_data.get("orderId")
                or webhook_data.get("payload")
            )
            status = webhook_data.get("status") or webhook_data.get("payment_status")

            if not order_id:
                raise ValueError("Missing order id in webhook")

            try:
                payment_id = UUID(str(order_id))
            except ValueError as exception:
                raise ValueError("Invalid UUID format for order id") from exception

            match status:
                case "paid" | "paid_over" | "success" | "Success" | "completed" | "Completed":
                    transaction_status = TransactionStatus.COMPLETED
                case (
                    "cancel"
                    | "fail"
                    | "failed"
                    | "system_fail"
                    | "refund_process"
                    | "refund_fail"
                    | "refund_paid"
                    | "declined"
                    | "Declined"
                ):
                    transaction_status = TransactionStatus.CANCELED
                case "wrong_amount" | "wrong_amount_waiting" | "pending" | "Pending":
                    transaction_status = TransactionStatus.PENDING
                case _:
                    logger.info(f"Ignoring Heleket webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate Heleket webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def get_invoice_info(self, invoice_uuid: str) -> dict[str, Any]:
        payload = {"uuid": invoice_uuid}
        body = self._serialize_v1_body(payload)

        try:
            response = await self._client.post(
                "/v1/payment/info",
                content=body,
                headers=self._build_v1_auth_headers_from_body(body),
            )
            response.raise_for_status()
            data = orjson.loads(response.content)
        except HTTPStatusError as exception:
            logger.error(
                "Heleket v1 payment info failed. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise
        except Exception as exception:
            logger.error(f"Failed to get Heleket invoice info: {exception}")
            raise

        self._emit_request_mode(operation="payment_info", mode="v1")
        return data

    async def _create_payment_v1(
        self,
        payload: dict[str, Any],
    ) -> tuple[int, dict[str, Any], str]:
        body = self._serialize_v1_body(payload)
        response = await self._client.post(
            "/v1/payment",
            content=body,
            headers=self._build_v1_auth_headers_from_body(body),
        )
        response.raise_for_status()
        return response.status_code, orjson.loads(response.content), response.text

    def _build_v1_payment_payload(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        details: str,
        payment_asset: CryptoAsset | None,
        success_redirect_url: str,
        return_redirect_url: str,
    ) -> dict[str, Any]:
        payload = {
            "amount": str(amount),
            "currency": self.DEFAULT_CURRENCY,
            "order_id": str(payment_id),
            "description": details[:255],
            "url_success": success_redirect_url,
            "url_return": return_redirect_url,
        }
        if payment_asset is not None:
            payload["to_currency"] = payment_asset.value
        return payload

    def _build_v1_auth_headers_from_body(self, body: bytes) -> dict[str, str]:
        if not isinstance(self.gateway.settings, HeleketGatewaySettingsDto):
            raise ValueError("Heleket settings are not configured")

        merchant_id = (self.gateway.settings.merchant_id or "").strip()
        api_key = self.gateway.settings.api_key
        api_secret = api_key.get_secret_value().strip() if api_key else ""
        if not merchant_id or not api_secret:
            raise ValueError("Heleket merchant_id/api_key are required for v1 auth")

        sign = self._calculate_v1_sign_from_body(body, api_secret)
        return {
            "Content-Type": "application/json",
            "merchant": merchant_id,
            "sign": sign,
        }

    @staticmethod
    def _serialize_v1_body(payload: dict[str, Any]) -> bytes:
        return orjson.dumps(payload)

    def _verify_webhook_signature(self, body: bytes, signature: str) -> None:
        if not isinstance(self.gateway.settings, HeleketGatewaySettingsDto):
            raise PermissionError("Heleket settings not configured")

        api_key = self.gateway.settings.api_key
        api_secret = api_key.get_secret_value().strip() if api_key else ""
        if not api_secret:
            raise PermissionError("Heleket api_key is missing")

        secret = api_secret
        provided_signature = signature.strip().lower()
        expected_v1_candidates = self._calculate_v1_sign_candidates_from_body(body, secret)
        expected_v1_candidates.add(self._calculate_v1_sign_from_body(body, secret).lower())

        if provided_signature in expected_v1_candidates:
            self._emit_webhook_signature_mode(mode="v1")
            return

        logger.warning("Heleket webhook signature mismatch")
        raise PermissionError("Invalid Heleket webhook signature")

    def _emit_request_mode(self, *, operation: str, mode: str) -> None:
        emit_counter(
            "payment_gateway_request_mode_total",
            gateway_type=self.gateway.type.value,
            operation=operation,
            mode=mode,
        )

    def _emit_webhook_signature_mode(self, *, mode: str) -> None:
        emit_counter(
            "payment_gateway_webhook_signature_mode_total",
            gateway_type=self.gateway.type.value,
            mode=mode,
        )

    @classmethod
    def _calculate_v1_sign_candidates_from_body(cls, body: bytes, secret: str) -> set[str]:
        try:
            parsed = orjson.loads(body)
        except Exception:
            return set()

        if not isinstance(parsed, dict):
            return set()

        cleaned_payload = {
            key: value for key, value in parsed.items() if key not in {"sign", "signature"}
        }
        if cleaned_payload == parsed:
            return set()

        candidates: set[str] = set()
        payload_bytes = cls._serialize_v1_body(cleaned_payload)
        payload_base64 = base64.b64encode(payload_bytes).decode()
        candidates.add(hashlib.md5(f"{payload_base64}{secret}".encode()).hexdigest().lower())

        sorted_payload_bytes = orjson.dumps(cleaned_payload, option=orjson.OPT_SORT_KEYS)
        sorted_payload_base64 = base64.b64encode(sorted_payload_bytes).decode()
        candidates.add(hashlib.md5(f"{sorted_payload_base64}{secret}".encode()).hexdigest().lower())
        return candidates

    @staticmethod
    def _calculate_v1_sign_from_body(body: bytes, secret: str) -> str:
        payload_base64 = base64.b64encode(body).decode()
        return hashlib.md5(f"{payload_base64}{secret}".encode()).hexdigest()

    @staticmethod
    def _extract_payment_url(data: dict[str, Any]) -> str | None:
        result = data.get("result")
        if isinstance(result, dict):
            return (
                result.get("url")
                or result.get("payment_url")
                or result.get("paymentUrl")
                or result.get("invoice_url")
            )
        return (
            data.get("url")
            or data.get("payment_url")
            or data.get("paymentUrl")
            or data.get("invoice_url")
        )
