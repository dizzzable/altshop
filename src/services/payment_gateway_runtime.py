from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from src.core.enums import PaymentGatewayType
from src.infrastructure.payment_gateways import BasePaymentGateway

if TYPE_CHECKING:
    from .payment_gateway import PaymentGatewayService
else:
    PaymentGatewayService = Any


async def get_gateway_instance(
    service: PaymentGatewayService,
    gateway_type: PaymentGatewayType,
) -> BasePaymentGateway:
    logger.debug(f"Creating gateway instance for type '{gateway_type}'")
    gateway = await service.get_by_type(gateway_type)

    if not gateway:
        raise ValueError(f"Payment gateway of type '{gateway_type}' not found")

    return service.payment_gateway_factory(gateway)
