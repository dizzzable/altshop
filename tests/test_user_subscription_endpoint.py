from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.endpoints.user_subscription import (
    SubscriptionAssignmentRequest,
    delete_subscription,
    get_subscription,
    update_subscription_assignment,
)
from src.core.enums import DeviceType
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto
from src.services.subscription_portal import (
    DeletedSubscriptionResult,
    SubscriptionPortalAccessDeniedError,
    SubscriptionPortalNotFoundError,
    SubscriptionPortalStateError,
)

GET_SUBSCRIPTION_ENDPOINT = getattr(
    inspect.unwrap(get_subscription),
    "__dishka_orig_func__",
    inspect.unwrap(get_subscription),
)
UPDATE_ASSIGNMENT_ENDPOINT = getattr(
    inspect.unwrap(update_subscription_assignment),
    "__dishka_orig_func__",
    inspect.unwrap(update_subscription_assignment),
)
DELETE_SUBSCRIPTION_ENDPOINT = getattr(
    inspect.unwrap(delete_subscription),
    "__dishka_orig_func__",
    inspect.unwrap(delete_subscription),
)


def _build_current_user(telegram_id: int) -> SimpleNamespace:
    return SimpleNamespace(telegram_id=telegram_id)


def _build_subscription(*, subscription_id: int = 77) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id="00000000-0000-0000-0000-000000000000",
        user_telegram_id=1001,
        traffic_limit=-1,
        device_limit=3,
        internal_squads=[],
        external_squad=None,
        expire_at="2099-01-01T00:00:00+00:00",
        url="https://example.test/subscription",
        plan=PlanSnapshotDto.test(),
    )


def test_get_subscription_delegates_to_subscription_portal_service() -> None:
    current_user = _build_current_user(telegram_id=1001)
    subscription = _build_subscription()
    subscription_portal_service = SimpleNamespace(
        get_detail=AsyncMock(return_value=subscription)
    )

    response = asyncio.run(
        GET_SUBSCRIPTION_ENDPOINT(
            subscription_id=77,
            current_user=current_user,
            subscription_portal_service=subscription_portal_service,
        )
    )

    assert response.id == 77
    subscription_portal_service.get_detail.assert_awaited_once_with(
        subscription_id=77,
        current_user=current_user,
    )


def test_update_assignment_delegates_to_subscription_portal_service() -> None:
    current_user = _build_current_user(telegram_id=1001)
    updated_subscription = _build_subscription(subscription_id=88)
    subscription_portal_service = SimpleNamespace(
        update_assignment=AsyncMock(return_value=updated_subscription)
    )

    response = asyncio.run(
        UPDATE_ASSIGNMENT_ENDPOINT(
            subscription_id=88,
            payload=SubscriptionAssignmentRequest(device_type=DeviceType.WINDOWS),
            current_user=current_user,
            subscription_portal_service=subscription_portal_service,
        )
    )

    assert response.id == 88
    update_arg = subscription_portal_service.update_assignment.await_args.kwargs["update"]
    assert update_arg.device_type == DeviceType.WINDOWS
    assert update_arg.device_type_provided is True


def test_delete_subscription_delegates_to_subscription_portal_service() -> None:
    current_user = _build_current_user(telegram_id=1001)
    subscription_portal_service = SimpleNamespace(
        delete_subscription=AsyncMock(
            return_value=DeletedSubscriptionResult(
                success=True,
                message="Subscription deleted successfully",
            )
        )
    )

    response = asyncio.run(
        DELETE_SUBSCRIPTION_ENDPOINT(
            subscription_id=99,
            current_user=current_user,
            subscription_portal_service=subscription_portal_service,
        )
    )

    assert response == {
        "success": True,
        "message": "Subscription deleted successfully",
    }


def test_get_subscription_maps_not_found_to_404() -> None:
    current_user = _build_current_user(telegram_id=1001)
    subscription_portal_service = SimpleNamespace(
        get_detail=AsyncMock(side_effect=SubscriptionPortalNotFoundError())
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            GET_SUBSCRIPTION_ENDPOINT(
                subscription_id=77,
                current_user=current_user,
                subscription_portal_service=subscription_portal_service,
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Subscription not found"


def test_delete_subscription_maps_state_error_to_500() -> None:
    current_user = _build_current_user(telegram_id=1001)
    subscription_portal_service = SimpleNamespace(
        delete_subscription=AsyncMock(
            side_effect=SubscriptionPortalStateError("Failed to delete subscription")
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            DELETE_SUBSCRIPTION_ENDPOINT(
                subscription_id=99,
                current_user=current_user,
                subscription_portal_service=subscription_portal_service,
            )
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to delete subscription"


def test_update_assignment_maps_access_denied_to_403() -> None:
    current_user = _build_current_user(telegram_id=1001)
    subscription_portal_service = SimpleNamespace(
        update_assignment=AsyncMock(
            side_effect=SubscriptionPortalAccessDeniedError("Only DEV can change plan assignment")
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            UPDATE_ASSIGNMENT_ENDPOINT(
                subscription_id=88,
                payload=SubscriptionAssignmentRequest(plan_id=55),
                current_user=current_user,
                subscription_portal_service=subscription_portal_service,
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only DEV can change plan assignment"
