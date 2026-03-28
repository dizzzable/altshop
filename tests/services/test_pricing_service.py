from __future__ import annotations

from decimal import Decimal

from src.core.enums import Currency, DiscountSource
from src.infrastructure.database.models.dto import UserDto
from src.services.pricing import PricingService


def build_user(*, telegram_id: int = 100, purchase_discount: int = 0) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Test User",
        purchase_discount=purchase_discount,
    )


def test_pricing_service_calculates_discount_without_base_service_dependencies() -> None:
    service = PricingService()

    pricing = service.calculate(
        user=build_user(purchase_discount=25),
        price=Decimal("10.99"),
        currency=Currency.USD,
    )

    assert pricing.original_amount == Decimal("10.99")
    assert pricing.discount_percent == 25
    assert pricing.discount_source == DiscountSource.PURCHASE
    assert pricing.final_amount == Decimal("8.24")
