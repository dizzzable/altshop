from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from src.core.enums import BackupScope, BackupSourceKind
from src.infrastructure.database.models.sql import BackupRecord

from .backup_models import BackupInfo

if TYPE_CHECKING:
    from .backup import BackupService


def normalize_backup_scope(metadata: dict[str, Any]) -> BackupScope:
    scope_value = str(metadata.get("backup_scope", BackupScope.FULL.value)).upper()
    try:
        scope = BackupScope(scope_value)
    except ValueError:
        scope = BackupScope.FULL

    if not metadata.get("includes_database") and metadata.get("database"):
        return BackupScope.DB if not metadata.get("includes_assets") else BackupScope.FULL
    return scope


def metadata_to_backup_info(
    service: BackupService,
    backup_file: Path,
    file_stats: Any,
    metadata: dict[str, Any],
) -> BackupInfo:
    scope = normalize_backup_scope(metadata)
    includes_database = bool(metadata.get("includes_database", metadata.get("database")))
    includes_assets = bool(metadata.get("includes_assets", metadata.get("assets")))
    assets_info = metadata.get("assets") or {}

    return BackupInfo(
        selection_key=f"local:{backup_file.name}",
        filename=backup_file.name,
        filepath=str(backup_file),
        timestamp=metadata.get(
            "timestamp",
            datetime.fromtimestamp(file_stats.st_mtime, tz=timezone.utc).isoformat(),
        ),
        tables_count=metadata.get("tables_count", 0),
        total_records=metadata.get("total_records", 0),
        compressed=service._is_archive_backup(backup_file),
        file_size_bytes=file_stats.st_size,
        file_size_mb=round(file_stats.st_size / 1024 / 1024, 2),
        created_by=metadata.get("created_by"),
        database_type=metadata.get("database_type", "unknown"),
        version=metadata.get("format_version", "1.0"),
        backup_scope=scope,
        includes_database=includes_database,
        includes_assets=includes_assets,
        assets_root=metadata.get("assets_root") or assets_info.get("root"),
        assets_files_count=int(assets_info.get("files_count", 0) or 0),
        assets_size_bytes=int(assets_info.get("size_bytes", 0) or 0),
        source_kind=BackupSourceKind.LOCAL,
        has_local_copy=True,
        has_telegram_copy=False,
        error=service._summarize_backup_integrity(metadata),
    )


def parse_backup_timestamp(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def backup_sort_timestamp(value: object) -> float:
    parsed = parse_backup_timestamp(value)
    if parsed is None:
        return 0.0
    return parsed.timestamp()


def resolve_backup_source_kind(
    *,
    has_local_copy: bool,
    has_telegram_copy: bool,
) -> BackupSourceKind:
    if has_local_copy and has_telegram_copy:
        return BackupSourceKind.LOCAL_AND_TELEGRAM
    if has_telegram_copy:
        return BackupSourceKind.TELEGRAM
    return BackupSourceKind.LOCAL


def resolve_registry_local_path(service: BackupService, record: BackupRecord) -> Optional[Path]:
    if record.local_path:
        candidate = Path(record.local_path)
        if candidate.exists():
            return candidate

    fallback = service.backup_dir / record.filename
    if fallback.exists():
        return fallback

    return None


def record_to_backup_info(
    service: BackupService,
    record: BackupRecord,
) -> Optional[BackupInfo]:
    local_path = resolve_registry_local_path(service, record)
    has_local_copy = local_path is not None
    has_telegram_copy = bool(record.telegram_file_id)
    if not has_local_copy and not has_telegram_copy:
        return None

    scope_value = (record.backup_scope or BackupScope.FULL.value).upper()
    try:
        backup_scope = BackupScope(scope_value)
    except ValueError:
        backup_scope = BackupScope.FULL

    timestamp = (
        record.backup_timestamp.isoformat()
        if record.backup_timestamp
        else record.created_at.isoformat()
    )

    return BackupInfo(
        selection_key=f"registry:{record.id}",
        filename=record.filename,
        filepath=str(local_path) if local_path else "",
        timestamp=timestamp,
        tables_count=record.tables_count,
        total_records=record.total_records,
        compressed=record.compressed,
        file_size_bytes=record.file_size_bytes,
        file_size_mb=round(record.file_size_bytes / 1024 / 1024, 2),
        created_by=record.created_by,
        database_type=record.database_type,
        version=record.version,
        backup_scope=backup_scope,
        includes_database=record.includes_database,
        includes_assets=record.includes_assets,
        assets_root=record.assets_root,
        assets_files_count=record.assets_files_count,
        assets_size_bytes=record.assets_size_bytes,
        source_kind=resolve_backup_source_kind(
            has_local_copy=has_local_copy,
            has_telegram_copy=has_telegram_copy,
        ),
        has_local_copy=has_local_copy,
        has_telegram_copy=has_telegram_copy,
        telegram_file_id=record.telegram_file_id,
    )
