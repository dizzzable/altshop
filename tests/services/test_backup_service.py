from __future__ import annotations

import asyncio
import json
import tarfile
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from remnawave.enums.users import TrafficLimitStrategy

from src.core.enums import (
    ArchivedPlanRenewMode,
    BackupScope,
    BackupSourceKind,
    Currency,
    DeviceType,
    Locale,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
    UserRole,
)
from src.core.security.password import hash_password, verify_password
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import RemnaSubscriptionDto
from src.infrastructure.database.models.sql.plan import Plan, PlanDuration, PlanPrice
from src.infrastructure.database.models.sql.promocode import Promocode
from src.infrastructure.database.models.sql.referral import ReferralInvite
from src.infrastructure.database.models.sql.subscription import Subscription
from src.infrastructure.database.models.sql.transaction import Transaction
from src.infrastructure.database.models.sql.user import User
from src.infrastructure.database.models.sql.web_account import WebAccount
from src.services.backup import BackupInfo, BackupService


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
        remnawave=MagicMock(),
    )
    service._send_backup_file_to_chat = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._cleanup_old_backups = AsyncMock()  # type: ignore[method-assign]
    service._list_registered_backup_infos = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service._upsert_backup_record = AsyncMock()  # type: ignore[method-assign]
    service._sync_backup_record_after_local_delete = AsyncMock()  # type: ignore[method-assign]
    service._download_telegram_backup_file = AsyncMock()  # type: ignore[method-assign]
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
    assert "Database: 12 tables / 345 records" in message
    assert "Created:" in message

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
    (assets_dir / ".altshop_assets_version").write_text("1.2.1", encoding="utf-8")
    backup_dir = assets_dir / ".bak"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "assets_backup_20260325.tar.gz").write_text("backup-payload", encoding="utf-8")

    service, _config = build_backup_service(tmp_path, assets_dir=assets_dir)

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.ASSETS))

    assert success is True
    assert file_path is not None
    assert "Scope: Assets only" in message
    assert "Assets: 1 files" in message
    assert "Created:" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.ASSETS.value
    assert metadata["includes_database"] is False
    assert metadata["includes_assets"] is True
    assert "database.json" not in names
    assert "assets/branding/logo.txt" in names
    assert "assets/.altshop_assets_version" not in names
    assert "assets/.bak/assets_backup_20260325.tar.gz" not in names


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
    assert "Database: 7 tables / 99 records" in message
    assert "Assets: 1 files" in message
    assert "Created:" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.FULL.value
    assert metadata["includes_database"] is True
    assert metadata["includes_assets"] is True
    assert "database.json" in names
    assert "assets/translations/en.ftl" in names


def test_create_backup_marks_degraded_archives_in_message_and_metadata(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 3, "total_records": 4}
    )

    async def write_degraded_dump(staging_dir: Path) -> dict[str, object]:
        dump_path = staging_dir / "database.json"
        dump_path.write_text(
            json.dumps(
                {
                    "metadata": {
                        "timestamp": "2026-03-24T10:00:00+00:00",
                        "integrity": {
                            "degraded": True,
                            "issues": [
                                {
                                    "code": "missing_subscription_rows",
                                    "message": (
                                        "Users reference current subscriptions "
                                        "that are absent from the export"
                                    ),
                                }
                            ],
                        },
                    },
                    "data": {},
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
            "tables_count": 3,
            "total_records": 4,
            "integrity": {
                "degraded": True,
                "issues": [
                    {
                        "code": "missing_subscription_rows",
                        "message": (
                            "Users reference current subscriptions that are absent from the export"
                        ),
                    }
                ],
            },
        }

    service._dump_database_json = AsyncMock(side_effect=write_degraded_dump)  # type: ignore[method-assign]

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.DB))

    assert success is True
    assert file_path is not None
    assert "degraded" in message.lower()
    metadata, _names = read_archive_metadata(Path(file_path))
    assert metadata["integrity"]["degraded"] is True


def test_send_backup_file_to_chat_uses_rich_caption_and_topic(tmp_path: Path) -> None:
    service, config = build_backup_service(tmp_path)
    service._send_backup_file_to_chat = BackupService._send_backup_file_to_chat.__get__(
        service,
        BackupService,
    )
    config.backup.send_enabled = True
    config.backup.send_chat_id = 123456
    config.backup.send_topic_id = 77
    config.backup.is_send_enabled = lambda: True
    service.bot.send_document = AsyncMock(return_value=SimpleNamespace(document=SimpleNamespace()))

    backup_path = service.backup_dir / "backup_full_20260413_000002.tar.gz"
    backup_path.write_text("payload", encoding="utf-8")
    backup_info = BackupInfo(
        selection_key=f"local:{backup_path.name}",
        filename=backup_path.name,
        filepath=str(backup_path),
        timestamp="2026-04-13T00:00:02+00:00",
        tables_count=7,
        total_records=99,
        compressed=True,
        file_size_bytes=440 * 1024,
        file_size_mb=0.43,
        created_by=None,
        database_type="postgresql",
        version="3.3",
        includes_database=True,
        includes_assets=False,
    )

    result = run_async(
        BackupService._send_backup_file_to_chat(
            service,
            str(backup_path),
            backup_info=backup_info,
            locale=None,
        )
    )

    assert result is not None
    service.bot.send_document.assert_awaited_once()
    kwargs = service.bot.send_document.await_args.kwargs
    assert kwargs["chat_id"] == 123456
    assert kwargs["message_thread_id"] == 77
    assert "Backup created" in kwargs["caption"]
    assert "Full backup" in kwargs["caption"]
    assert "2026-04-13 00:00:02" in kwargs["caption"]
    assert "7 tables / 99 records" in kwargs["caption"]
    assert "File:" not in kwargs["caption"]


def test_send_backup_file_to_chat_caption_stays_compact_without_restore_only_diagnostics(
    tmp_path: Path,
) -> None:
    service, config = build_backup_service(tmp_path)
    service._send_backup_file_to_chat = BackupService._send_backup_file_to_chat.__get__(
        service,
        BackupService,
    )
    config.backup.send_enabled = True
    config.backup.send_chat_id = 123456
    config.backup.is_send_enabled = lambda: True
    service.bot.send_document = AsyncMock(return_value=SimpleNamespace(document=SimpleNamespace()))

    backup_path = service.backup_dir / "backup_db_20260413_000002.tar.gz"
    backup_path.write_text("payload", encoding="utf-8")
    backup_info = BackupInfo(
        selection_key=f"local:{backup_path.name}",
        filename=backup_path.name,
        filepath=str(backup_path),
        timestamp="2026-04-13T00:00:02+00:00",
        tables_count=12,
        total_records=345,
        compressed=True,
        file_size_bytes=2 * 1024 * 1024,
        file_size_mb=2.0,
        created_by=None,
        database_type="postgresql",
        version="3.3",
        backup_scope=BackupScope.DB,
        includes_database=True,
        includes_assets=False,
        error="Degraded backup: missing rows (+1 more)",
    )

    run_async(
        BackupService._send_backup_file_to_chat(
            service,
            str(backup_path),
            backup_info=backup_info,
            locale=None,
        )
    )

    caption = service.bot.send_document.await_args.kwargs["caption"]
    assert "Degraded archive" in caption
    assert "Remnawave" not in caption
    assert "Recovered plans" not in caption


def test_build_backup_result_message_includes_db_assets_and_degraded_summary(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    backup_info = BackupInfo(
        selection_key="local:backup_full.tar.gz",
        filename="backup_full.tar.gz",
        filepath=str(tmp_path / "backup_full.tar.gz"),
        timestamp="2026-04-13T12:00:00+00:00",
        tables_count=7,
        total_records=99,
        compressed=True,
        file_size_bytes=1536,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.3",
        backup_scope=BackupScope.FULL,
        includes_database=True,
        includes_assets=True,
        assets_files_count=4,
        error="Degraded backup: missing rows (+1 more)",
    )

    message = service._build_backup_result_message(backup_info=backup_info, locale=None)

    assert "Scope: Full backup" in message
    assert "Size: 1.5 KB" in message
    assert "Database: 7 tables / 99 records" in message
    assert "Assets: 4 files" in message
    assert "Warning: backup marked as degraded" in message


def test_summarize_backup_integrity_uses_first_issue_and_more_count(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)

    summary = service._summarize_backup_integrity(
        {
            "integrity": {
                "degraded": True,
                "issues": [
                    {"message": "missing rows"},
                    {"message": "orphaned subscriptions"},
                    {"message": "legacy mismatch"},
                ],
            }
        }
    )

    assert summary == "Degraded backup: missing rows (+2 more)"


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
    restored_banner = (target_assets_dir / "branding" / "banner.txt").read_text(encoding="utf-8")

    assert restored_banner == "banner-v1"
    assert unrelated_file.read_text(encoding="utf-8") == "keep-me"


def test_restore_assets_backup_skips_internal_asset_sync_files(tmp_path: Path) -> None:
    source_assets_dir = tmp_path / "source-assets"
    marker_file = source_assets_dir / ".altshop_assets_version"
    backup_archive = source_assets_dir / ".bak" / "assets_backup_20260325.tar.gz"
    actual_file = source_assets_dir / "branding" / "banner.txt"
    backup_archive.parent.mkdir(parents=True, exist_ok=True)
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    marker_file.write_text("1.2.0", encoding="utf-8")
    backup_archive.write_text("old-assets", encoding="utf-8")
    actual_file.write_text("banner-v1", encoding="utf-8")

    service, config = build_backup_service(tmp_path)
    target_assets_dir = tmp_path / "target-assets"
    config.assets_dir = target_assets_dir

    restore_message = run_async(service._restore_assets_from_dir(source_assets_dir))

    assert "Assets restored successfully!" in restore_message
    assert (target_assets_dir / "branding" / "banner.txt").read_text(encoding="utf-8") == (
        "banner-v1"
    )
    assert not (target_assets_dir / ".altshop_assets_version").exists()
    assert not (target_assets_dir / ".bak").exists()


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


def test_restore_from_archive_restores_database_before_assets(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    archive_path = tmp_path / "restore-order.tar.gz"
    payload_dir = tmp_path / "restore-order"
    payload_dir.mkdir(parents=True, exist_ok=True)
    (payload_dir / "metadata.json").write_text(
        json.dumps(
            {
                "format_version": "3.3",
                "includes_database": True,
                "includes_assets": True,
                "database": {"path": "database.json"},
                "assets": {"path": "assets"},
            }
        ),
        encoding="utf-8",
    )
    (payload_dir / "database.json").write_text("{}", encoding="utf-8")
    asset_file = payload_dir / "assets" / "branding" / "banner.txt"
    asset_file.parent.mkdir(parents=True, exist_ok=True)
    asset_file.write_text("banner", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        for item in payload_dir.iterdir():
            archive.add(item, arcname=item.name)

    call_order: list[tuple[str, str]] = []

    async def restore_db(dump_path: Path, clear_existing: bool, locale: Locale | None = None):
        assert clear_existing is True
        assert locale is None
        call_order.append(("db", dump_path.name))
        return True, "database restored"

    async def restore_assets(source_dir: Path, *, locale: Locale | None = None) -> str:
        assert locale is None
        call_order.append(("assets", source_dir.name))
        return "assets restored"

    service._restore_from_json = AsyncMock(side_effect=restore_db)  # type: ignore[method-assign]
    service._restore_assets_from_dir = AsyncMock(side_effect=restore_assets)  # type: ignore[method-assign]

    restored, message = run_async(service._restore_from_archive(archive_path, clear_existing=True))

    assert restored is True
    assert message == "database restored\n\nassets restored"
    assert call_order == [("db", "database.json"), ("assets", "assets")]


def test_restore_from_archive_fails_cleanly_when_metadata_is_missing(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    archive_path = tmp_path / "missing-metadata.tar.gz"
    payload_dir = tmp_path / "missing-metadata"
    payload_dir.mkdir(parents=True, exist_ok=True)
    (payload_dir / "database.json").write_text("{}", encoding="utf-8")

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(payload_dir / "database.json", arcname="database.json")

    restored, message = run_async(service._restore_from_archive(archive_path, clear_existing=False))

    assert restored is False
    assert message == "Backup metadata file is missing"


def test_clear_database_tables_uses_single_truncate_statement(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    session = SimpleNamespace(execute=AsyncMock())

    run_async(service._clear_database_tables_atomic(session))

    assert session.execute.await_count == 1
    statement = str(session.execute.await_args.args[0])
    assert "TRUNCATE TABLE" in statement
    assert "RESTART IDENTITY CASCADE" in statement
    assert "users" in statement
    assert "referral_invites" in statement
    assert "web_accounts" in statement


def test_get_backup_list_merges_registry_entries_with_local_fallback(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)

    fallback_file = service.backup_dir / "backup_local_only.tar.gz"
    fallback_file.write_text("broken backup", encoding="utf-8")

    registry_backup = BackupInfo(
        selection_key="registry:1",
        filename="backup_registry.tar.gz",
        filepath=str(service.backup_dir / "backup_registry.tar.gz"),
        timestamp="2026-03-25T11:00:00+00:00",
        tables_count=1,
        total_records=2,
        compressed=True,
        file_size_bytes=1024,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.0",
        source_kind=BackupSourceKind.LOCAL_AND_TELEGRAM,
        has_local_copy=True,
        has_telegram_copy=True,
        telegram_file_id="telegram-file",
    )
    service._list_registered_backup_infos = AsyncMock(return_value=[registry_backup])  # type: ignore[method-assign]

    backups = run_async(service.get_backup_list())

    assert len(backups) == 2
    assert any(backup.selection_key == "registry:1" for backup in backups)
    assert any(backup.selection_key == "local:backup_local_only.tar.gz" for backup in backups)


def test_normalize_backup_scope_preserves_legacy_database_fallback(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)

    db_only_scope = service._normalize_backup_scope(
        {
            "backup_scope": BackupScope.FULL.value,
            "includes_database": False,
            "includes_assets": False,
            "database": {"path": "database.json"},
        }
    )
    full_scope = service._normalize_backup_scope(
        {
            "backup_scope": BackupScope.DB.value,
            "includes_database": False,
            "includes_assets": True,
            "database": {"path": "database.json"},
        }
    )

    assert db_only_scope == BackupScope.DB
    assert full_scope == BackupScope.FULL


def test_metadata_to_backup_info_preserves_assets_and_degraded_mapping(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    backup_path = service.backup_dir / "backup_local.tar.gz"
    backup_path.write_text("payload", encoding="utf-8")
    file_stats = backup_path.stat()

    backup_info = service._metadata_to_backup_info(
        backup_path,
        file_stats,
        {
            "timestamp": "2026-03-25T11:00:00+00:00",
            "created_by": 7,
            "database_type": "postgresql",
            "format_version": "3.3",
            "backup_scope": BackupScope.FULL.value,
            "includes_database": True,
            "includes_assets": True,
            "tables_count": 12,
            "total_records": 345,
            "assets_root": "runtime-assets",
            "assets": {"files_count": 5, "size_bytes": 1234},
            "integrity": {
                "degraded": True,
                "issues": [{"message": "missing rows"}],
            },
        },
    )

    assert backup_info.source_kind == BackupSourceKind.LOCAL
    assert backup_info.has_local_copy is True
    assert backup_info.includes_assets is True
    assert backup_info.assets_root == "runtime-assets"
    assert backup_info.assets_files_count == 5
    assert backup_info.assets_size_bytes == 1234
    assert backup_info.error == "Degraded backup: missing rows"


def test_record_to_backup_info_resolves_local_and_telegram_source_kind(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    local_copy = service.backup_dir / "backup_registry.tar.gz"
    local_copy.write_text("payload", encoding="utf-8")
    record = SimpleNamespace(
        id=9,
        filename=local_copy.name,
        local_path=str(local_copy),
        backup_timestamp=datetime(2026, 3, 25, 11, 0, tzinfo=timezone.utc),
        created_at=datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc),
        created_by=1,
        backup_scope=BackupScope.DB.value,
        includes_database=True,
        includes_assets=False,
        assets_root=None,
        tables_count=12,
        total_records=345,
        compressed=True,
        file_size_bytes=local_copy.stat().st_size,
        database_type="postgresql",
        version="3.3",
        assets_files_count=0,
        assets_size_bytes=0,
        telegram_file_id="telegram-file",
    )

    backup_info = service._record_to_backup_info(record)

    assert backup_info is not None
    assert backup_info.source_kind == BackupSourceKind.LOCAL_AND_TELEGRAM
    assert backup_info.has_local_copy is True
    assert backup_info.has_telegram_copy is True
    assert backup_info.filepath == str(local_copy)


def test_restore_selected_backup_downloads_telegram_only_backup(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    telegram_backup = BackupInfo(
        selection_key="registry:42",
        filename="backup_remote.tar.gz",
        filepath="",
        timestamp="2026-03-25T11:00:00+00:00",
        tables_count=1,
        total_records=2,
        compressed=True,
        file_size_bytes=1024,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.0",
        source_kind=BackupSourceKind.TELEGRAM,
        has_local_copy=False,
        has_telegram_copy=True,
        telegram_file_id="telegram-file",
    )
    service.get_backup_by_key = AsyncMock(return_value=telegram_backup)  # type: ignore[method-assign]
    service.restore_backup = AsyncMock(return_value=(True, "restored"))  # type: ignore[method-assign]

    success, message = run_async(service.restore_selected_backup("registry:42"))

    assert success is True
    assert message == "restored"
    service._download_telegram_backup_file.assert_awaited_once()
    service.restore_backup.assert_awaited_once()


def test_import_backup_file_registers_local_copy(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    archive_path = tmp_path / "backup_import.tar.gz"
    archive_path.write_text("fake", encoding="utf-8")
    service._read_backup_metadata = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "timestamp": "2026-03-25T10:00:00+00:00",
            "backup_scope": BackupScope.DB.value,
            "includes_database": True,
            "includes_assets": False,
        }
    )

    success, backup_info, error = run_async(
        service.import_backup_file(
            source_file_path=archive_path,
            original_filename="backup_import.tar.gz",
            created_by=7,
        )
    )

    assert success is True
    assert backup_info is not None
    assert error == ""
    service._upsert_backup_record.assert_awaited_once()


def test_build_imported_backup_filename_sanitizes_spaces_and_avoids_collisions(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 3, 25, 11, 0, tzinfo=tz or timezone.utc)

    existing_path = service.backup_dir / "backup_import_20260325_110000_my_backup.tar.gz"
    existing_path.write_text("exists", encoding="utf-8")

    with patch("src.services.backup_registry_storage.datetime", FixedDateTime):
        filename = service._build_imported_backup_filename("my backup.tar.gz")

    assert filename == "backup_import_20260325_110000_1_my_backup.tar.gz"


@pytest.mark.parametrize(
    "metadata,expected_error",
    [
        ({}, "Backup metadata file is missing."),
        (
            {
                "timestamp": "2026-03-25T10:00:00+00:00",
                "backup_scope": BackupScope.FULL.value,
                "includes_database": False,
                "includes_assets": False,
            },
            "Backup does not contain restorable data.",
        ),
    ],
)
def test_import_backup_file_removes_copied_file_on_invalid_metadata(
    tmp_path: Path,
    metadata: dict[str, object],
    expected_error: str,
) -> None:
    service, _config = build_backup_service(tmp_path)
    archive_path = tmp_path / "backup import.tar.gz"
    archive_path.write_text("fake", encoding="utf-8")
    service._read_backup_metadata = AsyncMock(return_value=metadata)  # type: ignore[method-assign]

    success, backup_info, error = run_async(
        service.import_backup_file(
            source_file_path=archive_path,
            original_filename="backup import.tar.gz",
            created_by=7,
        )
    )

    assert success is False
    assert backup_info is None
    assert error == expected_error
    assert list(service.backup_dir.iterdir()) == []
    service._upsert_backup_record.assert_not_awaited()


def test_delete_selected_backup_removes_local_copy_only(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    local_path = service.backup_dir / "backup_local.tar.gz"
    local_path.write_text("payload", encoding="utf-8")
    local_backup = BackupInfo(
        selection_key="registry:9",
        filename=local_path.name,
        filepath=str(local_path),
        timestamp="2026-03-25T11:00:00+00:00",
        tables_count=1,
        total_records=2,
        compressed=True,
        file_size_bytes=local_path.stat().st_size,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.0",
        source_kind=BackupSourceKind.LOCAL_AND_TELEGRAM,
        has_local_copy=True,
        has_telegram_copy=True,
        telegram_file_id="telegram-file",
    )
    service.get_backup_by_key = AsyncMock(return_value=local_backup)  # type: ignore[method-assign]

    success, _message = run_async(service.delete_selected_backup("registry:9"))

    assert success is True
    assert not local_path.exists()
    service._sync_backup_record_after_local_delete.assert_awaited_once()


def test_model_to_dict_preserves_plan_arrays_and_empty_lists(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    internal_squad_id = uuid4()
    external_squad_id = uuid4()
    plan = Plan(
        id=10,
        order_index=1,
        is_active=True,
        is_archived=False,
        type=PlanType.BOTH,
        availability=PlanAvailability.ALLOWED,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
        name="Starter",
        description="Base plan",
        tag="starter",
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        replacement_plan_ids=[],
        upgrade_to_plan_ids=[11, 12],
        allowed_user_ids=[],
        internal_squads=[internal_squad_id],
        external_squad=[external_squad_id],
    )
    duration = PlanDuration(id=20, plan_id=10, days=30)
    price = PlanPrice(id=30, plan_duration_id=20, currency=Currency.RUB, price=Decimal("99.90"))

    serialized_plan = service._model_to_dict(plan, Plan)
    serialized_duration = service._model_to_dict(duration, PlanDuration)
    serialized_price = service._model_to_dict(price, PlanPrice)

    assert serialized_plan["replacement_plan_ids"] == []
    assert serialized_plan["upgrade_to_plan_ids"] == [11, 12]
    assert serialized_plan["allowed_user_ids"] == []
    assert serialized_plan["internal_squads"] == [str(internal_squad_id)]
    assert serialized_plan["external_squad"] == [str(external_squad_id)]
    assert serialized_duration["days"] == 30
    assert serialized_price["price"] == "99.90"


def test_model_to_dict_preserves_transaction_json_objects(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    transaction = Transaction(
        id=1,
        payment_id=uuid4(),
        user_telegram_id=123,
        status=TransactionStatus.PENDING,
        is_test=False,
        purchase_type=PurchaseType.NEW,
        channel=None,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing={"amount": "9.99", "currency": "RUB"},
        currency=Currency.RUB,
        payment_asset=None,
        plan={"id": 10, "name": "Starter"},
        renew_subscription_id=None,
        renew_subscription_ids=[1, 2],
        device_types=["ios", "android"],
    )

    serialized = service._model_to_dict(transaction, Transaction)

    assert serialized["pricing"] == {"amount": "9.99", "currency": "RUB"}
    assert serialized["plan"] == {"id": 10, "name": "Starter"}
    assert serialized["renew_subscription_ids"] == [1, 2]
    assert serialized["device_types"] == ["ios", "android"]


def test_process_record_data_restores_legacy_plan_arrays_and_missing_defaults(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())

    processed = service._process_record_data(
        {
            "id": 10,
            "order_index": 1,
            "is_active": True,
            "is_archived": False,
            "type": PlanType.BOTH.value,
            "availability": PlanAvailability.ALLOWED.value,
            "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
            "name": "Starter",
            "description": "Base plan",
            "tag": "starter",
            "traffic_limit": 100,
            "device_limit": 3,
            "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
            "replacement_plan_ids": "[11, 12]",
            "upgrade_to_plan_ids": None,
            "allowed_user_ids": "[]",
            "internal_squads": f'["{squad_id}"]',
            # external_squad intentionally omitted to verify default salvage
        },
        Plan,
        "plans",
    )

    assert processed["replacement_plan_ids"] == [11, 12]
    assert processed["upgrade_to_plan_ids"] == []
    assert processed["allowed_user_ids"] == []
    assert processed["internal_squads"] == [UUID(squad_id)]
    assert "external_squad" not in processed


def test_process_record_data_restores_other_array_backed_models(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())

    promocode_processed = service._process_record_data(
        {
            "id": 1,
            "code": "PROMO",
            "is_active": True,
            "availability": PromocodeAvailability.ALL.value,
            "reward_type": PromocodeRewardType.DURATION.value,
            "reward": 30,
            "plan": '{"id": 10}',
            "lifetime": -1,
            "max_activations": -1,
            "allowed_user_ids": "[1, 2]",
            "allowed_plan_ids": None,
        },
        Promocode,
        "promocodes",
    )
    subscription_processed = service._process_record_data(
        {
            "id": 1,
            "user_remna_id": str(uuid4()),
            "user_telegram_id": 123,
            "status": SubscriptionStatus.ACTIVE.value,
            "is_trial": False,
            "traffic_limit": 100,
            "device_limit": 3,
            "internal_squads": f'["{squad_id}"]',
            "external_squad": str(uuid4()),
            "expire_at": datetime.now(timezone.utc).isoformat(),
            "url": "https://example.com",
            "device_type": DeviceType.IPHONE.value,
            "plan": '{"id": 10, "name": "Starter"}',
        },
        Subscription,
        "subscriptions",
    )
    transaction_processed = service._process_record_data(
        {
            "id": 1,
            "payment_id": str(uuid4()),
            "user_telegram_id": 123,
            "status": TransactionStatus.PENDING.value,
            "is_test": False,
            "purchase_type": PurchaseType.NEW.value,
            "channel": None,
            "gateway_type": PaymentGatewayType.PLATEGA.value,
            "pricing": '{"amount": "9.99"}',
            "currency": Currency.RUB.value,
            "payment_asset": None,
            "plan": '{"id": 10}',
            "renew_subscription_id": None,
            "renew_subscription_ids": "[1, 2]",
            "device_types": '["ios", "android"]',
        },
        Transaction,
        "transactions",
    )

    assert promocode_processed["allowed_user_ids"] == [1, 2]
    assert promocode_processed["allowed_plan_ids"] is None
    assert promocode_processed["plan"] == {"id": 10}
    assert subscription_processed["internal_squads"] == [UUID(squad_id)]
    assert subscription_processed["plan"] == {"id": 10, "name": "Starter"}
    assert transaction_processed["renew_subscription_ids"] == [1, 2]
    assert transaction_processed["device_types"] == ["ios", "android"]
    assert transaction_processed["pricing"] == {"amount": "9.99"}


def test_restore_table_records_builds_plan_instance_with_restored_arrays(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())
    captured_instances: list[Plan] = []
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=lambda instance: captured_instances.append(instance),
        no_autoflush=nullcontext(),
    )

    restored_count = run_async(
        service._restore_table_records(
            session,
            Plan,
            "plans",
            [
                {
                    "id": 10,
                    "order_index": 1,
                    "is_active": True,
                    "is_archived": False,
                    "type": PlanType.BOTH.value,
                    "availability": PlanAvailability.ALLOWED.value,
                    "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
                    "name": "Starter",
                    "description": "Base plan",
                    "tag": "starter",
                    "traffic_limit": 100,
                    "device_limit": 3,
                    "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                    "replacement_plan_ids": "[11, 12]",
                    "upgrade_to_plan_ids": None,
                    "allowed_user_ids": "[]",
                    "internal_squads": f'["{squad_id}"]',
                    "external_squad": "[]",
                }
            ],
            False,
        )
    )

    assert restored_count == 1
    assert len(captured_instances) == 1
    assert captured_instances[0].replacement_plan_ids == [11, 12]
    assert captured_instances[0].upgrade_to_plan_ids == []
    assert captured_instances[0].internal_squads == [UUID(squad_id)]


def test_restore_table_records_merges_existing_user_by_telegram_id(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: 7534150980),
                SimpleNamespace(rowcount=1),
            ]
        ),
        add=MagicMock(),
        no_autoflush=nullcontext(),
    )

    restored_count = run_async(
        service._restore_table_records(
            session,
            User,
            "users",
            [
                {
                    "id": 49,
                    "telegram_id": 7534150980,
                    "username": None,
                    "referral_code": "newCode",
                    "name": "Restored Name",
                    "role": UserRole.USER.value,
                    "language": Locale.RU.value,
                    "personal_discount": 0,
                    "purchase_discount": 0,
                    "points": 0,
                    "is_blocked": False,
                    "is_bot_blocked": False,
                    "is_rules_accepted": True,
                    "partner_balance_currency_override": None,
                    "referral_invite_settings": {},
                    "max_subscriptions": None,
                    "current_subscription_id": None,
                }
            ],
            False,
        )
    )

    assert restored_count == 1
    session.add.assert_not_called()
    assert session.execute.await_count == 2
    lookup_query = str(session.execute.await_args_list[0].args[0])
    update_query = str(session.execute.await_args_list[1].args[0])
    assert "SELECT users.telegram_id" in lookup_query
    assert "UPDATE users SET" in update_query
    assert "users.telegram_id" in update_query


def test_extract_and_apply_deferred_user_subscription_restore_update(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: 83),
                SimpleNamespace(rowcount=1),
            ]
        ),
        no_autoflush=nullcontext(),
    )

    processed_data, deferred_update = service._extract_deferred_restore_fields(
        User,
        {
            "id": 49,
            "telegram_id": 7534150980,
            "current_subscription_id": 83,
        },
    )

    assert processed_data["current_subscription_id"] is None
    assert deferred_update is not None
    assert deferred_update.phase == service.RESTORE_PHASE_POST_SUBSCRIPTIONS

    run_async(
        service._apply_deferred_restore_updates(
            session,
            [deferred_update],
            phase=service.RESTORE_PHASE_POST_SUBSCRIPTIONS,
        )
    )

    assert session.execute.await_count == 2
    subscription_check = str(session.execute.await_args_list[0].args[0])
    user_update = str(session.execute.await_args_list[1].args[0])
    assert "SELECT subscriptions.id" in subscription_check
    assert "UPDATE users SET current_subscription_id" in user_update
    assert "users.telegram_id" in user_update


def test_apply_deferred_user_subscription_restore_update_skips_missing_subscription(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: None),
            ]
        ),
        no_autoflush=nullcontext(),
    )

    _, deferred_update = service._extract_deferred_restore_fields(
        User,
        {
            "id": 49,
            "telegram_id": 7534150980,
            "current_subscription_id": 83,
        },
    )

    assert deferred_update is not None

    run_async(
        service._apply_deferred_restore_updates(
            session,
            [deferred_update],
            phase=service.RESTORE_PHASE_POST_SUBSCRIPTIONS,
        )
    )

    assert session.execute.await_count == 1
    subscription_check = str(session.execute.await_args_list[0].args[0])
    assert "SELECT subscriptions.id" in subscription_check


def test_build_backup_restore_error_message_summarizes_circular_dependency(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)

    message = service._build_backup_restore_error_message(
        "Circular dependency detected. (" + ("x" * 500) + ")"
    )

    assert message == "Restore failed: users and subscriptions could not be linked automatically"
    assert len(message) < 160


def test_dump_database_json_includes_referral_invites_and_web_accounts(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    referral_invite = ReferralInvite(
        id=1,
        inviter_telegram_id=123,
        token="invite-token",
        expires_at=None,
        revoked_at=None,
    )
    web_account = WebAccount(
        id=2,
        user_telegram_id=123,
        username="demo_user",
        password_hash="hash",
        email="demo@example.com",
        email_normalized="demo@example.com",
        email_verified_at=None,
        credentials_bootstrapped_at=None,
        token_version=0,
        requires_password_change=False,
        temporary_password_expires_at=None,
        link_prompt_snooze_until=None,
    )

    def _result_for(model: object) -> SimpleNamespace:
        records = {
            ReferralInvite: [referral_invite],
            WebAccount: [web_account],
        }.get(model, [])
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: records),
        )

    async def execute(statement):
        model = statement.column_descriptions[0]["entity"]
        return _result_for(model)

    fake_session = SimpleNamespace(execute=AsyncMock(side_effect=execute))

    class FakeSessionContext:
        async def __aenter__(self) -> SimpleNamespace:
            return fake_session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    service.session_pool = lambda: FakeSessionContext()  # type: ignore[assignment]

    dump_info = run_async(service._dump_database_json(staging_dir))
    dump_payload = json.loads((staging_dir / "database.json").read_text(encoding="utf-8"))

    assert dump_info["tables_count"] == len(service.BACKUP_MODELS)
    assert dump_payload["data"]["referral_invites"][0]["token"] == "invite-token"
    assert dump_payload["data"]["web_accounts"][0]["username"] == "demo_user"


def test_model_to_dict_preserves_web_account_auth_fields(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    password_hash = hash_password("secret-123")
    verified_at = datetime(2026, 4, 11, 12, 30, tzinfo=timezone.utc)
    bootstrap_at = datetime(2026, 4, 11, 12, 45, tzinfo=timezone.utc)
    temp_password_expires_at = datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
    snooze_until = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)
    web_account = WebAccount(
        id=2,
        user_telegram_id=123,
        username="demo_user",
        password_hash=password_hash,
        email="demo@example.com",
        email_normalized="demo@example.com",
        email_verified_at=verified_at,
        credentials_bootstrapped_at=bootstrap_at,
        token_version=4,
        requires_password_change=True,
        temporary_password_expires_at=temp_password_expires_at,
        link_prompt_snooze_until=snooze_until,
    )

    serialized = service._model_to_dict(web_account, WebAccount)

    assert serialized["password_hash"] == password_hash
    assert serialized["token_version"] == 4
    assert serialized["requires_password_change"] is True
    assert serialized["email_verified_at"] == verified_at.isoformat()
    assert serialized["credentials_bootstrapped_at"] == bootstrap_at.isoformat()
    assert serialized["temporary_password_expires_at"] == temp_password_expires_at.isoformat()
    assert serialized["link_prompt_snooze_until"] == snooze_until.isoformat()


def test_process_record_data_restores_web_account_auth_fields(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    password_hash = hash_password("secret-123")
    verified_at = datetime(2026, 4, 11, 12, 30, tzinfo=timezone.utc)
    bootstrap_at = datetime(2026, 4, 11, 12, 45, tzinfo=timezone.utc)
    temp_password_expires_at = datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
    snooze_until = datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc)

    processed = service._process_record_data(
        {
            "id": 2,
            "user_telegram_id": 123,
            "username": "demo_user",
            "password_hash": password_hash,
            "email": "demo@example.com",
            "email_normalized": "demo@example.com",
            "email_verified_at": verified_at.isoformat(),
            "credentials_bootstrapped_at": bootstrap_at.isoformat(),
            "token_version": "4",
            "requires_password_change": True,
            "temporary_password_expires_at": temp_password_expires_at.isoformat(),
            "link_prompt_snooze_until": snooze_until.isoformat(),
        },
        WebAccount,
        "web_accounts",
    )

    assert processed["password_hash"] == password_hash
    assert processed["token_version"] == 4
    assert processed["requires_password_change"] is True
    assert processed["email_verified_at"] == verified_at
    assert processed["credentials_bootstrapped_at"] == bootstrap_at
    assert processed["temporary_password_expires_at"] == temp_password_expires_at
    assert processed["link_prompt_snooze_until"] == snooze_until


def test_restore_table_records_preserves_restored_web_account_hash(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    password_hash = hash_password("secret-123")
    captured_instances: list[WebAccount] = []
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=lambda instance: captured_instances.append(instance),
        no_autoflush=nullcontext(),
    )

    restored_count = run_async(
        service._restore_table_records(
            session,
            WebAccount,
            "web_accounts",
            [
                {
                    "id": 2,
                    "user_telegram_id": 123,
                    "username": "demo_user",
                    "password_hash": password_hash,
                    "email": "demo@example.com",
                    "email_normalized": "demo@example.com",
                    "email_verified_at": datetime(
                        2026, 4, 11, 12, 30, tzinfo=timezone.utc
                    ).isoformat(),
                    "credentials_bootstrapped_at": datetime(
                        2026, 4, 11, 12, 45, tzinfo=timezone.utc
                    ).isoformat(),
                    "token_version": 4,
                    "requires_password_change": True,
                    "temporary_password_expires_at": datetime(
                        2026, 4, 12, 9, 0, tzinfo=timezone.utc
                    ).isoformat(),
                    "link_prompt_snooze_until": datetime(
                        2026, 4, 20, 9, 0, tzinfo=timezone.utc
                    ).isoformat(),
                }
            ],
            False,
        )
    )

    assert restored_count == 1
    assert len(captured_instances) == 1
    restored_account = captured_instances[0]
    assert restored_account.password_hash == password_hash
    assert verify_password("secret-123", restored_account.password_hash) is True
    assert restored_account.token_version == 4
    assert restored_account.requires_password_change is True


def test_recover_legacy_missing_plans_from_snapshots_and_durations(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())
    external_squad_id = str(uuid4())

    recovered_data, recovered_count = service._recover_legacy_missing_plans(
        {
            "plans": [],
            "plan_durations": [
                {"id": 1, "plan_id": 1, "days": 30},
                {"id": 2, "plan_id": 2, "days": 90},
            ],
            "transactions": [
                {
                    "id": 10,
                    "plan": {
                        "id": 1,
                        "name": "Starter",
                        "tag": "starter",
                        "type": PlanType.BOTH.value,
                        "traffic_limit": 100,
                        "device_limit": 3,
                        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                        "internal_squads": [squad_id],
                        "external_squad": external_squad_id,
                    },
                }
            ],
            "subscriptions": [
                {
                    "id": 11,
                    "plan": {
                        "id": 2,
                        "name": "Pro",
                        "tag": None,
                        "type": PlanType.TRAFFIC.value,
                        "traffic_limit": 500,
                        "device_limit": 1,
                        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                        "internal_squads": [],
                        "external_squad": None,
                    },
                }
            ],
        }
    )

    assert recovered_count == 2
    plans = recovered_data["plans"]
    assert len(plans) == 2
    assert plans[0]["name"] == "Starter"
    assert plans[0]["internal_squads"] == [squad_id]
    assert plans[0]["external_squad"] == [external_squad_id]
    assert plans[1]["name"] == "Pro"
    assert plans[1]["availability"] == PlanAvailability.ALL.value
    assert plans[1]["archived_renew_mode"] == ArchivedPlanRenewMode.SELF_RENEW.value


def test_recover_legacy_missing_plans_enriches_partial_catalog_from_snapshots(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)

    recovered_data, recovered_count = service._recover_legacy_missing_plans(
        {
            "plans": [
                {
                    "id": 1,
                    "order_index": 1,
                    "is_active": True,
                    "is_archived": False,
                    "type": PlanType.BOTH.value,
                    "availability": PlanAvailability.ALL.value,
                    "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
                    "name": "Starter",
                    "description": None,
                    "tag": "starter",
                    "traffic_limit": 100,
                    "device_limit": 1,
                    "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                    "replacement_plan_ids": [],
                    "upgrade_to_plan_ids": [],
                    "allowed_user_ids": [],
                    "internal_squads": [],
                    "external_squad": None,
                }
            ],
            "plan_durations": [],
            "transactions": [
                {
                    "id": 2,
                    "plan": {
                        "id": 2,
                        "name": "Legacy Archived",
                        "tag": "legacy",
                        "type": PlanType.TRAFFIC.value,
                        "traffic_limit": 500,
                        "device_limit": 1,
                        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                        "internal_squads": [],
                        "external_squad": None,
                    },
                }
            ],
        }
    )

    assert recovered_count == 1
    plans = recovered_data["plans"]
    assert len(plans) == 2
    assert plans[1]["id"] == 2
    assert plans[1]["is_active"] is False
    assert plans[1]["is_archived"] is True


def test_build_backup_integrity_report_marks_missing_plan_and_subscription_data(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)

    integrity = service._build_backup_integrity_report(
        backup_data={
            "plans": [],
            "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
            "plan_prices": [{"id": 1, "plan_duration_id": 1, "currency": "RUB", "price": "100"}],
            "users": [{"id": 1, "telegram_id": 123, "current_subscription_id": 77}],
            "subscriptions": [],
        },
        export_errors={"subscriptions": "mock export failure"},
    )

    assert integrity["degraded"] is True
    issue_codes = {issue["code"] for issue in integrity["issues"]}
    assert issue_codes == {
        "export_errors",
        "missing_plan_catalog",
        "missing_subscription_rows",
    }


def test_match_plan_for_panel_subscription_picks_lowest_order_index_match(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    internal_squad = uuid4()
    external_squad = uuid4()
    remna_subscription = RemnaSubscriptionDto(
        uuid=uuid4(),
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc),
        url="https://example.com/sub",
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        tag="starter",
        internal_squads=[internal_squad],
        external_squad=external_squad,
    )
    higher_order_match = Plan(
        id=10,
        order_index=5,
        is_active=True,
        is_archived=False,
        type=PlanType.BOTH,
        availability=PlanAvailability.ALL,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
        name="Starter Plus",
        description=None,
        tag="starter",
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        replacement_plan_ids=[],
        upgrade_to_plan_ids=[],
        allowed_user_ids=[],
        internal_squads=[internal_squad],
        external_squad=external_squad,
    )
    lower_order_match = Plan(
        id=11,
        order_index=1,
        is_active=True,
        is_archived=False,
        type=PlanType.BOTH,
        availability=PlanAvailability.ALL,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
        name="Starter",
        description=None,
        tag="starter",
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        replacement_plan_ids=[],
        upgrade_to_plan_ids=[],
        allowed_user_ids=[],
        internal_squads=[internal_squad],
        external_squad=external_squad,
    )

    matched = service._match_plan_for_panel_subscription(
        remna_subscription=remna_subscription,
        plans=[higher_order_match, lower_order_match],
    )

    assert matched is lower_order_match


def test_select_current_subscription_id_prefers_active_current_candidate(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    now = datetime_now()
    subscriptions = [
        SimpleNamespace(
            id=1,
            status=SubscriptionStatus.DELETED,
            expire_at=now + timedelta(days=10),
        ),
        SimpleNamespace(
            id=2,
            status=SubscriptionStatus.DISABLED,
            expire_at=now + timedelta(days=5),
        ),
        SimpleNamespace(
            id=3,
            status=SubscriptionStatus.ACTIVE,
            expire_at=now + timedelta(days=3),
        ),
        SimpleNamespace(
            id=4,
            status=SubscriptionStatus.ACTIVE,
            expire_at=now + timedelta(days=7),
        ),
    ]

    selected_id = service._select_current_subscription_id(subscriptions)

    assert selected_id == 4


def test_restore_from_json_appends_panel_recovery_summary(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    dump_path = tmp_path / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-25T12:00:00+00:00"},
                "data": {
                    "plans": [],
                    "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
                    "users": [{"id": 1, "telegram_id": 123, "current_subscription_id": 7}],
                    "subscriptions": [],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
            self.flush = AsyncMock()
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.no_autoflush = nullcontext()
            self.instances: list[object] = []

        def add(self, instance: object) -> None:
            self.instances.append(instance)

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    fake_session = FakeSession()
    service.session_pool = lambda: FakeSessionContext(fake_session)  # type: ignore[assignment]
    service._recover_missing_subscriptions_from_panel = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            archive_issue_messages=["Archive is missing subscription rows"],
            remnawave_users_recovered=1,
            remnawave_subscriptions_recovered=2,
            unrecovered_user_refs=[],
            panel_sync_errors=[],
        )
    )

    restored, message = run_async(service._restore_from_json(dump_path, clear_existing=False))

    assert restored is True
    assert "Archive issues detected: 1" in message
    assert "Users synced from Remnawave: 1" in message
    assert "Subscriptions recovered from Remnawave: 2" in message


def test_sync_panel_profiles_for_restore_updates_current_subscription_from_panel_data(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    plan_payload = {"id": 20, "name": "Recovered Plan"}
    matched_plan = SimpleNamespace(id=20, order_index=1)
    current_subscription = SimpleNamespace(
        id=42,
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=30),
    )
    added_instances: list[Subscription] = []

    class FakeRemnaUser:
        def __init__(self) -> None:
            self.uuid = uuid4()
            self.expire_at = datetime_now() + timedelta(days=30)
            self.status = SubscriptionStatus.ACTIVE
            self._payload = {
                "uuid": self.uuid,
                "status": self.status,
                "expire_at": self.expire_at,
                "subscription_url": "https://example.com/sub",
                "traffic_limit_bytes": 100 * 1024 * 1024 * 1024,
                "hwid_device_limit": 3,
                "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET,
                "tag": "starter",
                "active_internal_squads": [],
                "external_squad_uuid": None,
            }

        def model_dump(self) -> dict[str, object]:
            return dict(self._payload)

    class FakeSession:
        def __init__(self) -> None:
            self.execute = AsyncMock(
                side_effect=[
                    SimpleNamespace(scalar_one_or_none=lambda: 123),
                    SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [matched_plan])),
                    SimpleNamespace(scalar_one_or_none=lambda: None),
                    SimpleNamespace(
                        scalars=lambda: SimpleNamespace(all=lambda: [current_subscription])
                    ),
                ]
            )
            self.flush = AsyncMock()
            self.commit = AsyncMock()

        def add(self, instance: Subscription) -> None:
            added_instances.append(instance)

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    fake_session = FakeSession()
    fake_remna_user = FakeRemnaUser()
    service.session_pool = lambda: FakeSessionContext(fake_session)  # type: ignore[assignment]
    service._match_plan_for_panel_subscription = MagicMock(return_value=matched_plan)  # type: ignore[method-assign]
    service._build_panel_subscription_snapshot = MagicMock(return_value=plan_payload)  # type: ignore[method-assign]
    service._upsert_missing_plan_rows_from_snapshots = AsyncMock(return_value=0)  # type: ignore[method-assign]
    service._select_current_subscription_id = MagicMock(return_value=42)  # type: ignore[method-assign]
    service._apply_scalar_restore_update = AsyncMock(return_value=1)  # type: ignore[method-assign]

    restored_count, panel_snapshots = run_async(
        service._sync_panel_profiles_for_restore(
            telegram_id=123,
            remna_users=[fake_remna_user],
        )
    )

    assert restored_count == 1
    assert panel_snapshots == [plan_payload]
    assert len(added_instances) == 1
    assert added_instances[0].user_remna_id == fake_remna_user.uuid
    assert fake_session.commit.await_count == 1
    service._upsert_missing_plan_rows_from_snapshots.assert_awaited_once()
    service._apply_scalar_restore_update.assert_awaited_once()
    assert (
        service._apply_scalar_restore_update.await_args.kwargs["values"]["current_subscription_id"]
        == 42
    )


def test_recover_missing_subscriptions_from_panel_marks_unrecoverable_users(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    diagnostics = SimpleNamespace(
        panel_sync_candidate_ids=[123],
        missing_archive_subscription_refs=[(123, 7)],
        remnawave_users_recovered=0,
        remnawave_subscriptions_recovered=0,
        unrecovered_user_refs=[],
        panel_sync_errors=[],
    )
    service._fetch_panel_users_by_telegram_id = AsyncMock(return_value=[])  # type: ignore[method-assign]

    updated = run_async(service._recover_missing_subscriptions_from_panel(diagnostics))

    assert updated.unrecovered_user_refs == [(123, 7)]


def test_recover_missing_subscriptions_from_panel_counts_recovered_and_unrecoverable_users(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    diagnostics = SimpleNamespace(
        panel_sync_candidate_ids=[123, 456],
        missing_archive_subscription_refs=[(123, 7), (456, 8)],
        remnawave_users_recovered=0,
        remnawave_subscriptions_recovered=0,
        unrecovered_user_refs=[],
        panel_sync_errors=[],
    )
    service._fetch_panel_users_by_telegram_id = AsyncMock(  # type: ignore[method-assign]
        side_effect=[[object()], [object()]]
    )
    service._sync_panel_profiles_for_restore = AsyncMock(  # type: ignore[method-assign]
        side_effect=[(2, [{"id": 20}]), (0, [])]
    )

    updated = run_async(service._recover_missing_subscriptions_from_panel(diagnostics))

    assert updated.remnawave_users_recovered == 1
    assert updated.remnawave_subscriptions_recovered == 2
    assert updated.unrecovered_user_refs == [(456, 8)]
    assert updated.panel_sync_errors == []


def test_restore_from_json_flushes_each_table_before_children(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    dump_path = tmp_path / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-25T12:00:00+00:00"},
                "data": {
                    "plans": [
                        {
                            "id": 1,
                            "order_index": 1,
                            "is_active": True,
                            "is_archived": False,
                            "type": PlanType.BOTH.value,
                            "availability": PlanAvailability.ALL.value,
                            "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
                            "name": "Starter",
                            "description": None,
                            "tag": None,
                            "traffic_limit": 100,
                            "device_limit": 3,
                            "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                            "replacement_plan_ids": [],
                            "upgrade_to_plan_ids": [],
                            "allowed_user_ids": [],
                            "internal_squads": [],
                            "external_squad": None,
                        }
                    ],
                    "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
            self.flush = AsyncMock()
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.no_autoflush = nullcontext()
            self.instances: list[object] = []

        def add(self, instance: object) -> None:
            self.instances.append(instance)

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    fake_session = FakeSession()
    service.session_pool = lambda: FakeSessionContext(fake_session)  # type: ignore[assignment]

    restored, _message = run_async(service._restore_from_json(dump_path, clear_existing=False))

    assert restored is True
    assert fake_session.flush.await_count == 2
    assert fake_session.commit.await_count == 1
    assert len(fake_session.instances) == 2


def test_restore_from_json_recovers_missing_plans_before_restoring_durations(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    dump_path = tmp_path / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-25T12:00:00+00:00"},
                "data": {
                    "plans": [],
                    "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
                    "transactions": [
                        {
                            "id": 1,
                            "plan": {
                                "id": 1,
                                "name": "Recovered Starter",
                                "tag": "starter",
                                "type": PlanType.BOTH.value,
                                "traffic_limit": 100,
                                "device_limit": 3,
                                "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                                "internal_squads": [],
                                "external_squad": None,
                            },
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
            self.flush = AsyncMock()
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.no_autoflush = nullcontext()
            self.instances: list[object] = []

        def add(self, instance: object) -> None:
            self.instances.append(instance)

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    fake_session = FakeSession()
    service.session_pool = lambda: FakeSessionContext(fake_session)  # type: ignore[assignment]

    restored, message = run_async(service._restore_from_json(dump_path, clear_existing=False))

    assert restored is True
    assert "Recovered plans: 1" in message
    assert len(fake_session.instances) == 3
    assert isinstance(fake_session.instances[0], Plan)
    assert isinstance(fake_session.instances[1], PlanDuration)
