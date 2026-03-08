from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.core.enums import (
    Currency,
    DiscountSource,
    Locale,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PurchaseChannel,
    UserRole,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    PriceDetailsDto,
    UserDto,
)
from src.services.plan_catalog import PlanCatalogService
from src.services.pricing import PricingService


def _build_user(
    *,
    telegram_id: int = 1001,
    personal_discount: int = 0,
    purchase_discount: int = 0,
) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        referral_code=f"ref{telegram_id}",
        name=f"User {telegram_id}",
        role=UserRole.USER,
        language=Locale.EN,
        personal_discount=personal_discount,
        purchase_discount=purchase_discount,
    )


def _build_gateway(
    *,
    gateway_type: PaymentGatewayType,
    currency: Currency,
    order_index: int,
) -> PaymentGatewayDto:
    return PaymentGatewayDto(
        id=order_index,
        order_index=order_index,
        type=gateway_type,
        currency=currency,
        is_active=True,
    )


def _build_plan() -> PlanDto:
    return PlanDto(
        id=77,
        name="Combo Plan",
        description="Primary catalog plan",
        tag="combo",
        type=PlanType.BOTH,
        availability=PlanAvailability.ALL,
        traffic_limit=200,
        device_limit=3,
        order_index=4,
        is_active=True,
        allowed_user_ids=[1001],
        internal_squads=[uuid4()],
        durations=[
            PlanDurationDto(
                id=11,
                days=30,
                prices=[
                    PlanPriceDto(id=101, currency=Currency.RUB, price=Decimal("499")),
                    PlanPriceDto(id=102, currency=Currency.XTR, price=Decimal("199")),
                    PlanPriceDto(id=103, currency=Currency.USD, price=Decimal("9.99")),
                ],
            )
        ],
        created_at=datetime(2026, 3, 7, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 7, 11, 0, 0, tzinfo=UTC),
    )


def _build_service(
    pricing_service: object | None = None,
) -> tuple[PlanCatalogService, SimpleNamespace, SimpleNamespace]:
    plan_service = SimpleNamespace(get_available_plans=AsyncMock(return_value=[]))
    payment_gateway_service = SimpleNamespace(filter_active=AsyncMock(return_value=[]))
    resolved_pricing_service = pricing_service or SimpleNamespace(
        calculate=Mock(
            side_effect=lambda **kwargs: PriceDetailsDto(
                original_amount=kwargs["price"],
                discount_source=DiscountSource.NONE,
                final_amount=kwargs["price"],
            )
        )
    )
    service = PlanCatalogService(
        plan_service=plan_service,
        payment_gateway_service=payment_gateway_service,
        pricing_service=resolved_pricing_service,
    )
    return service, plan_service, payment_gateway_service


def test_list_available_plans_filters_telegram_stars_for_web_channel() -> None:
    service, plan_service, payment_gateway_service = _build_service()
    plan_service.get_available_plans.return_value = [_build_plan()]
    payment_gateway_service.filter_active.return_value = [
        _build_gateway(
            gateway_type=PaymentGatewayType.TELEGRAM_STARS,
            currency=Currency.XTR,
            order_index=1,
        ),
        _build_gateway(
            gateway_type=PaymentGatewayType.YOOMONEY,
            currency=Currency.RUB,
            order_index=2,
        ),
    ]

    result = asyncio.run(
        service.list_available_plans(
            current_user=_build_user(),
            channel=PurchaseChannel.WEB,
        )
    )

    assert len(result) == 1
    assert result[0].id == 77
    assert result[0].durations[0].prices == [
        result[0].durations[0].prices[0]
    ]
    assert result[0].durations[0].prices[0].gateway_type == PaymentGatewayType.YOOMONEY.value
    assert result[0].durations[0].prices[0].currency == Currency.RUB.value


def test_list_available_plans_keeps_telegram_stars_for_telegram_channel() -> None:
    service, plan_service, payment_gateway_service = _build_service()
    plan = _build_plan()
    plan_service.get_available_plans.return_value = [plan]
    payment_gateway_service.filter_active.return_value = [
        _build_gateway(
            gateway_type=PaymentGatewayType.TELEGRAM_STARS,
            currency=Currency.XTR,
            order_index=1,
        ),
        _build_gateway(
            gateway_type=PaymentGatewayType.YOOMONEY,
            currency=Currency.RUB,
            order_index=2,
        ),
    ]

    result = asyncio.run(
        service.list_available_plans(
            current_user=_build_user(),
            channel=PurchaseChannel.TELEGRAM,
        )
    )

    assert [price.gateway_type for price in result[0].durations[0].prices] == [
        PaymentGatewayType.TELEGRAM_STARS.value,
        PaymentGatewayType.YOOMONEY.value,
    ]
    assert result[0].created_at == "2026-03-07T10:00:00+00:00"
    assert result[0].updated_at == "2026-03-07T11:00:00+00:00"


@pytest.mark.parametrize(
    ("personal_discount", "purchase_discount", "expected_final", "expected_percent", "expected_source"),
    [
        (0, 0, 499.0, 0, "NONE"),
        (10, 0, 449.0, 10, "PERSONAL"),
        (0, 15, 424.0, 15, "PURCHASE"),
        (10, 30, 349.0, 30, "PURCHASE"),
        (0, 100, 0.0, 100, "PURCHASE"),
    ],
)
def test_list_available_plans_uses_server_authoritative_pricing_preview(
    personal_discount: int,
    purchase_discount: int,
    expected_final: float,
    expected_percent: int,
    expected_source: str,
) -> None:
    pricing_service = object.__new__(PricingService)
    service, plan_service, payment_gateway_service = _build_service(pricing_service=pricing_service)
    plan_service.get_available_plans.return_value = [_build_plan()]
    payment_gateway_service.filter_active.return_value = [
        _build_gateway(
            gateway_type=PaymentGatewayType.YOOMONEY,
            currency=Currency.RUB,
            order_index=1,
        )
    ]

    result = asyncio.run(
        service.list_available_plans(
            current_user=_build_user(
                personal_discount=personal_discount,
                purchase_discount=purchase_discount,
            ),
            channel=PurchaseChannel.WEB,
        )
    )

    price = result[0].durations[0].prices[0]
    assert price.price == expected_final
    assert price.original_price == 499.0
    assert price.discount_percent == expected_percent
    assert price.discount_source == expected_source
    assert price.discount == expected_percent
    assert price.supported_payment_assets is None


def test_list_available_plans_exposes_supported_payment_assets_for_crypto_gateways() -> None:
    pricing_service = object.__new__(PricingService)
    service, plan_service, payment_gateway_service = _build_service(pricing_service=pricing_service)
    plan_service.get_available_plans.return_value = [_build_plan()]
    payment_gateway_service.filter_active.return_value = [
        _build_gateway(
            gateway_type=PaymentGatewayType.HELEKET,
            currency=Currency.USD,
            order_index=1,
        )
    ]

    result = asyncio.run(
        service.list_available_plans(
            current_user=_build_user(personal_discount=10, purchase_discount=25),
            channel=PurchaseChannel.WEB,
        )
    )

    price = result[0].durations[0].prices[0]
    assert price.currency == Currency.USD.value
    assert price.price == 7.49
    assert price.original_price == 9.99
    assert price.discount_percent == 25
    assert price.discount_source == "PURCHASE"
    assert price.supported_payment_assets is not None
    assert price.supported_payment_assets[:4] == ["USDT", "TON", "BTC", "ETH"]
