from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.core.enums import Locale, PointsExchangeType
from src.infrastructure.database.models.dto import ReferralSettingsDto, UserDto
from src.services.referral_exchange import ReferralExchangeService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 101, points: int = 3) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Referral User",
        language=Locale.EN,
        points=points,
    )


def build_service(
    *,
    user: UserDto | None = None,
    referral_settings: ReferralSettingsDto | None = None,
    plans: list[object] | None = None,
) -> ReferralExchangeService:
    return ReferralExchangeService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=SimpleNamespace(),
        settings_service=SimpleNamespace(
            get_referral_settings=AsyncMock(
                return_value=referral_settings or ReferralSettingsDto()
            )
        ),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user or build_user())),
        subscription_service=SimpleNamespace(get_all_by_user=AsyncMock(return_value=[])),
        plan_service=SimpleNamespace(get_all=AsyncMock(return_value=plans or [])),
        promocode_service=SimpleNamespace(get_by_code=AsyncMock(return_value=None)),
        remnawave_service=SimpleNamespace(),
    )


def test_subscription_days_option_stays_visible_with_subscription_required_reason() -> None:
    service = build_service()

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
    service = build_service(
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
