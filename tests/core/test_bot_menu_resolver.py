from types import SimpleNamespace

from src.core.enums import BotMenuCustomButtonKind
from src.core.utils.bot_menu import (
    BOT_MENU_SOURCE_CONFIG,
    BOT_MENU_SOURCE_MISSING,
    BOT_MENU_SOURCE_SETTINGS,
    resolve_bot_menu_state,
    resolve_bot_menu_url,
)
from src.infrastructure.database.models.dto import (
    BotMenuCustomButtonDto,
    BotMenuSettingsDto,
    BrandingSettingsDto,
)


def _build_config(mini_app_url: str | None):
    return SimpleNamespace(bot=SimpleNamespace(mini_app_url=mini_app_url))


def test_resolve_bot_menu_url_prefers_settings_value() -> None:
    bot_menu = BotMenuSettingsDto(mini_app_url="https://settings.example/app")
    config = _build_config("https://config.example/app")

    resolved_url, source = resolve_bot_menu_url(bot_menu=bot_menu, config=config)

    assert resolved_url == "https://settings.example/app"
    assert source == BOT_MENU_SOURCE_SETTINGS


def test_resolve_bot_menu_url_uses_config_fallback() -> None:
    bot_menu = BotMenuSettingsDto()
    config = _build_config("https://config.example/app/")

    resolved_url, source = resolve_bot_menu_url(bot_menu=bot_menu, config=config)

    assert resolved_url == "https://config.example/app"
    assert source == BOT_MENU_SOURCE_CONFIG


def test_resolve_bot_menu_url_reports_missing_when_absent() -> None:
    bot_menu = BotMenuSettingsDto()
    config = _build_config(None)

    resolved_url, source = resolve_bot_menu_url(bot_menu=bot_menu, config=config)

    assert resolved_url is None
    assert source == BOT_MENU_SOURCE_MISSING


def test_resolve_bot_menu_state_filters_disabled_buttons_and_sorts_enabled() -> None:
    bot_menu = BotMenuSettingsDto(
        miniapp_only_enabled=True,
        mini_app_url="https://settings.example/app",
        custom_buttons=[
            BotMenuCustomButtonDto(
                id="second",
                label="Second",
                kind=BotMenuCustomButtonKind.URL,
                url="https://example.com/second",
                enabled=True,
                order=2,
            ),
            BotMenuCustomButtonDto(
                id="disabled",
                label="Disabled",
                kind=BotMenuCustomButtonKind.URL,
                url="https://example.com/disabled",
                enabled=False,
                order=0,
            ),
            BotMenuCustomButtonDto(
                id="first",
                label="First",
                kind=BotMenuCustomButtonKind.WEB_APP,
                url="https://example.com/first",
                enabled=True,
                order=1,
            ),
        ],
    )
    branding = BrandingSettingsDto(project_name="AltShop", bot_menu_button_text="Open App")
    config = _build_config(None)

    state = resolve_bot_menu_state(bot_menu=bot_menu, branding=branding, config=config)

    assert state.miniapp_only_enabled is True
    assert state.miniapp_only_active is True
    assert state.mini_app_source == BOT_MENU_SOURCE_SETTINGS
    assert state.primary_button_text == "Open App"
    assert [button.id for button in state.custom_buttons] == ["first", "second"]
    assert state.custom_buttons[0].is_web_app is True
    assert state.custom_buttons[1].is_url is True


def test_resolve_bot_menu_state_uses_project_name_as_primary_button_fallback() -> None:
    bot_menu = BotMenuSettingsDto(miniapp_only_enabled=True)
    branding = BrandingSettingsDto(project_name="2GET SHOP")
    branding.bot_menu_button_text = ""
    config = _build_config("https://config.example/app")

    state = resolve_bot_menu_state(bot_menu=bot_menu, branding=branding, config=config)

    assert state.primary_button_text == "2GET SHOP"
    assert state.miniapp_only_active is True
