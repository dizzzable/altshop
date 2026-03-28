import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.routers.subscription.getters import _resolve_mini_app_entry_state
from src.infrastructure.database.models.dto import BotMenuSettingsDto


def test_resolve_mini_app_entry_state_prefers_runtime_bot_menu_url() -> None:
    settings_service = AsyncMock()
    settings_service.get.return_value = SimpleNamespace(
        bot_menu=BotMenuSettingsDto(mini_app_url="https://settings.example/app")
    )
    config = SimpleNamespace(bot=SimpleNamespace(mini_app_url="https://config.example/app"))

    mini_app_url, is_app_enabled = asyncio.run(
        _resolve_mini_app_entry_state(
            config=config,
            settings_service=settings_service,
        )
    )

    assert mini_app_url == "https://settings.example/app"
    assert is_app_enabled is True


def test_resolve_mini_app_entry_state_keeps_t_me_launch_links_from_settings() -> None:
    settings_service = AsyncMock()
    settings_service.get.return_value = SimpleNamespace(
        bot_menu=BotMenuSettingsDto(mini_app_url="https://t.me/example_bot/app?startapp=launch")
    )
    config = SimpleNamespace(bot=SimpleNamespace(mini_app_url=False))

    mini_app_url, is_app_enabled = asyncio.run(
        _resolve_mini_app_entry_state(
            config=config,
            settings_service=settings_service,
        )
    )

    assert mini_app_url == "https://t.me/example_bot/app?startapp=launch"
    assert is_app_enabled is True


def test_subscription_renew_handlers_drop_legacy_plan_matching_block() -> None:
    source = Path("src/bot/routers/subscription/handlers.py").read_text(encoding="utf-8")

    assert "await _start_single_subscription_renew_flow(" in source
    assert "subscription.find_matching_plan(plans)" not in source
