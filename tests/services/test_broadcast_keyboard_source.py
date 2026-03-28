from pathlib import Path


def test_broadcast_keyboard_uses_per_request_button_copies() -> None:
    source = Path("src/bot/routers/dashboard/broadcast/handlers.py").read_text(encoding="utf-8")

    assert "def _build_goto_button(" in source
    assert "goto_buttons[button_id].model_copy(deep=True)" in source
    assert "goto_buttons[0].url =" not in source
