from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.core.enums import (
    Currency,
    Locale,
    PartnerAccrualStrategy,
    PartnerLevel,
    PartnerRewardType,
)
from src.infrastructure.database.models.dto import (
    PartnerDto,
    PartnerIndividualSettingsDto,
    PartnerReferralDto,
    PartnerWithdrawalDto,
    UserDto,
)
from src.services.partner_portal import (
    PartnerPortalBadRequestError,
    PartnerPortalNotPartnerError,
    PartnerPortalService,
    PartnerPortalStateError,
    PartnerPortalWithdrawalDisabledError,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 100, username: str | None = "user") -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=f"User {telegram_id}",
        username=username,
        language=Locale.EN,
        referral_code=f"ref-{telegram_id}",
    )


def build_partner(
    *,
    partner_id: int | None,
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
    partner_service: SimpleNamespace | None = None,
    referral_portal_service: SimpleNamespace | None = None,
    notification_service: SimpleNamespace | None = None,
    web_account_service: SimpleNamespace | None = None,
    market_quote_service: SimpleNamespace | None = None,
) -> PartnerPortalService:
    config = SimpleNamespace(
        bot=SimpleNamespace(
            support_username=SimpleNamespace(get_secret_value=lambda: "@support_test")
        ),
        web_app=SimpleNamespace(url_str="https://app.example.test"),
    )
    return PartnerPortalService(
        config=config,
        partner_service=partner_service or SimpleNamespace(),
        referral_portal_service=referral_portal_service or SimpleNamespace(),
        notification_service=notification_service or SimpleNamespace(notify_super_dev=AsyncMock()),
        web_account_service=web_account_service
        or SimpleNamespace(get_by_user_telegram_id=AsyncMock(return_value=None)),
        market_quote_service=market_quote_service
        or SimpleNamespace(
            convert_from_rub=AsyncMock(
                side_effect=lambda amount_rub, target_currency: SimpleNamespace(amount=amount_rub)
            ),
            get_usd_rub_quote=AsyncMock(
                return_value=SimpleNamespace(price=Decimal("100"), source="USD")
            ),
            get_asset_usd_quote=AsyncMock(
                return_value=SimpleNamespace(price=Decimal("1"), source="ASSET")
            ),
        ),
    )


def test_get_info_returns_zeroed_snapshot_for_non_partner() -> None:
    current_user = build_user(telegram_id=201)
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(partner=SimpleNamespace(min_withdrawal_amount=50000))),
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        ),
        get_partner_by_user=AsyncMock(return_value=None),
    )
    service = build_service(
        partner_service=partner_service,
        referral_portal_service=SimpleNamespace(
            user_service=SimpleNamespace(ensure_referral_code=AsyncMock(return_value=current_user)),
            referral_service=SimpleNamespace(get_ref_link=AsyncMock()),
        ),
    )

    snapshot = run_async(service.get_info(current_user))

    assert snapshot.is_partner is False
    assert snapshot.balance == 0
    assert snapshot.referral_link is None
    assert snapshot.level_settings == []


def test_get_info_preserves_effective_strategy_and_referral_links_for_partner() -> None:
    current_user = build_user(telegram_id=202)
    partner = build_partner(
        partner_id=12,
        telegram_id=current_user.telegram_id,
        balance=10_000,
        total_earned=25_000,
        total_withdrawn=5_000,
        settings=PartnerIndividualSettingsDto(
            use_global_settings=False,
            accrual_strategy=PartnerAccrualStrategy.ON_FIRST_PAYMENT,
            reward_type=PartnerRewardType.FIXED_AMOUNT,
            level1_fixed_amount=1500,
        ),
    )
    partner_settings = SimpleNamespace(
        min_withdrawal_amount=5000,
        get_level_percent=lambda level: (
            Decimal("10") if level == PartnerLevel.LEVEL_1 else Decimal("3")
        ),
    )
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(partner=partner_settings)),
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        ),
        get_partner_by_user=AsyncMock(return_value=partner),
        get_partner_statistics=AsyncMock(
            return_value={"level1_earnings": 1200, "level2_earnings": 0, "level3_earnings": 0}
        ),
    )
    service = build_service(
        partner_service=partner_service,
        referral_portal_service=SimpleNamespace(
            user_service=SimpleNamespace(ensure_referral_code=AsyncMock(return_value=current_user)),
            referral_service=SimpleNamespace(
                get_ref_link=AsyncMock(return_value="https://t.me/bot?start=ref-token")
            ),
        ),
    )

    snapshot = run_async(service.get_info(current_user))

    assert snapshot.is_partner is True
    assert snapshot.effective_reward_type == PartnerRewardType.FIXED_AMOUNT.value
    assert snapshot.effective_accrual_strategy == PartnerAccrualStrategy.ON_FIRST_PAYMENT.value
    assert snapshot.telegram_referral_link == "https://t.me/bot?start=ref-token"
    assert snapshot.web_referral_link.endswith(current_user.referral_code)


def test_list_referrals_paginates_and_uses_stats_maps() -> None:
    current_user = build_user(telegram_id=203)
    partner = build_partner(partner_id=13, telegram_id=current_user.telegram_id)
    referral_1 = PartnerReferralDto(
        id=1,
        partner_id=13,
        referral_telegram_id=301,
        level=PartnerLevel.LEVEL_1,
        referral=build_user(telegram_id=301),
    )
    referral_2 = PartnerReferralDto(
        id=2,
        partner_id=13,
        referral_telegram_id=302,
        level=PartnerLevel.LEVEL_2,
        referral=build_user(telegram_id=302),
    )
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB)
        ),
        get_partner_by_user=AsyncMock(return_value=partner),
        get_partner_referrals=AsyncMock(return_value=[referral_1, referral_2]),
        get_partner_referral_transaction_stats=AsyncMock(
            return_value={302: {"total_earned": 700, "total_paid_amount": 900}}
        ),
        get_referral_invite_sources=AsyncMock(return_value={302: "WEB"}),
    )
    service = build_service(partner_service=partner_service)

    snapshot = run_async(service.list_referrals(current_user=current_user, page=2, limit=1))

    assert snapshot.total == 2
    assert len(snapshot.referrals) == 1
    assert snapshot.referrals[0].telegram_id == 302
    partner_service.get_partner_referral_transaction_stats.assert_awaited_once_with(
        partner_id=partner.id,
        referral_telegram_ids=[302],
    )


def test_list_earnings_returns_empty_for_non_partner() -> None:
    current_user = build_user(telegram_id=204)
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB)
        ),
        get_partner_by_user=AsyncMock(return_value=None),
    )
    service = build_service(partner_service=partner_service)

    snapshot = run_async(service.list_earnings(current_user=current_user, page=1, limit=20))

    assert snapshot.total == 0
    assert snapshot.earnings == []


def test_list_earnings_raises_when_partner_id_is_missing() -> None:
    current_user = build_user(telegram_id=205)
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB)
        ),
        get_partner_by_user=AsyncMock(return_value=build_partner(partner_id=None, telegram_id=205)),
    )
    service = build_service(partner_service=partner_service)

    try:
        run_async(service.list_earnings(current_user=current_user, page=1, limit=20))
    except PartnerPortalStateError as error:
        assert str(error) == "Partner record is missing id"
    else:
        raise AssertionError("Expected PartnerPortalStateError")


def test_request_withdrawal_rejects_non_partner() -> None:
    current_user = build_user(telegram_id=206)
    base_settings = SimpleNamespace(
        resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        get=AsyncMock(
            return_value=SimpleNamespace(partner=SimpleNamespace(min_withdrawal_amount=5000))
        ),
    )
    service = build_service(
        partner_service=SimpleNamespace(
            settings_service=base_settings,
            get_partner_by_user=AsyncMock(return_value=None),
        )
    )
    try:
        run_async(
            service.request_withdrawal(
                current_user=current_user,
                amount=Decimal("10"),
                method="sbp",
                requisites="x",
            )
        )
    except PartnerPortalNotPartnerError:
        pass
    else:
        raise AssertionError("Expected PartnerPortalNotPartnerError")


def test_request_withdrawal_rejects_inactive_partner() -> None:
    current_user = build_user(telegram_id=206)
    base_settings = SimpleNamespace(
        resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        get=AsyncMock(
            return_value=SimpleNamespace(partner=SimpleNamespace(min_withdrawal_amount=5000))
        ),
    )
    inactive_partner = build_partner(
        partner_id=14,
        telegram_id=206,
        is_active=False,
        balance=10_000,
    )
    service = build_service(
        partner_service=SimpleNamespace(
            settings_service=base_settings,
            get_partner_by_user=AsyncMock(return_value=inactive_partner),
        )
    )
    try:
        run_async(
            service.request_withdrawal(
                current_user=current_user,
                amount=Decimal("10"),
                method="sbp",
                requisites="x",
            )
        )
    except PartnerPortalWithdrawalDisabledError:
        pass
    else:
        raise AssertionError("Expected PartnerPortalWithdrawalDisabledError")


def test_request_withdrawal_rejects_invalid_amount_and_balance_conditions() -> None:
    current_user = build_user(telegram_id=206)
    base_settings = SimpleNamespace(
        resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        get=AsyncMock(
            return_value=SimpleNamespace(partner=SimpleNamespace(min_withdrawal_amount=5000))
        ),
    )
    active_partner = build_partner(partner_id=15, telegram_id=206, is_active=True, balance=10_000)
    partner_service = SimpleNamespace(
        settings_service=base_settings,
        get_partner_by_user=AsyncMock(return_value=active_partner),
        create_withdrawal_request=AsyncMock(return_value=None),
    )
    service = build_service(partner_service=partner_service)

    try:
        run_async(
            service.request_withdrawal(
                current_user=current_user,
                amount=Decimal("0"),
                method="sbp",
                requisites="x",
            )
        )
    except PartnerPortalBadRequestError as error:
        assert str(error) == "Withdrawal amount must be positive"
    else:
        raise AssertionError("Expected PartnerPortalBadRequestError for zero amount")

    try:
        run_async(
            service.request_withdrawal(
                current_user=current_user,
                amount=Decimal("10"),
                method="sbp",
                requisites="x",
            )
        )
    except PartnerPortalBadRequestError as error:
        assert "Minimum withdrawal amount is" in str(error)
    else:
        raise AssertionError("Expected PartnerPortalBadRequestError for minimum underflow")

    partner_service.create_withdrawal_request = AsyncMock(return_value=None)
    active_partner.balance = 100
    try:
        run_async(
            service.request_withdrawal(
                current_user=current_user,
                amount=Decimal("60"),
                method="sbp",
                requisites="x",
            )
        )
    except PartnerPortalBadRequestError as error:
        assert "Insufficient balance" in str(error)
    else:
        raise AssertionError("Expected PartnerPortalBadRequestError for insufficient balance")


def test_request_withdrawal_serializes_created_withdrawal_with_display_currency() -> None:
    current_user = build_user(telegram_id=207)
    partner = build_partner(partner_id=16, telegram_id=207, is_active=True, balance=50_000)
    withdrawal = PartnerWithdrawalDto(
        id=55,
        partner_id=16,
        amount=12345,
        requested_amount=Decimal("123.45"),
        requested_currency=Currency.USD,
        quote_rate=Decimal("100"),
        quote_source="USD",
        status="pending",
        method="sbp",
        requisites="123",
    )
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.USD),
            get=AsyncMock(return_value=SimpleNamespace(partner=SimpleNamespace(min_withdrawal_amount=5000))),
        ),
        get_partner_by_user=AsyncMock(return_value=partner),
        create_withdrawal_request=AsyncMock(return_value=withdrawal),
    )
    notification_service = SimpleNamespace(notify_super_dev=AsyncMock())
    market_quote_service = SimpleNamespace(
        convert_from_rub=AsyncMock(return_value=SimpleNamespace(amount=Decimal("123.45"))),
        get_usd_rub_quote=AsyncMock(
            return_value=SimpleNamespace(price=Decimal("100"), source="USD")
        ),
        get_asset_usd_quote=AsyncMock(
            return_value=SimpleNamespace(price=Decimal("1"), source="ASSET")
        ),
    )
    service = build_service(
        partner_service=partner_service,
        notification_service=notification_service,
        market_quote_service=market_quote_service,
    )

    snapshot = run_async(
        service.request_withdrawal(
            current_user=current_user,
            amount=Decimal("123.45"),
            method="sbp",
            requisites="123",
        )
    )

    assert snapshot.id == 55
    assert snapshot.display_currency == Currency.USD.value
    assert snapshot.display_amount == 123.45
    notification_service.notify_super_dev.assert_awaited_once()


def test_list_withdrawals_preserves_normalized_status_aliases() -> None:
    current_user = build_user(telegram_id=208)
    partner = build_partner(partner_id=17, telegram_id=208)
    withdrawal = PartnerWithdrawalDto(
        id=66,
        partner_id=17,
        amount=5000,
        status="cancelled",
        method="sbp",
        requisites="123",
    )
    partner_service = SimpleNamespace(
        settings_service=SimpleNamespace(
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB)
        ),
        get_partner_by_user=AsyncMock(return_value=partner),
        get_partner_withdrawals=AsyncMock(return_value=[withdrawal]),
    )
    service = build_service(partner_service=partner_service)

    snapshot = run_async(service.list_withdrawals(current_user=current_user))

    assert len(snapshot.withdrawals) == 1
    assert snapshot.withdrawals[0].status == "CANCELED"
