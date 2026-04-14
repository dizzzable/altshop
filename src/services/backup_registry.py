from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from aiogram.types import Message

from src.core.enums import BackupScope, BackupSourceKind
from src.infrastructure.database.models.sql import BackupRecord

from .backup_models import BackupInfo
from .backup_registry_metadata import (
    backup_sort_timestamp as _backup_sort_timestamp_impl,
)
from .backup_registry_metadata import (
    metadata_to_backup_info as _metadata_to_backup_info_impl,
)
from .backup_registry_metadata import (
    normalize_backup_scope as _normalize_backup_scope_impl,
)
from .backup_registry_metadata import (
    parse_backup_timestamp as _parse_backup_timestamp_impl,
)
from .backup_registry_metadata import (
    record_to_backup_info as _record_to_backup_info_impl,
)
from .backup_registry_metadata import (
    resolve_backup_source_kind as _resolve_backup_source_kind_impl,
)
from .backup_registry_metadata import (
    resolve_registry_local_path as _resolve_registry_local_path_impl,
)
from .backup_registry_storage import (
    build_imported_backup_filename as _build_imported_backup_filename_impl,
)
from .backup_registry_storage import (
    download_telegram_backup_file as _download_telegram_backup_file_impl,
)
from .backup_registry_storage import import_backup_file as _import_backup_file_impl
from .backup_registry_storage import (
    list_registered_backup_infos as _list_registered_backup_infos_impl,
)
from .backup_registry_storage import (
    sync_backup_record_after_local_delete as _sync_backup_record_after_local_delete_impl,
)
from .backup_registry_storage import (
    upsert_backup_record as _upsert_backup_record_impl,
)


def _as_backup_service(instance: object) -> Any:
    return cast(Any, instance)


class BackupRegistryMixin:
    def _normalize_backup_scope(self, metadata: dict[str, Any]) -> BackupScope:
        return _normalize_backup_scope_impl(metadata)

    def _metadata_to_backup_info(
        self,
        backup_file: Path,
        file_stats: Any,
        metadata: dict[str, Any],
    ) -> BackupInfo:
        return _metadata_to_backup_info_impl(
            _as_backup_service(self),
            backup_file,
            file_stats,
            metadata,
        )

    def _parse_backup_timestamp(self, value: object) -> Optional[datetime]:
        return _parse_backup_timestamp_impl(value)

    def _backup_sort_timestamp(self, value: object) -> float:
        return _backup_sort_timestamp_impl(value)

    def _resolve_backup_source_kind(
        self,
        *,
        has_local_copy: bool,
        has_telegram_copy: bool,
    ) -> BackupSourceKind:
        return _resolve_backup_source_kind_impl(
            has_local_copy=has_local_copy,
            has_telegram_copy=has_telegram_copy,
        )

    def _resolve_registry_local_path(self, record: BackupRecord) -> Optional[Path]:
        return _resolve_registry_local_path_impl(_as_backup_service(self), record)

    def _record_to_backup_info(self, record: BackupRecord) -> Optional[BackupInfo]:
        return _record_to_backup_info_impl(_as_backup_service(self), record)

    async def _list_registered_backup_infos(self) -> list[BackupInfo]:
        return await _list_registered_backup_infos_impl(_as_backup_service(self))

    async def _upsert_backup_record(
        self,
        *,
        backup_info: BackupInfo,
        local_path: Optional[Path],
        telegram_message: Optional[Message] = None,
    ) -> None:
        await _upsert_backup_record_impl(
            _as_backup_service(self),
            backup_info=backup_info,
            local_path=local_path,
            telegram_message=telegram_message,
        )

    async def _sync_backup_record_after_local_delete(
        self,
        *,
        backup_filename: str,
        deleted_path: Optional[Path],
    ) -> None:
        await _sync_backup_record_after_local_delete_impl(
            _as_backup_service(self),
            backup_filename=backup_filename,
            deleted_path=deleted_path,
        )

    async def _download_telegram_backup_file(
        self,
        *,
        telegram_file_id: str,
        destination: Path,
    ) -> None:
        await _download_telegram_backup_file_impl(
            _as_backup_service(self),
            telegram_file_id=telegram_file_id,
            destination=destination,
        )

    async def import_backup_file(
        self,
        *,
        source_file_path: Path,
        original_filename: Optional[str],
        created_by: Optional[int],
    ) -> tuple[bool, Optional[BackupInfo], str]:
        return await _import_backup_file_impl(
            _as_backup_service(self),
            source_file_path=source_file_path,
            original_filename=original_filename,
            created_by=created_by,
        )

    def _build_imported_backup_filename(self, original_filename: str) -> str:
        return _build_imported_backup_filename_impl(_as_backup_service(self), original_filename)
