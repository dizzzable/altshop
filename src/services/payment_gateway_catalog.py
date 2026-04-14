from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from loguru import logger

from src.core.enums import Currency, PaymentGatewayType
from src.infrastructure.database.models.dto import (
    AnyGatewaySettingsDto,
    CloudPaymentsGatewaySettingsDto,
    CryptomusGatewaySettingsDto,
    CryptopayGatewaySettingsDto,
    HeleketGatewaySettingsDto,
    MulenpayGatewaySettingsDto,
    Pal24GatewaySettingsDto,
    PaymentGatewayDto,
    PlategaGatewaySettingsDto,
    RobokassaGatewaySettingsDto,
    StripeGatewaySettingsDto,
    TbankGatewaySettingsDto,
    WataGatewaySettingsDto,
    YookassaGatewaySettingsDto,
    YoomoneyGatewaySettingsDto,
    normalize_platega_payment_method,
)
from src.infrastructure.database.models.sql import PaymentGateway

if TYPE_CHECKING:
    from .payment_gateway import PaymentGatewayService
else:
    PaymentGatewayService = Any


_DEFAULT_GATEWAY_SETTINGS_FACTORIES: dict[
    PaymentGatewayType, Callable[[], Optional[AnyGatewaySettingsDto]]
] = {
    PaymentGatewayType.TELEGRAM_STARS: lambda: None,
    PaymentGatewayType.YOOKASSA: YookassaGatewaySettingsDto,
    PaymentGatewayType.YOOMONEY: YoomoneyGatewaySettingsDto,
    PaymentGatewayType.CRYPTOPAY: CryptopayGatewaySettingsDto,
    PaymentGatewayType.TBANK: TbankGatewaySettingsDto,
    PaymentGatewayType.CRYPTOMUS: CryptomusGatewaySettingsDto,
    PaymentGatewayType.HELEKET: HeleketGatewaySettingsDto,
    PaymentGatewayType.ROBOKASSA: RobokassaGatewaySettingsDto,
    PaymentGatewayType.STRIPE: StripeGatewaySettingsDto,
    PaymentGatewayType.MULENPAY: MulenpayGatewaySettingsDto,
    PaymentGatewayType.CLOUDPAYMENTS: CloudPaymentsGatewaySettingsDto,
    PaymentGatewayType.PAL24: Pal24GatewaySettingsDto,
    PaymentGatewayType.WATA: WataGatewaySettingsDto,
    PaymentGatewayType.PLATEGA: PlategaGatewaySettingsDto,
}


def _build_default_gateway_settings(
    gateway_type: PaymentGatewayType,
) -> tuple[bool, Optional[AnyGatewaySettingsDto]]:
    settings_factory = _DEFAULT_GATEWAY_SETTINGS_FACTORIES.get(gateway_type)
    if settings_factory is None:
        raise ValueError(f"Unhandled payment gateway type '{gateway_type}' - skipping")
    return gateway_type == PaymentGatewayType.TELEGRAM_STARS, settings_factory()


async def create_default(service: PaymentGatewayService) -> None:
    for gateway_type in PaymentGatewayType:
        if await service.get_by_type(gateway_type):
            continue

        try:
            is_active, settings = _build_default_gateway_settings(gateway_type)
        except ValueError as exception:
            logger.warning(str(exception))
            continue

        order_index = await service.uow.repository.gateways.get_max_index()
        order_index = (order_index or 0) + 1

        payment_gateway = PaymentGatewayDto(
            order_index=order_index,
            type=gateway_type,
            currency=Currency.from_gateway_type(gateway_type),
            is_active=is_active,
            settings=settings,
        )

        db_payment_gateway = PaymentGateway(**payment_gateway.model_dump())
        db_payment_gateway = await service.uow.repository.gateways.create(db_payment_gateway)

        logger.info(f"Payment gateway '{gateway_type}' created")


async def normalize_gateway_settings(service: PaymentGatewayService) -> None:
    """Normalize legacy gateway settings values to canonical forms."""
    db_gateways = await service.uow.repository.gateways.get_all()

    for db_gateway in db_gateways:
        if db_gateway.type != PaymentGatewayType.PLATEGA:
            if (
                db_gateway.type == PaymentGatewayType.CRYPTOPAY
                and db_gateway.currency != Currency.USD
            ):
                await service.uow.repository.gateways.update(
                    gateway_id=db_gateway.id,
                    currency=Currency.USD,
                )
                logger.warning(
                    "Normalized CRYPTOPAY currency for gateway_id='{}'. '{}' -> '{}'",
                    db_gateway.id,
                    db_gateway.currency,
                    Currency.USD,
                )
            continue

        if not isinstance(db_gateway.settings, dict):
            continue

        settings_data = dict(db_gateway.settings)
        old_method = settings_data.get("payment_method")
        normalized_method = normalize_platega_payment_method(
            old_method,
            strict=False,
            default=PlategaGatewaySettingsDto().payment_method,
        )

        if old_method == normalized_method and settings_data.get("type") is not None:
            continue

        settings_data["type"] = PaymentGatewayType.PLATEGA.value
        settings_data["payment_method"] = normalized_method

        await service.uow.repository.gateways.update(
            gateway_id=db_gateway.id,
            settings=settings_data,
        )
        logger.warning(
            "Normalized PLATEGA settings for gateway_id='{}'. payment_method: '{}' -> '{}'",
            db_gateway.id,
            old_method,
            normalized_method,
        )
