# mypy: ignore-errors
# ruff: noqa: E501

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from aiogram.types import Message
from sqlalchemy import select

from src.core.enums import BackupScope, BackupSourceKind
from src.infrastructure.database.models.sql import BackupRecord

from .backup_models import BackupInfo


class BackupRegistryMixin:
    def _normalize_backup_scope(self, metadata: dict[str, Any]) -> BackupScope:
        scope_value = str(metadata.get("backup_scope", BackupScope.FULL.value)).upper()
        try:
            scope = BackupScope(scope_value)
        except ValueError:
            scope = BackupScope.FULL

        if not metadata.get("includes_database") and metadata.get("database"):
            return BackupScope.DB if not metadata.get("includes_assets") else BackupScope.FULL
        return scope

    def _metadata_to_backup_info(
        self,
        backup_file: Path,
        file_stats: Any,
        metadata: dict[str, Any],
    ) -> BackupInfo:
        scope = self._normalize_backup_scope(metadata)
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
            compressed=self._is_archive_backup(backup_file),
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
            error=self._summarize_backup_integrity(metadata),
        )

    def _parse_backup_timestamp(self, value: object) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _backup_sort_timestamp(self, value: object) -> float:
        parsed = self._parse_backup_timestamp(value)
        if parsed is None:
            return 0.0
        return parsed.timestamp()

    def _resolve_backup_source_kind(
        self,
        *,
        has_local_copy: bool,
        has_telegram_copy: bool,
    ) -> BackupSourceKind:
        if has_local_copy and has_telegram_copy:
            return BackupSourceKind.LOCAL_AND_TELEGRAM
        if has_telegram_copy:
            return BackupSourceKind.TELEGRAM
        return BackupSourceKind.LOCAL

    def _resolve_registry_local_path(self, record: BackupRecord) -> Optional[Path]:
        if record.local_path:
            candidate = Path(record.local_path)
            if candidate.exists():
                return candidate

        fallback = self.backup_dir / record.filename
        if fallback.exists():
            return fallback

        return None

    def _record_to_backup_info(self, record: BackupRecord) -> Optional[BackupInfo]:
        local_path = self._resolve_registry_local_path(record)
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
            source_kind=self._resolve_backup_source_kind(
                has_local_copy=has_local_copy,
                has_telegram_copy=has_telegram_copy,
            ),
            has_local_copy=has_local_copy,
            has_telegram_copy=has_telegram_copy,
            telegram_file_id=record.telegram_file_id,
        )

    async def _list_registered_backup_infos(self) -> List[BackupInfo]:
        async with self.session_pool() as session:
            result = await session.execute(
                select(BackupRecord).order_by(
                    BackupRecord.backup_timestamp.desc().nullslast(),
                    BackupRecord.created_at.desc(),
                    BackupRecord.id.desc(),
                )
            )
            records = list(result.scalars().all())

        backups: List[BackupInfo] = []
        for record in records:
            backup_info = self._record_to_backup_info(record)
            if backup_info is not None:
                if backup_info.has_local_copy and backup_info.filepath:
                    metadata = await self._read_backup_metadata(Path(backup_info.filepath))
                    backup_info.error = self._summarize_backup_integrity(metadata)
                backups.append(backup_info)
        return backups

    async def _upsert_backup_record(
        self,
        *,
        backup_info: BackupInfo,
        local_path: Optional[Path],
        telegram_message: Optional[Message] = None,
    ) -> None:
        async with self.session_pool() as session:
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
                    backup_timestamp=self._parse_backup_timestamp(backup_info.timestamp),
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
                record.backup_timestamp = self._parse_backup_timestamp(backup_info.timestamp)
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

    async def _sync_backup_record_after_local_delete(
        self,
        *,
        backup_filename: str,
        deleted_path: Optional[Path],
    ) -> None:
        async with self.session_pool() as session:
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
                    deleted_path is not None and deleted_path == (self.backup_dir / record.filename)
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

    async def _download_telegram_backup_file(
        self,
        *,
        telegram_file_id: str,
        destination: Path,
    ) -> None:
        file = await self.bot.get_file(telegram_file_id)
        if not file.file_path:
            raise ValueError(f"File path not found for telegram backup '{telegram_file_id}'")

        await self.bot.download_file(file.file_path, destination=destination)

    async def import_backup_file(
        self,
        *,
        source_file_path: Path,
        original_filename: Optional[str],
        created_by: Optional[int],
    ) -> tuple[bool, Optional[BackupInfo], str]:
        filename = self._build_imported_backup_filename(original_filename or source_file_path.name)
        target_path = self.backup_dir / filename

        shutil.copy2(source_file_path, target_path)

        try:
            metadata = await self._read_backup_metadata(target_path)
            if not metadata:
                raise ValueError("Backup metadata file is missing.")

            scope = self._normalize_backup_scope(metadata)
            includes_database = bool(metadata.get("includes_database", metadata.get("database")))
            includes_assets = bool(metadata.get("includes_assets", metadata.get("assets")))
            if not includes_database and not includes_assets:
                raise ValueError("Backup does not contain restorable data.")

            file_stats = target_path.stat()
            backup_info = self._metadata_to_backup_info(target_path, file_stats, metadata)
            backup_info.backup_scope = scope
            backup_info.includes_database = includes_database
            backup_info.includes_assets = includes_assets
            backup_info.created_by = (
                created_by if created_by is not None else backup_info.created_by
            )
            await self._upsert_backup_record(backup_info=backup_info, local_path=target_path)
            await self._cleanup_old_backups()
            return True, backup_info, ""
        except Exception as exc:
            if target_path.exists():
                target_path.unlink()
            return False, None, str(exc)

    def _build_imported_backup_filename(self, original_filename: str) -> str:
        candidate = (
            Path(original_filename or "backup_import.tar.gz").name.strip()
            or "backup_import.tar.gz"
        )
        base_name = candidate.replace(" ", "_")
        timestamp_prefix = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_name = f"backup_import_{timestamp_prefix}_{base_name}"
        target_path = self.backup_dir / target_name
        suffix = 1
        while target_path.exists():
            target_name = f"backup_import_{timestamp_prefix}_{suffix}_{base_name}"
            target_path = self.backup_dir / target_name
            suffix += 1
        return target_name
