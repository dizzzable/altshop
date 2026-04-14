from __future__ import annotations

from typing import Any, Optional, cast
from uuid import UUID

from loguru import logger

from src.core.constants import IMPORTED_TAG
from src.infrastructure.database.models.dto import (
    PlanDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
)


async def _resolve_plan_by_tag(
    service: Any,
    plan_tag: Optional[str],
    telegram_id: int,
) -> Optional[PlanDto]:
    if not plan_tag:
        logger.debug(
            f"No tag in panel data, using imported snapshot metadata for user '{telegram_id}'"
        )
        return None

    try:
        plan = cast(Optional[PlanDto], await service.plan_service.get_by_tag(plan_tag))
    except Exception as exception:
        logger.exception(
            f"Error getting plan by tag '{plan_tag}' for user '{telegram_id}': {exception}"
        )
        return None

    if plan:
        logger.info(f"Found plan '{plan.name}' by tag '{plan_tag}' for user '{telegram_id}'")
        return plan

    logger.debug(
        f"Plan with tag '{plan_tag}' not found, using imported snapshot metadata for "
        f"user '{telegram_id}'"
    )
    return None


async def _resolve_plan_by_limits(
    service: Any,
    remna_subscription: RemnaSubscriptionDto,
    telegram_id: int,
) -> Optional[PlanDto]:
    try:
        plans = cast(list[PlanDto], await service.plan_service.get_all())
    except Exception as exception:
        logger.exception(
            f"Error loading plans for limits-based sync match for user '{telegram_id}': "
            f"{exception}"
        )
        return None

    active_plans = [plan for plan in plans if plan.is_active]
    matches = [
        plan
        for plan in active_plans
        if _plan_matches_subscription_limits(plan, remna_subscription)
    ]

    if not matches:
        logger.debug(
            f"No limits-based plan match for user '{telegram_id}' "
            f"(traffic={remna_subscription.traffic_limit}, "
            f"devices={remna_subscription.device_limit})"
        )
        return None

    if remna_subscription.tag:
        for plan in matches:
            if plan.tag == remna_subscription.tag:
                logger.info(
                    f"Matched plan '{plan.name}' by tag within limits candidates "
                    f"for user '{telegram_id}'"
                )
                return plan

    matches.sort(key=lambda plan: (plan.order_index, plan.id or 0))
    selected = matches[0]
    logger.info(
        f"Matched plan '{selected.name}' by limits for user '{telegram_id}' "
        f"({len(matches)} candidate(s))"
    )
    return selected


def _normalize_squads(value: list[UUID]) -> list[str]:
    return sorted(str(item) for item in value)


def _plan_matches_subscription_limits(
    plan: PlanDto,
    remna_subscription: RemnaSubscriptionDto,
) -> bool:
    if plan.traffic_limit != remna_subscription.traffic_limit:
        return False
    if plan.device_limit != remna_subscription.device_limit:
        return False

    if (
        remna_subscription.traffic_limit_strategy is not None
        and plan.traffic_limit_strategy != remna_subscription.traffic_limit_strategy
    ):
        return False

    if _normalize_squads(plan.internal_squads) != _normalize_squads(
        remna_subscription.internal_squads
    ):
        return False

    return plan.external_squad == remna_subscription.external_squad


def _is_imported_tag(plan_tag: Optional[str]) -> bool:
    return bool(plan_tag and str(plan_tag).upper() == IMPORTED_TAG)


def _is_imported_or_unassigned_snapshot(subscription: SubscriptionDto) -> bool:
    plan = subscription.plan
    if plan.id is None or plan.id <= 0:
        return True

    plan_tag = (plan.tag or "").upper()
    plan_name = (plan.name or "").upper()
    return plan_tag == IMPORTED_TAG or plan_name == IMPORTED_TAG


def _apply_plan_identity(
    subscription: SubscriptionDto,
    matched_plan: Optional[PlanDto],
    telegram_id: int,
) -> None:
    if not matched_plan or matched_plan.id is None:
        return

    plan = subscription.plan
    if plan.id != matched_plan.id:
        logger.info(
            f"Updating snapshot plan.id for user '{telegram_id}': "
            f"{plan.id} -> {matched_plan.id}"
        )
        plan.id = matched_plan.id

    if plan.tag != matched_plan.tag:
        plan.tag = matched_plan.tag

    if plan.name != matched_plan.name:
        plan.name = matched_plan.name


async def _resolve_matched_plan_for_sync(
    service: Any,
    *,
    remna_subscription: RemnaSubscriptionDto,
    telegram_id: int,
) -> Optional[PlanDto]:
    matched_plan = await _resolve_plan_by_tag(
        service,
        plan_tag=remna_subscription.tag,
        telegram_id=telegram_id,
    )
    if matched_plan:
        return matched_plan

    return await _resolve_plan_by_limits(
        service,
        remna_subscription=remna_subscription,
        telegram_id=telegram_id,
    )
