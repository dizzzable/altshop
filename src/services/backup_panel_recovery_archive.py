from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from loguru import logger
from remnawave.enums.users import TrafficLimitStrategy

from src.core.constants import IMPORTED_TAG
from src.core.enums import ArchivedPlanRenewMode, PlanAvailability, PlanType
from src.core.utils.formatters import format_limits_to_plan_type
from src.infrastructure.database.models.dto import PlanSnapshotDto, RemnaSubscriptionDto
from src.infrastructure.database.models.sql import (
    Plan,
    PlanDuration,
    PlanPrice,
    Promocode,
    Subscription,
    Transaction,
    User,
)

from .backup_models import RestoreArchiveDiagnostics

if TYPE_CHECKING:
    from .backup import BackupService


def _build_backup_integrity_report(
    service: BackupService,
    *,
    backup_data: dict[str, list[dict[str, Any]]],
    export_errors: dict[str, str],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    if export_errors:
        issues.append(
            {
                "code": "export_errors",
                "message": f"Export failed for {len(export_errors)} table(s)",
                "tables": sorted(export_errors),
            }
        )

    plan_rows = backup_data.get(Plan.__tablename__) or []
    duration_rows = backup_data.get(PlanDuration.__tablename__) or []
    price_rows = backup_data.get(PlanPrice.__tablename__) or []
    if not plan_rows and (duration_rows or price_rows):
        issues.append(
            {
                "code": "missing_plan_catalog",
                "message": "Plan rows are missing while plan durations or prices exist",
                "durations_count": len(duration_rows),
                "prices_count": len(price_rows),
            }
        )

    subscription_rows = backup_data.get(Subscription.__tablename__) or []
    subscription_ids = {
        int(row["id"])
        for row in subscription_rows
        if isinstance(row, dict) and row.get("id") is not None
    }
    user_rows = backup_data.get(User.__tablename__) or []
    current_refs = service._extract_current_subscription_refs(user_rows)
    missing_subscription_refs = [
        (telegram_id, subscription_id)
        for telegram_id, subscription_id in current_refs
        if subscription_id not in subscription_ids
    ]
    if missing_subscription_refs:
        issues.append(
            {
                "code": "missing_subscription_rows",
                "message": (
                    "Users reference current subscriptions that are absent "
                    "from the export"
                ),
                "users_count": len(missing_subscription_refs),
                "subscription_ids": sorted(
                    {
                        subscription_id
                        for _telegram_id, subscription_id in missing_subscription_refs
                    }
                ),
            }
        )

    return {
        "degraded": bool(issues),
        "issues": issues,
    }


def _extract_current_subscription_refs(
    _service: BackupService,
    user_rows: list[dict[str, Any]],
) -> list[tuple[int, int]]:
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


def _analyze_restore_archive(
    service: BackupService,
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
    current_refs = service._extract_current_subscription_refs(user_rows)
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


def _collect_plan_snapshots(  # noqa: C901
    service: BackupService,
    backup_data: dict[str, list[dict[str, Any]]],
    *,
    extra_snapshots: Optional[list[dict[str, Any]]] = None,
) -> dict[int, dict[str, Any]]:
    snapshots_by_id: dict[int, dict[str, Any]] = {}
    for table_name in (
        Subscription.__tablename__,
        Transaction.__tablename__,
        Promocode.__tablename__,
    ):
        for record in backup_data.get(table_name) or []:
            if not isinstance(record, dict):
                continue
            snapshot = service._parse_backup_snapshot(record.get("plan"))
            if not snapshot:
                continue
            raw_plan_id = snapshot.get("id")
            if not isinstance(raw_plan_id, int | str):
                continue
            try:
                plan_id = int(raw_plan_id)
            except (TypeError, ValueError):
                continue
            if plan_id <= 0:
                continue
            snapshots_by_id.setdefault(plan_id, snapshot)

    for snapshot in extra_snapshots or []:
        if not isinstance(snapshot, dict):
            continue
        raw_plan_id = snapshot.get("id")
        if not isinstance(raw_plan_id, int | str):
            continue
        try:
            plan_id = int(raw_plan_id)
        except (TypeError, ValueError):
            continue
        if plan_id <= 0:
            continue
        snapshots_by_id.setdefault(plan_id, snapshot)

    return snapshots_by_id


def _log_restore_archive_diagnostics(
    _service: BackupService,
    diagnostics: RestoreArchiveDiagnostics,
) -> None:
    if not diagnostics.archive_issue_messages:
        return

    for issue_message in diagnostics.archive_issue_messages:
        logger.warning(issue_message)


def _normalize_squad_values(_service: BackupService, values: list[UUID]) -> list[str]:
    return [str(value) for value in values]


def _match_plan_for_panel_subscription(
    _service: BackupService,
    *,
    remna_subscription: RemnaSubscriptionDto,
    plans: list[Plan],
) -> Optional[Plan]:
    matches = [
        plan
        for plan in plans
        if plan.tag == remna_subscription.tag
        and plan.traffic_limit == remna_subscription.traffic_limit
        and plan.device_limit == remna_subscription.device_limit
        and list(plan.internal_squads) == list(remna_subscription.internal_squads)
        and plan.external_squad == remna_subscription.external_squad
    ]
    if not matches:
        return None

    matches.sort(key=lambda plan: (plan.order_index, plan.id))
    return matches[0]


def _build_panel_subscription_snapshot(
    _service: BackupService,
    *,
    remna_subscription: RemnaSubscriptionDto,
    matched_plan: Optional[Plan],
) -> dict[str, Any]:
    snapshot = PlanSnapshotDto(
        id=matched_plan.id if matched_plan and matched_plan.id is not None else -1,
        name=matched_plan.name if matched_plan else IMPORTED_TAG,
        tag=matched_plan.tag if matched_plan else remna_subscription.tag,
        type=(
            matched_plan.type
            if matched_plan
            else format_limits_to_plan_type(
                remna_subscription.traffic_limit,
                remna_subscription.device_limit,
            )
        ),
        traffic_limit=(
            matched_plan.traffic_limit if matched_plan else remna_subscription.traffic_limit
        ),
        device_limit=matched_plan.device_limit if matched_plan else remna_subscription.device_limit,
        duration=-1,
        traffic_limit_strategy=(
            matched_plan.traffic_limit_strategy
            if matched_plan
            else remna_subscription.traffic_limit_strategy or TrafficLimitStrategy.NO_RESET
        ),
        internal_squads=(
            list(matched_plan.internal_squads)
            if matched_plan
            else list(remna_subscription.internal_squads)
        ),
        external_squad=(
            matched_plan.external_squad if matched_plan else remna_subscription.external_squad
        ),
    )
    return snapshot.model_dump(mode="json")


def _build_recovered_plan_record(
    service: BackupService,
    *,
    plan_id: int,
    order_index: int,
    snapshot: dict[str, Any] | None,
    snapshot_only: bool = False,
) -> dict[str, Any]:
    snapshot = snapshot or {}
    external_squad = snapshot.get("external_squad")
    if external_squad is not None and not isinstance(external_squad, list):
        external_squad = [external_squad]

    return {
        "id": plan_id,
        "order_index": order_index,
        "is_active": not snapshot_only,
        "is_archived": snapshot_only,
        "type": service._coerce_plan_enum_value(
            snapshot.get("type"),
            PlanType,
            PlanType.BOTH.value,
        ),
        "availability": PlanAvailability.ALL.value,
        "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
        "name": snapshot.get("name") or f"Recovered plan #{plan_id}",
        "description": None,
        "tag": snapshot.get("tag"),
        "traffic_limit": service._coerce_int_value(snapshot.get("traffic_limit"), 0),
        "device_limit": service._coerce_int_value(snapshot.get("device_limit"), 1),
        "traffic_limit_strategy": service._coerce_plan_enum_value(
            snapshot.get("traffic_limit_strategy"),
            TrafficLimitStrategy,
            TrafficLimitStrategy.NO_RESET.value,
        ),
        "replacement_plan_ids": [],
        "upgrade_to_plan_ids": [],
        "allowed_user_ids": [],
        "internal_squads": snapshot.get("internal_squads") or [],
        "external_squad": external_squad,
    }


def _recover_legacy_missing_plans(
    service: BackupService,
    backup_data: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    plans = list(backup_data.get(Plan.__tablename__) or [])
    durations = backup_data.get(PlanDuration.__tablename__) or []
    if not durations and not service._collect_plan_snapshots(backup_data):
        return backup_data, 0

    existing_plan_ids = {
        int(plan["id"])
        for plan in plans
        if isinstance(plan, dict) and isinstance(plan.get("id"), int | str)
    }
    referenced_plan_ids_set: set[int] = set()
    for duration in durations:
        if not isinstance(duration, dict):
            continue
        raw_plan_id = duration.get("plan_id")
        if not isinstance(raw_plan_id, int | str):
            continue
        try:
            plan_id = int(raw_plan_id)
        except ValueError:
            continue
        if plan_id > 0:
            referenced_plan_ids_set.add(plan_id)

    snapshots_by_id = service._collect_plan_snapshots(backup_data)
    referenced_plan_ids = sorted(referenced_plan_ids_set | set(snapshots_by_id))
    missing_plan_ids = [
        plan_id
        for plan_id in referenced_plan_ids
        if plan_id > 0 and plan_id not in existing_plan_ids
    ]
    if not missing_plan_ids:
        return backup_data, 0

    recovered_plans = [
        service._build_recovered_plan_record(
            plan_id=plan_id,
            order_index=len(plans) + index,
            snapshot=snapshots_by_id.get(plan_id),
            snapshot_only=plan_id not in referenced_plan_ids_set,
        )
        for index, plan_id in enumerate(missing_plan_ids, start=1)
    ]
    backup_data = dict(backup_data)
    backup_data[Plan.__tablename__] = [*plans, *recovered_plans]
    logger.warning(
        "Recovered {} missing plan records from a legacy backup using related snapshots",
        len(recovered_plans),
    )
    return backup_data, len(recovered_plans)
