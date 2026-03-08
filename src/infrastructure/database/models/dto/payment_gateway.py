from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator

from src.core.enums import Currency, PaymentGatewayType, YookassaVatCode

from .base import TrackableDto

PLATEGA_PAYMENT_METHOD_ALIASES: dict[str, int] = {
    "1": 1,
    "2": 2,
    "CARD": 1,
    "SBP": 2,
    "SBPQR": 2,
}


def normalize_platega_payment_method(
    value: Any,
    *,
    strict: bool = True,
    default: int = 2,
) -> int:
    if isinstance(value, bool):
        if strict:
            raise ValueError("Invalid Platega payment_method. Use 1 (CARD) or 2 (SBP).")
        return default

    if isinstance(value, int):
        if value in (1, 2):
            return value
        if strict:
            raise ValueError("Invalid Platega payment_method. Use 1 (CARD) or 2 (SBP).")
        return default

    if isinstance(value, str):
        mapped = PLATEGA_PAYMENT_METHOD_ALIASES.get(value.strip().upper())
        if mapped is not None:
            return mapped
        if strict:
            raise ValueError("Invalid Platega payment_method. Use 1 (CARD) or 2 (SBP).")
        return default

    if strict:
        raise ValueError("Invalid Platega payment_method. Use 1 (CARD) or 2 (SBP).")
    return default


class PaymentResult(TrackableDto):
    id: UUID
    url: Optional[str] = None


class GatewaySettingsDto(TrackableDto):
    @property
    def is_configure(self) -> bool:
        for name, value in self.__dict__.items():
            if value is None:
                return False
        return True

    @property
    def get_settings_as_list_data(self) -> list[dict[str, Any]]:
        return [
            {"field": field_name, "value": value}
            for field_name, value in self.__dict__.items()
            if field_name != "type"
        ]


class YookassaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.YOOKASSA] = PaymentGatewayType.YOOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    customer: Optional[str] = None
    vat_code: Optional[YookassaVatCode] = None


class YoomoneyGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.YOOMONEY] = PaymentGatewayType.YOOMONEY
    wallet_id: Optional[str] = None
    secret_key: Optional[SecretStr] = None


class CryptomusGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CRYPTOMUS] = PaymentGatewayType.CRYPTOMUS
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


class HeleketGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.HELEKET] = PaymentGatewayType.HELEKET
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


class CryptopayGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CRYPTOPAY] = PaymentGatewayType.CRYPTOPAY
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None


class TbankGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.TBANK] = PaymentGatewayType.TBANK
    terminal_key: Optional[str] = None
    password: Optional[SecretStr] = None


class RobokassaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.ROBOKASSA] = PaymentGatewayType.ROBOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None


class StripeGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.STRIPE] = PaymentGatewayType.STRIPE
    secret_key: Optional[SecretStr] = None
    webhook_secret: Optional[SecretStr] = None


class MulenpayGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.MULENPAY] = PaymentGatewayType.MULENPAY
    api_key: Optional[SecretStr] = None


class CloudPaymentsGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CLOUDPAYMENTS] = PaymentGatewayType.CLOUDPAYMENTS
    public_id: Optional[str] = None
    api_secret: Optional[SecretStr] = None


class Pal24GatewaySettingsDto(GatewaySettingsDto):
    """PayPalych (Pal24) payment gateway settings."""

    type: Literal[PaymentGatewayType.PAL24] = PaymentGatewayType.PAL24
    api_key: Optional[SecretStr] = None
    shop_id: Optional[str] = None


class WataGatewaySettingsDto(GatewaySettingsDto):
    """WATA payment gateway settings."""

    type: Literal[PaymentGatewayType.WATA] = PaymentGatewayType.WATA
    access_token: Optional[SecretStr] = None
    base_url: Optional[str] = None


class PlategaGatewaySettingsDto(GatewaySettingsDto):
    """Platega payment gateway settings."""

    type: Literal[PaymentGatewayType.PLATEGA] = PaymentGatewayType.PLATEGA
    merchant_id: Optional[str] = None
    secret: Optional[SecretStr] = None
    payment_method: int = 2

    @field_validator("payment_method", mode="before")
    @classmethod
    def _validate_payment_method(cls, value: Any) -> int:
        return normalize_platega_payment_method(value, strict=True, default=2)


AnyGatewaySettingsDto = Annotated[
    Union[
        YookassaGatewaySettingsDto,
        YoomoneyGatewaySettingsDto,
        CryptomusGatewaySettingsDto,
        HeleketGatewaySettingsDto,
        CryptopayGatewaySettingsDto,
        TbankGatewaySettingsDto,
        RobokassaGatewaySettingsDto,
        StripeGatewaySettingsDto,
        MulenpayGatewaySettingsDto,
        CloudPaymentsGatewaySettingsDto,
        Pal24GatewaySettingsDto,
        WataGatewaySettingsDto,
        PlategaGatewaySettingsDto,
    ],
    Field(discriminator="type"),
]


class PaymentGatewayDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    order_index: int
    type: PaymentGatewayType
    currency: Currency

    is_active: bool
    settings: Optional[AnyGatewaySettingsDto] = None

    @model_validator(mode="before")
    @classmethod
    def _inject_settings_type(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        settings = value.get("settings")
        gateway_type = value.get("type")

        if not isinstance(settings, dict) or not gateway_type:
            return value

        normalized_settings = dict(settings)
        normalized_settings.setdefault("type", gateway_type)

        normalized_type = normalized_settings.get("type")
        if normalized_type == PaymentGatewayType.PLATEGA or (
            isinstance(normalized_type, str) and normalized_type == PaymentGatewayType.PLATEGA.value
        ):
            normalized_settings["payment_method"] = normalize_platega_payment_method(
                normalized_settings.get("payment_method"),
                strict=False,
                default=2,
            )

        normalized_value = dict(value)
        normalized_value["settings"] = normalized_settings
        return normalized_value
