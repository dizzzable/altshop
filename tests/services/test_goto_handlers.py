from pathlib import Path


def test_goto_handler_routes_purchase_callbacks_through_purchase_flow() -> None:
    source = Path("src/bot/routers/extra/goto.py").read_text(encoding="utf-8")

    assert "def _start_purchase_flow(" in source
    assert "purchase_type = PurchaseType(data.removeprefix(PURCHASE_PREFIX))" in source
    assert "await _start_purchase_flow(" in source
    assert "state=Subscription.MAIN" in source
    assert "Trying go to invalid purchase type" in source
