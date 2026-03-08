"""Stripe hosted Checkout payment gateway implementation."""

import hashlib
import hmac
import time
import uuid
from decimal import Decimal
from typing import Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    StripeGatewaySettingsDto,
)

from .base import BasePaymentGateway


class StripeGateway(BasePaymentGateway):
    """Stripe Checkout Sessions gateway."""

    _client: AsyncClient

    API_BASE: Final[str] = "https://api.stripe.com"
    DEFAULT_CURRENCY: Final[str] = "usd"
    WEBHOOK_TOLERANCE_SECONDS: Final[int] = 300

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, StripeGatewaySettingsDto):
            raise TypeError("StripeGateway requires StripeGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={"Authorization": f"Bearer {self._get_secret_key()}"},
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
        success_url = success_redirect_url or default_redirect_url
        cancel_url = fail_redirect_url or success_url

        payload = {
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(payment_id),
            "metadata[payment_id]": str(payment_id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": self.DEFAULT_CURRENCY,
            "line_items[0][price_data][unit_amount]": str(self._format_minor_units(amount)),
            "line_items[0][price_data][product_data][name]": details[:120],
        }

        try:
            response = await self._client.post("/v1/checkout/sessions", data=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
        except HTTPStatusError as exception:
            logger.error(
                "Stripe create checkout session failed. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise

        payment_url = data.get("url")
        if not payment_url:
            raise KeyError("Invalid response from Stripe API: missing session url")

        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        if not signature:
            raise PermissionError("Missing Stripe-Signature header")
        self._verify_signature(body, signature)

        try:
            event = orjson.loads(body)
        except orjson.JSONDecodeError as exception:
            raise ValueError("Invalid Stripe webhook payload") from exception

        if not isinstance(event, dict):
            raise ValueError("Invalid Stripe webhook payload")

        event_type = str(event.get("type") or "")
        data_object = event.get("data", {}).get("object", {})
        if not isinstance(data_object, dict):
            raise ValueError("Invalid Stripe webhook object")

        metadata = data_object.get("metadata", {})
        raw_payment_id = None
        if isinstance(metadata, dict):
            raw_payment_id = metadata.get("payment_id")
        raw_payment_id = raw_payment_id or data_object.get("client_reference_id")
        if not raw_payment_id:
            raise ValueError("Missing payment id in Stripe webhook")

        try:
            payment_id = UUID(str(raw_payment_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format for Stripe payment id") from exception

        match event_type:
            case "checkout.session.completed":
                status = TransactionStatus.COMPLETED
            case "checkout.session.expired" | "checkout.session.async_payment_failed":
                status = TransactionStatus.CANCELED
            case _:
                raise ValueError(f"Unsupported Stripe event type: {event_type}")

        return payment_id, status

    def _verify_signature(self, body: bytes, signature_header: str) -> None:
        timestamp = ""
        signatures: list[str] = []
        for item in signature_header.split(","):
            key, _, value = item.partition("=")
            if key == "t":
                timestamp = value
            elif key == "v1":
                signatures.append(value)

        if not timestamp or not signatures:
            raise PermissionError("Invalid Stripe-Signature header")

        try:
            parsed_timestamp = int(timestamp)
        except ValueError as exception:
            raise PermissionError("Invalid Stripe-Signature header") from exception

        if abs(time.time() - parsed_timestamp) > self.WEBHOOK_TOLERANCE_SECONDS:
            raise PermissionError("Expired Stripe webhook signature")

        signed_payload = f"{timestamp}.".encode() + body
        expected_signature = hmac.new(
            self._get_webhook_secret().encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        if not any(hmac.compare_digest(expected_signature, signature) for signature in signatures):
            raise PermissionError("Invalid Stripe webhook signature")

    def _get_secret_key(self) -> str:
        secret_key = self.gateway.settings.secret_key
        secret = secret_key.get_secret_value().strip() if secret_key else ""
        if not secret:
            raise ValueError("Stripe secret_key is required")
        return secret

    def _get_webhook_secret(self) -> str:
        webhook_secret = self.gateway.settings.webhook_secret
        secret = webhook_secret.get_secret_value().strip() if webhook_secret else ""
        if not secret:
            raise ValueError("Stripe webhook_secret is required")
        return secret

    @staticmethod
    def _format_minor_units(amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1")))
