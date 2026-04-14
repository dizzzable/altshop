from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.enums import Locale, PlanType, PointsExchangeType, SubscriptionStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    ReferralSettingsDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.settings import ExchangeTypeSettingsDto
from src.services.referral_exchange import ReferralExchangeError, ReferralExchangeService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 101, points: int = 3, purchase_discount: int = 0) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Referral User",
        language=Locale.EN,
        points=points,
        purchase_discount=purchase_discount,
    )


def build_plan(*, plan_id: int = 7, name: str = "Gift Plan", is_active: bool = True) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name,
        is_active=is_active,
        type=PlanType.TRAFFIC,
        traffic_limit=50,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
    )


def build_subscription(
    *,
    subscription_id: int = 9,
    user_telegram_id: int = 101,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    traffic_limit: int = 10,
    expire_at_delta_days: int = 5,
    is_unlimited: bool = False,
) -> SubscriptionDto:
    expire_at = datetime_now() + timedelta(days=expire_at_delta_days)
    if is_unlimited:
        expire_at = expire_at.replace(year=2099)

    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=status,
        traffic_limit=traffic_limit,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=expire_at,
        url="https://example.com/sub",
        plan=PlanSnapshotDto.from_plan(build_plan(plan_id=33, name="Base Plan"), 30),
    )


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            users=SimpleNamespace(
                get_for_update=AsyncMock(),
                update=AsyncMock(),
            )
        )


def build_service(
    *,
    user: UserDto | None = None,
    referral_settings: ReferralSettingsDto | None = None,
    plans: list[PlanDto] | None = None,
    subscriptions: list[SubscriptionDto] | None = None,
    target_subscription: SubscriptionDto | None = None,
) -> tuple[ReferralExchangeService, DummyUow]:
    uow = DummyUow()
    service = ReferralExchangeService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=uow,
        settings_service=SimpleNamespace(
            get_referral_settings=AsyncMock(
                return_value=referral_settings or ReferralSettingsDto()
            )
        ),
        user_service=SimpleNamespace(
            get=AsyncMock(return_value=user or build_user()),
            clear_user_cache=AsyncMock(),
        ),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(return_value=subscriptions or []),
            get=AsyncMock(return_value=target_subscription),
            update=AsyncMock(),
        ),
        plan_service=SimpleNamespace(
            get_all=AsyncMock(return_value=plans or []),
            get=AsyncMock(return_value=(plans or [build_plan()])[0]),
        ),
        promocode_service=SimpleNamespace(
            get_by_code=AsyncMock(return_value=None),
            create=AsyncMock(),
        ),
        remnawave_service=SimpleNamespace(updated_user=AsyncMock()),
    )
    return service, uow


def test_subscription_days_option_stays_visible_with_subscription_required_reason() -> None:
    service, _uow = build_service()

    options = run_async(service.get_options(user_telegram_id=101))

    subscription_days_option = next(
        option for option in options.types if option.type == PointsExchangeType.SUBSCRIPTION_DAYS
    )

    assert subscription_days_option.enabled is True
    assert subscription_days_option.available is False
    assert subscription_days_option.availability_reason == "SUBSCRIPTION_REQUIRED"


def test_gift_subscription_reports_missing_plan_reason() -> None:
    settings = ReferralSettingsDto()
    settings.points_exchange.gift_subscription.enabled = True
    settings.points_exchange.gift_subscription.min_points = 10
    settings.points_exchange.gift_subscription.points_cost = 10
    service, _uow = build_service(
        user=build_user(points=25),
        referral_settings=settings,
        plans=[],
    )

    options = run_async(service.get_options(user_telegram_id=101))

    gift_option = next(
        option for option in options.types if option.type == PointsExchangeType.GIFT_SUBSCRIPTION
    )

    assert gift_option.enabled is True
    assert gift_option.available is False
    assert gift_option.availability_reason == "GIFT_PLAN_REQUIRED"


def test_resolve_availability_reason_prefers_insufficient_points_before_other_flags() -> None:
    reason = ReferralExchangeService._resolve_availability_reason(
        exchange_enabled=True,
        type_enabled=True,
        user_points=1,
        min_points=10,
        points_cost=5,
        computed_value=0,
        requires_subscription=True,
        has_subscriptions=False,
        has_plan_for_gift=False,
    )

    assert reason == "INSUFFICIENT_POINTS"


def test_compute_value_respects_discount_and_traffic_caps() -> None:
    discount_settings = ExchangeTypeSettingsDto(points_cost=5, max_discount_percent=10)
    traffic_settings = ExchangeTypeSettingsDto(points_cost=5, max_traffic_gb=3)

    assert (
        ReferralExchangeService._compute_value(
            PointsExchangeType.DISCOUNT,
            100,
            discount_settings,
        )
        == 10
    )
    assert (
        ReferralExchangeService._compute_value(
            PointsExchangeType.TRAFFIC,
            100,
            traffic_settings,
        )
        == 3
    )


def test_execute_subscription_days_updates_subscription_and_points() -> None:
    user = build_user(points=20)
    subscription = build_subscription()
    settings = ReferralSettingsDto()
    settings.points_exchange.subscription_days.points_cost = 2
    service, uow = build_service(
        user=user,
        referral_settings=settings,
        subscriptions=[subscription],
        target_subscription=subscription,
    )
    uow.repository.users.get_for_update = AsyncMock(
        return_value=SimpleNamespace(**user.model_dump())
    )

    result = run_async(
        service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
            subscription_id=subscription.id,
        )
    )

    assert result.result.days_added == 10
    assert result.points_spent == 20
    assert result.points_balance_after == 0
    service.subscription_service.update.assert_awaited_once()
    service.remnawave_service.updated_user.assert_awaited_once()
    service.user_service.clear_user_cache.assert_awaited_once_with(user.telegram_id)


def test_execute_gift_subscription_creates_promocode_and_debits_points() -> None:
    user = build_user(points=50)
    plan = build_plan(plan_id=12, name="Gift Gold")
    settings = ReferralSettingsDto()
    settings.points_exchange.gift_subscription.enabled = True
    settings.points_exchange.gift_subscription.points_cost = 25
    settings.points_exchange.gift_subscription.gift_plan_id = 12
    settings.points_exchange.gift_subscription.gift_duration_days = 14
    service, uow = build_service(
        user=user,
        referral_settings=settings,
        plans=[plan],
    )
    uow.repository.users.get_for_update = AsyncMock(
        return_value=SimpleNamespace(**user.model_dump())
    )
    service.plan_service.get = AsyncMock(return_value=plan)

    result = run_async(
        service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.GIFT_SUBSCRIPTION,
        )
    )

    assert result.points_spent == 25
    assert result.points_balance_after == 25
    assert result.result.gift_plan_name == "Gift Gold"
    assert result.result.gift_duration_days == 14
    assert result.result.gift_promocode is not None
    service.promocode_service.create.assert_awaited_once()
    uow.repository.users.update.assert_awaited_once_with(user.telegram_id, points=25)


def test_execute_discount_updates_purchase_discount_and_points() -> None:
    user = build_user(points=24, purchase_discount=5)
    settings = ReferralSettingsDto()
    settings.points_exchange.discount.enabled = True
    settings.points_exchange.discount.points_cost = 4
    settings.points_exchange.discount.max_discount_percent = 6
    service, uow = build_service(user=user, referral_settings=settings)
    uow.repository.users.get_for_update = AsyncMock(
        return_value=SimpleNamespace(**user.model_dump())
    )

    result = run_async(
        service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.DISCOUNT,
        )
    )

    assert result.result.discount_percent_added == 6
    assert result.points_spent == 24
    assert result.points_balance_after == 0
    uow.repository.users.update.assert_awaited_once_with(
        user.telegram_id,
        points=0,
        purchase_discount=11,
    )


def test_execute_traffic_updates_subscription_traffic_and_points() -> None:
    user = build_user(points=20)
    subscription = build_subscription(traffic_limit=50)
    settings = ReferralSettingsDto()
    settings.points_exchange.traffic.enabled = True
    settings.points_exchange.traffic.points_cost = 5
    settings.points_exchange.traffic.max_traffic_gb = 3
    service, uow = build_service(
        user=user,
        referral_settings=settings,
        subscriptions=[subscription],
        target_subscription=subscription,
    )
    uow.repository.users.get_for_update = AsyncMock(
        return_value=SimpleNamespace(**user.model_dump())
    )

    result = run_async(
        service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.TRAFFIC,
            subscription_id=subscription.id,
        )
    )

    assert result.result.traffic_gb_added == 3
    assert result.points_spent == 15
    assert result.points_balance_after == 5
    assert subscription.traffic_limit == 53
    service.subscription_service.update.assert_awaited_once()
    service.remnawave_service.updated_user.assert_awaited_once()


def test_execute_rejects_disabled_exchange_type() -> None:
    user = build_user(points=50)
    settings = ReferralSettingsDto()
    settings.points_exchange.discount.enabled = False
    service, uow = build_service(user=user, referral_settings=settings)
    uow.repository.users.get_for_update = AsyncMock(
        return_value=SimpleNamespace(**user.model_dump())
    )

    with pytest.raises(ReferralExchangeError) as error_info:
        run_async(
            service.execute(
                user_telegram_id=user.telegram_id,
                exchange_type=PointsExchangeType.DISCOUNT,
            )
        )

    assert error_info.value.code == "EXCHANGE_TYPE_DISABLED"


def test_get_exchangeable_subscription_rejects_unlimited_or_foreign_subscription() -> None:
    service, _uow = build_service(
        target_subscription=build_subscription(user_telegram_id=999, is_unlimited=True)
    )

    with pytest.raises(ReferralExchangeError) as error_info:
        run_async(
            service._get_exchangeable_subscription(
                user_telegram_id=101,
                subscription_id=9,
            )
        )

    assert error_info.value.code == "SUBSCRIPTION_NOT_FOUND"
