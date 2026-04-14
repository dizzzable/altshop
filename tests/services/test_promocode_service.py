from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from remnawave.enums.users import TrafficLimitStrategy

from src.core.enums import (
    Locale,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    SubscriptionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    PromocodeDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.promocode import PromocodeActivationBaseDto
from src.services.promocode import ActivationError, ActivationResult, PromocodeService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_plan_snapshot(*, duration: int = 30) -> PlanSnapshotDto:
    return PlanSnapshotDto(
        id=1,
        name="Starter",
        tag="starter",
        type=PlanType.BOTH,
        traffic_limit=100,
        device_limit=2,
        duration=duration,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        internal_squads=[],
        external_squad=None,
    )


def build_user(
    *,
    telegram_id: int = 100,
    current_subscription: SubscriptionDto | None = None,
    invited: bool = False,
) -> UserDto:
    user = UserDto(
        telegram_id=telegram_id,
        name="User",
        language=Locale.EN,
        current_subscription=current_subscription,
    )
    user._is_invited_user = invited
    return user


def build_subscription(
    *,
    subscription_id: int = 10,
    expire_days: int = 30,
    traffic_limit: int = 100,
    device_limit: int = 2,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=100,
        status=SubscriptionStatus.ACTIVE,
        is_trial=False,
        traffic_limit=traffic_limit,
        device_limit=device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=expire_days),
        url="https://example.com/sub",
        plan=build_plan_snapshot(duration=30),
    )


def build_promocode(
    *,
    code: str = "PROMO",
    availability: PromocodeAvailability = PromocodeAvailability.ALL,
    reward_type: PromocodeRewardType = PromocodeRewardType.PERSONAL_DISCOUNT,
    reward: int | None = 10,
    is_active: bool = True,
    lifetime: int = -1,
    created_at=None,
    max_activations: int = -1,
    activations: list[PromocodeActivationBaseDto] | None = None,
    allowed_user_ids: list[int] | None = None,
    allowed_plan_ids: list[int] | None = None,
    plan: PlanSnapshotDto | None = None,
) -> PromocodeDto:
    return PromocodeDto(
        id=1,
        code=code,
        availability=availability,
        reward_type=reward_type,
        reward=reward,
        is_active=is_active,
        lifetime=lifetime,
        created_at=created_at,
        max_activations=max_activations,
        activations=activations or [],
        allowed_user_ids=allowed_user_ids or [],
        allowed_plan_ids=allowed_plan_ids or [],
        plan=plan,
    )


def build_service() -> tuple[PromocodeService, SimpleNamespace, SimpleNamespace]:
    promocode_session = SimpleNamespace(add=MagicMock(), flush=AsyncMock())
    promocode_repo = SimpleNamespace(
        session=promocode_session,
        create=AsyncMock(),
        get=AsyncMock(),
        get_by_code=AsyncMock(),
        get_all=AsyncMock(return_value=[]),
        update=AsyncMock(),
        delete=AsyncMock(return_value=False),
        filter_by_type=AsyncMock(return_value=[]),
        filter_active=AsyncMock(return_value=[]),
        count_activations_by_user=AsyncMock(return_value=0),
        get_activations_by_user=AsyncMock(return_value=[]),
    )
    uow = SimpleNamespace(
        repository=SimpleNamespace(promocodes=promocode_repo),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    service = PromocodeService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave_service=SimpleNamespace(),
        uow=uow,
    )
    return service, promocode_repo, uow


def test_check_availability_preserves_new_existing_invited_allowed_rules() -> None:
    service, _repo, _uow = build_service()
    active_subscription = build_subscription()

    invited_user = build_user(invited=True)
    allowed_user = build_user(telegram_id=777)
    existing_user = build_user(current_subscription=active_subscription)
    new_user = build_user()

    assert run_async(
        service._check_availability(
            build_promocode(availability=PromocodeAvailability.ALL),
            new_user,
        )
    ) is True
    assert run_async(
        service._check_availability(
            build_promocode(availability=PromocodeAvailability.NEW),
            new_user,
        )
    ) is True
    assert run_async(
        service._check_availability(
            build_promocode(availability=PromocodeAvailability.NEW),
            existing_user,
        )
    ) is False
    assert run_async(
        service._check_availability(
            build_promocode(availability=PromocodeAvailability.EXISTING),
            existing_user,
        )
    ) is True
    assert run_async(
        service._check_availability(
            build_promocode(availability=PromocodeAvailability.INVITED),
            invited_user,
        )
    ) is True
    assert run_async(
        service._check_availability(
            build_promocode(
                availability=PromocodeAvailability.ALLOWED,
                allowed_user_ids=[777],
            ),
            allowed_user,
        )
    ) is True
    assert run_async(
        service._check_availability(
            build_promocode(
                availability=PromocodeAvailability.ALLOWED,
                allowed_user_ids=[555],
            ),
            allowed_user,
        )
    ) is False


@pytest.mark.parametrize(
    ("promocode", "already_activated", "available", "expected_error", "expected_key"),
    [
        (None, False, True, ActivationError.NOT_FOUND, "ntf-promocode-not-found"),
        (
            build_promocode(is_active=False),
            False,
            True,
            ActivationError.INACTIVE,
            "ntf-promocode-inactive",
        ),
        (
            build_promocode(
                lifetime=1,
                created_at=datetime_now() - timedelta(days=2),
            ),
            False,
            True,
            ActivationError.EXPIRED,
            "ntf-promocode-expired",
        ),
        (
            build_promocode(
                max_activations=1,
                activations=[
                    PromocodeActivationBaseDto(
                        id=1,
                        promocode_id=1,
                        user_telegram_id=100,
                        promocode_code="PROMO",
                        reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
                        reward_value=10,
                    )
                ],
            ),
            False,
            True,
            ActivationError.DEPLETED,
            "ntf-promocode-depleted",
        ),
        (
            build_promocode(),
            True,
            True,
            ActivationError.ALREADY_ACTIVATED,
            "ntf-promocode-already-activated",
        ),
        (
            build_promocode(),
            False,
            False,
            ActivationError.NOT_AVAILABLE_FOR_USER,
            "ntf-promocode-not-available",
        ),
    ],
)
def test_validate_promocode_returns_expected_failures(
    promocode: PromocodeDto | None,
    already_activated: bool,
    available: bool,
    expected_error: ActivationError,
    expected_key: str,
) -> None:
    service, _repo, _uow = build_service()
    service.get_by_code = AsyncMock(return_value=promocode)  # type: ignore[method-assign]
    service.check_user_activation = AsyncMock(return_value=already_activated)  # type: ignore[method-assign]
    service._check_availability = AsyncMock(return_value=available)  # type: ignore[method-assign]

    result = run_async(service.validate_promocode("promo", build_user()))

    assert result.success is False
    assert result.error == expected_error
    assert result.message_key == expected_key


def test_activate_creates_activation_and_rolls_back_when_reward_fails() -> None:
    service, promocode_repo, uow = build_service()
    promocode = build_promocode(reward_type=PromocodeRewardType.PERSONAL_DISCOUNT)
    service.validate_promocode = AsyncMock(  # type: ignore[method-assign]
        return_value=ActivationResult(
            success=True,
            promocode=promocode,
            message_key="ntf-promocode-valid",
        )
    )
    service._apply_reward = AsyncMock(return_value=False)  # type: ignore[method-assign]

    result = run_async(
        service.activate(
            "promo",
            build_user(),
            user_service=SimpleNamespace(),
        )
    )

    assert result.success is False
    assert result.message_key == "ntf-promocode-reward-failed"
    promocode_repo.session.add.assert_called_once()
    assert promocode_repo.session.flush.await_count == 1
    assert uow.rollback.await_count == 1
    assert uow.commit.await_count == 0


def test_apply_subscription_reward_extends_selected_subscription() -> None:
    service, _repo, _uow = build_service()
    subscription = build_subscription(expire_days=10)
    original_expire_at = subscription.expire_at
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(),
    )
    service._sync_subscription_with_panel = AsyncMock()  # type: ignore[method-assign]

    success = run_async(
        service._apply_subscription_reward(
            promocode=build_promocode(
                reward_type=PromocodeRewardType.SUBSCRIPTION,
                reward=None,
                plan=build_plan_snapshot(duration=15),
            ),
            user=build_user(),
            subscription_service=subscription_service,
            target_subscription_id=subscription.id,
        )
    )

    assert success is True
    assert subscription.expire_at == original_expire_at + timedelta(days=15)
    service._sync_subscription_with_panel.assert_awaited_once()


def test_apply_subscription_reward_creates_new_subscription_when_needed() -> None:
    service, _repo, _uow = build_service()
    created_user = SimpleNamespace(
        uuid=uuid4(),
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime_now() + timedelta(days=30),
        subscription_url="",
    )
    service.remnawave_service = SimpleNamespace(
        create_user=AsyncMock(return_value=created_user),
        get_subscription_url=AsyncMock(return_value="https://example.com/generated"),
    )
    subscription_service = SimpleNamespace(
        create=AsyncMock(),
    )

    success = run_async(
        service._apply_subscription_reward(
            promocode=build_promocode(
                reward_type=PromocodeRewardType.SUBSCRIPTION,
                reward=None,
                plan=build_plan_snapshot(duration=30),
            ),
            user=build_user(),
            subscription_service=subscription_service,
            target_subscription_id=None,
        )
    )

    assert success is True
    assert subscription_service.create.await_count == 1
    created_subscription = subscription_service.create.await_args.args[1]
    assert created_subscription.user_remna_id == created_user.uuid
    assert created_subscription.url == "https://example.com/generated"


@pytest.mark.parametrize(
    ("reward_type", "reward_value", "expected_traffic", "expected_devices", "expected_days"),
    [
        (PromocodeRewardType.DURATION, 7, 100, 2, 7),
        (PromocodeRewardType.TRAFFIC, 50, 150, 2, 0),
        (PromocodeRewardType.DEVICES, 3, 100, 5, 0),
    ],
)
def test_apply_subscription_mutation_reward_updates_subscription_and_syncs(
    reward_type: PromocodeRewardType,
    reward_value: int,
    expected_traffic: int,
    expected_devices: int,
    expected_days: int,
) -> None:
    service, _repo, _uow = build_service()
    subscription = build_subscription(traffic_limit=100, device_limit=2, expire_days=10)
    original_expire_at = subscription.expire_at
    service._sync_subscription_with_panel = AsyncMock()  # type: ignore[method-assign]

    success = run_async(
        service._apply_subscription_mutation_reward(
            reward_type=reward_type,
            reward=reward_value,
            target_id=subscription.id or 10,
            user=build_user(),
            subscription=subscription,
            subscription_service=SimpleNamespace(),
        )
    )

    assert success is True
    assert subscription.traffic_limit == expected_traffic
    assert subscription.device_limit == expected_devices
    assert subscription.plan.traffic_limit == expected_traffic
    assert subscription.plan.device_limit == expected_devices
    if expected_days:
        assert subscription.expire_at == original_expire_at + timedelta(days=expected_days)
    else:
        assert subscription.expire_at == original_expire_at
    service._sync_subscription_with_panel.assert_awaited_once()


@pytest.mark.parametrize(
    ("reward_type", "field_name"),
    [
        (PromocodeRewardType.PERSONAL_DISCOUNT, "personal_discount"),
        (PromocodeRewardType.PURCHASE_DISCOUNT, "purchase_discount"),
    ],
)
def test_apply_user_discount_reward_mutates_only_user(
    reward_type: PromocodeRewardType,
    field_name: str,
) -> None:
    service, _repo, _uow = build_service()
    user = build_user()
    user_service = SimpleNamespace(update=AsyncMock())

    success = run_async(
        service._apply_user_discount_reward(
            reward_type=reward_type,
            reward=15,
            user=user,
            user_service=user_service,
        )
    )

    assert success is True
    assert getattr(user, field_name) == 15
    assert user_service.update.await_count == 1


def test_get_activations_count_uses_service_getter() -> None:
    service, _repo, _uow = build_service()
    service.get = AsyncMock(  # type: ignore[method-assign]
        return_value=build_promocode(
            activations=[
                PromocodeActivationBaseDto(
                    id=1,
                    promocode_id=1,
                    user_telegram_id=1,
                    promocode_code="PROMO",
                    reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
                    reward_value=10,
                ),
                PromocodeActivationBaseDto(
                    id=2,
                    promocode_id=1,
                    user_telegram_id=2,
                    promocode_code="PROMO",
                    reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
                    reward_value=10,
                ),
            ]
        )
    )

    count = run_async(service.get_activations_count(1))

    assert count == 2


def test_get_user_activations_short_circuits_when_empty() -> None:
    service, promocode_repo, _uow = build_service()
    promocode_repo.count_activations_by_user = AsyncMock(return_value=0)

    activations = run_async(service.get_user_activations(100))

    assert activations == []
    assert promocode_repo.get_activations_by_user.await_count == 0


def test_get_user_activation_history_uses_limit_and_offset() -> None:
    service, promocode_repo, _uow = build_service()
    promocode_repo.count_activations_by_user = AsyncMock(return_value=25)
    promocode_repo.get_activations_by_user = AsyncMock(return_value=[])

    activations, total = run_async(service.get_user_activation_history(100, page=2, limit=10))

    assert activations == []
    assert total == 25
    promocode_repo.get_activations_by_user.assert_awaited_once_with(100, limit=10, offset=10)
