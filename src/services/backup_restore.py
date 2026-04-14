from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import Locale

from .backup_models import DeferredRestoreUpdate
from .backup_restore_archive import _is_archive_backup as _is_archive_backup_impl
from .backup_restore_archive import _read_backup_metadata as _read_backup_metadata_impl
from .backup_restore_archive import (
    _restore_archive_assets_part as _restore_archive_assets_part_impl,
)
from .backup_restore_archive import (
    _restore_archive_database_part as _restore_archive_database_part_impl,
)
from .backup_restore_archive import _restore_assets_from_dir as _restore_assets_from_dir_impl
from .backup_restore_archive import _restore_from_archive as _restore_from_archive_impl
from .backup_restore_records import (
    _apply_deferred_restore_updates as _apply_deferred_restore_updates_impl,
)
from .backup_restore_records import (
    _apply_scalar_deferred_restore_update as _apply_scalar_deferred_restore_update_impl,
)
from .backup_restore_records import (
    _apply_scalar_restore_update as _apply_scalar_restore_update_impl,
)
from .backup_restore_records import _clear_database_tables as _clear_database_tables_impl
from .backup_restore_records import (
    _clear_database_tables_atomic as _clear_database_tables_atomic_impl,
)
from .backup_restore_records import (
    _extract_deferred_restore_fields as _extract_deferred_restore_fields_impl,
)
from .backup_restore_records import (
    _filter_deferred_restore_values as _filter_deferred_restore_values_impl,
)
from .backup_restore_records import (
    _find_existing_restore_record as _find_existing_restore_record_impl,
)
from .backup_restore_records import (
    _find_existing_user_restore_target as _find_existing_user_restore_target_impl,
)
from .backup_restore_records import (
    _merge_existing_user_record as _merge_existing_user_record_impl,
)
from .backup_restore_records import _restore_from_json as _restore_from_json_impl
from .backup_restore_records import _restore_table_records as _restore_table_records_impl

if TYPE_CHECKING:
    from .backup import BackupService
else:
    BackupService = Any


def _as_backup_service(instance: object) -> BackupService:
    return cast(BackupService, instance)


class BackupRestoreMixin:
    def _is_archive_backup(self, backup_path: Path) -> bool:
        return _is_archive_backup_impl(_as_backup_service(self), backup_path)

    async def _read_backup_metadata(self, backup_path: Path) -> dict[str, Any]:
        return await _read_backup_metadata_impl(_as_backup_service(self), backup_path)

    async def _restore_archive_database_part(
        self,
        *,
        temp_path: Path,
        metadata: dict[str, Any],
        clear_existing: bool,
        locale: Locale | None,
    ) -> tuple[bool, str]:
        return await _restore_archive_database_part_impl(
            _as_backup_service(self),
            temp_path=temp_path,
            metadata=metadata,
            clear_existing=clear_existing,
            locale=locale,
        )

    async def _restore_archive_assets_part(
        self,
        *,
        temp_path: Path,
        metadata: dict[str, Any],
        locale: Locale | None,
    ) -> tuple[bool, str]:
        return await _restore_archive_assets_part_impl(
            _as_backup_service(self),
            temp_path=temp_path,
            metadata=metadata,
            locale=locale,
        )

    async def _restore_from_archive(
        self,
        backup_path: Path,
        clear_existing: bool,
        locale: Locale | None = None,
    ) -> tuple[bool, str]:
        return await _restore_from_archive_impl(
            _as_backup_service(self),
            backup_path,
            clear_existing,
            locale=locale,
        )

    async def _restore_assets_from_dir(
        self,
        source_dir: Path,
        *,
        locale: Locale | None = None,
    ) -> str:
        return await _restore_assets_from_dir_impl(
            _as_backup_service(self),
            source_dir,
            locale=locale,
        )

    async def _restore_from_json(
        self,
        dump_path: Path,
        clear_existing: bool,
        locale: Locale | None = None,
    ) -> tuple[bool, str]:
        return await _restore_from_json_impl(
            _as_backup_service(self),
            dump_path,
            clear_existing,
            locale=locale,
        )

    async def _restore_table_records(
        self,
        session: AsyncSession,
        model: Any,
        table_name: str,
        records: list[dict[str, Any]],
        clear_existing: bool,
        deferred_updates: Optional[list[DeferredRestoreUpdate]] = None,
    ) -> int:
        return await _restore_table_records_impl(
            _as_backup_service(self),
            session,
            model,
            table_name,
            records,
            clear_existing,
            deferred_updates=deferred_updates,
        )

    async def _merge_existing_user_record(
        self,
        *,
        session: AsyncSession,
        processed_data: dict[str, Any],
        primary_key_col: Optional[str],
    ) -> bool:
        return await _merge_existing_user_record_impl(
            _as_backup_service(self),
            session=session,
            processed_data=processed_data,
            primary_key_col=primary_key_col,
        )

    async def _find_existing_user_restore_target(
        self,
        *,
        session: AsyncSession,
        processed_data: dict[str, Any],
        primary_key_col: Optional[str],
    ) -> tuple[str, Any] | None:
        return await _find_existing_user_restore_target_impl(
            _as_backup_service(self),
            session=session,
            processed_data=processed_data,
            primary_key_col=primary_key_col,
        )

    async def _find_existing_restore_record(
        self,
        *,
        session: AsyncSession,
        model: Any,
        processed_data: dict[str, Any],
        primary_key_col: Optional[str],
    ) -> Any:
        return await _find_existing_restore_record_impl(
            _as_backup_service(self),
            session=session,
            model=model,
            processed_data=processed_data,
            primary_key_col=primary_key_col,
        )

    def _extract_deferred_restore_fields(
        self,
        model: Any,
        processed_data: dict[str, Any],
    ) -> tuple[dict[str, Any], Optional[DeferredRestoreUpdate]]:
        return _extract_deferred_restore_fields_impl(
            _as_backup_service(self),
            model,
            processed_data,
        )

    async def _apply_deferred_restore_updates(
        self,
        session: AsyncSession,
        deferred_updates: list[DeferredRestoreUpdate],
        *,
        phase: str,
    ) -> None:
        await _apply_deferred_restore_updates_impl(
            _as_backup_service(self),
            session,
            deferred_updates,
            phase=phase,
        )

    async def _apply_scalar_deferred_restore_update(
        self,
        session: AsyncSession,
        deferred_update: DeferredRestoreUpdate,
        values: dict[str, Any],
    ) -> None:
        await _apply_scalar_deferred_restore_update_impl(
            _as_backup_service(self),
            session,
            deferred_update,
            values,
        )

    async def _apply_scalar_restore_update(
        self,
        *,
        session: AsyncSession,
        model: Any,
        lookup_field: str,
        lookup_value: Any,
        values: dict[str, Any],
    ) -> int | None:
        return await _apply_scalar_restore_update_impl(
            _as_backup_service(self),
            session=session,
            model=model,
            lookup_field=lookup_field,
            lookup_value=lookup_value,
            values=values,
        )

    async def _filter_deferred_restore_values(
        self,
        session: AsyncSession,
        deferred_update: DeferredRestoreUpdate,
    ) -> dict[str, Any]:
        return await _filter_deferred_restore_values_impl(
            _as_backup_service(self),
            session,
            deferred_update,
        )

    async def _clear_database_tables(self, session: AsyncSession) -> None:
        await _clear_database_tables_impl(_as_backup_service(self), session)

    async def _clear_database_tables_atomic(self, session: AsyncSession) -> None:
        await _clear_database_tables_atomic_impl(_as_backup_service(self), session)
