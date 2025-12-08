"""Heleket payment gateway implementation.

Documentation: https://heleket.com/docs
Heleket is a cryptocurrency payment processor.
"""

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

from src.core.enums import TransactionStatus
from src.infrastructure.database.models.dto import (
    HeleketGatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class HeleketGateway(BasePaymentGateway):
    """Heleket cryptocurrency payment gateway.
    
    Supports various cryptocurrencies for payment processing.
    """

    _client: AsyncClient

    API_BASE: Final[str] = "https://api.heleket.com/v1"
    
    # Default currency for Heleket payments
    DEFAULT_CURRENCY: Final[str] = "USD"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot) -> None:
        super().__init__(gateway, bot)

        if not isinstance(self.gateway.settings, HeleketGatewaySettingsDto):
            raise TypeError("HeleketGateway requires HeleketGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.gateway.settings.api_key.get_secret_value()}",  # type: ignore[union-attr]
            },
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        """Create a new payment invoice in Heleket."""
        payment_id = uuid.uuid4()
        
        payload = {
            "amount": str(amount),
            "currency": self.DEFAULT_CURRENCY,
            "order_id": str(payment_id),
            "description": details[:255],
            "success_url": await self._get_bot_redirect_url(),
            "fail_url": await self._get_bot_redirect_url(),
        }

        try:
            response = await self._client.post("/invoice/create", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            if data.get("state") != 0:
                error_msg = data.get("message", "Unknown error")
                raise ValueError(f"Heleket API error: {error_msg}")
            
            result = data.get("result", {})
            payment_url = result.get("url")
            
            if not payment_url:
                raise KeyError("Invalid response from Heleket API: missing payment URL")
            
            logger.info(f"Heleket invoice created: {result.get('uuid')}, payment_id: {payment_id}")
            
            return PaymentResult(id=payment_id, url=payment_url)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating Heleket payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse Heleket response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating Heleket payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        """Handle Heleket webhook notification.
        
        Heleket sends webhook with signature verification.
        """
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"Heleket webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            # Verify signature if provided
            signature = request.headers.get("X-Signature")
            if signature and self.gateway.settings:
                expected_signature = self._calculate_signature(body)
                if signature != expected_signature:
                    logger.warning("Heleket webhook signature mismatch")
                    raise PermissionError("Invalid webhook signature")

            order_id = webhook_data.get("order_id")
            status = webhook_data.get("status")
            
            if not order_id:
                raise ValueError("Missing order_id in webhook")
            
            try:
                payment_id = UUID(order_id)
            except ValueError:
                raise ValueError("Invalid UUID format for order_id")

            match status:
                case "paid" | "paid_over":
                    transaction_status = TransactionStatus.COMPLETED
                case "cancel" | "fail" | "system_fail" | "refund_process" | "refund_fail" | "refund_paid":
                    transaction_status = TransactionStatus.CANCELED
                case "wrong_amount" | "wrong_amount_waiting":
                    transaction_status = TransactionStatus.PENDING
                case _:
                    logger.info(f"Ignoring Heleket webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate Heleket webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    def _calculate_signature(self, body: bytes) -> str:
        """Calculate webhook signature for verification."""
        if not isinstance(self.gateway.settings, HeleketGatewaySettingsDto):
            return ""
        
        api_key = self.gateway.settings.api_key
        if not api_key:
            return ""
            
        secret = api_key.get_secret_value()
        return hashlib.sha256(body + secret.encode()).hexdigest()

    async def get_invoice_info(self, invoice_uuid: str) -> dict[str, Any]:
        """Get invoice information from Heleket API."""
        try:
            response = await self._client.get(f"/invoice/info/{invoice_uuid}")
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            if data.get("state") != 0:
                raise ValueError(f"Heleket API error: {data.get('message', 'Unknown')}")
            
            return data.get("result", {})
            
        except Exception as exception:
            logger.error(f"Failed to get Heleket invoice info: {exception}")
            raise