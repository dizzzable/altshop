"""CryptoBot (Crypto Pay) payment gateway implementation.

Documentation: https://help.crypt.bot/crypto-pay-api
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
    CryptopayGatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
)

from .base import BasePaymentGateway


class CryptopayGateway(BasePaymentGateway):
    """CryptoBot (Crypto Pay) payment gateway.
    
    Supports cryptocurrency payments via Telegram's @CryptoBot.
    Currencies: USDT, TON, BTC, ETH, LTC, BNB, TRX, USDC
    """

    _client: AsyncClient

    API_BASE: Final[str] = "https://pay.crypt.bot/api"
    
    # Default currency for crypto payments
    DEFAULT_ASSET: Final[str] = "USDT"

    def __init__(self, gateway: PaymentGatewayDto, bot: Bot) -> None:
        super().__init__(gateway, bot)

        if not isinstance(self.gateway.settings, CryptopayGatewaySettingsDto):
            raise TypeError("CryptopayGateway requires CryptopayGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "Crypto-Pay-API-Token": self.gateway.settings.api_key.get_secret_value(),  # type: ignore[union-attr]
            },
        )

    async def handle_create_payment(self, amount: Decimal, details: str) -> PaymentResult:
        """Create a new invoice in CryptoBot."""
        payment_id = uuid.uuid4()
        
        payload = {
            "asset": self.DEFAULT_ASSET,
            "amount": str(amount),
            "description": details[:1024],  # Max 1024 chars
            "payload": str(payment_id),
            "expires_in": 3600,  # 1 hour
        }

        try:
            response = await self._client.post("/createInvoice", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            if not data.get("ok"):
                error = data.get("error", {})
                raise ValueError(f"CryptoBot API error: {error.get('name', 'Unknown')}")
            
            result = data.get("result", {})
            invoice_url = result.get("bot_invoice_url") or result.get("pay_url")
            
            if not invoice_url:
                raise KeyError("Invalid response from CryptoBot API: missing invoice URL")
            
            # Use invoice_id from CryptoBot as our payment reference
            invoice_id = result.get("invoice_id")
            logger.info(f"CryptoBot invoice created: {invoice_id}, payment_id: {payment_id}")
            
            return PaymentResult(id=payment_id, url=invoice_url)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating CryptoBot payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse CryptoBot response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating CryptoBot payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        """Handle CryptoBot webhook notification.
        
        CryptoBot sends webhook with signature in header.
        """
        try:
            body = await request.body()
            webhook_data = orjson.loads(body)
            logger.debug(f"CryptoBot webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            update_type = webhook_data.get("update_type")
            payload_data = webhook_data.get("payload", {})
            
            if update_type != "invoice_paid":
                logger.info(f"Ignoring CryptoBot webhook type: {update_type}")
                raise ValueError(f"Unsupported webhook type: {update_type}")

            # Get payment_id from payload field we set during creation
            payment_payload = payload_data.get("payload")
            status = payload_data.get("status")
            
            if not payment_payload:
                raise ValueError("Missing payload in webhook")
            
            try:
                payment_id = UUID(payment_payload)
            except ValueError:
                raise ValueError("Invalid UUID format for payment ID")

            match status:
                case "paid":
                    transaction_status = TransactionStatus.COMPLETED
                case "expired":
                    transaction_status = TransactionStatus.CANCELED
                case _:
                    logger.info(f"Ignoring CryptoBot webhook status: {status}")
                    raise ValueError(f"Unsupported status: {status}")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate CryptoBot webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def get_invoice_status(self, invoice_id: int) -> dict[str, Any]:
        """Get invoice status from CryptoBot API."""
        try:
            response = await self._client.get("/getInvoices", params={"invoice_ids": invoice_id})
            response.raise_for_status()
            data = orjson.loads(response.content)
            
            if not data.get("ok"):
                raise ValueError(f"CryptoBot API error: {data.get('error', {})}")
            
            items = data.get("result", {}).get("items", [])
            if items:
                return items[0]
            return {}
            
        except Exception as exception:
            logger.error(f"Failed to get CryptoBot invoice status: {exception}")
            raise