from __future__ import annotations

from pathlib import Path

from src.core.i18n.storage import OverlayFileStorage


def _write_ftl(root: Path, locale: str, relative_path: str, content: str) -> None:
    target = root / locale / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf8")


def test_overlay_storage_prefers_primary_translations(tmp_path: Path) -> None:
    primary_root = tmp_path / "assets" / "translations"
    fallback_root = tmp_path / "assets.default" / "translations"

    _write_ftl(primary_root, "en", "buttons.ftl", "btn-test = Primary value\n")
    _write_ftl(
        fallback_root,
        "en",
        "buttons.ftl",
        "btn-test = Fallback value\nbtn-fallback-only = Fallback only\n",
    )

    storage = OverlayFileStorage(primary_root / "{locale}", fallback_root / "{locale}")
    translator = storage.get_translator("en")

    assert translator is not None
    assert translator.get("btn-test") == "Primary value"
    assert translator.get("btn-fallback-only") == "Fallback only"


def test_overlay_storage_uses_fallback_locale_files_when_primary_missing_file(
    tmp_path: Path,
) -> None:
    primary_root = tmp_path / "assets" / "translations"
    fallback_root = tmp_path / "assets.default" / "translations"

    _write_ftl(primary_root, "en", "messages.ftl", "msg-primary = Primary message\n")
    _write_ftl(
        fallback_root,
        "en",
        "buttons.ftl",
        "btn-default-only = Default button\n",
    )

    storage = OverlayFileStorage(primary_root / "{locale}", fallback_root / "{locale}")
    translator = storage.get_translator("en")

    assert translator is not None
    assert translator.get("msg-primary") == "Primary message"
    assert translator.get("btn-default-only") == "Default button"


def test_overlay_storage_uses_fallback_for_public_main_menu_key_when_primary_is_stale(
    tmp_path: Path,
) -> None:
    primary_root = tmp_path / "assets" / "translations"
    fallback_root = tmp_path / "assets.default" / "translations"

    _write_ftl(
        primary_root,
        "en",
        "messages.ftl",
        "msg-main-menu = Legacy main menu\n",
    )
    _write_ftl(
        fallback_root,
        "en",
        "messages.ftl",
        "msg-main-menu-public = Fresh main menu\n",
    )

    storage = OverlayFileStorage(primary_root / "{locale}", fallback_root / "{locale}")
    translator = storage.get_translator("en")

    assert translator is not None
    assert translator.get("msg-main-menu") == "Legacy main menu"
    assert translator.get("msg-main-menu-public") == "Fresh main menu"
