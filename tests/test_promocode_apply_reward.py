from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import PlanType, PromocodeRewardType, SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    PromocodeDto,
    SubscriptionDto,
    UserDto,
)
from src.services.promocode import PromocodeService


def _build_service() -> PromocodeService:
    service = object.__new__(PromocodeService)
    service.remnawave_service = SimpleNamespace(
        updated_user=AsyncMock(
            return_value=SimpleNamespace(
                expire_at=datetime_now() + timedelta(days=60),
                status=SubscriptionStatus.ACTIVE,
                subscription_url="https://sub.local/panel",
            )
        ),
        create_user=AsyncMock(
            return_value=SimpleNamespace(
                uuid=uuid4(),
                status=SubscriptionStatus.ACTIVE,
                expire_at=datetime_now() + timedelta(days=30),
                subscription_url="https://sub.local/new",
            )
        ),
        get_subscription_url=AsyncMock(return_value="https://sub.local/new"),
    )
    return service


def _build_user() -> UserDto:
    return UserDto(
        telegram_id=1001,
        referral_code="ref1001",
        name="Promo User",
    )


def _build_plan(
    *,
    duration: int = 30,
    traffic_limit: int = 50,
    device_limit: int = 3,
) -> PlanSnapshotDto:
    return PlanSnapshotDto(
        id=11,
        name="Promo Plan",
        tag="PROMO",
        type=PlanType.UNLIMITED,
        traffic_limit=traffic_limit,
        device_limit=device_limit,
        duration=duration,
        internal_squads=[],
    )


def _build_subscription(*, user: UserDto, plan: PlanSnapshotDto) -> SubscriptionDto:
    return SubscriptionDto(
        id=222,
        user_remna_id=uuid4(),
        user_telegram_id=user.telegram_id,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=15),
        url="https://sub.local/current",
        plan=plan,
    )


def test_apply_reward_personal_discount_updates_user_profile() -> None:
    service = _build_service()
    user = _build_user()
    user_service = SimpleNamespace(update=AsyncMock(return_value=user))
    promocode = PromocodeDto(
        id=1,
        code="PROMO_PERSONAL",
        is_active=True,
        reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
        reward=20,
    )

    applied = asyncio.run(
        service._apply_reward(
            promocode=promocode,
            user=user,
            user_service=user_service,
        )
    )

    assert applied is True
    assert user.personal_discount == 20
    user_service.update.assert_awaited_once_with(user)


def test_apply_reward_subscription_target_adds_duration() -> None:
    service = _build_service()
    user = _build_user()
    user_service = SimpleNamespace(update=AsyncMock(return_value=user))
    plan = _build_plan(duration=7)
    subscription = _build_subscription(user=user, plan=_build_plan(duration=30))
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(return_value=subscription),
        create=AsyncMock(return_value=subscription),
    )
    promocode = PromocodeDto(
        id=2,
        code="PROMO_SUB_TARGET",
        is_active=True,
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        reward=0,
    )
    promocode.plan = plan

    applied = asyncio.run(
        service._apply_reward(
            promocode=promocode,
            user=user,
            user_service=user_service,
            subscription_service=subscription_service,
            target_subscription_id=subscription.id,
        )
    )

    assert applied is True
    subscription_service.update.assert_awaited_once()
    assert service.remnawave_service.updated_user.await_count == 1


def test_apply_reward_duration_without_subscription_service_returns_false() -> None:
    service = _build_service()
    user = _build_user()
    user_service = SimpleNamespace(update=AsyncMock(return_value=user))
    promocode = PromocodeDto(
        id=3,
        code="PROMO_DURATION",
        is_active=True,
        reward_type=PromocodeRewardType.DURATION,
        reward=5,
    )

    applied = asyncio.run(
        service._apply_reward(
            promocode=promocode,
            user=user,
            user_service=user_service,
            subscription_service=None,
        )
    )

    assert applied is False


def test_apply_reward_devices_updates_subscription_limits() -> None:
    service = _build_service()
    user = _build_user()
    user_service = SimpleNamespace(update=AsyncMock(return_value=user))
    plan = _build_plan(duration=30, device_limit=2)
    subscription = _build_subscription(user=user, plan=plan)
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(return_value=subscription),
        create=AsyncMock(return_value=subscription),
    )
    promocode = PromocodeDto(
        id=4,
        code="PROMO_DEVICES",
        is_active=True,
        reward_type=PromocodeRewardType.DEVICES,
        reward=3,
    )

    applied = asyncio.run(
        service._apply_reward(
            promocode=promocode,
            user=user,
            user_service=user_service,
            subscription_service=subscription_service,
            target_subscription_id=subscription.id,
        )
    )

    assert applied is True
    assert subscription.device_limit == 5
    assert subscription.plan.device_limit == 5
    subscription_service.update.assert_awaited_once()
