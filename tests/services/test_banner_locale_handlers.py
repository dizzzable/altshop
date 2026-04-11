from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.routers.dashboard.remnashop.banners.getters import (
    ALL_BANNER_LOCALE,
    banner_select_getter,
)
from src.bot.routers.dashboard.remnashop.banners.handlers import (
    _resolve_banner_target_locales,
    on_locale_select,
)
from src.core.enums import BannerName


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_resolve_banner_target_locales_expands_all() -> None:
    config = SimpleNamespace(locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")])

    assert _resolve_banner_target_locales(config, ALL_BANNER_LOCALE) == ["ru", "en"]
    assert _resolve_banner_target_locales(config, "ru") == ["ru"]


def test_on_locale_select_updates_dialog_and_refreshes_window() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={},
        show=AsyncMock(),
        middleware_data={"user": SimpleNamespace(telegram_id=1, name="Dev", role="DEV")},
    )
    callback = SimpleNamespace()
    widget = SimpleNamespace()

    run_async(on_locale_select(callback, widget, dialog_manager, "ru"))

    assert dialog_manager.dialog_data["locale"] == "ru"
    dialog_manager.show.assert_awaited_once()


def test_banner_select_getter_exposes_all_locale_option() -> None:
    config = SimpleNamespace(
        banners_dir=Path("."),
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={"banner_name": BannerName.MENU.value, "locale": "ru"},
        middleware_data={"config": config},
    )

    payload = run_async(banner_select_getter(dialog_manager))

    assert payload["locale_list"][0]["locale"] == ALL_BANNER_LOCALE
