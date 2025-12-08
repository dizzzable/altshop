"""Pal24 (PayPalych) payment gateway implementation.

Documentation: https://paypalych.com/api
PayPalych supports SBP (Russian Fast Payment System) and card payments.
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
    Pal24GatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class Pal24Gateway(BasePaymentGateway):
    """PayPalych (Pal24) payment gateway.
    
    Supports SBP and card payments in Russia.
    """

    _client: AsyncClient

    API_BASE: Final[str] = "https://paypalych.com/api/v1"
    
    # Default currency for Pal24 payments
    DEFAULT_CURRENCY: Final[str] = "RUB"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot) -> None:
        super().__init__(gateway, bot)

        if not isinstance(self.gateway.settings, Pal24GatewaySettingsDto):
            raise TypeError("Pal24Gateway requires Pal24GatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.gateway.settings.api_key.get_secret_value()}",  # type: ignore[union-attr]
            },
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        """Create a new payment bill in PayPalych."""
        payment_id = uuid.uuid4()
        
        payload = {
            "amount": float(amount),
            "order_id": str(payment_id),
            "description": details[:255],
            "type": "normal",  # normal, multi
            "shop_id": self.gateway.settings.shop_id,  # type: ignore[union-attr]
            "success_url": await self._get_bot_redirect_url(),
            "fail_url": await self._get_bot_redirect_url(),
        }

        try:
            response = await self._client.post("/bills/create", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            if not data.get("success"):
                error_msg = data.get("message", "Unknown error")
                raise ValueError(f"PayPalych API error: {error_msg}")
            
            payment_url = data.get("link_url") or data.get("link_page_url")
            
            if not payment_url:
                raise KeyError("Invalid response from PayPalych API: missing payment URL")
            
            bill_id = data.get("bill_id")
            logger.info(f"PayPalych bill created: {bill_id}, payment_id: {payment_id}")
            
            return PaymentResult(id=payment_id, url=payment_url)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating PayPalych payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse PayPalych response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating PayPalych payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        """Handle PayPalych webhook notification.
        
        PayPalych sends webhook with signature verification.
        """
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"PayPalych webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            # Verify signature if provided
            signature = request.headers.get("X-Signature")
            if signature and self.gateway.settings:
                expected_signature = self._calculate_signature(webhook_data)
                if signature != expected_signature:
                    logger.warning("PayPalych webhook signature mismatch")
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
                case "PAID" | "paid":
                    transaction_status = TransactionStatus.COMPLETED
                case "REJECTED" | "rejected" | "EXPIRED" | "expired":
                    transaction_status = TransactionStatus.CANCELED
                case _:
                    logger.info(f"Ignoring PayPalych webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate PayPalych webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    def _calculate_signature(self, data: dict[str, Any]) -> str:
        """Calculate webhook signature for verification."""
        if not isinstance(self.gateway.settings, Pal24GatewaySettingsDto):
            return ""
        
        api_key = self.gateway.settings.api_key
        if not api_key:
            return ""
        
        # PayPalych signature calculation
        sign_string = f"{data.get('order_id')}:{data.get('bill_id')}:{data.get('status')}:{api_key.get_secret_value()}"
        return hashlib.sha256(sign_string.encode()).hexdigest()

    async def get_bill_info(self, bill_id: str) -> dict[str, Any]:
        """Get bill information from PayPalych API."""
        try:
            response = await self._client.get(f"/bills/{bill_id}")
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            if not data.get("success"):
                raise ValueError(f"PayPalych API error: {data.get('message', 'Unknown')}")
            
            return data
            
        except Exception as exception:
            logger.error(f"Failed to get PayPalych bill info: {exception}")
            raise