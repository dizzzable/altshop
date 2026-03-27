from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus
from typing import Protocol

from src.core.crypto_assets import get_supported_payment_assets
from src.core.enums import CryptoAsset, PaymentGatewayType, PurchaseChannel
from src.infrastructure.database.models.dto import PaymentGatewayDto

from .payment_gateway import PaymentGatewayService
from .purchase_gateway_policy import (
    filter_gateways_by_channel,
    is_gateway_available_for_channel,
)

PurchaseSelectionErrorDetail = str | dict[str, str]
PurchaseSelectionErrorFactory = Callable[[int, PurchaseSelectionErrorDetail], Exception]


class PurchaseGatewaySelectionRequest(Protocol):
    @property
    def channel(self) -> PurchaseChannel: ...

    @property
    def gateway_type(self) -> str | None: ...

    @property
    def payment_asset(self) -> CryptoAsset | None: ...


class SubscriptionPurchaseGatewaySelectionService:
    def __init__(
        self,
        *,
        payment_gateway_service: PaymentGatewayService,
        error_factory: PurchaseSelectionErrorFactory,
    ) -> None:
        self.payment_gateway_service = payment_gateway_service
        self.error_factory = error_factory

    async def resolve_purchase_gateway(
        self,
        *,
        request: PurchaseGatewaySelectionRequest,
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        available_gateways = filter_gateways_by_channel(
            await self.payment_gateway_service.filter_active(is_active=True),
            channel=request.channel,
        )
        available_by_type = {gateway.type: gateway for gateway in available_gateways}

        if request.gateway_type:
            return await self._resolve_explicit_purchase_gateway(
                request=request,
                available_by_type=available_by_type,
            )

        return self._resolve_implicit_purchase_gateway(
            request=request,
            available_gateways=available_gateways,
            available_by_type=available_by_type,
        )

    async def _resolve_explicit_purchase_gateway(
        self,
        *,
        request: PurchaseGatewaySelectionRequest,
        available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        try:
            gateway_type = PaymentGatewayType(request.gateway_type or "")
        except ValueError as exception:
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                f"Invalid gateway type: {request.gateway_type}",
            ) from exception

        if not is_gateway_available_for_channel(gateway_type, request.channel):
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                (
                    f"Gateway {gateway_type.value} is not available for "
                    f"{request.channel.value.lower()} purchases"
                ),
            )

        gateway = available_by_type.get(gateway_type)
        if gateway:
            return gateway, gateway_type

        configured_gateway = await self.payment_gateway_service.get_by_type(gateway_type)
        if not configured_gateway:
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                f"Gateway {gateway_type.value} is not configured",
            )
        if not configured_gateway.is_active:
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                f"Gateway {gateway_type.value} is disabled",
            )
        raise self.error_factory(
            HTTPStatus.BAD_REQUEST,
            (
                f"Gateway {gateway_type.value} is not available for "
                f"{request.channel.value.lower()} purchases"
            ),
        )

    def _resolve_implicit_purchase_gateway(
        self,
        *,
        request: PurchaseGatewaySelectionRequest,
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
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                "Gateway type is required for Telegram purchase",
            )

        if not available_gateways:
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                "No active web payment gateways are available",
            )
        if len(available_gateways) > 1:
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                "Gateway type is required when multiple web gateways are available",
            )

        only_gateway = available_gateways[0]
        return only_gateway, only_gateway.type

    def resolve_payment_asset(
        self,
        *,
        request: PurchaseGatewaySelectionRequest,
        gateway_type: PaymentGatewayType,
    ) -> CryptoAsset | None:
        supported_assets = get_supported_payment_assets(gateway_type)
        requested_asset = request.payment_asset

        if not supported_assets:
            if requested_asset is not None:
                raise self.error_factory(
                    HTTPStatus.BAD_REQUEST,
                    f"Gateway {gateway_type.value} does not support payment_asset",
                )
            return None

        if requested_asset is None:
            if len(supported_assets) == 1:
                return supported_assets[0]
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                f"payment_asset is required for gateway {gateway_type.value}",
            )

        if requested_asset not in supported_assets:
            raise self.error_factory(
                HTTPStatus.BAD_REQUEST,
                (
                    f"Unsupported payment_asset '{requested_asset.value}' for "
                    f"gateway {gateway_type.value}"
                ),
            )

        return requested_asset
