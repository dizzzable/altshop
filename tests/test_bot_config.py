from __future__ import annotations

from pydantic import ValidationError

from src.core.config.bot import BotConfig


def _build_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "token": "123:token",
        "secret_token": "secret",
        "dev_id": "1",
        "support_username": "support_account",
        "mini_app": "https://remnabot.2get.pro/webapp/miniapp",
    }
    values.update(overrides)
    return values


def test_bot_config_uses_exact_mini_app_url() -> None:
    config = BotConfig(**_build_kwargs())

    assert config.mini_app_url == "https://remnabot.2get.pro/webapp/miniapp"
    assert config.has_configured_mini_app_url is True
    assert config.is_mini_app is True


def test_bot_config_false_disables_mini_app() -> None:
    config = BotConfig(**_build_kwargs(mini_app="false"))

    assert config.mini_app_url is False
    assert config.has_configured_mini_app_url is False
    assert config.is_mini_app is False


def test_bot_config_rejects_true_mode() -> None:
    try:
        BotConfig(**_build_kwargs(mini_app="true"))
    except ValidationError as exc:
        assert "BOT_MINI_APP must be empty, false, or an exact Mini App URL" in str(exc)
    else:
        raise AssertionError("BOT_MINI_APP=true must be rejected")
