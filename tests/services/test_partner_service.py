from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

from src.core.enums import (
    Currency,
    Locale,
    PartnerAccrualStrategy,
    PartnerLevel,
    PartnerRewardType,
    PaymentGatewayType,
    WithdrawalStatus,
)
from src.infrastructure.database.models.dto import (
    PartnerDto,
    PartnerIndividualSettingsDto,
    UserDto,
)
from src.services.partner import PartnerService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int, name: str = "User") -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=name,
        language=Locale.EN,
    )


def build_partner(
    *,
    partner_id: int,
    telegram_id: int,
    is_active: bool = True,
    balance: int = 0,
    total_earned: int = 0,
    total_withdrawn: int = 0,
    settings: PartnerIndividualSettingsDto | None = None,
) -> PartnerDto:
    return PartnerDto(
        id=partner_id,
        user_telegram_id=telegram_id,
        is_active=is_active,
        balance=balance,
        total_earned=total_earned,
        total_withdrawn=total_withdrawn,
        individual_settings=settings or PartnerIndividualSettingsDto(),
    )


def build_service(
    *,
    partners_repo: SimpleNamespace | None = None,
    referrals_repo: SimpleNamespace | None = None,
    user_service: SimpleNamespace | None = None,
    settings_service: SimpleNamespace | None = None,
    notification_service: SimpleNamespace | None = None,
) -> PartnerService:
    return PartnerService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=SimpleNamespace(
            repository=SimpleNamespace(
                partners=partners_repo or SimpleNamespace(),
                referrals=referrals_repo or SimpleNamespace(),
            )
        ),
        user_service=user_service or SimpleNamespace(get=AsyncMock(return_value=None)),
        settings_service=settings_service or SimpleNamespace(get=AsyncMock()),
        notification_service=notification_service
        or SimpleNamespace(notify_user=AsyncMock()),
    )


def test_attach_partner_referral_chain_builds_three_levels_only_for_active_partners() -> None:
    referrer = build_user(telegram_id=900, name="Referrer")
    target_user = build_user(telegram_id=901, name="Target")
    referrer_partner = build_partner(partner_id=1, telegram_id=referrer.telegram_id)
    level2_partner = build_partner(partner_id=2, telegram_id=902)
    level3_partner = build_partner(partner_id=3, telegram_id=903)

    partners_repo = SimpleNamespace(
        get_partner_referral_by_user=AsyncMock(
            side_effect=[
                SimpleNamespace(partner_id=level2_partner.id),
                SimpleNamespace(partner_id=level3_partner.id),
            ]
        )
    )
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=build_user(telegram_id=level2_partner.user_telegram_id))
    )
    service = build_service(partners_repo=partners_repo, user_service=user_service)
    service.get_partner_by_user = AsyncMock(return_value=referrer_partner)  # type: ignore[method-assign]
    service.get_partner = AsyncMock(side_effect=[level2_partner, level3_partner])  # type: ignore[method-assign]
    service.add_partner_referral = AsyncMock()  # type: ignore[method-assign]

    result = run_async(service.attach_partner_referral_chain(user=target_user, referrer=referrer))

    assert result is True
    assert service.add_partner_referral.await_args_list == [
        call(
            partner=referrer_partner,
            referral_telegram_id=target_user.telegram_id,
            level=PartnerLevel.LEVEL_1,
        ),
        call(
            partner=level2_partner,
            referral_telegram_id=target_user.telegram_id,
            level=PartnerLevel.LEVEL_2,
            parent_partner_id=referrer_partner.id,
        ),
        call(
            partner=level3_partner,
            referral_telegram_id=target_user.telegram_id,
            level=PartnerLevel.LEVEL_3,
            parent_partner_id=level2_partner.id,
        ),
    ]


def test_process_partner_earning_skips_when_partner_program_is_disabled() -> None:
    partners_repo = SimpleNamespace(get_partner_chain_for_user=AsyncMock())
    service = build_service(
        partners_repo=partners_repo,
        settings_service=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(partner=SimpleNamespace(enabled=False)))),
    )

    run_async(service.process_partner_earning(payer_user_id=500, payment_amount=Decimal("199")))

    partners_repo.get_partner_chain_for_user.assert_not_awaited()


def test_process_partner_earning_deduplicates_existing_source_transaction() -> None:
    partner = build_partner(
        partner_id=7,
        telegram_id=7007,
        settings=PartnerIndividualSettingsDto(
            use_global_settings=False,
            accrual_strategy=PartnerAccrualStrategy.ON_FIRST_PAYMENT,
            reward_type=PartnerRewardType.PERCENT,
            level1_percent=Decimal("10"),
        ),
    )
    partners_repo = SimpleNamespace(
        get_partner_chain_for_user=AsyncMock(
            return_value=[SimpleNamespace(partner_id=partner.id, level=PartnerLevel.LEVEL_1.value)]
        ),
        has_partner_received_payment_from_referral=AsyncMock(return_value=False),
        get_transaction_by_partner_and_source=AsyncMock(return_value=object()),
    )
    partner_settings = SimpleNamespace(
        enabled=True,
        auto_calculate_commission=False,
        tax_percent=Decimal("0"),
        get_gateway_commission=MagicMock(return_value=Decimal("0")),
    )
    service = build_service(
        partners_repo=partners_repo,
        settings_service=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(partner=partner_settings))),
    )
    service.get_partner = AsyncMock(return_value=partner)  # type: ignore[method-assign]
    service.create_partner_transaction = AsyncMock()  # type: ignore[method-assign]
    service._notify_partner_earning = AsyncMock()  # type: ignore[method-assign]

    run_async(
        service.process_partner_earning(
            payer_user_id=501,
            payment_amount=Decimal("199"),
            gateway_type=PaymentGatewayType.PLATEGA,
            source_transaction_id=11,
        )
    )

    service.create_partner_transaction.assert_not_awaited()
    service._notify_partner_earning.assert_not_awaited()


def test_create_withdrawal_request_converts_to_kopecks_and_reserves_balance() -> None:
    partner = build_partner(partner_id=8, telegram_id=8008, balance=20_000)
    partners_repo = SimpleNamespace(
        create_withdrawal=AsyncMock(
            return_value=SimpleNamespace(
                id=91,
                partner_id=partner.id,
                amount=1234,
                requested_amount=Decimal("12.34"),
                requested_currency=Currency.RUB,
                quote_rate=None,
                quote_source=None,
                status=WithdrawalStatus.PENDING.value,
                method="sbp",
                requisites="123",
                admin_comment=None,
                processed_by=None,
                created_at=None,
                updated_at=None,
            )
        ),
        update_partner=AsyncMock(),
    )
    service = build_service(
        partners_repo=partners_repo,
        settings_service=SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(
                    partner=SimpleNamespace(min_withdrawal_amount=1000)
                )
            )
        ),
    )
    service.get_partner = AsyncMock(return_value=partner)  # type: ignore[method-assign]

    result = run_async(
        service.create_withdrawal_request(
            partner_id=partner.id or 0,
            amount=Decimal("12.34"),
            method="sbp",
            requisites="123",
        )
    )

    assert result is not None
    assert result.amount == 1234
    partners_repo.update_partner.assert_awaited_once_with(
        partner.id,
        balance=partner.balance - 1234,
    )


def test_approve_withdrawal_updates_total_withdrawn() -> None:
    partners_repo = SimpleNamespace(
        get_withdrawal_by_id=AsyncMock(return_value=SimpleNamespace(partner_id=8, amount=1500)),
        get_partner_by_id=AsyncMock(return_value=SimpleNamespace(id=8, total_withdrawn=500)),
        update_withdrawal=AsyncMock(),
        update_partner=AsyncMock(),
    )
    service = build_service(partners_repo=partners_repo)

    result = run_async(service.approve_withdrawal(withdrawal_id=31, admin_telegram_id=999))

    assert result is True
    partners_repo.update_partner.assert_awaited_once_with(
        8,
        total_withdrawn=2000,
    )


def test_reject_withdrawal_restores_partner_balance() -> None:
    partners_repo = SimpleNamespace(
        get_withdrawal_by_id=AsyncMock(return_value=SimpleNamespace(partner_id=9, amount=1700)),
        get_partner_by_id=AsyncMock(return_value=SimpleNamespace(id=9, balance=5000)),
        update_withdrawal=AsyncMock(),
        update_partner=AsyncMock(),
    )
    service = build_service(partners_repo=partners_repo)

    result = run_async(service.reject_withdrawal(withdrawal_id=32, admin_telegram_id=999))

    assert result is True
    partners_repo.update_partner.assert_awaited_once_with(
        9,
        balance=6700,
    )


def test_debit_balance_for_subscription_purchase_requires_active_partner() -> None:
    inactive_partner = build_partner(partner_id=10, telegram_id=10010, is_active=False)
    partners_repo = SimpleNamespace(deduct_partner_balance_if_possible=AsyncMock())
    service = build_service(partners_repo=partners_repo)
    service.get_partner_by_user = AsyncMock(return_value=inactive_partner)  # type: ignore[method-assign]

    result = run_async(
        service.debit_balance_for_subscription_purchase(
            user_telegram_id=inactive_partner.user_telegram_id,
            amount_kopecks=500,
        )
    )

    assert result is False
    partners_repo.deduct_partner_balance_if_possible.assert_not_awaited()


def test_credit_balance_for_failed_subscription_purchase_restores_balance_when_partner_exists(
) -> None:
    partner = build_partner(partner_id=11, telegram_id=11011)
    partners_repo = SimpleNamespace(add_partner_balance=AsyncMock(return_value=True))
    service = build_service(partners_repo=partners_repo)
    service.get_partner_by_user = AsyncMock(return_value=partner)  # type: ignore[method-assign]

    result = run_async(
        service.credit_balance_for_failed_subscription_purchase(
            user_telegram_id=partner.user_telegram_id,
            amount_kopecks=700,
        )
    )

    assert result is True
    partners_repo.add_partner_balance.assert_awaited_once_with(
        partner_id=partner.id,
        amount=700,
    )


def test_create_partner_returns_existing_partner_when_present() -> None:
    existing_partner = build_partner(partner_id=21, telegram_id=21021)
    partners_repo = SimpleNamespace(create_partner=AsyncMock())
    service = build_service(partners_repo=partners_repo)
    service.get_partner_by_user = AsyncMock(return_value=existing_partner)  # type: ignore[method-assign]

    result = run_async(service.create_partner(build_user(telegram_id=21021)))

    assert result == existing_partner
    partners_repo.create_partner.assert_not_awaited()


def test_create_partner_creates_new_partner_when_missing() -> None:
    created_model = SimpleNamespace(
        id=22,
        user_telegram_id=22022,
        balance=0,
        total_earned=0,
        total_withdrawn=0,
        referrals_count=0,
        level2_referrals_count=0,
        level3_referrals_count=0,
        is_active=True,
        individual_settings=None,
    )
    partners_repo = SimpleNamespace(create_partner=AsyncMock(return_value=created_model))
    service = build_service(partners_repo=partners_repo)
    service.get_partner_by_user = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = run_async(service.create_partner(build_user(telegram_id=22022)))

    assert result is not None
    assert result.user_telegram_id == 22022
    partners_repo.create_partner.assert_awaited_once()


def test_has_partner_attribution_reflects_referral_presence() -> None:
    partners_repo = SimpleNamespace(
        get_partner_referral_by_user=AsyncMock(side_effect=[object(), None])
    )
    service = build_service(partners_repo=partners_repo)

    assert run_async(service.has_partner_attribution(101)) is True
    assert run_async(service.has_partner_attribution(102)) is False


def test_is_partner_requires_active_partner() -> None:
    service = build_service()
    service.get_partner_by_user = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            build_partner(partner_id=31, telegram_id=31031, is_active=True),
            build_partner(partner_id=32, telegram_id=32032, is_active=False),
            None,
        ]
    )

    assert run_async(service.is_partner(31031)) is True
    assert run_async(service.is_partner(32032)) is False
    assert run_async(service.is_partner(33033)) is False


def test_toggle_partner_status_flips_active_flag_and_returns_none_for_unknown() -> None:
    partner = build_partner(partner_id=41, telegram_id=41041, is_active=True)
    updated_model = SimpleNamespace(
        id=41,
        user_telegram_id=41041,
        is_active=False,
        balance=0,
        total_earned=0,
        total_withdrawn=0,
        individual_settings=None,
    )
    partners_repo = SimpleNamespace(update_partner=AsyncMock(return_value=updated_model))
    service = build_service(partners_repo=partners_repo)
    service.get_partner = AsyncMock(side_effect=[partner, None])  # type: ignore[method-assign]

    result = run_async(service.toggle_partner_status(41))
    missing = run_async(service.toggle_partner_status(99))

    assert result is not None
    assert result.is_active is False
    assert missing is None
    partners_repo.update_partner.assert_awaited_once_with(41, is_active=False)


def test_deactivate_partner_forces_inactive_status() -> None:
    updated_model = SimpleNamespace(
        id=51,
        user_telegram_id=51051,
        is_active=False,
        balance=0,
        total_earned=0,
        total_withdrawn=0,
        individual_settings=None,
    )
    partners_repo = SimpleNamespace(update_partner=AsyncMock(return_value=updated_model))
    service = build_service(partners_repo=partners_repo)

    result = run_async(service.deactivate_partner(51))

    assert result is not None
    assert result.is_active is False
    partners_repo.update_partner.assert_awaited_once_with(51, is_active=False)


def test_update_partner_individual_settings_serializes_repository_payload_shape() -> None:
    partner = build_partner(partner_id=61, telegram_id=61061)
    settings = PartnerIndividualSettingsDto(
        use_global_settings=False,
        accrual_strategy=PartnerAccrualStrategy.ON_FIRST_PAYMENT,
        reward_type=PartnerRewardType.PERCENT,
        level1_percent=Decimal("10.5"),
        level2_percent=Decimal("5.25"),
        level3_percent=None,
        level1_fixed_amount=100,
        level2_fixed_amount=None,
        level3_fixed_amount=300,
    )
    updated_model = SimpleNamespace(
        id=61,
        user_telegram_id=61061,
        is_active=True,
        balance=0,
        total_earned=0,
        total_withdrawn=0,
        individual_settings={
            "use_global_settings": False,
            "accrual_strategy": "ON_FIRST_PAYMENT",
            "reward_type": "PERCENT",
        },
    )
    partners_repo = SimpleNamespace(update_partner=AsyncMock(return_value=updated_model))
    service = build_service(partners_repo=partners_repo)
    service.get_partner = AsyncMock(return_value=partner)  # type: ignore[method-assign]

    result = run_async(service.update_partner_individual_settings(61, settings))

    assert result is not None
    payload = partners_repo.update_partner.await_args.kwargs["individual_settings"]
    assert payload == {
        "use_global_settings": False,
        "accrual_strategy": "ON_FIRST_PAYMENT",
        "reward_type": "PERCENT",
        "level1_percent": "10.5",
        "level2_percent": "5.25",
        "level3_percent": None,
        "level1_fixed_amount": 100,
        "level2_fixed_amount": None,
        "level3_fixed_amount": 300,
    }


def test_adjust_partner_balance_rejects_negative_result_and_updates_when_valid() -> None:
    partner = build_partner(partner_id=71, telegram_id=71071, balance=500)
    updated_model = SimpleNamespace(
        id=71,
        user_telegram_id=71071,
        is_active=True,
        balance=900,
        total_earned=0,
        total_withdrawn=0,
        individual_settings=None,
    )
    partners_repo = SimpleNamespace(update_partner=AsyncMock(return_value=updated_model))
    service = build_service(partners_repo=partners_repo)
    service.get_partner = AsyncMock(side_effect=[partner, partner])  # type: ignore[method-assign]

    rejected = run_async(
        service.adjust_partner_balance(
            partner_id=71,
            amount=-600,
            admin_telegram_id=999,
            reason="too much",
        )
    )
    accepted = run_async(
        service.adjust_partner_balance(
            partner_id=71,
            amount=400,
            admin_telegram_id=999,
            reason="bonus",
        )
    )

    assert rejected is None
    assert accepted is not None
    assert accepted.balance == 900
    partners_repo.update_partner.assert_awaited_once_with(71, balance=900)
