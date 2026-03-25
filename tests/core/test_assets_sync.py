from __future__ import annotations

import tarfile
from pathlib import Path

from src.core.utils.assets_sync import (
    ASSETS_VERSION_MARKER,
    AssetSyncAction,
    initialize_assets,
)


def _write_default_assets(default_assets_dir: Path, *, content: str) -> None:
    translations_dir = default_assets_dir / "translations" / "ru"
    translations_dir.mkdir(parents=True, exist_ok=True)
    (translations_dir / "buttons.ftl").write_text(content, encoding="utf-8")


def test_initialize_assets_copies_defaults_into_empty_runtime_dir(tmp_path: Path) -> None:
    runtime_assets_dir = tmp_path / "assets"
    default_assets_dir = tmp_path / "assets.default"
    _write_default_assets(default_assets_dir, content="btn = 🎫 Назначить план")

    result = initialize_assets(
        assets_dir=runtime_assets_dir,
        default_assets_dir=default_assets_dir,
        app_version="1.2.1",
    )

    assert result.action == AssetSyncAction.INITIAL_COPY
    assert (runtime_assets_dir / "translations" / "ru" / "buttons.ftl").read_text(
        encoding="utf-8"
    ) == "btn = 🎫 Назначить план"
    assert (runtime_assets_dir / ASSETS_VERSION_MARKER).read_text(encoding="utf-8").strip() == (
        "1.2.1"
    )


def test_initialize_assets_syncs_runtime_assets_when_version_changes(tmp_path: Path) -> None:
    runtime_assets_dir = tmp_path / "assets"
    default_assets_dir = tmp_path / "assets.default"
    _write_default_assets(default_assets_dir, content="btn = 🎫 Назначить план")

    runtime_translations_dir = runtime_assets_dir / "translations" / "ru"
    runtime_translations_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_translations_dir / "buttons.ftl"
    runtime_file.write_text("btn = Назначить план", encoding="utf-8")
    (runtime_assets_dir / ASSETS_VERSION_MARKER).write_text("1.2.0\n", encoding="utf-8")

    result = initialize_assets(
        assets_dir=runtime_assets_dir,
        default_assets_dir=default_assets_dir,
        app_version="1.2.1",
    )

    assert result.action == AssetSyncAction.VERSION_SYNC
    assert result.backup_path is not None
    assert runtime_file.read_text(encoding="utf-8") == "btn = 🎫 Назначить план"
    assert (runtime_assets_dir / ASSETS_VERSION_MARKER).read_text(encoding="utf-8").strip() == (
        "1.2.1"
    )

    with tarfile.open(result.backup_path, "r:gz") as archive:
        archived_text = archive.extractfile("translations/ru/buttons.ftl")
        assert archived_text is not None
        assert archived_text.read().decode("utf-8") == "btn = Назначить план"


def test_initialize_assets_skips_sync_when_runtime_version_matches(tmp_path: Path) -> None:
    runtime_assets_dir = tmp_path / "assets"
    default_assets_dir = tmp_path / "assets.default"
    _write_default_assets(default_assets_dir, content="btn = 🎫 Назначить план")

    runtime_translations_dir = runtime_assets_dir / "translations" / "ru"
    runtime_translations_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_translations_dir / "buttons.ftl"
    runtime_file.write_text("btn = кастомный текст", encoding="utf-8")
    (runtime_assets_dir / ASSETS_VERSION_MARKER).write_text("1.2.1\n", encoding="utf-8")

    result = initialize_assets(
        assets_dir=runtime_assets_dir,
        default_assets_dir=default_assets_dir,
        app_version="1.2.1",
    )

    assert result.action == AssetSyncAction.UP_TO_DATE
    assert result.backup_path is None
    assert runtime_file.read_text(encoding="utf-8") == "btn = кастомный текст"


def test_initialize_assets_resets_runtime_assets_when_reset_flag_enabled(tmp_path: Path) -> None:
    runtime_assets_dir = tmp_path / "assets"
    default_assets_dir = tmp_path / "assets.default"
    _write_default_assets(default_assets_dir, content="btn = 🎫 Назначить план")

    runtime_translations_dir = runtime_assets_dir / "translations" / "ru"
    runtime_translations_dir.mkdir(parents=True, exist_ok=True)
    runtime_file = runtime_translations_dir / "buttons.ftl"
    runtime_file.write_text("btn = старый текст", encoding="utf-8")
    (runtime_assets_dir / ASSETS_VERSION_MARKER).write_text("1.2.1\n", encoding="utf-8")

    result = initialize_assets(
        assets_dir=runtime_assets_dir,
        default_assets_dir=default_assets_dir,
        app_version="1.2.1",
        reset_assets=True,
    )

    assert result.action == AssetSyncAction.RESET
    assert result.backup_path is not None
    assert runtime_file.read_text(encoding="utf-8") == "btn = 🎫 Назначить план"
