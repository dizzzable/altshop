from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from aiogram.types import Message

from src.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralInviteSource,
    ReferralLevel,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import (
    ReferralDto,
    ReferralSettingsDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.plan import PlanSnapshotDto
from src.infrastructure.database.models.dto.transaction import PriceDetailsDto
from src.services.referral import ReferralService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int, name: str = "User") -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=name,
        language=Locale.EN,
    )


def build_transaction(
    *,
    transaction_id: int = 1,
    purchase_type: PurchaseType = PurchaseType.NEW,
    plan_id: int = 10,
    user: UserDto | None = None,
) -> TransactionDto:
    plan = PlanSnapshotDto.test()
    plan.id = plan_id
    plan.name = f"Plan {plan_id}"
    plan.duration = 30
    return TransactionDto(
        id=transaction_id,
        payment_id=uuid4(),
        status=TransactionStatus.COMPLETED,
        purchase_type=purchase_type,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(
            original_amount=Decimal("199"),
            final_amount=Decimal("199"),
        ),
        currency=Currency.RUB,
        plan=plan,
        user=user,
    )


def build_referral(*, referrer: UserDto, referred: UserDto) -> ReferralDto:
    return ReferralDto(
        id=77,
        level=ReferralLevel.FIRST,
        invite_source=ReferralInviteSource.UNKNOWN,
        referrer=referrer,
        referred=referred,
    )


def build_service(*, referral_settings: ReferralSettingsDto | None = None) -> ReferralService:
    return ReferralService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=SimpleNamespace(
            repository=SimpleNamespace(
                referrals=SimpleNamespace(),
                referral_invites=SimpleNamespace(),
                partners=SimpleNamespace(),
            )
        ),
        user_service=SimpleNamespace(
            clear_user_cache=AsyncMock(),
            get=AsyncMock(return_value=None),
            get_by_referral_code=AsyncMock(return_value=None),
        ),
        settings_service=SimpleNamespace(
            get_referral_settings=AsyncMock(
                return_value=referral_settings or ReferralSettingsDto()
            ),
            is_referral_enable=AsyncMock(return_value=True),
        ),
        notification_service=MagicMock(),
    )


def build_start_event(payload: str) -> Message:
    return Message.model_construct(text=f"/start {payload}")


def test_handle_referral_prefers_valid_invite_over_partner_code() -> None:
    service = build_service()
    service.resolve_invite_token = AsyncMock(
        return_value=(SimpleNamespace(token="TOKEN123"), build_user(telegram_id=201), None)
    )  # type: ignore[method-assign]
    service.get_partner_referrer_by_code = AsyncMock(return_value=build_user(telegram_id=202))  # type: ignore[method-assign]
    service._attach_referral = AsyncMock()  # type: ignore[method-assign]

    target_user = build_user(telegram_id=200)
    run_async(service.handle_referral(target_user, "ref_TOKEN123", source=ReferralInviteSource.WEB))

    service._attach_referral.assert_awaited_once_with(
        user=target_user,
        referrer=build_user(telegram_id=201),
        source=ReferralInviteSource.WEB,
        enforce_slot_capacity=True,
    )
    service.get_partner_referrer_by_code.assert_not_awaited()


def test_handle_referral_falls_back_to_partner_code_when_invite_is_blocked() -> None:
    service = build_service()
    partner_referrer = build_user(telegram_id=302)
    service.resolve_invite_token = AsyncMock(
        return_value=(SimpleNamespace(token="TOKEN123"), None, "EXPIRED")
    )  # type: ignore[method-assign]
    service.get_partner_referrer_by_code = AsyncMock(return_value=partner_referrer)  # type: ignore[method-assign]
    service._attach_referral = AsyncMock()  # type: ignore[method-assign]

    target_user = build_user(telegram_id=301)
    run_async(service.handle_referral(target_user, "ref_TOKEN123"))

    service._attach_referral.assert_awaited_once_with(
        user=target_user,
        referrer=partner_referrer,
        source=ReferralInviteSource.UNKNOWN,
        enforce_slot_capacity=False,
    )


def test_assign_referral_rewards_skips_non_eligible_plan_ids() -> None:
    settings = ReferralSettingsDto(eligible_plan_ids=[99])
    service = build_service(referral_settings=settings)
    service.get_referral_by_referred = AsyncMock()  # type: ignore[method-assign]
    service._mark_referral_as_qualified = AsyncMock()  # type: ignore[method-assign]

    transaction = build_transaction(plan_id=10, user=build_user(telegram_id=401))
    run_async(service.assign_referral_rewards(transaction))

    service.get_referral_by_referred.assert_not_awaited()
    service._mark_referral_as_qualified.assert_not_awaited()


def test_assign_referral_rewards_skips_non_new_under_first_payment_strategy() -> None:
    settings = ReferralSettingsDto(accrual_strategy=ReferralAccrualStrategy.ON_FIRST_PAYMENT)
    service = build_service(referral_settings=settings)
    service.get_referral_by_referred = AsyncMock()  # type: ignore[method-assign]
    service._mark_referral_as_qualified = AsyncMock()  # type: ignore[method-assign]

    transaction = build_transaction(
        purchase_type=PurchaseType.RENEW,
        user=build_user(telegram_id=402),
    )
    run_async(service.assign_referral_rewards(transaction))

    service.get_referral_by_referred.assert_not_awaited()
    service._mark_referral_as_qualified.assert_not_awaited()


def test_issue_referral_reward_for_level_skips_active_partner_referrer() -> None:
    service = build_service()
    service.uow.repository.partners.get_partner_by_user = AsyncMock(
        return_value=SimpleNamespace(is_active=True)
    )
    service.create_reward = AsyncMock()  # type: ignore[method-assign]

    referred_user = build_user(telegram_id=501, name="Referred")
    referrer = build_user(telegram_id=502, name="Referrer")
    referral = build_referral(referrer=referrer, referred=referred_user)
    settings = ReferralSettingsDto()
    task = SimpleNamespace(kiq=AsyncMock())

    run_async(
        service._issue_referral_reward_for_level(
            settings=settings,
            transaction=build_transaction(user=referred_user),
            referral=referral,
            referred_user=referred_user,
            level=ReferralLevel.FIRST,
            referrer=referrer,
            task=task,
        )
    )

    service.create_reward.assert_not_awaited()
    task.kiq.assert_not_awaited()


def test_get_referrer_by_event_prefers_invite_then_partner_fallback() -> None:
    service = build_service()
    invite_referrer = build_user(telegram_id=601)
    partner_referrer = build_user(telegram_id=602)
    event = build_start_event("ref_TOKEN123")

    service.resolve_invite_token = AsyncMock(
        side_effect=[
            (SimpleNamespace(token="TOKEN123"), invite_referrer, None),
            (SimpleNamespace(token="TOKEN123"), None, "EXPIRED"),
        ]
    )  # type: ignore[method-assign]
    service.get_partner_referrer_by_code = AsyncMock(return_value=partner_referrer)  # type: ignore[method-assign]

    first = run_async(service.get_referrer_by_event(event, user_telegram_id=700))
    second = run_async(service.get_referrer_by_event(event, user_telegram_id=701))

    assert first == invite_referrer
    assert second == partner_referrer


def test_is_referral_event_checks_start_ref_payload_before_validation() -> None:
    service = build_service()
    service.is_valid_invite_or_partner_code = AsyncMock(return_value=True)  # type: ignore[method-assign]

    non_ref_event = Message.model_construct(text="/start")
    ref_event = build_start_event("ref_TOKEN123")

    non_ref_result = run_async(service.is_referral_event(non_ref_event, user_telegram_id=801))
    ref_result = run_async(service.is_referral_event(ref_event, user_telegram_id=802))

    assert non_ref_result is False
    assert ref_result is True
    service.is_valid_invite_or_partner_code.assert_awaited_once_with(
        "ref_TOKEN123",
        user_telegram_id=802,
    )
