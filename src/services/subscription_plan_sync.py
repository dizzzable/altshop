from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger
from remnawave.enums.users import TrafficLimitStrategy

from src.core.constants import TIMEZONE
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanDto, SubscriptionDto

if TYPE_CHECKING:
    from .subscription import SubscriptionService


async def sync_plan_snapshot_metadata(service: SubscriptionService, plan: PlanDto) -> int:
    if plan.id is None:
        raise ValueError("Plan ID is required for snapshot sync")

    subscriptions = await service.uow.repository.subscriptions.filter_by_plan_id(plan.id)
    updated_count = 0

    for subscription in SubscriptionDto.from_model_list(subscriptions):
        if subscription.status == service._deleted_status():
            continue

        changed = False
        if subscription.plan.name != plan.name:
            subscription.plan.name = plan.name
            changed = True
        if subscription.plan.tag != plan.tag:
            subscription.plan.tag = plan.tag
            changed = True

        if not changed:
            continue

        updated_subscription = await service.update(subscription, auto_commit=False)
        if updated_subscription:
            updated_count += 1

    if updated_count:
        await service.uow.commit()

    logger.info(
        "Plan snapshot metadata sync completed for plan '{}': updated={}",
        plan.id,
        updated_count,
    )
    return updated_count


def get_traffic_reset_delta(strategy: TrafficLimitStrategy) -> timedelta | None:
    now = datetime_now()

    if strategy == TrafficLimitStrategy.NO_RESET:
        return None

    if strategy == TrafficLimitStrategy.DAY:
        next_day = now.date() + timedelta(days=1)
        reset_at = datetime.combine(
            next_day,
            datetime.min.time(),
            tzinfo=TIMEZONE,
        )
        return reset_at - now

    if strategy == TrafficLimitStrategy.WEEK:
        weekday = now.weekday()
        days_until = (7 - weekday) % 7 or 7
        date_target = now.date() + timedelta(days=days_until)
        reset_at = datetime(
            date_target.year,
            date_target.month,
            date_target.day,
            0,
            5,
            0,
            tzinfo=TIMEZONE,
        )
        return reset_at - now

    if strategy == TrafficLimitStrategy.MONTH:
        year = now.year
        month = now.month + 1
        if month == 13:
            year += 1
            month = 1
        reset_at = datetime(year, month, 1, 0, 10, 0, tzinfo=TIMEZONE)
        return reset_at - now

    raise ValueError(f"Unsupported traffic limit strategy: {strategy}")
