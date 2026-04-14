from __future__ import annotations

from typing import Any, Optional, cast

from src.core.enums import BackupScope, Locale

from .backup_formatting_render import (
    build_backup_caption as _build_backup_caption_impl,
)
from .backup_formatting_render import (
    build_backup_created_summary as _build_backup_created_summary_impl,
)
from .backup_formatting_render import (
    build_backup_result_message as _build_backup_result_message_impl,
)
from .backup_formatting_render import (
    format_backup_file_size as _format_backup_file_size_impl,
)
from .backup_formatting_render import (
    format_backup_timestamp as _format_backup_timestamp_impl,
)
from .backup_formatting_render import (
    format_scope_label as _format_scope_label_impl,
)
from .backup_formatting_render import (
    format_scope_label_localized as _format_scope_label_localized_impl,
)
from .backup_formatting_render import (
    get_backup_integrity_from_metadata as _get_backup_integrity_from_metadata_impl,
)
from .backup_formatting_render import (
    summarize_backup_integrity as _summarize_backup_integrity_impl,
)
from .backup_formatting_restore import (
    append_restore_diagnostics_to_message as _append_restore_diagnostics_to_message_impl,
)
from .backup_formatting_restore import (
    build_backup_create_error_message as _build_backup_create_error_message_impl,
)
from .backup_formatting_restore import (
    build_backup_delete_error_message as _build_backup_delete_error_message_impl,
)
from .backup_formatting_restore import (
    build_backup_deleted_message as _build_backup_deleted_message_impl,
)
from .backup_formatting_restore import (
    build_backup_missing_file_message as _build_backup_missing_file_message_impl,
)
from .backup_formatting_restore import (
    build_backup_restore_error_message as _build_backup_restore_error_message_impl,
)
from .backup_formatting_restore import (
    build_restore_result_message as _build_restore_result_message_impl,
)
from .backup_formatting_restore import (
    summarize_backup_restore_error as _summarize_backup_restore_error_impl,
)
from .backup_models import BackupInfo, RestoreArchiveDiagnostics


def _as_backup_service(instance: object) -> Any:
    return cast(Any, instance)


class BackupFormattingMixin:
    @staticmethod
    def _format_backup_file_size(file_size_bytes: int) -> str:
        return _format_backup_file_size_impl(file_size_bytes)

    @staticmethod
    def _format_backup_timestamp(value: str) -> str:
        return _format_backup_timestamp_impl(value)

    def _build_backup_created_summary(
        self,
        *,
        backup_info: BackupInfo,
        locale: Locale | None,
    ) -> dict[str, Any]:
        return _build_backup_created_summary_impl(
            _as_backup_service(self),
            backup_info=backup_info,
            locale=locale,
        )

    @staticmethod
    def _format_scope_label(scope: BackupScope) -> str:
        return _format_scope_label_impl(scope)

    def _format_scope_label_localized(self, scope: BackupScope, locale: Locale | None) -> str:
        return _format_scope_label_localized_impl(
            _as_backup_service(self),
            scope,
            locale,
        )

    def _build_backup_result_message(
        self,
        *,
        backup_info: BackupInfo,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_result_message_impl(
            _as_backup_service(self),
            backup_info=backup_info,
            locale=locale,
        )

    def _build_backup_caption(
        self,
        *,
        backup_info: BackupInfo,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_caption_impl(
            _as_backup_service(self),
            backup_info=backup_info,
            locale=locale,
        )

    @staticmethod
    def _get_backup_integrity_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        return _get_backup_integrity_from_metadata_impl(metadata)

    def _summarize_backup_integrity(self, metadata: dict[str, Any]) -> Optional[str]:
        return _summarize_backup_integrity_impl(metadata)

    def _build_backup_create_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_create_error_message_impl(
            _as_backup_service(self),
            error,
            locale=locale,
        )

    def _build_backup_restore_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_restore_error_message_impl(
            _as_backup_service(self),
            error,
            locale=locale,
        )

    @staticmethod
    def _summarize_backup_restore_error(error: str) -> str:
        return _summarize_backup_restore_error_impl(error)

    def _build_backup_missing_file_message(
        self,
        path: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_missing_file_message_impl(
            _as_backup_service(self),
            path,
            locale=locale,
        )

    def _build_backup_deleted_message(
        self,
        backup_filename: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_deleted_message_impl(
            _as_backup_service(self),
            backup_filename,
            locale=locale,
        )

    def _build_backup_delete_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        return _build_backup_delete_error_message_impl(
            _as_backup_service(self),
            error,
            locale=locale,
        )

    def _build_restore_result_message(
        self,
        *,
        locale: Locale | None,
        metadata: dict[str, Any],
        restored_tables: int,
        restored_records: int,
        recovered_legacy_plans: int,
    ) -> str:
        return _build_restore_result_message_impl(
            _as_backup_service(self),
            locale=locale,
            metadata=metadata,
            restored_tables=restored_tables,
            restored_records=restored_records,
            recovered_legacy_plans=recovered_legacy_plans,
        )

    def _append_restore_diagnostics_to_message(
        self,
        *,
        message: str,
        locale: Locale | None,
        diagnostics: RestoreArchiveDiagnostics,
    ) -> str:
        return _append_restore_diagnostics_to_message_impl(
            _as_backup_service(self),
            message=message,
            locale=locale,
            diagnostics=diagnostics,
        )
