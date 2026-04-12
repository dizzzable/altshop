from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.routers.dashboard.remnashop.banners.getters import (
    ALL_BANNER_LOCALE,
    ALL_BANNER_SECTION,
    banner_select_getter,
)
from src.bot.routers.dashboard.remnashop.banners.handlers import (
    _resolve_banner_target_locales,
    _resolve_banner_target_sections,
    on_banner_select,
    on_locale_select,
)
from src.bot.states import RemnashopBanners
from src.core.enums import BannerName


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_resolve_banner_target_locales_expands_all() -> None:
    config = SimpleNamespace(locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")])

    assert _resolve_banner_target_locales(config, ALL_BANNER_LOCALE) == ["ru", "en"]
    assert _resolve_banner_target_locales(config, "ru") == ["ru"]


def test_resolve_banner_target_sections_expands_bulk_scope() -> None:
    assert _resolve_banner_target_sections(ALL_BANNER_SECTION) == [
        BannerName.MENU,
        BannerName.DASHBOARD,
        BannerName.SUBSCRIPTION,
        BannerName.PROMOCODE,
        BannerName.REFERRAL,
    ]
    assert _resolve_banner_target_sections(BannerName.MENU.value) == [BannerName.MENU]


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
        middleware_data={"config": config, "user": SimpleNamespace(language="en")},
    )

    payload = run_async(banner_select_getter(dialog_manager))

    assert payload["locale"] == "ru"
    assert payload["locale_display_name"] == "\U0001f1f7\U0001f1fa RU"
    assert "scope_summary" in payload
    assert payload["banner_display_name"] == "\U0001f5bc\ufe0f Menu"


def test_on_banner_select_opens_editor_screen_directly() -> None:
    config = SimpleNamespace(
        banners_dir=Path("."),
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={},
        middleware_data={
            "config": config,
            "user": SimpleNamespace(telegram_id=1, name="Dev", role="DEV"),
        },
        switch_to=AsyncMock(),
    )

    run_async(
        on_banner_select(
            SimpleNamespace(),
            SimpleNamespace(),
            dialog_manager,
            BannerName.MENU.value,
        )
    )

    assert dialog_manager.dialog_data["banner_name"] == BannerName.MENU.value
    assert dialog_manager.dialog_data["locale"] == "ru"
    dialog_manager.switch_to.assert_awaited_once_with(RemnashopBanners.SELECT_BANNER)


def test_banner_select_getter_formats_bulk_scope_and_all_locales() -> None:
    config = SimpleNamespace(
        banners_dir=Path("."),
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={"banner_name": ALL_BANNER_SECTION, "locale": ALL_BANNER_LOCALE},
        middleware_data={"config": config, "user": SimpleNamespace(language="en")},
    )

    payload = run_async(banner_select_getter(dialog_manager))

    assert payload["locale_display_name"] == "All locales"
    assert payload["banner_display_name"] == "\U0001f4e3 For all"


def test_banner_select_getter_includes_locale_scope_items_for_locale_selector() -> None:
    config = SimpleNamespace(
        banners_dir=Path("."),
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={"banner_name": BannerName.MENU.value, "locale": "ru"},
        middleware_data={"config": config, "user": SimpleNamespace(language="en")},
    )

    payload = run_async(banner_select_getter(dialog_manager))

    assert [item["locale"] for item in payload["locale_scope_items"]] == [
        ALL_BANNER_LOCALE,
        "ru",
        "en",
    ]
    assert payload["locale_scope_items"][1]["selected"] == 1
