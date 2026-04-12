# mypy: ignore-errors

from __future__ import annotations

from typing import Any, Optional

from src.core.enums import BackupScope, Locale

from .backup_models import RestoreArchiveDiagnostics


class BackupFormattingMixin:
    @staticmethod
    def _format_scope_label(scope: BackupScope) -> str:
        mapping = {
            BackupScope.DB: "Database only",
            BackupScope.ASSETS: "Assets only",
            BackupScope.FULL: "Full backup",
        }
        return mapping[scope]

    def _format_scope_label_localized(self, scope: BackupScope, locale: Locale | None) -> str:
        if locale is None:
            return self._format_scope_label(scope)

        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        mapping = {
            BackupScope.DB: i18n.get("msg-backup-scope-db-label"),
            BackupScope.ASSETS: i18n.get("msg-backup-scope-assets-label"),
            BackupScope.FULL: i18n.get("msg-backup-scope-full-label"),
        }
        return mapping[scope]

    def _build_backup_result_message(
        self,
        *,
        scope: BackupScope,
        filename: str,
        size_mb: float,
        overview: dict[str, Any],
        includes_database: bool,
        assets_info: Optional[dict[str, Any]],
        locale: Locale | None = None,
    ) -> str:
        if locale is not None:
            i18n = self.translator_hub.get_translator_by_locale(locale=locale)
            lines = [
                i18n.get("msg-backup-result-created-title"),
                i18n.get(
                    "msg-backup-result-scope",
                    scope=self._format_scope_label_localized(scope, locale),
                ),
                i18n.get("msg-backup-result-file", value=filename),
                i18n.get("msg-backup-result-size", value=f"{size_mb:.2f} MB"),
            ]
            if includes_database:
                lines.append(
                    i18n.get("msg-backup-result-tables", count=overview.get("tables_count", 0))
                )
                lines.append(
                    i18n.get(
                        "msg-backup-result-records",
                        count=f"{overview.get('total_records', 0):,}",
                    )
                )
            if assets_info is not None:
                lines.append(
                    i18n.get(
                        "msg-backup-content-assets-files",
                        count=int(assets_info.get("files_count", 0) or 0),
                    )
                )
            integrity = self._get_backup_integrity_from_metadata(overview)
            if integrity.get("degraded"):
                lines.append(i18n.get("msg-backup-result-degraded"))
            return "\n".join(lines)

        lines = [
            "Backup created successfully!",
            f"Scope: {self._format_scope_label(scope)}",
            f"File: {filename}",
            f"Size: {size_mb:.2f} MB",
        ]
        if includes_database:
            lines.append(f"Tables: {overview.get('tables_count', 0)}")
            lines.append(f"Records: {overview.get('total_records', 0):,}")
        if assets_info is not None:
            lines.append(f"Assets files: {assets_info.get('files_count', 0)}")
        integrity = self._get_backup_integrity_from_metadata(overview)
        if integrity.get("degraded"):
            lines.append("Warning: backup marked as degraded")
        return "\n".join(lines)

    @staticmethod
    def _get_backup_integrity_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        integrity = metadata.get("integrity")
        if isinstance(integrity, dict):
            return integrity
        return {"degraded": False, "issues": []}

    def _summarize_backup_integrity(self, metadata: dict[str, Any]) -> Optional[str]:
        integrity = self._get_backup_integrity_from_metadata(metadata)
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

    def _build_backup_create_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup creation failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-create", error=error)

    def _build_backup_restore_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        error = self._summarize_backup_restore_error(error)
        if locale is None:
            return f"Restore failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-restore", error=error)

    @staticmethod
    def _summarize_backup_restore_error(error: str) -> str:
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

    def _build_backup_missing_file_message(
        self,
        path: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup file not found: {path}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-file-missing", path=path)

    def _build_backup_deleted_message(
        self,
        backup_filename: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup {backup_filename} deleted"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-result-deleted", filename=backup_filename)

    def _build_backup_delete_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup deletion failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-delete", error=error)

    def _build_restore_result_message(
        self,
        *,
        locale: Locale | None,
        metadata: dict[str, Any],
        restored_tables: int,
        restored_records: int,
        recovered_legacy_plans: int,
    ) -> str:
        message = (
            f"✅ Восстановление завершено!\n"
            f"📊 Таблиц: {restored_tables}\n"
            f"📈 Записей: {restored_records:,}\n"
            f"🗓 Дата бэкапа: {metadata.get('timestamp', 'неизвестно')}"
        )

        if locale is None:
            if recovered_legacy_plans:
                message += f"\nRecovered plans: {recovered_legacy_plans}"
            return message

        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
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

    def _append_restore_diagnostics_to_message(  # noqa: C901
        self,
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
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(i18n.get("msg-backup-result-archive-issues", count=issue_count))

        if diagnostics.remnawave_users_recovered:
            if locale is None:
                extra_lines.append(
                    f"Users synced from Remnawave: {diagnostics.remnawave_users_recovered}"
                )
            else:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
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
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
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
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
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
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(
                    i18n.get(
                        "msg-backup-result-remnawave-sync-errors",
                        count=len(diagnostics.panel_sync_errors),
                    )
                )

        if not extra_lines:
            return message

        return "\n".join([message, *extra_lines])
