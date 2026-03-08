from __future__ import annotations

from src.core.enums import PaymentGatewayType, PurchaseChannel
from src.infrastructure.database.models.dto import PaymentGatewayDto


def is_gateway_available_for_channel(
    gateway_type: PaymentGatewayType,
    channel: PurchaseChannel,
) -> bool:
    if channel == PurchaseChannel.WEB:
        return gateway_type != PaymentGatewayType.TELEGRAM_STARS
    return True


def filter_gateways_by_channel(
    gateways: list[PaymentGatewayDto],
    channel: PurchaseChannel,
) -> list[PaymentGatewayDto]:
    return [
        gateway for gateway in gateways if is_gateway_available_for_channel(gateway.type, channel)
    ]
