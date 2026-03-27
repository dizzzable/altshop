from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.infrastructure.database.models.sql import Plan, PlanDuration, PlanPrice, Subscription, User


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


def extract_current_subscription_refs(user_rows: list[dict[str, Any]]) -> list[tuple[int, int]]:
    refs: list[tuple[int, int]] = []
    for row in user_rows:
        if not isinstance(row, dict):
            continue
        telegram_id = row.get("telegram_id")
        subscription_id = row.get("current_subscription_id")
        if telegram_id is None or subscription_id is None:
            continue
        try:
            refs.append((int(telegram_id), int(subscription_id)))
        except (TypeError, ValueError):
            continue
    return refs


def analyze_restore_archive(
    backup_data: dict[str, list[dict[str, Any]]],
) -> RestoreArchiveDiagnostics:
    diagnostics = RestoreArchiveDiagnostics()
    plan_rows = backup_data.get(Plan.__tablename__) or []
    duration_rows = backup_data.get(PlanDuration.__tablename__) or []
    price_rows = backup_data.get(PlanPrice.__tablename__) or []
    if not plan_rows and (duration_rows or price_rows):
        diagnostics.archive_issue_messages.append(
            "Archive is missing plan rows and requires legacy plan recovery"
        )

    user_rows = backup_data.get(User.__tablename__) or []
    current_refs = extract_current_subscription_refs(user_rows)
    diagnostics.current_subscription_refs = current_refs
    subscription_ids = {
        int(row["id"])
        for row in (backup_data.get(Subscription.__tablename__) or [])
        if isinstance(row, dict) and row.get("id") is not None
    }
    diagnostics.missing_archive_subscription_refs = [
        (telegram_id, subscription_id)
        for telegram_id, subscription_id in current_refs
        if subscription_id not in subscription_ids
    ]
    diagnostics.panel_sync_candidate_ids = sorted(
        {
            telegram_id
            for telegram_id, _subscription_id in diagnostics.missing_archive_subscription_refs
        }
    )
    if diagnostics.missing_archive_subscription_refs:
        diagnostics.archive_issue_messages.append(
            "Archive is missing subscription rows referenced by users.current_subscription_id"
        )

    return diagnostics


def log_restore_archive_diagnostics(diagnostics: RestoreArchiveDiagnostics) -> None:
    if not diagnostics.archive_issue_messages:
        return

    logger.warning(
        (
            "Legacy archive diagnostics: issues={}, "
            "users_with_missing_subscriptions={}, "
            "missing_subscription_refs={}"
        ),
        diagnostics.archive_issue_messages,
        len(diagnostics.panel_sync_candidate_ids),
        len(diagnostics.missing_archive_subscription_refs),
    )
