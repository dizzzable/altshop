from pathlib import Path
from types import SimpleNamespace

from src.bot.routers.dashboard.remnashop.bot_menu.common import (
    BOT_MENU_CALLBACK_ID_LENGTH,
    BOT_MENU_LIST_WIDGET_ID,
    BOT_MENU_SELECT_WIDGET_ID,
    bot_menu_callback_payload_length,
    button_callback_id,
)
from src.bot.routers.dashboard.remnashop.bot_menu.handlers import _find_selected_button
from src.infrastructure.database.models.dto import BotMenuCustomButtonDto, SettingsDto


def test_bot_menu_handlers_request_config_via_dishka() -> None:
    source = Path("src/bot/routers/dashboard/remnashop/bot_menu/handlers.py").read_text(
        encoding="utf-8"
    )

    assert "async def on_bot_menu_mode_toggle" in source
    assert "async def on_mini_app_url_input" in source
    assert source.count("config: FromDishka[AppConfig]") >= 2


def test_button_callback_id_stays_short_and_callback_payload_fits_telegram_limit() -> None:
    raw_id = "9f6dc57fd1c546e8b37c2f1649b7b0c2"

    callback_id = button_callback_id(raw_id)
    payload_length = bot_menu_callback_payload_length(raw_id)

    assert 1 <= len(callback_id) <= BOT_MENU_CALLBACK_ID_LENGTH
    assert callback_id != raw_id
    assert payload_length < 64
    assert (
        len(f"{BOT_MENU_LIST_WIDGET_ID}:{callback_id}:{BOT_MENU_SELECT_WIDGET_ID}")
        == payload_length
    )


def test_find_selected_button_matches_short_callback_id_to_long_stored_id() -> None:
    button = BotMenuCustomButtonDto(
        id="9f6dc57fd1c546e8b37c2f1649b7b0c2",
        label="Test",
        url="https://example.com",
    )
    settings = SettingsDto()
    settings.bot_menu.custom_buttons = [button]
    dialog_manager = SimpleNamespace(
        dialog_data={"bot_menu_button_id": button_callback_id(button.id)}
    )

    selected = _find_selected_button(dialog_manager, settings)

    assert selected is not None
    buttons, index, selected_button = selected
    assert index == 0
    assert buttons[0].id == button.id
    assert selected_button.id == button.id
