"""Robokassa hosted payment gateway implementation."""

import hashlib
import hmac
import uuid
from decimal import Decimal
from typing import Final
from urllib.parse import parse_qs, urlencode
from uuid import UUID

from aiogram import Bot
from fastapi import Request
from fastapi.responses import PlainTextResponse
from loguru import logger

from src.core.config import AppConfig
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    RobokassaGatewaySettingsDto,
)

from .base import BasePaymentGateway


class RobokassaGateway(BasePaymentGateway):
    """Robokassa hosted payment form gateway."""

    PAYMENT_URL: Final[str] = "https://auth.robokassa.ru/Merchant/Index.aspx"

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, RobokassaGatewaySettingsDto):
            raise TypeError("RobokassaGateway requires RobokassaGatewaySettingsDto")

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
        payment_id = payment_id or uuid.uuid4()
        inv_id = payment_id.hex
        out_sum = self._format_amount(amount)
        shp_items = {"Shp_payment_id": str(payment_id)}
        signature = self._calculate_payment_signature(out_sum, inv_id, shp_items)

        params = {
            "MerchantLogin": self._get_shop_id(),
            "OutSum": out_sum,
            "InvId": inv_id,
            "Description": details[:100],
            "SignatureValue": signature,
            "Culture": "ru",
            "Encoding": "utf-8",
            **shp_items,
        }
        if success_redirect_url:
            params["SuccessUrl"] = success_redirect_url
        if fail_redirect_url:
            params["FailUrl"] = fail_redirect_url
        if is_test_payment:
            params["IsTest"] = "1"

        payment_url = f"{self.PAYMENT_URL}?{urlencode(params)}"
        logger.info("Robokassa payment created. payment_id='{}' inv_id='{}'", payment_id, inv_id)
        return PaymentResult(id=payment_id, url=payment_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        form_data = await self._parse_request_data(request)
        raw_out_sum = form_data.get("OutSum")
        inv_id = form_data.get("InvId")
        provided_signature = form_data.get("SignatureValue") or form_data.get("signaturevalue")
        if not raw_out_sum or not inv_id or not provided_signature:
            raise ValueError("Missing Robokassa webhook fields")

        shp_params = {
            key: value
            for key, value in form_data.items()
            if key.startswith("Shp_")
        }
        expected_signature = self._calculate_result_signature(raw_out_sum, inv_id, shp_params)
        if not hmac.compare_digest(expected_signature.lower(), provided_signature.lower()):
            raise PermissionError("Invalid Robokassa webhook signature")

        raw_payment_id = shp_params.get("Shp_payment_id") or inv_id
        try:
            payment_id = UUID(str(raw_payment_id))
        except ValueError as exception:
            raise ValueError("Invalid UUID format for Robokassa payment id") from exception

        return payment_id, TransactionStatus.COMPLETED

    async def build_webhook_response(self, request: Request) -> PlainTextResponse:
        data = await self._parse_request_data(request)
        inv_id = data.get("InvId", "")
        return PlainTextResponse(f"OK{inv_id}")

    async def _parse_request_data(self, request: Request) -> dict[str, str]:
        body = await request.body()
        if body:
            parsed_body = {
                key: values[0]
                for key, values in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()
                if values
            }
            if parsed_body:
                return parsed_body

        return dict(request.query_params)

    def _calculate_payment_signature(
        self,
        out_sum: str,
        inv_id: str,
        shp_params: dict[str, str],
    ) -> str:
        parts = [self._get_shop_id(), out_sum, inv_id, self._get_api_key()]
        parts.extend(f"{key}={shp_params[key]}" for key in sorted(shp_params))
        return hashlib.md5(":".join(parts).encode()).hexdigest()

    def _calculate_result_signature(
        self,
        out_sum: str,
        inv_id: str,
        shp_params: dict[str, str],
    ) -> str:
        parts = [out_sum, inv_id, self._get_secret_key()]
        parts.extend(f"{key}={shp_params[key]}" for key in sorted(shp_params))
        return hashlib.md5(":".join(parts).encode()).hexdigest()

    def _get_shop_id(self) -> str:
        shop_id = (self.gateway.settings.shop_id or "").strip()
        if not shop_id:
            raise ValueError("Robokassa shop_id is required")
        return shop_id

    def _get_api_key(self) -> str:
        api_key = self.gateway.settings.api_key
        secret = api_key.get_secret_value().strip() if api_key else ""
        if not secret:
            raise ValueError("Robokassa api_key is required")
        return secret

    def _get_secret_key(self) -> str:
        secret_key = self.gateway.settings.secret_key
        secret = secret_key.get_secret_value().strip() if secret_key else ""
        if not secret:
            raise ValueError("Robokassa secret_key is required")
        return secret

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")
