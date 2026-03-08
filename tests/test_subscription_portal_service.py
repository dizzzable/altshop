from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.constants import IMPORTED_TAG
from src.core.enums import DeviceType, Locale, PlanAvailability, PlanType, UserRole
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanDurationDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)
from src.services.subscription_portal import (
    SubscriptionAssignmentUpdate,
    SubscriptionPortalAccessDeniedError,
    SubscriptionPortalBadRequestError,
    SubscriptionPortalService,
    SubscriptionPortalStateError,
)


def _build_user(*, telegram_id: int = 1001, role: UserRole = UserRole.USER) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        referral_code=f"ref{telegram_id}",
        name=f"User {telegram_id}",
        role=role,
        language=Locale.EN,
    )


def _build_plan_snapshot(*, plan_id: int = 11, duration: int = 30) -> PlanSnapshotDto:
    plan = PlanDto(
        id=plan_id,
        name=f"Plan {plan_id}",
        tag=f"plan-{plan_id}",
        type=PlanType.UNLIMITED,
        availability=PlanAvailability.ALL,
        is_active=True,
        traffic_limit=-1,
        device_limit=-1,
        durations=[PlanDurationDto(days=duration, prices=[])],
        internal_squads=[],
    )
    return PlanSnapshotDto.from_plan(plan, duration)


def _build_subscription(
    *,
    subscription_id: int = 77,
    user_telegram_id: int = 1001,
    duration: int = 30,
    device_type: DeviceType | None = None,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        traffic_limit=-1,
        device_limit=3,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=duration),
        url="https://example.test/subscription",
        plan=_build_plan_snapshot(duration=duration),
        device_type=device_type,
    )


def _build_service(
    *,
    subscription: SubscriptionDto | None,
) -> tuple[SubscriptionPortalService, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(return_value=subscription),
        delete_subscription=AsyncMock(return_value=True),
    )
    subscription_runtime_service = SimpleNamespace(
        prepare_for_detail=AsyncMock(return_value=subscription),
    )
    plan_service = SimpleNamespace(get_available_plans=AsyncMock(return_value=[]))
    service = SubscriptionPortalService(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        plan_service=plan_service,
    )
    return service, subscription_service, subscription_runtime_service, plan_service


def test_get_detail_prepares_owned_subscription() -> None:
    subscription = _build_subscription()
    refreshed = subscription.model_copy(update={"url": "https://runtime.test/subscription"})
    service, _, subscription_runtime_service, _ = _build_service(subscription=subscription)
    subscription_runtime_service.prepare_for_detail = AsyncMock(return_value=refreshed)

    result = asyncio.run(
        service.get_detail(
            subscription_id=subscription.id or 0,
            current_user=_build_user(),
        )
    )

    assert result.url == "https://runtime.test/subscription"
    subscription_runtime_service.prepare_for_detail.assert_awaited_once_with(subscription)


def test_update_assignment_requires_payload_fields() -> None:
    subscription = _build_subscription()
    service, _, _, _ = _build_service(subscription=subscription)

    with pytest.raises(SubscriptionPortalBadRequestError) as exc_info:
        asyncio.run(
            service.update_assignment(
                subscription_id=subscription.id or 0,
                current_user=_build_user(),
                update=SubscriptionAssignmentUpdate(),
            )
        )

    assert str(exc_info.value) == "At least one field must be provided"


def test_update_assignment_rejects_non_dev_plan_change() -> None:
    subscription = _build_subscription()
    service, _, _, _ = _build_service(subscription=subscription)

    with pytest.raises(SubscriptionPortalAccessDeniedError) as exc_info:
        asyncio.run(
            service.update_assignment(
                subscription_id=subscription.id or 0,
                current_user=_build_user(role=UserRole.USER),
                update=SubscriptionAssignmentUpdate(plan_id=99, plan_id_provided=True),
            )
        )

    assert str(exc_info.value) == "Only DEV can change plan assignment"


def test_update_assignment_resets_imported_snapshot() -> None:
    subscription = _build_subscription()
    service, subscription_service, _, _ = _build_service(subscription=subscription)

    result = asyncio.run(
        service.update_assignment(
            subscription_id=subscription.id or 0,
            current_user=_build_user(role=UserRole.DEV),
            update=SubscriptionAssignmentUpdate(plan_id=None, plan_id_provided=True),
        )
    )

    assert result.plan.id == -1
    assert result.plan.name == IMPORTED_TAG
    assert result.plan.tag == IMPORTED_TAG
    subscription_service.update.assert_awaited_once()


def test_update_assignment_uses_available_plan_and_duration_fallback() -> None:
    subscription = _build_subscription(duration=30)
    selected_plan = PlanDto(
        id=55,
        name="Selected",
        tag="selected",
        type=PlanType.UNLIMITED,
        availability=PlanAvailability.ALL,
        is_active=True,
        traffic_limit=-1,
        device_limit=-1,
        durations=[PlanDurationDto(days=90, prices=[])],
        internal_squads=[],
    )
    service, _, _, plan_service = _build_service(subscription=subscription)
    plan_service.get_available_plans = AsyncMock(return_value=[selected_plan])

    result = asyncio.run(
        service.update_assignment(
            subscription_id=subscription.id or 0,
            current_user=_build_user(role=UserRole.DEV),
            update=SubscriptionAssignmentUpdate(plan_id=55, plan_id_provided=True),
        )
    )

    assert result.plan.id == 55
    assert result.plan.duration == 90


def test_delete_subscription_raises_when_mark_deleted_fails() -> None:
    subscription = _build_subscription()
    service, subscription_service, _, _ = _build_service(subscription=subscription)
    subscription_service.delete_subscription = AsyncMock(return_value=False)

    with pytest.raises(SubscriptionPortalStateError) as exc_info:
        asyncio.run(
            service.delete_subscription(
                subscription_id=subscription.id or 0,
                current_user=_build_user(),
            )
        )

    assert str(exc_info.value) == "Failed to delete subscription"
