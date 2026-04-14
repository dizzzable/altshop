from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.enums import Locale

from .backup_models import RestoreArchiveDiagnostics

if TYPE_CHECKING:
    from .backup import BackupService


def build_backup_create_error_message(
    service: BackupService,
    error: str,
    *,
    locale: Locale | None = None,
) -> str:
    if locale is None:
        return f"Backup creation failed: {error}"
    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    return i18n.get("msg-backup-error-create", error=error)


def build_backup_restore_error_message(
    service: BackupService,
    error: str,
    *,
    locale: Locale | None = None,
) -> str:
    summarized_error = summarize_backup_restore_error(error)
    if locale is None:
        return f"Restore failed: {summarized_error}"
    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    return i18n.get("msg-backup-error-restore", error=summarized_error)


def summarize_backup_restore_error(error: str) -> str:
    normalized = " ".join(str(error).split())
    if not normalized:
        return "unknown restore error"

    if "Circular dependency detected" in normalized:
        return "users and subscriptions could not be linked automatically"

    if "[SQL:" in normalized:
        normalized = normalized.split("[SQL:", 1)[0].strip()

    max_length = 320
    if len(normalized) <= max_length:
        return normalized

    return f"{normalized[: max_length - 3].rstrip()}..."


def build_backup_missing_file_message(
    service: BackupService,
    path: str,
    *,
    locale: Locale | None = None,
) -> str:
    if locale is None:
        return f"Backup file not found: {path}"
    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    return i18n.get("msg-backup-error-file-missing", path=path)


def build_backup_deleted_message(
    service: BackupService,
    backup_filename: str,
    *,
    locale: Locale | None = None,
) -> str:
    if locale is None:
        return f"Backup {backup_filename} deleted"
    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    return i18n.get("msg-backup-result-deleted", filename=backup_filename)


def build_backup_delete_error_message(
    service: BackupService,
    error: str,
    *,
    locale: Locale | None = None,
) -> str:
    if locale is None:
        return f"Backup deletion failed: {error}"
    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    return i18n.get("msg-backup-error-delete", error=error)


def build_restore_result_message(
    service: BackupService,
    *,
    locale: Locale | None,
    metadata: dict[str, object],
    restored_tables: int,
    restored_records: int,
    recovered_legacy_plans: int,
) -> str:
    message = (
        "Restore completed successfully!\n"
        f"Tables: {restored_tables}\n"
        f"Records: {restored_records:,}\n"
        f"Backup date: {metadata.get('timestamp', 'unknown')}"
    )

    if locale is None:
        if recovered_legacy_plans:
            message += f"\nRecovered plans: {recovered_legacy_plans}"
        return message

    i18n = service.translator_hub.get_translator_by_locale(locale=locale)
    message = "\n".join(
        [
            i18n.get("msg-backup-result-db-restored-title"),
            i18n.get("msg-backup-result-tables", count=restored_tables),
            i18n.get("msg-backup-result-records", count=f"{restored_records:,}"),
            i18n.get(
                "msg-backup-result-backup-date",
                value=metadata.get("timestamp", i18n.get("msg-backup-value-unknown")),
            ),
        ]
    )
    if recovered_legacy_plans:
        message = "\n".join(
            [
                message,
                i18n.get(
                    "msg-backup-result-recovered-plans",
                    count=recovered_legacy_plans,
                ),
            ]
        )
    return message


def append_restore_diagnostics_to_message(  # noqa: C901
    service: BackupService,
    *,
    message: str,
    locale: Locale | None,
    diagnostics: RestoreArchiveDiagnostics,
) -> str:
    extra_lines: list[str] = []

    if diagnostics.archive_issue_messages:
        issue_count = len(diagnostics.archive_issue_messages)
        if locale is None:
            extra_lines.append(f"Archive issues detected: {issue_count}")
        else:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            extra_lines.append(i18n.get("msg-backup-result-archive-issues", count=issue_count))

    if diagnostics.remnawave_users_recovered:
        if locale is None:
            extra_lines.append(
                f"Users synced from Remnawave: {diagnostics.remnawave_users_recovered}"
            )
        else:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            extra_lines.append(
                i18n.get(
                    "msg-backup-result-remnawave-users",
                    count=diagnostics.remnawave_users_recovered,
                )
            )

    if diagnostics.remnawave_subscriptions_recovered:
        if locale is None:
            extra_lines.append(
                "Subscriptions recovered from Remnawave: "
                f"{diagnostics.remnawave_subscriptions_recovered}"
            )
        else:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            extra_lines.append(
                i18n.get(
                    "msg-backup-result-remnawave-subscriptions",
                    count=diagnostics.remnawave_subscriptions_recovered,
                )
            )

    unrecovered_count = len(diagnostics.unrecovered_user_refs)
    if unrecovered_count:
        if locale is None:
            extra_lines.append(f"Unrecoverable user subscriptions: {unrecovered_count}")
        else:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            extra_lines.append(
                i18n.get(
                    "msg-backup-result-unrecoverable-subscriptions",
                    count=unrecovered_count,
                )
            )

    if diagnostics.panel_sync_errors:
        if locale is None:
            extra_lines.append(f"Remnawave sync errors: {len(diagnostics.panel_sync_errors)}")
        else:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            extra_lines.append(
                i18n.get(
                    "msg-backup-result-remnawave-sync-errors",
                    count=len(diagnostics.panel_sync_errors),
                )
            )

    if not extra_lines:
        return message

    return "\n".join([message, *extra_lines])
