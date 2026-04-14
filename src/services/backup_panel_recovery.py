from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast
from uuid import UUID

from remnawave.models import UserResponseDto
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto import RemnaSubscriptionDto
from src.infrastructure.database.models.sql import Plan, Subscription

from .backup_models import RestoreArchiveDiagnostics
from .backup_panel_recovery_archive import (
    _analyze_restore_archive as _analyze_restore_archive_impl,
)
from .backup_panel_recovery_archive import (
    _build_backup_integrity_report as _build_backup_integrity_report_impl,
)
from .backup_panel_recovery_archive import (
    _build_panel_subscription_snapshot as _build_panel_subscription_snapshot_impl,
)
from .backup_panel_recovery_archive import (
    _build_recovered_plan_record as _build_recovered_plan_record_impl,
)
from .backup_panel_recovery_archive import (
    _collect_plan_snapshots as _collect_plan_snapshots_impl,
)
from .backup_panel_recovery_archive import (
    _extract_current_subscription_refs as _extract_current_subscription_refs_impl,
)
from .backup_panel_recovery_archive import (
    _log_restore_archive_diagnostics as _log_restore_archive_diagnostics_impl,
)
from .backup_panel_recovery_archive import (
    _match_plan_for_panel_subscription as _match_plan_for_panel_subscription_impl,
)
from .backup_panel_recovery_archive import (
    _normalize_squad_values as _normalize_squad_values_impl,
)
from .backup_panel_recovery_archive import (
    _recover_legacy_missing_plans as _recover_legacy_missing_plans_impl,
)
from .backup_panel_recovery_sync import (
    _fetch_panel_users_by_telegram_id as _fetch_panel_users_by_telegram_id_impl,
)
from .backup_panel_recovery_sync import (
    _recover_missing_subscriptions_from_panel as _recover_missing_subscriptions_from_panel_impl,
)
from .backup_panel_recovery_sync import (
    _resolve_effective_subscription_status as _resolve_effective_subscription_status_impl,
)
from .backup_panel_recovery_sync import (
    _select_current_subscription_id as _select_current_subscription_id_impl,
)
from .backup_panel_recovery_sync import (
    _sync_panel_profiles_for_restore as _sync_panel_profiles_for_restore_impl,
)
from .backup_panel_recovery_sync import (
    _upsert_missing_plan_rows_from_snapshots as _upsert_missing_plan_rows_from_snapshots_impl,
)

if TYPE_CHECKING:
    from .backup import BackupService
else:
    BackupService = Any


def _as_backup_service(instance: object) -> BackupService:
    return cast(BackupService, instance)


class BackupPanelRecoveryMixin:
    def _build_backup_integrity_report(
        self,
        *,
        backup_data: dict[str, list[dict[str, Any]]],
        export_errors: dict[str, str],
    ) -> dict[str, Any]:
        return _build_backup_integrity_report_impl(
            _as_backup_service(self),
            backup_data=backup_data,
            export_errors=export_errors,
        )

    def _extract_current_subscription_refs(
        self,
        user_rows: list[dict[str, Any]],
    ) -> list[tuple[int, int]]:
        return _extract_current_subscription_refs_impl(_as_backup_service(self), user_rows)

    def _analyze_restore_archive(
        self,
        backup_data: dict[str, list[dict[str, Any]]],
    ) -> RestoreArchiveDiagnostics:
        return _analyze_restore_archive_impl(_as_backup_service(self), backup_data)

    def _collect_plan_snapshots(
        self,
        backup_data: dict[str, list[dict[str, Any]]],
        *,
        extra_snapshots: Optional[list[dict[str, Any]]] = None,
    ) -> dict[int, dict[str, Any]]:
        return _collect_plan_snapshots_impl(
            _as_backup_service(self),
            backup_data,
            extra_snapshots=extra_snapshots,
        )

    def _log_restore_archive_diagnostics(
        self,
        diagnostics: RestoreArchiveDiagnostics,
    ) -> None:
        _log_restore_archive_diagnostics_impl(_as_backup_service(self), diagnostics)

    def _normalize_squad_values(self, values: list[UUID]) -> list[str]:
        return _normalize_squad_values_impl(_as_backup_service(self), values)

    def _match_plan_for_panel_subscription(
        self,
        *,
        remna_subscription: RemnaSubscriptionDto,
        plans: list[Plan],
    ) -> Optional[Plan]:
        return _match_plan_for_panel_subscription_impl(
            _as_backup_service(self),
            remna_subscription=remna_subscription,
            plans=plans,
        )

    def _build_panel_subscription_snapshot(
        self,
        *,
        remna_subscription: RemnaSubscriptionDto,
        matched_plan: Optional[Plan],
    ) -> dict[str, Any]:
        return _build_panel_subscription_snapshot_impl(
            _as_backup_service(self),
            remna_subscription=remna_subscription,
            matched_plan=matched_plan,
        )

    async def _fetch_panel_users_by_telegram_id(
        self,
        telegram_id: int,
    ) -> list[UserResponseDto]:
        return await _fetch_panel_users_by_telegram_id_impl(_as_backup_service(self), telegram_id)

    async def _upsert_missing_plan_rows_from_snapshots(
        self,
        session: AsyncSession,
        *,
        snapshots_by_id: dict[int, dict[str, Any]],
    ) -> int:
        return await _upsert_missing_plan_rows_from_snapshots_impl(
            _as_backup_service(self),
            session,
            snapshots_by_id=snapshots_by_id,
        )

    def _resolve_effective_subscription_status(
        self,
        subscription: Subscription,
    ) -> SubscriptionStatus:
        return _resolve_effective_subscription_status_impl(_as_backup_service(self), subscription)

    def _select_current_subscription_id(
        self,
        subscriptions: list[Subscription],
    ) -> Optional[int]:
        return _select_current_subscription_id_impl(_as_backup_service(self), subscriptions)

    async def _sync_panel_profiles_for_restore(
        self,
        *,
        telegram_id: int,
        remna_users: list[UserResponseDto],
    ) -> tuple[int, list[dict[str, object]]]:
        return await _sync_panel_profiles_for_restore_impl(
            _as_backup_service(self),
            telegram_id=telegram_id,
            remna_users=remna_users,
        )

    async def _recover_missing_subscriptions_from_panel(
        self,
        diagnostics: RestoreArchiveDiagnostics,
    ) -> RestoreArchiveDiagnostics:
        return await _recover_missing_subscriptions_from_panel_impl(
            _as_backup_service(self),
            diagnostics,
        )

    def _build_recovered_plan_record(
        self,
        *,
        plan_id: int,
        order_index: int,
        snapshot: dict[str, Any] | None,
        snapshot_only: bool = False,
    ) -> dict[str, Any]:
        return _build_recovered_plan_record_impl(
            _as_backup_service(self),
            plan_id=plan_id,
            order_index=order_index,
            snapshot=snapshot,
            snapshot_only=snapshot_only,
        )

    def _recover_legacy_missing_plans(
        self,
        backup_data: dict[str, list[dict[str, Any]]],
    ) -> tuple[dict[str, list[dict[str, Any]]], int]:
        return _recover_legacy_missing_plans_impl(_as_backup_service(self), backup_data)
