"""WATA payment gateway implementation.

WATA is a payment processor supporting various payment methods.
"""

import uuid
from datetime import datetime, timedelta, timezone
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
    WataGatewaySettingsDto,
)

from .base import BasePaymentGateway


class WataGateway(BasePaymentGateway):
    """WATA payment gateway.
    
    Supports various payment methods including cards and SBP.
    """

    _client: AsyncClient

    DEFAULT_BASE_URL: Final[str] = "https://api.wata.pro/api"
    
    # Default currency for WATA payments
    DEFAULT_CURRENCY: Final[str] = "RUB"
    
    # Link expiration time in minutes
    LINK_TTL_MINUTES: Final[int] = 60

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot) -> None:
        super().__init__(gateway, bot)

        if not isinstance(self.gateway.settings, WataGatewaySettingsDto):
            raise TypeError("WataGateway requires WataGatewaySettingsDto")

        base_url = self.gateway.settings.base_url or self.DEFAULT_BASE_URL
        
        self._client = self._make_client(
            base_url=base_url.rstrip("/"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.gateway.settings.access_token.get_secret_value()}",  # type: ignore[union-attr]
            },
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        """Create a new payment link in WATA."""
        payment_id = uuid.uuid4()
        
        # Calculate expiration time
        expiration_time = datetime.now(timezone.utc) + timedelta(minutes=self.LINK_TTL_MINUTES)
        expiration_str = expiration_time.isoformat().replace("+00:00", "Z")
        
        # Convert amount to kopeks (WATA expects amount in main currency units)
        amount_value = float(amount)
        
        payload = {
            "amount": amount_value,
            "currency": self.DEFAULT_CURRENCY,
            "description": details[:255],
            "orderId": str(payment_id),
            "type": "OneTime",
            "expirationDateTime": expiration_str,
            "successRedirectUrl": await self._get_bot_redirect_url(),
            "failRedirectUrl": await self._get_bot_redirect_url(),
        }

        try:
            response = await self._client.post("/links", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            payment_url = data.get("url") or data.get("paymentUrl")
            
            if not payment_url:
                raise KeyError("Invalid response from WATA API: missing payment URL")
            
            link_id = data.get("id")
            logger.info(f"WATA payment link created: {link_id}, payment_id: {payment_id}")
            
            return PaymentResult(id=payment_id, url=payment_url)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating WATA payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse WATA response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating WATA payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        """Handle WATA webhook notification."""
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"WATA webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            order_id = webhook_data.get("orderId")
            status = webhook_data.get("status")
            
            if not order_id:
                raise ValueError("Missing orderId in webhook")
            
            try:
                payment_id = UUID(order_id)
            except ValueError:
                raise ValueError("Invalid UUID format for orderId")

            match status:
                case "Completed" | "completed" | "Success" | "success":
                    transaction_status = TransactionStatus.COMPLETED
                case "Failed" | "failed" | "Cancelled" | "cancelled" | "Expired" | "expired":
                    transaction_status = TransactionStatus.CANCELED
                case "Pending" | "pending" | "Processing" | "processing":
                    transaction_status = TransactionStatus.PENDING
                case _:
                    logger.info(f"Ignoring WATA webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate WATA webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def get_payment_link(self, link_id: str) -> dict[str, Any]:
        """Get payment link information from WATA API."""
        try:
            response = await self._client.get(f"/links/{link_id}")
            response.raise_for_status()
            data = orjson.loads(response.content)
            return data
            
        except Exception as exception:
            logger.error(f"Failed to get WATA payment link info: {exception}")
            raise

    async def search_transactions(
        self,
        order_id: str | None = None,
        payment_link_id: str | None = None,
        status: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search transactions in WATA."""
        params: dict[str, Any] = {
            "skipCount": 0,
            "maxResultCount": max(1, min(limit, 1000)),
        }
        if order_id:
            params["orderId"] = order_id
        if status:
            params["statuses"] = status
        if payment_link_id:
            params["paymentLinkId"] = payment_link_id

        try:
            response = await self._client.get("/transactions", params=params)
            response.raise_for_status()
            data = orjson.loads(response.content)
            return data
            
        except Exception as exception:
            logger.error(f"Failed to search WATA transactions: {exception}")
            raise