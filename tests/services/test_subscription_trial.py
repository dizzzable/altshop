from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.core.enums import Locale, PlanAvailability, PlanType, PurchaseChannel, SubscriptionStatus
from src.infrastructure.database.models.dto import PlanDto, PlanDurationDto, UserDto
from src.services.subscription_trial import (
    TRIAL_REASON_ALREADY_USED,
    TRIAL_REASON_NOT_FIRST_SUBSCRIPTION,
    TRIAL_REASON_TELEGRAM_LINK_REQUIRED,
    SubscriptionTrialService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_trial_plan() -> PlanDto:
    return PlanDto(
        id=77,
        name="Trial",
        type=PlanType.BOTH,
        availability=PlanAvailability.TRIAL,
        is_active=True,
        durations=[PlanDurationDto(days=7)],
    )


def build_user(*, telegram_id: int) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Guest",
        language=Locale.EN,
    )


def build_service(
    *,
    used_trial: bool = False,
    subscriptions: list[object] | None = None,
    partner_attribution: bool = False,
) -> SubscriptionTrialService:
    return SubscriptionTrialService(
        plan_service=SimpleNamespace(
            get_trial_plan=AsyncMock(return_value=build_trial_plan()),
            get=AsyncMock(return_value=build_trial_plan()),
        ),
        partner_service=SimpleNamespace(
            has_partner_attribution=AsyncMock(return_value=partner_attribution)
        ),
        purchase_access_service=SimpleNamespace(assert_can_purchase=AsyncMock(return_value=None)),
        remnawave_service=SimpleNamespace(),
        subscription_service=SimpleNamespace(
            has_used_trial=AsyncMock(return_value=used_trial),
            get_all_by_user=AsyncMock(return_value=subscriptions or []),
            create=AsyncMock(),
        ),
    )


def test_bot_trial_eligibility_does_not_require_linked_telegram() -> None:
    service = build_service()
    user = build_user(telegram_id=-101)

    snapshot = run_async(service.get_eligibility(user, channel=PurchaseChannel.TELEGRAM))

    assert snapshot.eligible is True
    assert snapshot.requires_telegram_link is False
    assert snapshot.trial_plan_id == 77


def test_web_trial_requires_link_when_user_is_not_invited_or_partner_attributed() -> None:
    service = build_service()
    user = build_user(telegram_id=-102)

    snapshot = run_async(service.get_eligibility(user, channel=PurchaseChannel.WEB))

    assert snapshot.eligible is False
    assert snapshot.requires_telegram_link is True
    assert snapshot.reason_code == TRIAL_REASON_TELEGRAM_LINK_REQUIRED


def test_web_trial_allows_invited_user_without_linked_telegram() -> None:
    service = build_service()
    user = build_user(telegram_id=-103)
    user._is_invited_user = True

    snapshot = run_async(service.get_eligibility(user, channel=PurchaseChannel.WEB))

    assert snapshot.eligible is True
    assert snapshot.requires_telegram_link is False


def test_web_trial_allows_partner_attributed_user_without_linked_telegram() -> None:
    service = build_service(partner_attribution=True)
    user = build_user(telegram_id=-104)

    snapshot = run_async(service.get_eligibility(user, channel=PurchaseChannel.WEB))

    assert snapshot.eligible is True
    service.partner_service.has_partner_attribution.assert_awaited_once_with(-104)


def test_trial_is_blocked_after_trial_was_already_used() -> None:
    service = build_service(used_trial=True)
    user = build_user(telegram_id=105)

    snapshot = run_async(service.get_eligibility(user, channel=PurchaseChannel.WEB))

    assert snapshot.eligible is False
    assert snapshot.reason_code == TRIAL_REASON_ALREADY_USED


def test_trial_is_blocked_when_user_already_has_subscription() -> None:
    active_subscription = SimpleNamespace(status=SubscriptionStatus.ACTIVE)
    service = build_service(subscriptions=[active_subscription])
    user = build_user(telegram_id=106)

    snapshot = run_async(service.get_eligibility(user, channel=PurchaseChannel.WEB))

    assert snapshot.eligible is False
    assert snapshot.reason_code == TRIAL_REASON_NOT_FIRST_SUBSCRIPTION
