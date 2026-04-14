from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from src.core.enums import BackupScope, Locale

from .backup_models import BackupInfo

if TYPE_CHECKING:
    from .backup import BackupService


def format_backup_file_size(file_size_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(file_size_bytes)
    unit = units[0]
    for candidate in units[1:]:
        if value < 1024:
            break
        value /= 1024
        unit = candidate

    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def format_backup_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value[:19].replace("T", " ")


def build_backup_created_summary(
    service: BackupService,
    *,
    backup_info: BackupInfo,
    locale: Locale | None,
) -> dict[str, Any]:
    return {
        "scope_label": format_scope_label_localized(service, backup_info.backup_scope, locale),
        "file_size": format_backup_file_size(backup_info.file_size_bytes),
        "timestamp": format_backup_timestamp(backup_info.timestamp),
        "integrity_warning": bool(backup_info.error),
    }


def format_scope_label(scope: BackupScope) -> str:
    mapping = {
        BackupScope.DB: "Database only",
        BackupScope.ASSETS: "Assets only",
        BackupScope.FULL: "Full backup",
    }
    return mapping[scope]


def format_scope_label_localized(
    service: BackupService,
    scope: BackupScope,
    locale: Locale | None,
) -> str:
    if locale is None:
        return format_scope_label(scope)

    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    mapping = {
        BackupScope.DB: i18n.get("msg-backup-scope-db-label"),
        BackupScope.ASSETS: i18n.get("msg-backup-scope-assets-label"),
        BackupScope.FULL: i18n.get("msg-backup-scope-full-label"),
    }
    return mapping[scope]


def build_backup_result_message(
    service: BackupService,
    *,
    backup_info: BackupInfo,
    locale: Locale | None = None,
) -> str:
    summary = build_backup_created_summary(service, backup_info=backup_info, locale=locale)
    if locale is not None:
        i18n = service.translator_hub.get_translator_by_locale(locale=locale)
        lines = [
            i18n.get("msg-backup-result-created-title"),
            i18n.get("msg-backup-result-scope", scope=summary["scope_label"]),
            i18n.get("msg-backup-result-file", value=backup_info.filename),
            i18n.get("msg-backup-result-size", value=summary["file_size"]),
            i18n.get("msg-backup-result-created-at", value=summary["timestamp"]),
        ]
        if backup_info.includes_database:
            lines.append(
                i18n.get(
                    "msg-backup-result-db-summary",
                    tables=backup_info.tables_count,
                    records=f"{backup_info.total_records:,}",
                )
            )
        if backup_info.includes_assets:
            lines.append(
                i18n.get(
                    "msg-backup-result-assets-summary",
                    count=backup_info.assets_files_count,
                )
            )
        if summary["integrity_warning"]:
            lines.append(i18n.get("msg-backup-result-degraded"))
        return "\n".join(lines)

    lines = [
        "Backup created successfully!",
        f"Scope: {summary['scope_label']}",
        f"File: {backup_info.filename}",
        f"Size: {summary['file_size']}",
        f"Created: {summary['timestamp']}",
    ]
    if backup_info.includes_database:
        lines.append(
            "Database: "
            f"{backup_info.tables_count} tables / {backup_info.total_records:,} records"
        )
    if backup_info.includes_assets:
        lines.append(f"Assets: {backup_info.assets_files_count} files")
    if summary["integrity_warning"]:
        lines.append("Warning: backup marked as degraded")
    return "\n".join(lines)


def build_backup_caption(
    service: BackupService,
    *,
    backup_info: BackupInfo,
    locale: Locale | None = None,
) -> str:
    summary = build_backup_created_summary(service, backup_info=backup_info, locale=locale)
    if locale is not None:
        i18n = service.translator_hub.get_translator_by_locale(locale=locale)
        lines = [
            i18n.get("msg-backup-caption-created-title"),
            i18n.get("msg-backup-caption-scope", scope=summary["scope_label"]),
            i18n.get("msg-backup-caption-size", value=summary["file_size"]),
            i18n.get("msg-backup-caption-created-at", value=summary["timestamp"]),
        ]
        if backup_info.includes_database:
            lines.append(
                i18n.get(
                    "msg-backup-caption-db-summary",
                    tables=backup_info.tables_count,
                    records=f"{backup_info.total_records:,}",
                )
            )
        if backup_info.includes_assets:
            lines.append(
                i18n.get(
                    "msg-backup-caption-assets-summary",
                    count=backup_info.assets_files_count,
                )
            )
        if summary["integrity_warning"]:
            lines.append(i18n.get("msg-backup-caption-degraded"))
        return "\n".join(lines)

    lines = [
        "Backup created",
        f"Scope: {summary['scope_label']}",
        f"Size: {summary['file_size']}",
        f"Created: {summary['timestamp']}",
    ]
    if backup_info.includes_database:
        lines.append(
            f"DB: {backup_info.tables_count} tables / {backup_info.total_records:,} records"
        )
    if backup_info.includes_assets:
        lines.append(f"Assets: {backup_info.assets_files_count} files")
    if summary["integrity_warning"]:
        lines.append("Degraded archive")
    return "\n".join(lines)


def get_backup_integrity_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    integrity = metadata.get("integrity")
    if isinstance(integrity, dict):
        return integrity
    return {"degraded": False, "issues": []}


def summarize_backup_integrity(metadata: dict[str, Any]) -> Optional[str]:
    integrity = get_backup_integrity_from_metadata(metadata)
    issues = integrity.get("issues")
    if not integrity.get("degraded") or not isinstance(issues, list) or not issues:
        return None

    first_issue = issues[0]
    first_message = first_issue.get("message") if isinstance(first_issue, dict) else None
    if isinstance(first_message, str) and first_message.strip():
        if len(issues) == 1:
            return f"Degraded backup: {first_message}"
        return f"Degraded backup: {first_message} (+{len(issues) - 1} more)"

    return f"Degraded backup: {len(issues)} issue(s)"
