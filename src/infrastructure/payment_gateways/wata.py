"""WATA payment gateway implementation."""

import base64
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    WataGatewaySettingsDto,
)

from .base import BasePaymentGateway


class WataGateway(BasePaymentGateway):
    """WATA payment gateway."""

    _client: AsyncClient
    _public_key_cache: str | None
    _public_key_loaded_at: datetime | None

    DEFAULT_BASE_URL: Final[str] = "https://api.wata.pro/api/h2h"
    DEFAULT_CURRENCY: Final[str] = "RUB"
    LINK_TTL_MINUTES: Final[int] = 60
    PUBLIC_KEY_TTL_SECONDS: Final[int] = 6 * 60 * 60

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, WataGatewaySettingsDto):
            raise TypeError("WataGateway requires WataGatewaySettingsDto")

        base_url = self.gateway.settings.base_url or self.DEFAULT_BASE_URL
        self._client = self._make_client(
            base_url=base_url.rstrip("/"),
            headers={
                "Content-Type": "application/json",
                "Authorization": (
                    f"Bearer {self.gateway.settings.access_token.get_secret_value()}"
                ),
            },
        )
        self._public_key_cache = None
        self._public_key_loaded_at = None

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

        expiration_time = datetime.now(timezone.utc) + timedelta(minutes=self.LINK_TTL_MINUTES)
        expiration_str = expiration_time.isoformat().replace("+00:00", "Z")

        payload = {
            "amount": float(amount),
            "currency": self.DEFAULT_CURRENCY,
            "description": details[:255],
            "orderId": str(payment_id),
            "type": "OneTime",
            "expirationDateTime": expiration_str,
            "successRedirectUrl": resolved_success_url,
            "failRedirectUrl": resolved_fail_url,
        }

        try:
            response = await self._client.post("/links", json=payload)
            response.raise_for_status()
            data = orjson.loads(response.content)

            payment_url = data.get("url") or data.get("paymentUrl")
            if not payment_url:
                raise KeyError("Invalid response from WATA API: missing payment URL")

            logger.info(
                "WATA payment link created. payment_id='{}' link_id='{}'",
                payment_id,
                data.get("id"),
            )
            return PaymentResult(id=payment_id, url=payment_url)

        except HTTPStatusError as exception:
            logger.error(
                "HTTP error creating WATA payment. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse WATA response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(
                f"An unexpected error occurred while creating WATA payment: {exception}"
            )
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        try:
            body = await request.body()
            signature = request.headers.get("X-Signature")
            if not signature or not signature.strip():
                raise PermissionError("Missing WATA webhook signature")
            await self._verify_signature(body, signature)

            webhook_data = orjson.loads(body)
            logger.debug(f"WATA webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError("Invalid webhook payload format")

            status = webhook_data.get("transactionStatus") or webhook_data.get("status")
            payment_id = self._extract_payment_id(webhook_data)
            transaction_status = self._map_webhook_status(status)
            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate WATA webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    @staticmethod
    def _extract_payment_id(webhook_data: dict[str, Any]) -> UUID:
        raw_transaction_id = webhook_data.get("transactionId")
        raw_order_id = webhook_data.get("orderId")
        if not raw_transaction_id and not raw_order_id:
            raise ValueError("Missing orderId/transactionId in webhook")

        parse_error: ValueError | None = None
        for candidate in (raw_transaction_id, raw_order_id):
            if not candidate:
                continue
            try:
                return UUID(str(candidate))
            except ValueError as exception:
                parse_error = exception

        raise ValueError("Invalid UUID format for webhook payment id") from parse_error

    @staticmethod
    def _map_webhook_status(status: Any) -> TransactionStatus:
        normalized = str(status or "").lower()
        if normalized in {"paid", "completed", "success"}:
            return TransactionStatus.COMPLETED
        if normalized in {"declined", "failed", "cancelled", "expired"}:
            return TransactionStatus.CANCELED
        if normalized in {"created", "pending", "processing"}:
            return TransactionStatus.PENDING

        logger.info(f"Ignoring WATA webhook status: {status}")
        raise ValueError(f"Unsupported status: {status}")

    async def get_payment_link(self, link_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(f"/links/{link_id}")
            response.raise_for_status()
            return orjson.loads(response.content)
        except Exception as exception:
            logger.error(f"Failed to get WATA payment link info: {exception}")
            raise

    async def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        try:
            response = await self._client.get(f"/transactions/{transaction_id}")
            response.raise_for_status()
            return orjson.loads(response.content)
        except Exception as exception:
            logger.error(f"Failed to get WATA transaction info: {exception}")
            raise

    async def search_transactions(
        self,
        order_id: str | None = None,
        payment_link_id: str | None = None,
        status: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
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
            return orjson.loads(response.content)
        except HTTPStatusError as exception:
            if exception.response.status_code == 429:
                logger.warning(
                    "WATA transactions rate limited. retry_after='{}'",
                    exception.response.headers.get("Retry-After"),
                )
            logger.error(
                "Failed to search WATA transactions. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise
        except Exception as exception:
            logger.error(f"Failed to search WATA transactions: {exception}")
            raise

    async def _verify_signature(self, body: bytes, signature: str) -> None:
        public_key_pem = await self._get_public_key()
        if not public_key_pem:
            raise PermissionError("Unable to verify WATA signature: public key is unavailable")

        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
        except (TypeError, ValueError) as exception:
            raise PermissionError("Invalid WATA public key") from exception
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise PermissionError("Invalid WATA public key type")
        try:
            signature_bytes = self._decode_signature(signature)
            public_key.verify(
                signature_bytes,
                body,
                padding.PKCS1v15(),
                hashes.SHA512(),
            )
        except (TypeError, ValueError, InvalidSignature) as exception:
            raise PermissionError("Invalid WATA webhook signature") from exception

    async def _get_public_key(self) -> str | None:
        now = datetime.now(timezone.utc)
        if (
            self._public_key_cache
            and self._public_key_loaded_at
            and (now - self._public_key_loaded_at).total_seconds() < self.PUBLIC_KEY_TTL_SECONDS
        ):
            return self._public_key_cache

        response = await self._client.get("/public-key")
        response.raise_for_status()

        key: str | None = None
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            payload = orjson.loads(response.content)
            if isinstance(payload, dict):
                key = payload.get("value") or payload.get("publicKey") or payload.get("public_key")
        else:
            key = response.text

        if not key:
            raise ValueError("WATA public key response is empty")

        if "BEGIN PUBLIC KEY" not in key:
            key = f"-----BEGIN PUBLIC KEY-----\n{key}\n-----END PUBLIC KEY-----"

        self._public_key_cache = key
        self._public_key_loaded_at = now
        return key

    @staticmethod
    def _decode_signature(signature: str) -> bytes:
        raw = signature.strip()
        try:
            return base64.b64decode(raw, validate=True)
        except Exception:
            return bytes.fromhex(raw)
