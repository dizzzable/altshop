from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aiogram.types import Message
from sqlalchemy import select

from src.infrastructure.database.models.sql import BackupRecord

from .backup_models import BackupInfo
from .backup_registry_metadata import (
    metadata_to_backup_info,
    normalize_backup_scope,
    parse_backup_timestamp,
    record_to_backup_info,
)

if TYPE_CHECKING:
    from .backup import BackupService


async def list_registered_backup_infos(service: BackupService) -> list[BackupInfo]:
    async with service.session_pool() as session:
        result = await session.execute(
            select(BackupRecord).order_by(
                BackupRecord.backup_timestamp.desc().nullslast(),
                BackupRecord.created_at.desc(),
                BackupRecord.id.desc(),
            )
        )
        records = list(result.scalars().all())

    backups: list[BackupInfo] = []
    for record in records:
        backup_info = record_to_backup_info(service, record)
        if backup_info is not None:
            if backup_info.has_local_copy and backup_info.filepath:
                metadata = await service._read_backup_metadata(Path(backup_info.filepath))
                backup_info.error = service._summarize_backup_integrity(metadata)
            backups.append(backup_info)
    return backups


async def upsert_backup_record(
    service: BackupService,
    *,
    backup_info: BackupInfo,
    local_path: Optional[Path],
    telegram_message: Optional[Message] = None,
) -> None:
    async with service.session_pool() as session:
        result = await session.execute(
            select(BackupRecord)
            .where(BackupRecord.filename == backup_info.filename)
            .order_by(BackupRecord.id.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

        if record is None:
            record = BackupRecord(
                filename=backup_info.filename,
                backup_timestamp=parse_backup_timestamp(backup_info.timestamp),
                created_by=backup_info.created_by,
                backup_scope=backup_info.backup_scope.value,
                includes_database=backup_info.includes_database,
                includes_assets=backup_info.includes_assets,
                assets_root=backup_info.assets_root,
                tables_count=backup_info.tables_count,
                total_records=backup_info.total_records,
                compressed=backup_info.compressed,
                file_size_bytes=backup_info.file_size_bytes,
                database_type=backup_info.database_type,
                version=backup_info.version,
                assets_files_count=backup_info.assets_files_count,
                assets_size_bytes=backup_info.assets_size_bytes,
                local_path=str(local_path) if local_path else None,
            )
            session.add(record)
        else:
            record.backup_timestamp = parse_backup_timestamp(backup_info.timestamp)
            record.created_by = backup_info.created_by
            record.backup_scope = backup_info.backup_scope.value
            record.includes_database = backup_info.includes_database
            record.includes_assets = backup_info.includes_assets
            record.assets_root = backup_info.assets_root
            record.tables_count = backup_info.tables_count
            record.total_records = backup_info.total_records
            record.compressed = backup_info.compressed
            record.file_size_bytes = backup_info.file_size_bytes
            record.database_type = backup_info.database_type
            record.version = backup_info.version
            record.assets_files_count = backup_info.assets_files_count
            record.assets_size_bytes = backup_info.assets_size_bytes
            if local_path is not None:
                record.local_path = str(local_path)

        if telegram_message and telegram_message.document:
            record.telegram_chat_id = telegram_message.chat.id
            record.telegram_thread_id = telegram_message.message_thread_id
            record.telegram_message_id = telegram_message.message_id
            record.telegram_file_id = telegram_message.document.file_id
            record.telegram_file_unique_id = telegram_message.document.file_unique_id

        await session.commit()


async def sync_backup_record_after_local_delete(
    service: BackupService,
    *,
    backup_filename: str,
    deleted_path: Optional[Path],
) -> None:
    async with service.session_pool() as session:
        result = await session.execute(
            select(BackupRecord).where(BackupRecord.filename == backup_filename)
        )
        records = list(result.scalars().all())
        changed = False

        for record in records:
            matches_deleted_path = (
                deleted_path is not None and record.local_path == str(deleted_path)
            )
            matches_fallback_path = (
                deleted_path is not None and deleted_path == (service.backup_dir / record.filename)
            )
            if record.local_path is None and not matches_fallback_path:
                continue
            if deleted_path is not None and not matches_deleted_path and not matches_fallback_path:
                continue

            record.local_path = None
            changed = True
            if not record.telegram_file_id:
                await session.delete(record)

        if changed:
            await session.commit()


async def download_telegram_backup_file(
    service: BackupService,
    *,
    telegram_file_id: str,
    destination: Path,
) -> None:
    file = await service.bot.get_file(telegram_file_id)
    if not file.file_path:
        raise ValueError(f"File path not found for telegram backup '{telegram_file_id}'")

    await service.bot.download_file(file.file_path, destination=destination)


async def import_backup_file(
    service: BackupService,
    *,
    source_file_path: Path,
    original_filename: Optional[str],
    created_by: Optional[int],
) -> tuple[bool, Optional[BackupInfo], str]:
    filename = build_imported_backup_filename(service, original_filename or source_file_path.name)
    target_path = service.backup_dir / filename

    shutil.copy2(source_file_path, target_path)

    try:
        metadata = await service._read_backup_metadata(target_path)
        if not metadata:
            raise ValueError("Backup metadata file is missing.")

        scope = normalize_backup_scope(metadata)
        includes_database = bool(metadata.get("includes_database", metadata.get("database")))
        includes_assets = bool(metadata.get("includes_assets", metadata.get("assets")))
        if not includes_database and not includes_assets:
            raise ValueError("Backup does not contain restorable data.")

        file_stats = target_path.stat()
        backup_info = metadata_to_backup_info(service, target_path, file_stats, metadata)
        backup_info.backup_scope = scope
        backup_info.includes_database = includes_database
        backup_info.includes_assets = includes_assets
        backup_info.created_by = created_by if created_by is not None else backup_info.created_by
        await service._upsert_backup_record(backup_info=backup_info, local_path=target_path)
        await service._cleanup_old_backups()
        return True, backup_info, ""
    except Exception as exc:
        if target_path.exists():
            target_path.unlink()
        return False, None, str(exc)


def build_imported_backup_filename(service: BackupService, original_filename: str) -> str:
    candidate = (
        Path(original_filename or "backup_import.tar.gz").name.strip()
        or "backup_import.tar.gz"
    )
    base_name = candidate.replace(" ", "_")
    timestamp_prefix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_name = f"backup_import_{timestamp_prefix}_{base_name}"
    target_path = service.backup_dir / target_name
    suffix = 1
    while target_path.exists():
        target_name = f"backup_import_{timestamp_prefix}_{suffix}_{base_name}"
        target_path = service.backup_dir / target_name
        suffix += 1
    return target_name
