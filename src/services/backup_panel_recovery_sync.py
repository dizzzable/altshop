from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from loguru import logger
from remnawave.models import TelegramUserResponseDto, UserResponseDto
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import DeviceType, SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import RemnaSubscriptionDto
from src.infrastructure.database.models.sql import Plan, Subscription, User

from .backup_models import RestoreArchiveDiagnostics

if TYPE_CHECKING:
    from .backup import BackupService


async def _fetch_panel_users_by_telegram_id(
    service: BackupService,
    telegram_id: int,
) -> list[UserResponseDto]:
    users_result = await service.remnawave.users.get_users_by_telegram_id(
        telegram_id=str(telegram_id)
    )
    if not isinstance(users_result, TelegramUserResponseDto):
        raise ValueError(
            "Unexpected Remnawave response for telegram_id "
            f"'{telegram_id}': {users_result!r}"
        )
    return list(users_result.root)


async def _upsert_missing_plan_rows_from_snapshots(
    service: BackupService,
    session: AsyncSession,
    *,
    snapshots_by_id: dict[int, dict[str, object]],
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
                **service._build_recovered_plan_record(
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


def _resolve_effective_subscription_status(
    _service: BackupService,
    subscription: Subscription,
) -> SubscriptionStatus:
    if subscription.expire_at < datetime_now():
        return SubscriptionStatus.EXPIRED
    return subscription.status


def _select_current_subscription_id(
    service: BackupService,
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
        if service._resolve_effective_subscription_status(subscription)
        != SubscriptionStatus.DELETED
    ]
    if not candidates:
        return None

    selected = sorted(
        candidates,
        key=lambda subscription: (
            status_priority.get(service._resolve_effective_subscription_status(subscription), 99),
            -subscription.expire_at.timestamp(),
            -(subscription.id or 0),
        ),
    )[0]
    return selected.id


async def _sync_panel_profiles_for_restore(
    service: BackupService,
    *,
    telegram_id: int,
    remna_users: list[UserResponseDto],
) -> tuple[int, list[dict[str, object]]]:
    panel_snapshots: list[dict[str, object]] = []

    async with service.session_pool() as session:
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
            matched_plan = service._match_plan_for_panel_subscription(
                remna_subscription=remna_subscription,
                plans=plans,
            )
            plan_payload = service._build_panel_subscription_snapshot(
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

        await service._upsert_missing_plan_rows_from_snapshots(
            session,
            snapshots_by_id=service._collect_plan_snapshots({}, extra_snapshots=panel_snapshots),
        )
        await session.flush()
        subscriptions_result = await session.execute(
            select(Subscription).where(Subscription.user_telegram_id == telegram_id)
        )
        subscriptions = list(subscriptions_result.scalars().all())
        current_subscription_id = service._select_current_subscription_id(subscriptions)
        await service._apply_scalar_restore_update(
            session=session,
            model=User,
            lookup_field="telegram_id",
            lookup_value=telegram_id,
            values={"current_subscription_id": current_subscription_id},
        )
        await session.commit()

    return restored_subscriptions, panel_snapshots


async def _recover_missing_subscriptions_from_panel(
    service: BackupService,
    diagnostics: RestoreArchiveDiagnostics,
) -> RestoreArchiveDiagnostics:
    if not diagnostics.panel_sync_candidate_ids:
        return diagnostics

    for telegram_id, missing_subscription_id in diagnostics.missing_archive_subscription_refs:
        try:
            remna_users = await service._fetch_panel_users_by_telegram_id(telegram_id)
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

        restored_subscriptions, _panel_snapshots = await service._sync_panel_profiles_for_restore(
            telegram_id=telegram_id,
            remna_users=remna_users,
        )
        if restored_subscriptions == 0:
            diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
            continue

        diagnostics.remnawave_users_recovered += 1
        diagnostics.remnawave_subscriptions_recovered += restored_subscriptions

    return diagnostics
