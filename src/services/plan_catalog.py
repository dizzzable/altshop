from __future__ import annotations

from dataclasses import dataclass

from src.core.enums import PurchaseChannel
from src.core.crypto_assets import get_supported_payment_assets
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    UserDto,
)

from .payment_gateway import PaymentGatewayService
from .plan import PlanService
from .pricing import PricingService
from .purchase_gateway_policy import filter_gateways_by_channel


@dataclass(slots=True, frozen=True)
class PlanCatalogPriceSnapshot:
    id: int
    duration_id: int
    gateway_type: str
    price: float
    original_price: float
    currency: str
    discount_percent: int
    discount_source: str
    discount: int
    supported_payment_assets: list[str] | None


@dataclass(slots=True, frozen=True)
class PlanCatalogDurationSnapshot:
    id: int
    plan_id: int
    days: int
    prices: list[PlanCatalogPriceSnapshot]


@dataclass(slots=True, frozen=True)
class PlanCatalogItemSnapshot:
    id: int
    name: str
    description: str | None
    tag: str | None
    type: str
    availability: str
    traffic_limit: int
    device_limit: int
    order_index: int
    is_active: bool
    allowed_user_ids: list[int]
    internal_squads: list[str]
    external_squad: str | None
    durations: list[PlanCatalogDurationSnapshot]
    created_at: str
    updated_at: str


class PlanCatalogService:
    def __init__(
        self,
        plan_service: PlanService,
        payment_gateway_service: PaymentGatewayService,
        pricing_service: PricingService,
    ) -> None:
        self.plan_service = plan_service
        self.payment_gateway_service = payment_gateway_service
        self.pricing_service = pricing_service

    async def list_available_plans(
        self,
        *,
        current_user: UserDto,
        channel: PurchaseChannel,
    ) -> list[PlanCatalogItemSnapshot]:
        plans = await self.plan_service.get_available_plans(current_user)
        gateways = filter_gateways_by_channel(
            await self.payment_gateway_service.filter_active(is_active=True),
            channel=channel,
        )
        return [self._build_plan_item(plan, gateways, current_user) for plan in plans]

    def _build_plan_item(
        self,
        plan: PlanDto,
        gateways: list[PaymentGatewayDto],
        current_user: UserDto,
    ) -> PlanCatalogItemSnapshot:
        plan_created_at = getattr(plan, "created_at", None)
        plan_updated_at = getattr(plan, "updated_at", None)

        return PlanCatalogItemSnapshot(
            id=plan.id or 0,
            name=plan.name,
            description=plan.description,
            tag=plan.tag,
            type=plan.type.value,
            availability=plan.availability.value,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            order_index=plan.order_index,
            is_active=plan.is_active,
            allowed_user_ids=plan.allowed_user_ids,
            internal_squads=[str(squad) for squad in plan.internal_squads],
            external_squad=str(plan.external_squad) if plan.external_squad else None,
            durations=[
                self._build_duration_item(
                    duration=duration,
                    plan_id=plan.id or 0,
                    gateways=gateways,
                    current_user=current_user,
                )
                for duration in plan.durations
            ],
            created_at=plan_created_at.isoformat() if plan_created_at else "",
            updated_at=plan_updated_at.isoformat() if plan_updated_at else "",
        )

    def _build_duration_item(
        self,
        *,
        duration: PlanDurationDto,
        plan_id: int,
        gateways: list[PaymentGatewayDto],
        current_user: UserDto,
    ) -> PlanCatalogDurationSnapshot:
        prices: list[PlanCatalogPriceSnapshot] = []
        for gateway in gateways:
            snapshot = self._build_price_item(
                duration=duration,
                gateway=gateway,
                current_user=current_user,
            )
            if snapshot is not None:
                prices.append(snapshot)

        return PlanCatalogDurationSnapshot(
            id=duration.id or 0,
            plan_id=plan_id,
            days=duration.days,
            prices=prices,
        )

    def _build_price_item(
        self,
        *,
        duration: PlanDurationDto,
        gateway: PaymentGatewayDto,
        current_user: UserDto,
    ) -> PlanCatalogPriceSnapshot | None:
        matching_price = next(
            (price for price in duration.prices if price.currency == gateway.currency),
            None,
        )
        if not matching_price:
            return None

        pricing = self.pricing_service.calculate(
            user=current_user,
            price=matching_price.price,
            currency=gateway.currency,
        )
        supported_payment_assets = [
            asset.value for asset in get_supported_payment_assets(gateway.type)
        ] or None

        return PlanCatalogPriceSnapshot(
            id=matching_price.id or 0,
            duration_id=duration.id or 0,
            gateway_type=gateway.type.value,
            price=float(pricing.final_amount),
            original_price=float(pricing.original_amount),
            currency=matching_price.currency.value,
            discount_percent=pricing.discount_percent,
            discount_source=pricing.discount_source.value,
            discount=pricing.discount_percent,
            supported_payment_assets=supported_payment_assets,
        )
