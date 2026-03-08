from __future__ import annotations

import asyncio
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import PlanType, SubscriptionStatus
from src.infrastructure.database.models.dto.plan import PlanDto, PlanDurationDto, PlanSnapshotDto
from src.infrastructure.taskiq.tasks.importer import assign_plan_to_synced_users_task


def _unwrap_callable(func):
    if hasattr(func, "original_func"):
        original_func = getattr(func, "original_func")
        closure = getattr(original_func, "__closure__", None) or ()
        for cell in closure:
            cell_value = getattr(cell, "cell_contents", None)
            if (
                isinstance(cell_value, types.FunctionType)
                and cell_value.__name__ == "assign_plan_to_synced_users_task"
            ):
                return cell_value

    target = func
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__  # type: ignore[attr-defined]
    return target


_ASSIGN_PLAN_IMPL = _unwrap_callable(assign_plan_to_synced_users_task)


def _build_plan() -> PlanDto:
    return PlanDto(
        id=101,
        name="Assigned Plan",
        tag="ASSIGNED",
        type=PlanType.BOTH,
        traffic_limit=100,
        device_limit=3,
        subscription_count=1,
        durations=[
            PlanDurationDto(days=30),
            PlanDurationDto(days=60),
        ],
        internal_squads=[],
        external_squad=None,
        is_active=True,
    )


def _build_snapshot(*, plan_id: int, name: str, tag: str | None, duration: int) -> PlanSnapshotDto:
    return PlanSnapshotDto(
        id=plan_id,
        name=name,
        tag=tag,
        type=PlanType.BOTH,
        traffic_limit=50,
        device_limit=1,
        subscription_count=1,
        duration=duration,
        internal_squads=[],
        external_squad=None,
    )


def test_assign_plan_to_synced_users_updates_all_imported_subscriptions() -> None:
    selected_plan = _build_plan()

    imported_with_mismatch_duration = SimpleNamespace(
        id=1,
        status=SubscriptionStatus.ACTIVE,
        url="",
        user_remna_id=uuid4(),
        plan=_build_snapshot(plan_id=-1, name="IMPORTED", tag="IMPORTED", duration=45),
    )
    imported_with_same_duration = SimpleNamespace(
        id=2,
        status=SubscriptionStatus.ACTIVE,
        url="https://existing.example/sub2",
        user_remna_id=uuid4(),
        plan=_build_snapshot(plan_id=-1, name="IMPORTED", tag="IMPORTED", duration=60),
    )
    manually_assigned = SimpleNamespace(
        id=3,
        status=SubscriptionStatus.ACTIVE,
        url="https://existing.example/sub3",
        user_remna_id=uuid4(),
        plan=_build_snapshot(plan_id=77, name="Default Plan", tag="DEFAULT", duration=30),
    )
    deleted_subscription = SimpleNamespace(
        id=4,
        status=SubscriptionStatus.DELETED,
        url="",
        user_remna_id=uuid4(),
        plan=_build_snapshot(plan_id=-1, name="IMPORTED", tag="IMPORTED", duration=30),
    )

    plan_service = SimpleNamespace(get=AsyncMock(return_value=selected_plan))
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(
            side_effect=[
                [
                    imported_with_mismatch_duration,
                    imported_with_same_duration,
                    manually_assigned,
                    deleted_subscription,
                ],
                [],
            ]
        ),
        update=AsyncMock(side_effect=lambda subscription, auto_commit=False: subscription),
        uow=SimpleNamespace(commit=AsyncMock()),
    )
    remnawave_service = SimpleNamespace(
        get_subscription_url=AsyncMock(return_value="https://refreshed.example/sub1")
    )

    result = asyncio.run(
        _ASSIGN_PLAN_IMPL(
            plan_id=selected_plan.id,
            synced_telegram_ids=[1001, 2002],
            plan_service=plan_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result == {
        "updated": 2,
        "skipped_no_subscription": 1,
        "skipped_deleted": 1,
        "skipped_already_assigned": 1,
        "errors": 0,
    }

    assert subscription_service.get_all_by_user.await_count == 2
    assert remnawave_service.get_subscription_url.await_count == 1
    subscription_service.uow.commit.assert_awaited_once()

    updated_subscriptions = [call.args[0] for call in subscription_service.update.await_args_list]
    assert [subscription.id for subscription in updated_subscriptions] == [1, 2]
    assert updated_subscriptions[0].plan.id == selected_plan.id
    assert updated_subscriptions[1].plan.id == selected_plan.id
    assert updated_subscriptions[0].plan.duration == 30
    assert updated_subscriptions[1].plan.duration == 60
