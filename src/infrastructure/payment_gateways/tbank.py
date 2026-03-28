"""T-Bank Acquiring hosted payment gateway implementation."""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from fastapi.responses import PlainTextResponse
from httpx import AsyncClient, HTTPStatusError
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    TbankGatewaySettingsDto,
)

from .base import BasePaymentGateway


class TbankGateway(BasePaymentGateway):
    """T-Bank EACQ hosted payment gateway."""

    API_BASE: Final[str] = "https://securepay.tinkoff.ru"
    SUCCESS_RESPONSE: Final[str] = "OK"

    _client: AsyncClient

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, TbankGatewaySettingsDto):
            raise TypeError("TbankGateway requires TbankGatewaySettingsDto")

        self._client = self._make_client(
            base_url=self.API_BASE,
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
        del payment_asset, is_test_payment

        payment_id = payment_id or uuid.uuid4()
        payload = self._build_init_payload(
            payment_id=payment_id,
            amount=amount,
            details=details,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
        )

        try:
            response = await self._client.post("/v2/Init", content=orjson.dumps(payload))
            response.raise_for_status()
            data = orjson.loads(response.content)
        except HTTPStatusError as exception:
            logger.error(
                "T-Bank Init failed. status='{}' body='{}'",
                exception.response.status_code,
                exception.response.text,
            )
            raise

        if not isinstance(data, dict):
            raise ValueError("Invalid T-Bank response payload")
        if not data.get("Success", False):
            message = data.get("Message") or data.get("Details") or "Unknown error"
            raise ValueError(f"T-Bank API error: {message}")

        payment_url = data.get("PaymentURL")
        if not payment_url:
            raise KeyError("Invalid T-Bank response: missing PaymentURL")

        return PaymentResult(id=payment_id, url=str(payment_url))

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        body = await request.body()
        try:
            payload = orjson.loads(body)
        except orjson.JSONDecodeError as exception:
            raise ValueError("Invalid T-Bank webhook payload") from exception

        if not isinstance(payload, dict):
            raise ValueError("Invalid T-Bank webhook payload")

        provided_token = payload.get("Token")
        if not isinstance(provided_token, str) or not provided_token.strip():
            raise PermissionError("Missing T-Bank webhook token")

        expected_token = self._generate_token(payload)
        if expected_token != provided_token.strip():
            raise PermissionError("Invalid T-Bank webhook token")

        raw_order_id = payload.get("OrderId")
        if not raw_order_id:
            raise ValueError("Missing OrderId in T-Bank webhook")

        try:
            payment_id = UUID(str(raw_order_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format for T-Bank OrderId") from exception

        return payment_id, self._map_status(payload.get("Status"))

    async def build_webhook_response(self, request: Request) -> PlainTextResponse:
        del request
        return PlainTextResponse(self.SUCCESS_RESPONSE)

    async def get_state(self, payment_id: UUID) -> dict[str, Any]:
        payload = {
            "TerminalKey": self._get_terminal_key(),
            "OrderId": str(payment_id),
        }
        payload["Token"] = self._generate_token(payload)

        response = await self._client.post("/v2/GetState", content=orjson.dumps(payload))
        response.raise_for_status()
        data = orjson.loads(response.content)
        if not isinstance(data, dict):
            raise ValueError("Invalid T-Bank GetState response payload")
        return data

    def _build_init_payload(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        details: str,
        success_redirect_url: str | None,
        fail_redirect_url: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "TerminalKey": self._get_terminal_key(),
            "Amount": self._to_kopecks(amount),
            "OrderId": str(payment_id),
            "Description": details[:140],
            "Language": "ru",
            "NotificationURL": self._get_notification_url(),
        }
        if success_redirect_url:
            payload["SuccessURL"] = success_redirect_url
        if fail_redirect_url:
            payload["FailURL"] = fail_redirect_url

        payload["Token"] = self._generate_token(payload)
        return payload

    def _generate_token(self, payload: dict[str, Any]) -> str:
        token_payload: dict[str, str] = {
            "Password": self._get_password(),
        }
        for key, value in payload.items():
            if key == "Token" or isinstance(value, (dict, list, tuple, set)) or value is None:
                continue
            token_payload[key] = str(value)

        concatenated = "".join(token_payload[key] for key in sorted(token_payload))
        return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

    def _get_terminal_key(self) -> str:
        terminal_key = (self.gateway.settings.terminal_key or "").strip()
        if not terminal_key:
            raise ValueError("T-Bank terminal_key is required")
        return terminal_key

    def _get_password(self) -> str:
        password = self.gateway.settings.password
        secret = password.get_secret_value().strip() if password else ""
        if not secret:
            raise ValueError("T-Bank password is required")
        return secret

    def _get_notification_url(self) -> str:
        if not self.config:
            raise ValueError("App config is required for T-Bank webhooks")
        return self.config.get_webhook(self.gateway.type)

    @staticmethod
    def _to_kopecks(amount: Decimal) -> int:
        return int((amount * Decimal("100")).quantize(Decimal("1")))

    @staticmethod
    def _map_status(status: object) -> TransactionStatus:
        normalized = str(status or "").upper()
        if normalized in {"AUTHORIZED", "CONFIRMED"}:
            return TransactionStatus.COMPLETED
        if normalized in {
            "NEW",
            "FORM_SHOWED",
            "3DS_CHECKING",
            "3DS_CHECKED",
            "AUTHORIZING",
            "REVERSING",
            "PARTIAL_REVERSED",
        }:
            return TransactionStatus.PENDING
        if normalized in {
            "CANCELED",
            "REJECTED",
            "AUTH_FAIL",
            "REVERSED",
            "REFUNDED",
            "DEADLINE_EXPIRED",
        }:
            return TransactionStatus.CANCELED
        raise ValueError(f"Unsupported T-Bank status: {status}")
