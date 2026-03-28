from pathlib import Path


def test_menu_start_handlers_answer_rules_and_channel_callbacks() -> None:
    source = Path("src/bot/routers/menu/handlers.py").read_text(encoding="utf-8")

    assert "def _handle_rules_accept(" in source
    assert "def _handle_channel_confirm(" in source
    assert source.count("await callback.answer()") >= 2
