from __future__ import annotations

from types import SimpleNamespace

from src.bot.routers.subscription.handlers import _get_purchase_state, _serialize_final_quote
from src.core.enums import PurchaseType


def test_get_purchase_state_recovers_missing_renew_purchase_type() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={
            "renew_subscription_id": 42,
            "renew_subscription_ids": None,
        }
    )

    purchase_type, renew_subscription_id, renew_subscription_ids = _get_purchase_state(
        dialog_manager
    )

    assert purchase_type == PurchaseType.RENEW
    assert renew_subscription_id == 42
    assert renew_subscription_ids is None
    assert dialog_manager.dialog_data["purchase_type"] == PurchaseType.RENEW


def test_serialize_final_quote_keeps_dialog_cache_json_safe() -> None:
    quote = SimpleNamespace(
        price=100.0,
        original_price=120.0,
        currency="RUB",
        settlement_price=100.0,
        settlement_original_price=120.0,
        settlement_currency="RUB",
        discount_percent=17,
        discount_source="PURCHASE",
        payment_asset=None,
        quote_source="test",
        quote_expires_at="2026-04-05T12:00:00Z",
        quote_provider_count=1,
        renew_items=(SimpleNamespace(subscription_id=1),),
    )

    serialized = _serialize_final_quote(quote)

    assert serialized["price"] == 100.0
    assert serialized["quote_provider_count"] == 1
    assert "renew_items" not in serialized
