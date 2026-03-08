"""YooMoney wallet hosted payment gateway implementation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from decimal import Decimal
from typing import Final
from urllib.parse import parse_qs, urlencode
from uuid import UUID

import orjson
from aiogram import Bot
from fastapi import Request
from loguru import logger

from src.core.config import AppConfig
from src.core.constants import API_V1, PAYMENTS_WEBHOOK_PATH
from src.core.enums import CryptoAsset, TransactionStatus
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    YoomoneyGatewaySettingsDto,
)

from .base import BasePaymentGateway

YOOMONEY_REDIRECT_PATH: Final[str] = f"{API_V1 + PAYMENTS_WEBHOOK_PATH}/yoomoney/redirect"


def build_yoomoney_redirect_token(
    *,
    signing_secret: str,
    form_fields: dict[str, str],
) -> str:
    payload = base64.urlsafe_b64encode(orjson.dumps(form_fields)).decode().rstrip("=")
    signature = hmac.new(
        signing_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def parse_yoomoney_redirect_token(
    *,
    token: str,
    signing_secret: str,
) -> dict[str, str]:
    payload, separator, signature = token.partition(".")
    if not payload or not separator or not signature:
        raise ValueError("Invalid YooMoney redirect token")

    expected_signature = hmac.new(
        signing_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        raise PermissionError("Invalid YooMoney redirect token signature")

    padding = "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload + padding)
    parsed = orjson.loads(decoded)
    if not isinstance(parsed, dict):
        raise ValueError("Invalid YooMoney redirect payload")

    form_fields: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Invalid YooMoney redirect payload")
        form_fields[key] = value

    required_fields = {
        "receiver",
        "quickpay-form",
        "paymentType",
        "sum",
        "label",
        "targets",
    }
    if not required_fields.issubset(form_fields):
        raise ValueError("Invalid YooMoney redirect payload")

    return form_fields


class YoomoneyGateway(BasePaymentGateway):
    """YooMoney wallet hosted quickpay gateway."""

    QUICKPAY_URL: Final[str] = "https://yoomoney.ru/quickpay/confirm"
    QUICKPAY_FORM: Final[str] = "shop"
    DEFAULT_PAYMENT_TYPE: Final[str] = "AC"
    SUPPORTED_NOTIFICATION_TYPES: Final[set[str]] = {"p2p-in", "card-in"}
    TRUE_VALUES: Final[set[str]] = {"1", "true", "yes", "on"}

    def __init__(
        self,
        gateway: PaymentGatewayDto,
        bot: Bot,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(gateway, bot, config=config)

        if not isinstance(self.gateway.settings, YoomoneyGatewaySettingsDto):
            raise TypeError("YoomoneyGateway requires YoomoneyGatewaySettingsDto")

    async def handle_create_payment(
        self,
        amount: Decimal,
        details: str,
        payment_asset: CryptoAsset | None = None,
        success_redirect_url: str | None = None,
        fail_redirect_url: str | None = None,
        is_test_payment: bool = False,
    ) -> PaymentResult:
        if self.config is None:
            raise ValueError("YooMoney gateway requires AppConfig")

        payment_id = uuid.uuid4()
        success_url = (
            success_redirect_url or fail_redirect_url or await self._get_bot_redirect_url()
        )
        form_fields = self._build_form_fields(
            payment_id=payment_id,
            amount=amount,
            details=details,
            success_redirect_url=success_url,
        )
        token = build_yoomoney_redirect_token(
            signing_secret=self._get_redirect_signing_secret(),
            form_fields=form_fields,
        )
        redirect_url = self._build_redirect_url(token=token)

        logger.info(
            "YooMoney payment created. payment_id='{}' receiver='{}'",
            payment_id,
            form_fields["receiver"],
        )
        return PaymentResult(id=payment_id, url=redirect_url)

    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        form_data = await self._parse_request_data(request)
        notification_type = (form_data.get("notification_type") or "").strip().lower()
        if notification_type not in self.SUPPORTED_NOTIFICATION_TYPES:
            raise ValueError("Unsupported YooMoney notification_type")

        provided_signature = (form_data.get("sha1_hash") or "").strip()
        if not provided_signature:
            raise ValueError("Missing YooMoney sha1_hash")

        expected_signature = self._calculate_webhook_signature(form_data)
        if not hmac.compare_digest(expected_signature.lower(), provided_signature.lower()):
            raise PermissionError("Invalid YooMoney webhook signature")

        raw_payment_id = form_data.get("label")
        if not raw_payment_id:
            raise ValueError("Missing YooMoney label")

        try:
            payment_id = UUID(raw_payment_id)
        except ValueError as exception:
            raise ValueError("Invalid UUID format for YooMoney label") from exception

        is_pending = self._is_true_flag(form_data.get("codepro")) or self._is_true_flag(
            form_data.get("unaccepted")
        )
        status = TransactionStatus.PENDING if is_pending else TransactionStatus.COMPLETED
        return payment_id, status

    def _build_form_fields(
        self,
        *,
        payment_id: UUID,
        amount: Decimal,
        details: str,
        success_redirect_url: str,
    ) -> dict[str, str]:
        form_fields = {
            "receiver": self._get_wallet_id(),
            "quickpay-form": self.QUICKPAY_FORM,
            "paymentType": self.DEFAULT_PAYMENT_TYPE,
            "targets": details[:150],
            "sum": self._format_amount(amount),
            "label": str(payment_id),
        }
        if success_redirect_url:
            form_fields["successURL"] = success_redirect_url
        return form_fields

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

    def _calculate_webhook_signature(self, form_data: dict[str, str]) -> str:
        signature_parts = [
            form_data.get("notification_type", ""),
            form_data.get("operation_id", ""),
            form_data.get("amount", ""),
            form_data.get("currency", ""),
            form_data.get("datetime", ""),
            form_data.get("sender", ""),
            form_data.get("codepro", ""),
            self._get_secret_key(),
            form_data.get("label", ""),
        ]
        return hashlib.sha1("&".join(signature_parts).encode()).hexdigest()

    def _build_redirect_url(self, *, token: str) -> str:
        if self.config is None:
            raise ValueError("YooMoney gateway requires AppConfig")
        base_url = f"https://{self.config.domain.get_secret_value()}"
        return f"{base_url}{YOOMONEY_REDIRECT_PATH}?{urlencode({'token': token})}"

    def _get_wallet_id(self) -> str:
        wallet_id = (self.gateway.settings.wallet_id or "").strip()
        if not wallet_id:
            raise ValueError("YooMoney wallet_id is required")
        return wallet_id

    def _get_secret_key(self) -> str:
        secret_key = self.gateway.settings.secret_key
        secret = secret_key.get_secret_value().strip() if secret_key else ""
        if not secret:
            raise ValueError("YooMoney secret_key is required")
        return secret

    def _get_redirect_signing_secret(self) -> str:
        if self.config is None:
            raise ValueError("YooMoney gateway requires AppConfig")
        return self.config.crypt_key.get_secret_value()

    @classmethod
    def _is_true_flag(cls, value: str | None) -> bool:
        return (value or "").strip().lower() in cls.TRUE_VALUES

    @staticmethod
    def _format_amount(amount: Decimal) -> str:
        return format(amount.quantize(Decimal("0.01")), "f")
