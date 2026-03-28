import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.api.utils.request_ip import resolve_client_ip
from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus, YookassaVatCode
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    YookassaGatewaySettingsDto,
)

from .base import BasePaymentGateway


class YookassaGateway(BasePaymentGateway):
    _client: AsyncClient | None

    API_BASE: Final[str] = "https://api.yookassa.ru/v3/payments"
    PAYMENT_SUBJECT: Final[str] = "service"
    PAYMENT_MODE: Final[str] = "full_payment"

    VAT_CODE: Final[YookassaVatCode] = YookassaVatCode.VAT_CODE_01
    CUSTOMER: Final[str] = "test@remnashop.com"

    # IP-адреса ЮKassa для webhook уведомлений
    # https://yookassa.ru/developers/using-api/webhooks#ip
    NETWORKS = [
        "185.71.76.0/27",
        "185.71.77.0/27",
        "77.75.153.0/25",
        "77.75.156.11/32",
        "77.75.156.35/32",
        "77.75.154.128/25",
        "2a02:5180::/32",
    ]

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, YookassaGatewaySettingsDto):
            raise TypeError("YookassaGateway requires YookassaGatewaySettingsDto")
        self._client = None

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
        client = self._get_client()
        resolved_payment_id = payment_id or uuid.uuid4()
        headers = {"Idempotence-Key": str(resolved_payment_id)}
        payload = await self._create_payment_payload(
            str(amount),
            details,
            payment_id=resolved_payment_id,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
        )

        try:
            content = orjson.dumps(payload)
            response = await client.post("", headers=headers, content=content)
            response.raise_for_status()
            data = orjson.loads(response.content)
            return self._get_payment_data(data, payment_id=resolved_payment_id)

        except HTTPStatusError as exception:
            logger.error(
                f"HTTP error creating payment. "
                f"Status: '{exception.response.status_code}', Body: {exception.response.text}"
            )
            raise
        except (KeyError, orjson.JSONDecodeError) as exception:
            logger.error(f"Failed to parse response. Error: {exception}")
            raise
        except Exception as exception:
            logger.exception(f"An unexpected error occurred while creating payment: {exception}")
            raise

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        # Получаем IP клиента из различных заголовков
        client_ip = (
            resolve_client_ip(request, self.config)
            if self.config is not None
            else (request.client.host if request.client else "")
        )
        x_forwarded_for = request.headers.get("X-Forwarded-For", "")
        x_real_ip = request.headers.get("X-Real-IP", "")

        logger.debug(
            f"Webhook request - X-Forwarded-For: '{x_forwarded_for}', "
            f"X-Real-IP: '{x_real_ip}', Resolved IP: '{client_ip}'"
        )

        if not self._is_ip_trusted(client_ip):
            logger.warning(
                f"Webhook received from untrusted IP: '{client_ip}'. "
                f"Trusted networks: {self.NETWORKS}"
            )
            raise PermissionError("IP address is not trusted")

        try:
            webhook_data = orjson.loads(await request.body())
            logger.debug(f"Webhook data: {webhook_data}")

            if not isinstance(webhook_data, dict):
                raise ValueError

            payment_object: dict = webhook_data.get("object", {})
            metadata = payment_object.get("metadata") or {}
            payment_id_str = None
            if isinstance(metadata, dict):
                payment_id_str = metadata.get("payment_id")
            payment_id_str = payment_id_str or payment_object.get("id")
            status_str = payment_object.get("status")

            if not payment_id_str or not status_str:
                raise ValueError("Required fields 'id' or 'status' are missing")

            try:
                payment_id = UUID(payment_id_str)
            except ValueError:
                raise ValueError("Invalid UUID format for payment ID")

            match status_str:
                case "succeeded":
                    transaction_status = TransactionStatus.COMPLETED
                case "canceled":
                    transaction_status = TransactionStatus.CANCELED
                case _:
                    logger.info(f"Ignoring webhook status: {status_str}")
                    raise ValueError("Field 'status' not support")

            return payment_id, transaction_status

        except (orjson.JSONDecodeError, ValueError) as exception:
            logger.error(f"Failed to parse or validate webhook payload: {exception}")
            raise ValueError("Invalid webhook payload") from exception

    async def _create_payment_payload(
        self,
        amount: str,
        details: str,
        payment_id: UUID,
        success_redirect_url: str | None = None,
        fail_redirect_url: str | None = None,
    ) -> dict[str, Any]:
        return_url = success_redirect_url or fail_redirect_url or await self._get_bot_redirect_url()
        return {
            "amount": {"value": amount, "currency": self.gateway.currency},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": details,
            "metadata": {"payment_id": str(payment_id)},
            "receipt": {
                "customer": {"email": self.gateway.settings.customer or self.CUSTOMER},
                "items": [
                    {
                        "description": details,
                        "quantity": "1.00",
                        "amount": {"value": amount, "currency": self.gateway.currency},
                        "vat_code": self.gateway.settings.vat_code or self.VAT_CODE,
                        "payment_subject": self.PAYMENT_SUBJECT,
                        "payment_mode": self.PAYMENT_MODE,
                    }
                ],
            },
        }

    def _get_payment_data(self, data: dict[str, Any], *, payment_id: UUID) -> PaymentResult:
        payment_id_str = data.get("id")

        if not payment_id_str:
            raise KeyError("Invalid response from Yookassa API: missing 'id'")

        confirmation: dict = data.get("confirmation", {})
        payment_url = confirmation.get("confirmation_url")

        if not payment_url:
            raise KeyError("Invalid response from Yookassa API: missing 'confirmation_url'")

        logger.debug(
            "Yookassa payment created. internal_payment_id='{}' provider_payment_id='{}'",
            payment_id,
            payment_id_str,
        )
        return PaymentResult(id=payment_id, url=str(payment_url))

    def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = self._make_client(
                base_url=self.API_BASE,
                auth=(self._get_shop_id(), self._get_api_key()),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    def _get_shop_id(self) -> str:
        shop_id = (self.gateway.settings.shop_id or "").strip()
        if not shop_id:
            raise ValueError("Yookassa shop_id is required")
        return shop_id

    def _get_api_key(self) -> str:
        api_key = self.gateway.settings.api_key
        secret = api_key.get_secret_value().strip() if api_key else ""
        if not secret:
            raise ValueError("Yookassa api_key is required")
        return secret
