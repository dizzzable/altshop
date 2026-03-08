from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.endpoints.user_account import list_plans
from src.core.enums import PurchaseChannel
from src.services.plan_catalog import (
    PlanCatalogDurationSnapshot,
    PlanCatalogItemSnapshot,
    PlanCatalogPriceSnapshot,
)

LIST_PLANS_ENDPOINT = getattr(
    inspect.unwrap(list_plans),
    "__dishka_orig_func__",
    inspect.unwrap(list_plans),
)


def test_list_plans_delegates_to_plan_catalog_service() -> None:
    current_user = SimpleNamespace(telegram_id=1001)
    plan_catalog_service = SimpleNamespace(
        list_available_plans=AsyncMock(
            return_value=[
                PlanCatalogItemSnapshot(
                    id=77,
                    name="Combo Plan",
                    description="Primary catalog plan",
                    tag="combo",
                    type="BOTH",
                    availability="ALL",
                    traffic_limit=200,
                    device_limit=3,
                    order_index=4,
                    is_active=True,
                    allowed_user_ids=[1001],
                    internal_squads=["squad-1"],
                    external_squad="external-1",
                    durations=[
                        PlanCatalogDurationSnapshot(
                            id=11,
                            plan_id=77,
                            days=30,
                            prices=[
                                PlanCatalogPriceSnapshot(
                                    id=101,
                                    duration_id=11,
                                    gateway_type="YOOMONEY",
                                    price=499.0,
                                    original_price=499.0,
                                    currency="RUB",
                                    discount_percent=0,
                                    discount_source="NONE",
                                    discount=0,
                                    supported_payment_assets=None,
                                )
                            ],
                        )
                    ],
                    created_at="2026-03-07T10:00:00+00:00",
                    updated_at="2026-03-07T11:00:00+00:00",
                )
            ]
        )
    )

    response = asyncio.run(
        LIST_PLANS_ENDPOINT(
            current_user=current_user,
            channel=PurchaseChannel.WEB,
            plan_catalog_service=plan_catalog_service,
        )
    )

    assert len(response) == 1
    assert response[0].id == 77
    assert response[0].durations[0].prices[0].gateway_type == "YOOMONEY"
    plan_catalog_service.list_available_plans.assert_awaited_once_with(
        current_user=current_user,
        channel=PurchaseChannel.WEB,
    )
