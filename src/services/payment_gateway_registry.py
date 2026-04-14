from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.core.enums import PaymentGatewayType
from src.infrastructure.database.models.dto import PaymentGatewayDto

if TYPE_CHECKING:
    from .payment_gateway import PaymentGatewayService
else:
    PaymentGatewayService = Any


async def get(
    service: PaymentGatewayService,
    gateway_id: int,
) -> Optional[PaymentGatewayDto]:
    db_gateway = await service.uow.repository.gateways.get(gateway_id)

    if not db_gateway:
        logger.warning(f"Payment gateway '{gateway_id}' not found")
        return None

    logger.debug(f"Retrieved payment gateway '{gateway_id}'")
    return PaymentGatewayDto.from_model(db_gateway, decrypt=True)


async def get_by_type(
    service: PaymentGatewayService,
    gateway_type: PaymentGatewayType,
) -> Optional[PaymentGatewayDto]:
    db_gateway = await service.uow.repository.gateways.get_by_type(gateway_type)

    if not db_gateway:
        logger.warning(f"Payment gateway of type '{gateway_type}' not found")
        return None

    logger.debug(f"Retrieved payment gateway of type '{gateway_type}'")
    return PaymentGatewayDto.from_model(db_gateway, decrypt=True)


async def get_all(
    service: PaymentGatewayService,
    sorted: bool = False,
) -> list[PaymentGatewayDto]:
    db_gateways = await service.uow.repository.gateways.get_all(sorted)
    logger.debug(f"Retrieved '{len(db_gateways)}' payment gateways")
    return PaymentGatewayDto.from_model_list(db_gateways, decrypt=False)


async def update(
    service: PaymentGatewayService,
    gateway: PaymentGatewayDto,
) -> Optional[PaymentGatewayDto]:
    updated_data = gateway.changed_data

    if gateway.settings and gateway.settings.changed_data:
        updated_data["settings"] = gateway.settings.prepare_init_data(encrypt=True)

    db_updated_gateway = await service.uow.repository.gateways.update(
        gateway_id=gateway.id,  # type: ignore[arg-type]
        **updated_data,
    )

    if db_updated_gateway:
        logger.info(f"Payment gateway '{gateway.type}' updated successfully")
    else:
        logger.warning(
            f"Attempted to update gateway '{gateway.type}' (ID: '{gateway.id}'), "
            f"but gateway was not found or update failed"
        )

    return PaymentGatewayDto.from_model(db_updated_gateway, decrypt=True)


async def filter_active(
    service: PaymentGatewayService,
    is_active: bool = True,
) -> list[PaymentGatewayDto]:
    db_gateways = await service.uow.repository.gateways.filter_active(is_active)
    logger.debug(f"Filtered active gateways: '{is_active}', found '{len(db_gateways)}'")
    return PaymentGatewayDto.from_model_list(db_gateways, decrypt=False)


async def move_gateway_up(
    service: PaymentGatewayService,
    gateway_id: int,
) -> bool:
    db_gateways = await service.uow.repository.gateways.get_all()
    db_gateways.sort(key=lambda gateway: gateway.order_index)

    index = next((i for i, gateway in enumerate(db_gateways) if gateway.id == gateway_id), None)
    if index is None:
        logger.warning(f"Payment gateway with ID '{gateway_id}' not found for move operation")
        return False

    if index == 0:
        gateway = db_gateways.pop(0)
        db_gateways.append(gateway)
        logger.debug(f"Payment gateway '{gateway_id}' moved from top to bottom")
    else:
        db_gateways[index - 1], db_gateways[index] = db_gateways[index], db_gateways[index - 1]
        logger.debug(f"Payment gateway '{gateway_id}' moved up one position")

    for order_index, gateway in enumerate(db_gateways, start=1):
        gateway.order_index = order_index

    logger.info(f"Payment gateway '{gateway_id}' reorder successfully")
    return True
