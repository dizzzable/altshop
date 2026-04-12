from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.core.enums import BackupScope, BackupSourceKind


@dataclass
class BackupMetadata:
    timestamp: str
    version: str = "3.3"
    database_type: str = "postgresql"
    backup_scope: BackupScope = BackupScope.FULL
    includes_database: bool = True
    includes_assets: bool = False
    assets_root: Optional[str] = None
    tables_count: int = 0
    total_records: int = 0
    compressed: bool = True
    file_size_bytes: int = 0
    created_by: Optional[int] = None


@dataclass
class BackupInfo:
    selection_key: str
    filename: str
    filepath: str
    timestamp: str
    tables_count: int
    total_records: int
    compressed: bool
    file_size_bytes: int
    file_size_mb: float
    created_by: Optional[int]
    database_type: str
    version: str
    backup_scope: BackupScope = BackupScope.FULL
    includes_database: bool = True
    includes_assets: bool = False
    assets_root: Optional[str] = None
    assets_files_count: int = 0
    assets_size_bytes: int = 0
    source_kind: BackupSourceKind = BackupSourceKind.LOCAL
    has_local_copy: bool = True
    has_telegram_copy: bool = False
    telegram_file_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DeferredRestoreUpdate:
    model: Any
    lookup_field: str
    lookup_value: Any
    values: dict[str, Any]
    phase: str = "default"
    apply_as_scalar_update: bool = False


@dataclass
class RestoreArchiveDiagnostics:
    archive_issue_messages: list[str] = field(default_factory=list)
    current_subscription_refs: list[tuple[int, int]] = field(default_factory=list)
    missing_archive_subscription_refs: list[tuple[int, int]] = field(default_factory=list)
    panel_sync_candidate_ids: list[int] = field(default_factory=list)
    remnawave_users_recovered: int = 0
    remnawave_subscriptions_recovered: int = 0
    unrecovered_user_refs: list[tuple[int, int]] = field(default_factory=list)
    panel_sync_errors: list[tuple[int, str]] = field(default_factory=list)

    @property
    def has_partial_recovery(self) -> bool:
        return bool(
            self.archive_issue_messages
            or self.unrecovered_user_refs
            or self.panel_sync_errors
            or self.remnawave_subscriptions_recovered
        )
