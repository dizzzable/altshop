from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, call
from uuid import uuid4

from remnawave.enums.users import TrafficLimitStrategy

import src.services.subscription_plan_sync as subscription_plan_sync_module
from src.core.constants import TIMEZONE
from src.core.enums import Locale, PlanType, SubscriptionStatus, UserRole
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)
from src.services.subscription import SubscriptionService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            subscriptions=SimpleNamespace(
                create=AsyncMock(),
                get=AsyncMock(return_value=None),
                get_by_remna_id=AsyncMock(return_value=None),
                get_all_by_user=AsyncMock(return_value=[]),
                get_all=AsyncMock(return_value=[]),
                get_by_ids=AsyncMock(return_value=[]),
                update=AsyncMock(return_value=None),
                rebind_user=AsyncMock(return_value=None),
                filter_by_plan_id=AsyncMock(return_value=[]),
                _count=AsyncMock(return_value=0),
                _get_many=AsyncMock(return_value=[]),
            ),
            users=SimpleNamespace(
                get=AsyncMock(return_value=None),
                get_by_ids=AsyncMock(return_value=[]),
                _get_many=AsyncMock(return_value=[]),
            ),
        )
        self.commit = AsyncMock()


def build_service(*, user_service=None, uow=None) -> tuple[SubscriptionService, DummyUow]:
    actual_uow = uow or DummyUow()
    service = SubscriptionService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        uow=actual_uow,
        user_service=user_service or SimpleNamespace(
            set_current_subscription=AsyncMock(),
            clear_user_cache=AsyncMock(),
        ),
    )
    return service, actual_uow


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Test User",
        username="alice",
        role=UserRole.USER,
        language=Locale.EN,
    )


def build_plan(*, plan_id: int = 1, name: str = "Plan", tag: str | None = "PLAN") -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name,
        tag=tag,
        is_active=True,
        type=PlanType.BOTH,
        traffic_limit=100,
        device_limit=2,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        internal_squads=[],
        external_squad=None,
        durations=[],
        allowed_user_ids=[],
    )


def build_subscription(
    *,
    subscription_id: int = 10,
    user_telegram_id: int = 100,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    is_trial: bool = False,
    plan: PlanDto | None = None,
) -> SubscriptionDto:
    source_plan = plan or build_plan()
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=status,
        is_trial=is_trial,
        traffic_limit=source_plan.traffic_limit,
        device_limit=source_plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now(),
        url="https://example.test/subscription",
        plan=PlanSnapshotDto.from_plan(source_plan, 30),
    )


def make_user_model(
    telegram_id: int,
    *,
    current_subscription=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=None,
        telegram_id=telegram_id,
        username="alice",
        referral_code="REFCODE",
        name="Test User",
        role=UserRole.USER,
        language=Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
        partner_balance_currency_override=None,
        referral_invite_settings=None,
        max_subscriptions=None,
        created_at=None,
        updated_at=None,
        current_subscription=current_subscription,
        subscriptions=[],
        referral=None,
        current_subscription_id=getattr(current_subscription, "id", None),
    )


def make_subscription_model(
    subscription: SubscriptionDto,
    *,
    user=None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=subscription.id,
        user_remna_id=subscription.user_remna_id,
        user_telegram_id=subscription.user_telegram_id,
        status=subscription.status,
        is_trial=subscription.is_trial,
        traffic_limit=subscription.traffic_limit,
        traffic_used=subscription.traffic_used,
        device_limit=subscription.device_limit,
        devices_count=subscription.devices_count,
        internal_squads=subscription.internal_squads,
        external_squad=subscription.external_squad,
        expire_at=subscription.expire_at,
        url=subscription.url,
        device_type=subscription.device_type,
        plan=subscription.plan.model_dump(mode="json"),
        created_at=None,
        updated_at=None,
        user=user,
    )


def test_create_sets_current_subscription_for_user() -> None:
    user = build_user(telegram_id=100)
    subscription = build_subscription()
    created_model = make_subscription_model(subscription)
    user_service = SimpleNamespace(
        set_current_subscription=AsyncMock(),
        clear_user_cache=AsyncMock(),
    )
    service, uow = build_service(user_service=user_service)
    uow.repository.subscriptions.create = AsyncMock(return_value=created_model)

    result = run_async(service.create(user, subscription))

    assert result.id == subscription.id
    user_service.set_current_subscription.assert_awaited_once_with(
        telegram_id=user.telegram_id,
        subscription_id=subscription.id,
    )
    uow.commit.assert_awaited_once()


def test_update_persists_allowed_fields_and_plan_snapshot_and_clears_cache() -> None:
    user = build_user(telegram_id=100)
    plan = build_plan(name="Starter", tag="OLD")
    subscription = build_subscription(plan=plan)
    subscription.user = user
    subscription.traffic_limit = 250
    subscription.plan.name = "Starter Plus"
    updated_model = make_subscription_model(subscription, user=make_user_model(user.telegram_id))
    user_service = SimpleNamespace(
        set_current_subscription=AsyncMock(),
        clear_user_cache=AsyncMock(),
    )
    service, uow = build_service(user_service=user_service)
    uow.repository.subscriptions.update = AsyncMock(return_value=updated_model)

    result = run_async(service.update(subscription))

    assert result is not None
    kwargs = uow.repository.subscriptions.update.await_args.kwargs
    assert kwargs["subscription_id"] == subscription.id
    assert kwargs["traffic_limit"] == 250
    assert kwargs["plan"]["name"] == "Starter Plus"
    user_service.clear_user_cache.assert_awaited_once_with(telegram_id=user.telegram_id)
    uow.commit.assert_awaited_once()


def test_rebind_user_clears_both_previous_and_new_user_caches() -> None:
    subscription = build_subscription()
    updated_model = make_subscription_model(subscription)
    user_service = SimpleNamespace(
        set_current_subscription=AsyncMock(),
        clear_user_cache=AsyncMock(),
    )
    service, uow = build_service(user_service=user_service)
    uow.repository.subscriptions.rebind_user = AsyncMock(return_value=updated_model)

    result = run_async(
        service.rebind_user(
            subscription_id=subscription.id or 0,
            user_telegram_id=200,
            previous_user_telegram_id=100,
        )
    )

    assert result is not None
    assert user_service.clear_user_cache.await_args_list == [call(100), call(200)]
    uow.commit.assert_awaited_once()


def test_sync_plan_snapshot_metadata_updates_only_non_deleted_and_commits_when_changed() -> None:
    plan = build_plan(plan_id=3, name="Updated", tag="NEW")
    active_subscription = build_subscription(
        subscription_id=1,
        status=SubscriptionStatus.ACTIVE,
        plan=build_plan(plan_id=3, name="Old", tag="OLD"),
    )
    deleted_subscription = build_subscription(
        subscription_id=2,
        status=SubscriptionStatus.DELETED,
        plan=build_plan(plan_id=3, name="Old", tag="OLD"),
    )
    service, uow = build_service()
    uow.repository.subscriptions.filter_by_plan_id = AsyncMock(
        return_value=[
            make_subscription_model(active_subscription),
            make_subscription_model(deleted_subscription),
        ]
    )
    service.update = AsyncMock(return_value=active_subscription)  # type: ignore[method-assign]

    updated_count = run_async(service.sync_plan_snapshot_metadata(plan))

    assert updated_count == 1
    service.update.assert_awaited_once()
    updated_subscription = service.update.await_args.args[0]
    assert updated_subscription.plan.name == "Updated"
    assert updated_subscription.plan.tag == "NEW"
    uow.commit.assert_awaited_once()


def test_get_users_by_plan_returns_only_active_subscriptions_for_plan() -> None:
    active_subscription = SimpleNamespace(user_telegram_id=100, status=SubscriptionStatus.ACTIVE)
    expired_subscription = SimpleNamespace(user_telegram_id=200, status=SubscriptionStatus.EXPIRED)
    active_user = make_user_model(100)
    service, uow = build_service()
    uow.repository.subscriptions.filter_by_plan_id = AsyncMock(
        return_value=[active_subscription, expired_subscription]
    )
    uow.repository.users.get_by_ids = AsyncMock(return_value=[active_user])

    users = run_async(service.get_users_by_plan(5))

    assert [user.telegram_id for user in users] == [100]
    assert uow.repository.users.get_by_ids.await_args.kwargs["telegram_ids"] == [100]


def test_has_used_trial_checks_historical_trial_semantics() -> None:
    captured = {}

    async def fake_count(model, conditions):
        captured["model"] = model
        captured["conditions"] = conditions
        return 1

    service, uow = build_service()
    uow.repository.subscriptions._count = AsyncMock(side_effect=fake_count)

    result = run_async(service.has_used_trial(build_user()))

    assert result is True
    assert "is_trial" in str(captured["conditions"]).lower()
    assert "status" not in str(captured["conditions"]).lower()


def test_delete_subscription_marks_deleted_and_returns_success_flag() -> None:
    service, uow = build_service()
    uow.repository.subscriptions.update = AsyncMock(
        side_effect=[
            make_subscription_model(build_subscription(status=SubscriptionStatus.DELETED)),
            None,
        ]
    )

    assert run_async(service.delete_subscription(11)) is True
    assert run_async(service.delete_subscription(12)) is False
    assert uow.commit.await_count == 2


def test_get_traffic_reset_delta_preserves_existing_strategy_rules(monkeypatch) -> None:
    fixed_now = datetime(2026, 4, 13, 12, 0, 0, tzinfo=TIMEZONE)
    monkeypatch.setattr(subscription_plan_sync_module, "datetime_now", lambda: fixed_now)

    assert SubscriptionService.get_traffic_reset_delta(TrafficLimitStrategy.NO_RESET) is None

    day_delta = SubscriptionService.get_traffic_reset_delta(TrafficLimitStrategy.DAY)
    week_delta = SubscriptionService.get_traffic_reset_delta(TrafficLimitStrategy.WEEK)
    month_delta = SubscriptionService.get_traffic_reset_delta(TrafficLimitStrategy.MONTH)

    assert day_delta == datetime(2026, 4, 14, 0, 0, 0, tzinfo=TIMEZONE) - fixed_now
    assert week_delta == datetime(2026, 4, 20, 0, 5, 0, tzinfo=TIMEZONE) - fixed_now
    assert month_delta == datetime(2026, 5, 1, 0, 10, 0, tzinfo=TIMEZONE) - fixed_now
