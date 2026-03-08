from types import SimpleNamespace

from src.bot.routers.menu.getters import (
    _resolve_mini_app_entry_url as resolve_menu_mini_app_entry_url,
)
from src.bot.routers.subscription.getters import (
    _resolve_mini_app_entry_url as resolve_subscription_mini_app_entry_url,
)


def _build_config(
    *,
    mini_app_url: str | bool,
    web_app_url: str = "https://example.com",
) -> SimpleNamespace:
    return SimpleNamespace(
        bot=SimpleNamespace(
            mini_app_url=mini_app_url,
            has_configured_mini_app_url=(
                isinstance(mini_app_url, str) and bool(mini_app_url.strip())
            ),
        ),
        web_app=SimpleNamespace(url_str=web_app_url),
    )


def test_menu_mini_app_entry_url_requires_explicit_bot_url() -> None:
    config = _build_config(mini_app_url=False)

    assert resolve_menu_mini_app_entry_url(config) is None


def test_subscription_mini_app_entry_url_requires_explicit_bot_url() -> None:
    config = _build_config(mini_app_url=False)

    assert resolve_subscription_mini_app_entry_url(config) is None


def test_menu_mini_app_entry_url_uses_explicit_bot_url() -> None:
    config = _build_config(mini_app_url="https://mini.example/path")

    assert (
        resolve_menu_mini_app_entry_url(config)
        == "https://mini.example/path"
    )


def test_subscription_mini_app_entry_url_uses_explicit_bot_url() -> None:
    config = _build_config(mini_app_url="https://mini.example/path")

    assert (
        resolve_subscription_mini_app_entry_url(config)
        == "https://mini.example/path"
    )
