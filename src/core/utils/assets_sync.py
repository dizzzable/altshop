from __future__ import annotations

import os
import shutil
import sys
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, auto
from pathlib import Path

from src.__version__ import __version__

ASSETS_VERSION_MARKER = ".altshop_assets_version"
ASSETS_BACKUP_DIRNAME = ".bak"


class AssetSyncAction(StrEnum):
    INITIAL_COPY = auto()
    RESET = auto()
    VERSION_SYNC = auto()
    UP_TO_DATE = auto()


@dataclass(frozen=True)
class AssetSyncResult:
    action: AssetSyncAction
    app_version: str
    previous_version: str | None
    backup_path: Path | None = None


def _list_runtime_entries(assets_dir: Path) -> list[Path]:
    if not assets_dir.exists():
        return []

    ignored_names = {ASSETS_BACKUP_DIRNAME, ASSETS_VERSION_MARKER}
    return sorted(path for path in assets_dir.iterdir() if path.name not in ignored_names)


def _read_runtime_version(assets_dir: Path) -> str | None:
    marker_path = assets_dir / ASSETS_VERSION_MARKER
    if not marker_path.exists():
        return None

    marker_value = marker_path.read_text(encoding="utf-8").strip()
    return marker_value or None


def _write_runtime_version(assets_dir: Path, app_version: str) -> None:
    marker_path = assets_dir / ASSETS_VERSION_MARKER
    marker_path.write_text(f"{app_version}\n", encoding="utf-8")


def _archive_runtime_assets(assets_dir: Path) -> Path | None:
    runtime_entries = _list_runtime_entries(assets_dir)
    if not runtime_entries:
        return None

    backup_dir = assets_dir / ASSETS_BACKUP_DIRNAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"assets_backup_{timestamp}.tar.gz"

    with tarfile.open(backup_path, "w:gz") as archive:
        for item in runtime_entries:
            archive.add(item, arcname=item.name)

    return backup_path


def _clear_runtime_assets(assets_dir: Path) -> None:
    if not assets_dir.exists():
        return

    for entry in assets_dir.iterdir():
        if entry.name == ASSETS_BACKUP_DIRNAME:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _copy_default_assets(default_assets_dir: Path, assets_dir: Path) -> None:
    shutil.copytree(default_assets_dir, assets_dir, dirs_exist_ok=True)


def initialize_assets(
    *,
    assets_dir: Path,
    default_assets_dir: Path,
    app_version: str,
    reset_assets: bool = False,
) -> AssetSyncResult:
    if not default_assets_dir.exists():
        raise FileNotFoundError(f"Default assets directory does not exist: {default_assets_dir}")

    assets_dir.mkdir(parents=True, exist_ok=True)
    previous_version = _read_runtime_version(assets_dir)
    runtime_entries = _list_runtime_entries(assets_dir)

    if reset_assets:
        backup_path = _archive_runtime_assets(assets_dir)
        _clear_runtime_assets(assets_dir)
        _copy_default_assets(default_assets_dir, assets_dir)
        _write_runtime_version(assets_dir, app_version)
        return AssetSyncResult(
            action=AssetSyncAction.RESET,
            app_version=app_version,
            previous_version=previous_version,
            backup_path=backup_path,
        )

    if not runtime_entries:
        _copy_default_assets(default_assets_dir, assets_dir)
        _write_runtime_version(assets_dir, app_version)
        return AssetSyncResult(
            action=AssetSyncAction.INITIAL_COPY,
            app_version=app_version,
            previous_version=previous_version,
        )

    if previous_version == app_version:
        return AssetSyncResult(
            action=AssetSyncAction.UP_TO_DATE,
            app_version=app_version,
            previous_version=previous_version,
        )

    backup_path = _archive_runtime_assets(assets_dir)
    _clear_runtime_assets(assets_dir)
    _copy_default_assets(default_assets_dir, assets_dir)
    _write_runtime_version(assets_dir, app_version)
    return AssetSyncResult(
        action=AssetSyncAction.VERSION_SYNC,
        app_version=app_version,
        previous_version=previous_version,
        backup_path=backup_path,
    )


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _emit(message: str) -> None:
    sys.stdout.write(f"{message}\n")


def main() -> None:
    assets_dir = Path(os.getenv("ASSETS_CONTAINER_PATH", "/opt/altshop/assets"))
    default_assets_dir = Path(os.getenv("ASSETS_DEFAULT_PATH", "/opt/altshop/assets.default"))
    app_version = os.getenv("APP_VERSION", __version__)
    reset_assets = _env_flag("RESET_ASSETS", default=False)

    _emit(f"Starting asset initialization, reset flag is '{str(reset_assets).lower()}'")
    result = initialize_assets(
        assets_dir=assets_dir,
        default_assets_dir=default_assets_dir,
        app_version=app_version,
        reset_assets=reset_assets,
    )

    if result.action == AssetSyncAction.INITIAL_COPY:
        _emit(
            "Runtime assets are empty, copied defaults "
            f"and wrote version marker {result.app_version}."
        )
        return

    if result.action == AssetSyncAction.RESET:
        if result.backup_path is not None:
            _emit(f"Archived existing runtime assets to '{result.backup_path}'.")
        _emit(f"Reset runtime assets to defaults for version {result.app_version}.")
        return

    if result.action == AssetSyncAction.VERSION_SYNC:
        if result.backup_path is not None:
            _emit(f"Archived existing runtime assets to '{result.backup_path}'.")
        previous_version = result.previous_version or "missing"
        _emit(
            "Runtime assets version changed "
            f"from '{previous_version}' to '{result.app_version}', synced defaults."
        )
        return

    _emit(f"Runtime assets are already up to date for version {result.app_version}.")


if __name__ == "__main__":
    main()
