# mypy: ignore-errors
# ruff: noqa: E501

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from loguru import logger
from remnawave.enums.users import TrafficLimitStrategy
from remnawave.models import TelegramUserResponseDto, UserResponseDto
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import IMPORTED_TAG
from src.core.enums import (
    ArchivedPlanRenewMode,
    DeviceType,
    PlanAvailability,
    PlanType,
    SubscriptionStatus,
)
from src.core.utils.formatters import format_limits_to_plan_type
from src.core.utils.time import datetime_now
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


class BackupPanelRecoveryMixin:
    def _build_backup_integrity_report(
        self,
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
        current_refs = self._extract_current_subscription_refs(user_rows)
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
        self,
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
        self,
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
        current_refs = self._extract_current_subscription_refs(user_rows)
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
        self,
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
                snapshot = self._parse_backup_snapshot(record.get("plan"))
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

    def _log_restore_archive_diagnostics(self, diagnostics: RestoreArchiveDiagnostics) -> None:
        if not diagnostics.archive_issue_messages:
            return

        for issue_message in diagnostics.archive_issue_messages:
            logger.warning(issue_message)

    @staticmethod
    def _normalize_squad_values(values: list[UUID]) -> list[str]:
        return [str(value) for value in values]

    def _match_plan_for_panel_subscription(
        self,
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
        self,
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
            device_limit=(
                matched_plan.device_limit if matched_plan else remna_subscription.device_limit
            ),
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

    async def _fetch_panel_users_by_telegram_id(self, telegram_id: int) -> list[UserResponseDto]:
        users_result = await self.remnawave.users.get_users_by_telegram_id(
            telegram_id=str(telegram_id)
        )
        if not isinstance(users_result, TelegramUserResponseDto):
            raise ValueError(
                "Unexpected Remnawave response for telegram_id "
                f"'{telegram_id}': {users_result!r}"
            )
        return list(users_result.root)

    async def _upsert_missing_plan_rows_from_snapshots(
        self,
        session: AsyncSession,
        *,
        snapshots_by_id: dict[int, dict[str, Any]],
    ) -> int:
        if not snapshots_by_id:
            return 0

        result = await session.execute(select(Plan.id, Plan.order_index))
        existing_rows = list(result.all())
        existing_plan_ids = {int(plan_id) for plan_id, _order_index in existing_rows}
        max_order_index = max((int(order_index) for _plan_id, order_index in existing_rows), default=0)
        created = 0

        for plan_id in sorted(snapshots_by_id):
            if plan_id <= 0 or plan_id in existing_plan_ids:
                continue

            max_order_index += 1
            session.add(
                Plan(
                    **self._build_recovered_plan_record(
                        plan_id=plan_id,
                        order_index=max_order_index,
                        snapshot=snapshots_by_id[plan_id],
                        snapshot_only=True,
                    )
                )
            )
            existing_plan_ids.add(plan_id)
            created += 1

        return created

    @staticmethod
    def _resolve_effective_subscription_status(subscription: Subscription) -> SubscriptionStatus:
        if subscription.expire_at < datetime_now():
            return SubscriptionStatus.EXPIRED
        return subscription.status

    def _select_current_subscription_id(
        self,
        subscriptions: list[Subscription],
    ) -> Optional[int]:
        if not subscriptions:
            return None

        status_priority = {
            SubscriptionStatus.ACTIVE: 0,
            SubscriptionStatus.DISABLED: 1,
            SubscriptionStatus.EXPIRED: 2,
        }
        candidates = [
            subscription
            for subscription in subscriptions
            if self._resolve_effective_subscription_status(subscription) != SubscriptionStatus.DELETED
        ]
        if not candidates:
            return None

        selected = sorted(
            candidates,
            key=lambda subscription: (
                status_priority.get(self._resolve_effective_subscription_status(subscription), 99),
                -subscription.expire_at.timestamp(),
                -(subscription.id or 0),
            ),
        )[0]
        return selected.id

    async def _sync_panel_profiles_for_restore(
        self,
        *,
        telegram_id: int,
        remna_users: list[UserResponseDto],
    ) -> tuple[int, list[dict[str, Any]]]:
        panel_snapshots: list[dict[str, Any]] = []

        async with self.session_pool() as session:
            existing_user = await session.execute(
                select(User.telegram_id).where(User.telegram_id == telegram_id)
            )
            if existing_user.scalar_one_or_none() is None:
                return 0, panel_snapshots

            plans_result = await session.execute(select(Plan))
            plans = list(plans_result.scalars().all())
            restored_subscriptions = 0

            for remna_user in remna_users:
                remna_payload = remna_user.model_dump()
                remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_payload)
                matched_plan = self._match_plan_for_panel_subscription(
                    remna_subscription=remna_subscription,
                    plans=plans,
                )
                plan_payload = self._build_panel_subscription_snapshot(
                    remna_subscription=remna_subscription,
                    matched_plan=matched_plan,
                )
                panel_snapshots.append(plan_payload)

                status = (
                    SubscriptionStatus.EXPIRED
                    if remna_user.expire_at and remna_user.expire_at < datetime_now()
                    else remna_user.status
                )
                values = {
                    "user_telegram_id": telegram_id,
                    "status": status,
                    "is_trial": False,
                    "traffic_limit": remna_subscription.traffic_limit,
                    "device_limit": remna_subscription.device_limit,
                    "internal_squads": list(remna_subscription.internal_squads),
                    "external_squad": remna_subscription.external_squad,
                    "expire_at": remna_user.expire_at,
                    "url": remna_subscription.url or "",
                    "device_type": DeviceType.OTHER,
                    "plan": plan_payload,
                }

                subscription_result = await session.execute(
                    select(Subscription.id).where(Subscription.user_remna_id == remna_user.uuid)
                )
                existing_subscription_id = subscription_result.scalar_one_or_none()

                if existing_subscription_id is None:
                    session.add(
                        Subscription(
                            user_remna_id=remna_user.uuid,
                            **values,
                        )
                    )
                else:
                    await session.execute(
                        update(Subscription)
                        .where(Subscription.id == existing_subscription_id)
                        .values(**values)
                        .execution_options(synchronize_session=False)
                    )
                restored_subscriptions += 1

            await self._upsert_missing_plan_rows_from_snapshots(
                session,
                snapshots_by_id=self._collect_plan_snapshots({}, extra_snapshots=panel_snapshots),
            )
            await session.flush()
            subscriptions_result = await session.execute(
                select(Subscription).where(Subscription.user_telegram_id == telegram_id)
            )
            subscriptions = list(subscriptions_result.scalars().all())
            current_subscription_id = self._select_current_subscription_id(subscriptions)
            await self._apply_scalar_restore_update(
                session=session,
                model=User,
                lookup_field="telegram_id",
                lookup_value=telegram_id,
                values={"current_subscription_id": current_subscription_id},
            )
            await session.commit()

        return restored_subscriptions, panel_snapshots

    async def _recover_missing_subscriptions_from_panel(
        self,
        diagnostics: RestoreArchiveDiagnostics,
    ) -> RestoreArchiveDiagnostics:
        if not diagnostics.panel_sync_candidate_ids:
            return diagnostics

        for telegram_id, missing_subscription_id in diagnostics.missing_archive_subscription_refs:
            try:
                remna_users = await self._fetch_panel_users_by_telegram_id(telegram_id)
            except Exception as exc:
                logger.warning(
                    "Panel recovery failed for telegram_id '{}': {}",
                    telegram_id,
                    exc,
                )
                diagnostics.panel_sync_errors.append((telegram_id, str(exc)))
                diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
                continue

            if not remna_users:
                diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
                continue

            restored_subscriptions, _panel_snapshots = await self._sync_panel_profiles_for_restore(
                telegram_id=telegram_id,
                remna_users=remna_users,
            )
            if restored_subscriptions == 0:
                diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
                continue

            diagnostics.remnawave_users_recovered += 1
            diagnostics.remnawave_subscriptions_recovered += restored_subscriptions

        return diagnostics

    def _build_recovered_plan_record(
        self,
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
            "type": self._coerce_plan_enum_value(
                snapshot.get("type"),
                PlanType,
                PlanType.BOTH.value,
            ),
            "availability": PlanAvailability.ALL.value,
            "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
            "name": snapshot.get("name") or f"Recovered plan #{plan_id}",
            "description": None,
            "tag": snapshot.get("tag"),
            "traffic_limit": self._coerce_int_value(snapshot.get("traffic_limit"), 0),
            "device_limit": self._coerce_int_value(snapshot.get("device_limit"), 1),
            "traffic_limit_strategy": self._coerce_plan_enum_value(
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
        self,
        backup_data: dict[str, list[dict[str, Any]]],
    ) -> tuple[dict[str, list[dict[str, Any]]], int]:
        plans = list(backup_data.get(Plan.__tablename__) or [])
        durations = backup_data.get(PlanDuration.__tablename__) or []
        if not durations and not self._collect_plan_snapshots(backup_data):
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

        snapshots_by_id = self._collect_plan_snapshots(backup_data)
        referenced_plan_ids = sorted(referenced_plan_ids_set | set(snapshots_by_id))
        missing_plan_ids = [
            plan_id
            for plan_id in referenced_plan_ids
            if plan_id > 0 and plan_id not in existing_plan_ids
        ]
        if not missing_plan_ids:
            return backup_data, 0

        recovered_plans = [
            self._build_recovered_plan_record(
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
