"""CryptoBot (Crypto Pay) payment gateway implementation.

Documentation: https://help.crypt.bot/crypto-pay-api
"""

import hashlib
import hmac
import uuid
from datetime import datetime
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

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, CryptopayGatewaySettingsDto):
            raise TypeError("CryptopayGateway requires CryptopayGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
            headers={
                "Content-Type": "application/json",
                "Crypto-Pay-API-Token": self.gateway.settings.api_key.get_secret_value(),
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
        """Create a new fiat invoice in CryptoBot restricted to the selected asset."""
        payment_id = uuid.uuid4()

        payload = {
            "currency_type": "fiat",
            "fiat": self.gateway.currency.value,
            "amount": self._format_amount(amount),
            "description": details[:1024],  # Max 1024 chars
            "payload": str(payment_id),
            "expires_in": 3600,  # 1 hour
        }
        if payment_asset is not None:
            payload["accepted_assets"] = payment_asset.value
        if success_redirect_url:
            payload["paid_btn_name"] = "callback"
            payload["paid_btn_url"] = success_redirect_url

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
            logger.info(
                "CryptoBot invoice created. mode='fiat' payment_id='{}' invoice_id='{}' "
                "payment_asset='{}' status='{}' body='{}'",
                payment_id,
                invoice_id,
                payment_asset.value if payment_asset else None,
                response.status_code,
                response.text,
            )

            return PaymentResult(id=payment_id, url=invoice_url)

        except HTTPStatusError as exception:
            logger.error(
                "HTTP error creating CryptoBot payment. mode='fiat' payment_id='{}' "
                "payment_asset='{}' status='{}' body='{}'",
                payment_id,
                payment_asset.value if payment_asset else None,
                exception.response.status_code,
                exception.response.text,
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse CryptoBot response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(
                f"An unexpected error occurred while creating CryptoBot payment: {exception}"
            )
            raise

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        """Handle CryptoBot webhook notification.

        CryptoBot sends webhook with signature in header.
        """
        try:
            body = await request.body()
            signature = request.headers.get("crypto-pay-api-signature")
            if not signature:
                raise PermissionError("Missing crypto-pay-api-signature header")

            webhook_data = orjson.loads(body)
            logger.debug(f"CryptoBot webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            self._verify_webhook_signature(body, signature)
            self._validate_request_date(webhook_data)

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

    def _verify_webhook_signature(self, body: bytes, signature: str) -> None:
        expected_signature = hmac.new(
            self._get_webhook_secret(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            raise PermissionError("Invalid Crypto Pay webhook signature")

    def _get_webhook_secret(self) -> bytes:
        configured_secret = self.gateway.settings.secret_key
        if configured_secret:
            secret_value = configured_secret.get_secret_value().strip()
            if secret_value:
                try:
                    return bytes.fromhex(secret_value)
                except ValueError:
                    logger.warning("Crypto Pay secret_key is not hex; using raw bytes fallback")
                    return secret_value.encode("utf-8")

        api_key = self.gateway.settings.api_key
        token = api_key.get_secret_value().strip() if api_key else ""
        if not token:
            raise ValueError("Crypto Pay api_key is required")
        return hashlib.sha256(token.encode("utf-8")).digest()

    @staticmethod
    def _validate_request_date(webhook_data: dict[str, Any]) -> None:
        request_date = webhook_data.get("request_date")
        if request_date is None:
            return
        try:
            datetime.fromisoformat(str(request_date).replace("Z", "+00:00"))
        except ValueError as exception:
            raise ValueError("Invalid request_date in webhook") from exception

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
