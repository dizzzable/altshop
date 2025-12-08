"""Platega payment gateway implementation.

Documentation: https://app.platega.io/docs
Platega is a payment processor supporting various payment methods.
"""

import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.enums import TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    PlategaGatewaySettingsDto,
)

from .base import BasePaymentGateway


class PlategaGateway(BasePaymentGateway):
    """Platega payment gateway.
    
    Supports various payment methods including cards and SBP.
    """

    _client: AsyncClient

    API_BASE: Final[str] = "https://app.platega.io"
    
    # Default currency for Platega payments
    DEFAULT_CURRENCY: Final[str] = "RUB"
    
    # Default payment method (1 = card, 2 = SBP, etc.)
    DEFAULT_PAYMENT_METHOD: Final[int] = 1
    
    # Max description length in bytes
    DESCRIPTION_MAX_LENGTH: Final[int] = 64

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot) -> None:
        super().__init__(gateway, bot)

        if not isinstance(self.gateway.settings, PlategaGatewaySettingsDto):
            raise TypeError("PlategaGateway requires PlategaGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "X-MerchantId": self.gateway.settings.merchant_id or "",  # type: ignore[union-attr]
                "X-Secret": self.gateway.settings.secret.get_secret_value() if self.gateway.settings.secret else "",  # type: ignore[union-attr]
            },
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        """Create a new payment transaction in Platega."""
        payment_id = uuid.uuid4()
        
        # Sanitize description to fit byte limit
        sanitized_description = self._sanitize_description(details, self.DESCRIPTION_MAX_LENGTH)
        
        # Get payment method from settings or use default
        payment_method = self.DEFAULT_PAYMENT_METHOD
        if isinstance(self.gateway.settings, PlategaGatewaySettingsDto):
            payment_method = self.gateway.settings.payment_method or self.DEFAULT_PAYMENT_METHOD
        
        payload = {
            "paymentMethod": payment_method,
            "paymentDetails": {
                "amount": float(amount),
                "currency": self.DEFAULT_CURRENCY,
            },
            "description": sanitized_description,
            "payload": str(payment_id),
            "return": await self._get_bot_redirect_url(),
            "failedUrl": await self._get_bot_redirect_url(),
        }

        try:
            response = await self._client.post("/transaction/process", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            payment_url = data.get("paymentUrl") or data.get("url")
            
            if not payment_url:
                raise KeyError("Invalid response from Platega API: missing payment URL")
            
            transaction_id = data.get("transactionId")
            logger.info(f"Platega transaction created: {transaction_id}, payment_id: {payment_id}")
            
            return PaymentResult(id=payment_id, url=payment_url)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating Platega payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse Platega response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating Platega payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        """Handle Platega webhook notification."""
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"Platega webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            # Get payment_id from payload field we set during creation
            payload = webhook_data.get("payload")
            status = webhook_data.get("status")
            
            if not payload:
                raise ValueError("Missing payload in webhook")
            
            try:
                payment_id = UUID(payload)
            except ValueError:
                raise ValueError("Invalid UUID format for payload")

            match status:
                case "completed" | "Completed" | "success" | "Success":
                    transaction_status = TransactionStatus.COMPLETED
                case "failed" | "Failed" | "cancelled" | "Cancelled" | "expired" | "Expired":
                    transaction_status = TransactionStatus.CANCELED
                case "pending" | "Pending" | "processing" | "Processing":
                    transaction_status = TransactionStatus.PENDING
                case _:
                    logger.info(f"Ignoring Platega webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate Platega webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    @staticmethod
    def _sanitize_description(description: str, max_bytes: int) -> str:
        """Truncate description to fit byte limit while preserving valid UTF-8."""
        cleaned = (description or "").strip()
        if not max_bytes:
            return cleaned

        encoded = cleaned.encode("utf-8")
        if len(encoded) <= max_bytes:
            return cleaned

        logger.debug(
            f"Platega description trimmed from {len(encoded)} to {max_bytes} bytes"
        )

        trimmed_bytes = encoded[:max_bytes]
        while True:
            try:
                return trimmed_bytes.decode("utf-8")
            except UnicodeDecodeError:
                trimmed_bytes = trimmed_bytes[:-1]

    async def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        """Get transaction information from Platega API."""
        try:
            response = await self._client.get(f"/transaction/{transaction_id}")
            response.raise_for_status()
            data = orjson.loads(response.content)
            return data
            
        except Exception as exception:
            logger.error(f"Failed to get Platega transaction info: {exception}")
            raise