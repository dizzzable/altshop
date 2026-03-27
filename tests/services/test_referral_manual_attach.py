from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import TransactionDto, UserDto
from src.infrastructure.database.models.dto.plan import PlanSnapshotDto
from src.infrastructure.database.models.dto.transaction import PriceDetailsDto
from src.services.referral import ReferralService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int, name: str) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=name,
        language=Locale.EN,
    )


def build_transaction(*, transaction_id: int, amount: str) -> TransactionDto:
    return TransactionDto(
        id=transaction_id,
        payment_id=uuid4(),
        status=TransactionStatus.COMPLETED,
        purchase_type=PurchaseType.NEW,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(
            original_amount=Decimal(amount),
            final_amount=Decimal(amount),
        ),
        currency=Currency.RUB,
        plan=PlanSnapshotDto.test(),
    )


def build_service() -> ReferralService:
    return ReferralService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=SimpleNamespace(repository=SimpleNamespace()),
        user_service=SimpleNamespace(clear_user_cache=AsyncMock()),
        settings_service=SimpleNamespace(is_referral_enable=AsyncMock(return_value=True)),
        notification_service=MagicMock(),
    )


def test_attach_referrer_manually_replays_paid_transactions() -> None:
    service = build_service()
    service.has_referral_attribution = AsyncMock(return_value=False)  # type: ignore[method-assign]
    service._attach_referral = AsyncMock()  # type: ignore[method-assign]
    service.assign_referral_rewards = AsyncMock()  # type: ignore[method-assign]

    target_user = build_user(telegram_id=301, name="Target")
    referrer = build_user(telegram_id=302, name="Referrer")
    paid_transaction = build_transaction(transaction_id=11, amount="199")
    free_transaction = build_transaction(transaction_id=12, amount="0")

    partner_service = SimpleNamespace(
        has_partner_attribution=AsyncMock(return_value=False),
        attach_partner_referral_chain=AsyncMock(return_value=True),
        process_partner_earning=AsyncMock(),
    )
    transaction_service = SimpleNamespace(
        get_completed_by_user_chronological=AsyncMock(
            return_value=[paid_transaction, free_transaction]
        )
    )

    result = run_async(
        service.attach_referrer_manually(
            user=target_user,
            referrer=referrer,
            partner_service=partner_service,
            transaction_service=transaction_service,
        )
    )

    assert result.historical_payments_processed == 1
    assert result.partner_chain_attached is True
    service._attach_referral.assert_awaited_once()
    service.assign_referral_rewards.assert_awaited_once()
    partner_service.attach_partner_referral_chain.assert_awaited_once_with(
        user=target_user,
        referrer=referrer,
    )
    partner_service.process_partner_earning.assert_awaited_once_with(
        payer_user_id=target_user.telegram_id,
        payment_amount=Decimal("199"),
        gateway_type=PaymentGatewayType.PLATEGA,
        source_transaction_id=11,
    )


def test_attach_referrer_manually_fails_when_user_is_already_referred() -> None:
    service = build_service()
    service.has_referral_attribution = AsyncMock(return_value=True)  # type: ignore[method-assign]
    service._attach_referral = AsyncMock()  # type: ignore[method-assign]

    target_user = build_user(telegram_id=401, name="Target")
    referrer = build_user(telegram_id=402, name="Referrer")

    partner_service = SimpleNamespace(has_partner_attribution=AsyncMock(return_value=False))
    transaction_service = SimpleNamespace(get_completed_by_user_chronological=AsyncMock())

    try:
        run_async(
            service.attach_referrer_manually(
                user=target_user,
                referrer=referrer,
                partner_service=partner_service,
                transaction_service=transaction_service,
            )
        )
    except ValueError as error:
        assert str(error) == "User already has referral attribution"
    else:
        raise AssertionError("Expected ValueError for already referred user")

    service._attach_referral.assert_not_awaited()
