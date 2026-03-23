from __future__ import annotations

import asyncio
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.core.enums import BackupScope
from src.services.backup import BackupService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_backup_service(
    tmp_path: Path,
    *,
    assets_dir: Path | None = None,
) -> tuple[BackupService, object]:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    current_assets_dir = assets_dir or (tmp_path / "assets")
    current_assets_dir.mkdir(parents=True, exist_ok=True)

    backup_config = SimpleNamespace(
        compression=True,
        include_logs=False,
        auto_enabled=False,
        interval_hours=24,
        time="03:00",
        max_keep=7,
        location=backup_dir,
        send_enabled=False,
        send_chat_id=None,
        send_topic_id=None,
        is_send_enabled=lambda: False,
        get_backup_dir=lambda: backup_dir,
    )
    config = SimpleNamespace(
        backup=backup_config,
        assets_dir=current_assets_dir,
    )

    service = BackupService(
        config=config,
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        session_pool=MagicMock(),
        engine=MagicMock(),
    )
    service._send_backup_file_to_chat = AsyncMock()  # type: ignore[method-assign]
    service._cleanup_old_backups = AsyncMock()  # type: ignore[method-assign]
    return service, config


def read_archive_metadata(archive_path: Path) -> tuple[dict[str, object], list[str]]:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        with archive.extractfile("metadata.json") as metadata_file:
            assert metadata_file is not None
            metadata = json.load(metadata_file)
    return metadata, names


async def write_database_dump(staging_dir: Path) -> dict[str, object]:
    dump_path = staging_dir / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-24T10:00:00+00:00"},
                "data": {"users": [{"id": 1}], "plans": [{"id": 10}]},
            }
        ),
        encoding="utf-8",
    )
    return {
        "type": "postgresql",
        "path": dump_path.name,
        "size_bytes": dump_path.stat().st_size,
        "format": "json",
        "tool": "orm",
        "tables_count": 2,
        "total_records": 2,
    }


def test_create_database_backup_contains_db_manifest_only(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 12, "total_records": 345}
    )
    service._dump_database_json = AsyncMock(side_effect=write_database_dump)  # type: ignore[method-assign]

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.DB))

    assert success is True
    assert file_path is not None
    assert "Scope: Database only" in message
    assert "Records: 345" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.DB.value
    assert metadata["includes_database"] is True
    assert metadata["includes_assets"] is False
    assert "database.json" in names
    assert all(not name.startswith("assets/") for name in names)


def test_create_assets_backup_contains_assets_only(tmp_path: Path) -> None:
    assets_dir = tmp_path / "runtime-assets"
    branded_file = assets_dir / "branding" / "logo.txt"
    branded_file.parent.mkdir(parents=True, exist_ok=True)
    branded_file.write_text("custom-logo", encoding="utf-8")

    service, _config = build_backup_service(tmp_path, assets_dir=assets_dir)

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.ASSETS))

    assert success is True
    assert file_path is not None
    assert "Scope: Assets only" in message
    assert "Assets files: 1" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.ASSETS.value
    assert metadata["includes_database"] is False
    assert metadata["includes_assets"] is True
    assert "database.json" not in names
    assert "assets/branding/logo.txt" in names


def test_create_full_backup_contains_database_and_assets(tmp_path: Path) -> None:
    assets_dir = tmp_path / "runtime-assets"
    branded_file = assets_dir / "translations" / "en.ftl"
    branded_file.parent.mkdir(parents=True, exist_ok=True)
    branded_file.write_text("hello = world", encoding="utf-8")

    service, _config = build_backup_service(tmp_path, assets_dir=assets_dir)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 7, "total_records": 99}
    )
    service._dump_database_json = AsyncMock(side_effect=write_database_dump)  # type: ignore[method-assign]

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.FULL))

    assert success is True
    assert file_path is not None
    assert "Scope: Full backup" in message
    assert "Tables: 7" in message
    assert "Assets files: 1" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.FULL.value
    assert metadata["includes_database"] is True
    assert metadata["includes_assets"] is True
    assert "database.json" in names
    assert "assets/translations/en.ftl" in names


def test_restore_assets_backup_merges_files_without_deleting_unrelated(tmp_path: Path) -> None:
    source_assets_dir = tmp_path / "source-assets"
    backed_up_file = source_assets_dir / "branding" / "banner.txt"
    backed_up_file.parent.mkdir(parents=True, exist_ok=True)
    backed_up_file.write_text("banner-v1", encoding="utf-8")

    service, config = build_backup_service(tmp_path, assets_dir=source_assets_dir)
    success, _message, file_path = run_async(service.create_backup(scope=BackupScope.ASSETS))
    assert success is True
    assert file_path is not None

    target_assets_dir = tmp_path / "target-assets"
    unrelated_file = target_assets_dir / "keep.txt"
    unrelated_file.parent.mkdir(parents=True, exist_ok=True)
    unrelated_file.write_text("keep-me", encoding="utf-8")
    config.assets_dir = target_assets_dir

    restored, restore_message = run_async(service.restore_backup(file_path))

    assert restored is True
    assert "Assets restored successfully!" in restore_message
    restored_banner = (target_assets_dir / "branding" / "banner.txt").read_text(
        encoding="utf-8"
    )

    assert restored_banner == "banner-v1"
    assert unrelated_file.read_text(encoding="utf-8") == "keep-me"


def test_restore_database_backup_leaves_assets_untouched(tmp_path: Path) -> None:
    service, config = build_backup_service(tmp_path)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 4, "total_records": 10}
    )
    service._dump_database_json = AsyncMock(side_effect=write_database_dump)  # type: ignore[method-assign]
    service._restore_from_json = AsyncMock(return_value=(True, "DB restored"))  # type: ignore[method-assign]

    success, _message, file_path = run_async(service.create_backup(scope=BackupScope.DB))
    assert success is True
    assert file_path is not None

    target_assets_dir = tmp_path / "runtime-assets"
    existing_file = target_assets_dir / "custom.txt"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("do-not-touch", encoding="utf-8")
    config.assets_dir = target_assets_dir

    restored, restore_message = run_async(service.restore_backup(file_path, clear_existing=True))

    assert restored is True
    assert restore_message == "DB restored"
    assert existing_file.read_text(encoding="utf-8") == "do-not-touch"
    service._restore_from_json.assert_awaited_once()
