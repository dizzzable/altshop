from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from src.core.crypto_assets import get_supported_payment_assets
from src.core.enums import CryptoAsset, Currency, PaymentGatewayType, PurchaseChannel
from src.infrastructure.database.models.dto import PaymentGatewayDto, UserDto

from .purchase_gateway_policy import filter_gateways_by_channel, is_gateway_available_for_channel
from .subscription_purchase_models import SubscriptionPurchaseError, SubscriptionPurchaseRequest

if TYPE_CHECKING:
    from .subscription_purchase import SubscriptionPurchaseService


async def _resolve_purchase_gateway(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
    available_gateways = filter_gateways_by_channel(
        await service.payment_gateway_service.filter_active(is_active=True),
        channel=request.channel,
    )
    available_by_type = {gateway.type: gateway for gateway in available_gateways}

    if request.gateway_type:
        return await service._resolve_explicit_purchase_gateway(
            request=request,
            available_by_type=available_by_type,
        )

    return service._resolve_implicit_purchase_gateway(
        request=request,
        available_gateways=available_gateways,
        available_by_type=available_by_type,
    )


async def _resolve_explicit_purchase_gateway(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
    try:
        gateway_type = PaymentGatewayType(request.gateway_type or "")
    except ValueError as exception:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid gateway type: {request.gateway_type}",
        ) from exception

    if not is_gateway_available_for_channel(gateway_type, request.channel):
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Gateway {gateway_type.value} is not available for "
                f"{request.channel.value.lower()} purchases"
            ),
        )

    gateway = available_by_type.get(gateway_type)
    if gateway:
        return gateway, gateway_type

    configured_gateway = await service.payment_gateway_service.get_by_type(gateway_type)
    if not configured_gateway:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Gateway {gateway_type.value} is not configured",
        )
    if not configured_gateway.is_active:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Gateway {gateway_type.value} is disabled",
        )
    raise SubscriptionPurchaseError(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=(
            f"Gateway {gateway_type.value} is not available for "
            f"{request.channel.value.lower()} purchases"
        ),
    )


def _resolve_implicit_purchase_gateway(
    _service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    available_gateways: list[PaymentGatewayDto],
    available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
    if request.channel == PurchaseChannel.TELEGRAM:
        preferred_gateway = available_by_type.get(PaymentGatewayType.TELEGRAM_STARS)
        if preferred_gateway:
            return preferred_gateway, preferred_gateway.type
        if len(available_gateways) == 1:
            only_gateway = available_gateways[0]
            return only_gateway, only_gateway.type
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Gateway type is required for Telegram purchase",
        )

    if not available_gateways:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="No active web payment gateways are available",
        )
    if len(available_gateways) > 1:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Gateway type is required when multiple web gateways are available",
        )

    only_gateway = available_gateways[0]
    return only_gateway, only_gateway.type


def _resolve_payment_asset(
    _service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    gateway_type: PaymentGatewayType,
) -> CryptoAsset | None:
    supported_assets = get_supported_payment_assets(gateway_type)
    requested_asset = request.payment_asset

    if not supported_assets:
        if requested_asset is not None:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Gateway {gateway_type.value} does not support payment_asset",
            )
        return None

    if requested_asset is None:
        if len(supported_assets) == 1:
            return supported_assets[0]
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"payment_asset is required for gateway {gateway_type.value}",
        )

    if requested_asset not in supported_assets:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Unsupported payment_asset '{requested_asset.value}' for "
                f"gateway {gateway_type.value}"
            ),
        )

    return requested_asset


async def _assert_partner_balance_purchase_allowed(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    gateway: PaymentGatewayDto,
) -> None:
    if request.channel != PurchaseChannel.WEB:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": "PARTNER_BALANCE_WEB_ONLY",
                "message": "Partner balance payments are allowed only in WEB channel",
            },
        )

    if not request.gateway_type:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": "PARTNER_BALANCE_GATEWAY_REQUIRED",
                "message": "gateway_type is required for partner balance payment",
            },
        )

    if gateway.currency != Currency.RUB:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": "PARTNER_BALANCE_RUB_ONLY",
                "message": "Partner balance payments are available only with RUB gateways",
            },
        )

    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner or not partner.is_active:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.FORBIDDEN,
            detail={
                "code": "PARTNER_BALANCE_PARTNER_INACTIVE",
                "message": "Partner balance payments are available only for active partners",
            },
        )
