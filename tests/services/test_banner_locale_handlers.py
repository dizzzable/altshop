from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.routers.dashboard.remnashop.banners.getters import (
    ALL_BANNER_LOCALE,
    ALL_BANNER_SECTION,
    _build_banner_select_payload,
    get_banner_info,
)
from src.bot.routers.dashboard.remnashop.banners.handlers import (
    _resolve_banner_target_locales,
    _resolve_banner_target_sections,
    _store_banner_bytes,
    on_banner_select,
    on_locale_select,
)
from src.bot.states import RemnashopBanners
from src.core.enums import BannerFormat, BannerName


def run_async(coroutine):
    return asyncio.run(coroutine)


class FakeTranslator:
    def __init__(self) -> None:
        self._values = {
            "msg-banner-section-all": "For all",
            "msg-banner-section-menu": "Menu",
            "msg-banner-section-dashboard": "Dashboard",
            "msg-banner-section-subscription": "Subscription",
            "msg-banner-section-promocode": "Promocode",
            "msg-banner-section-referral": "Referral",
            "msg-banner-locale-all": "All locales",
            "msg-banner-locale-ru": "RU",
            "msg-banner-locale-en": "EN",
            "msg-banner-scope-status-empty": "No targets selected",
            "msg-banner-scope-status-progress": "Uploaded targets: {uploaded} / {total}",
        }

    def get(self, key: str, **kwargs: object) -> str:
        template = self._values[key]
        return template.format(**kwargs)


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

    run_async(on_locale_select(SimpleNamespace(), SimpleNamespace(), dialog_manager, "ru"))

    assert dialog_manager.dialog_data["locale"] == "ru"
    dialog_manager.show.assert_awaited_once()


def test_banner_select_getter_exposes_localized_section_and_locale_names() -> None:
    config = SimpleNamespace(
        banners_dir=Path("."),
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    payload = _build_banner_select_payload(
        config=config,
        section_key=BannerName.MENU.value,
        locale_key="ru",
        i18n=FakeTranslator(),
    )

    assert payload["locale"] == "ru"
    assert payload["locale_display_name"] == "RU"
    assert payload["banner_display_name"] == "Menu"
    assert payload["scope_summary"] == "Uploaded targets: 0 / 1"


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
    payload = _build_banner_select_payload(
        config=config,
        section_key=ALL_BANNER_SECTION,
        locale_key=ALL_BANNER_LOCALE,
        i18n=FakeTranslator(),
    )

    assert payload["locale_display_name"] == "All locales"
    assert payload["banner_display_name"] == "For all"


def test_banner_select_getter_includes_locale_scope_items_for_locale_selector() -> None:
    config = SimpleNamespace(
        banners_dir=Path("."),
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    payload = _build_banner_select_payload(
        config=config,
        section_key=BannerName.MENU.value,
        locale_key="ru",
        i18n=FakeTranslator(),
    )

    assert [item["locale"] for item in payload["locale_scope_items"]] == [
        ALL_BANNER_LOCALE,
        "ru",
        "en",
    ]
    assert payload["locale_scope_items"][1]["selected"] == 1
    assert payload["locale_scope_items"][1]["display_name"] == "RU"


def test_store_banner_bytes_writes_menu_banner_for_single_locale(tmp_path: Path) -> None:
    config = SimpleNamespace(
        banners_dir=tmp_path,
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )

    written_paths = _store_banner_bytes(
        config,
        banner_name=BannerName.MENU.value,
        locale="ru",
        file_ext=BannerFormat.PNG.value,
        file_bytes=b"menu-banner",
    )

    expected_path = tmp_path / "ru" / f"{BannerName.MENU.value}.{BannerFormat.PNG.value}"
    assert written_paths == [expected_path]
    assert expected_path.read_bytes() == b"menu-banner"
    assert get_banner_info(tmp_path, BannerName.MENU, "ru")["exists"] is True


def test_store_banner_bytes_keeps_first_bulk_target_and_reports_full_progress(
    tmp_path: Path,
) -> None:
    config = SimpleNamespace(
        banners_dir=tmp_path,
        locales=[SimpleNamespace(value="ru"), SimpleNamespace(value="en")],
        default_locale=SimpleNamespace(value="ru"),
    )
    menu_old = tmp_path / "ru" / f"{BannerName.MENU.value}.{BannerFormat.JPG.value}"
    menu_old.parent.mkdir(parents=True, exist_ok=True)
    menu_old.write_bytes(b"old")

    written_paths = _store_banner_bytes(
        config,
        banner_name=ALL_BANNER_SECTION,
        locale="ru",
        file_ext=BannerFormat.PNG.value,
        file_bytes=b"bulk-banner",
    )

    assert len(written_paths) == 5
    assert menu_old.exists() is False
    for section in _resolve_banner_target_sections(ALL_BANNER_SECTION):
        expected_path = tmp_path / "ru" / f"{section.value}.{BannerFormat.PNG.value}"
        assert expected_path in written_paths
        assert expected_path.read_bytes() == b"bulk-banner"

    payload = _build_banner_select_payload(
        config=config,
        section_key=ALL_BANNER_SECTION,
        locale_key="ru",
        i18n=FakeTranslator(),
    )
    assert payload["scope_summary"] == "Uploaded targets: 5 / 5"
