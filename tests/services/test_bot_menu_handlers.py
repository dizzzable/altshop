from pathlib import Path


def test_bot_menu_handlers_request_config_via_dishka() -> None:
    source = Path("src/bot/routers/dashboard/remnashop/bot_menu/handlers.py").read_text(
        encoding="utf-8"
    )

    assert "async def on_bot_menu_mode_toggle" in source
    assert "async def on_mini_app_url_input" in source
    assert source.count("config: FromDishka[AppConfig]") >= 2
    assert "resolve_bot_menu_web_app_url" in source
    assert "is_valid_bot_menu_web_app_url" in source
    assert "next_kind == BotMenuCustomButtonKind.WEB_APP" in source
