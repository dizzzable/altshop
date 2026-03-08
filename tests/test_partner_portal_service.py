from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.enums import Currency, PartnerLevel
from src.services.partner_portal import (
    PartnerPortalService,
    PartnerPortalWithdrawalDisabledError,
)


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        bot=SimpleNamespace(
            support_username=SimpleNamespace(get_secret_value=lambda: "support_helper")
        )
    )


def _build_service(*, partner_service: SimpleNamespace) -> PartnerPortalService:
    if not hasattr(partner_service, "settings_service"):
        partner_service.settings_service = SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(
                    partner=SimpleNamespace(min_withdrawal_amount=1000)
                )
            ),
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        )

    market_quote_service = SimpleNamespace(
        convert_from_rub=AsyncMock(
            side_effect=lambda *, amount_rub, target_currency: SimpleNamespace(amount=amount_rub)
        ),
        get_usd_rub_quote=AsyncMock(return_value=SimpleNamespace(price=Decimal("100"), source="CBR")),
        get_asset_usd_quote=AsyncMock(return_value=SimpleNamespace(price=Decimal("1"), source="STATIC")),
    )
    return PartnerPortalService(
        config=_build_config(),
        partner_service=partner_service,
        referral_portal_service=SimpleNamespace(),
        notification_service=SimpleNamespace(notify_super_dev=AsyncMock()),
        web_account_service=SimpleNamespace(get_by_user_telegram_id=AsyncMock(return_value=None)),
        market_quote_service=market_quote_service,
    )


def test_list_referrals_maps_stats_and_invite_source() -> None:
    referral = SimpleNamespace(
        referral_telegram_id=404,
        referral=SimpleNamespace(
            username="ref_user",
            name="Referral User",
            is_blocked=False,
        ),
        level=PartnerLevel.LEVEL_2,
        created_at=datetime(2026, 3, 7, 10, 30, 0, tzinfo=UTC),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(id=77)),
        get_partner_referrals=AsyncMock(return_value=[referral]),
        get_partner_referral_transaction_stats=AsyncMock(
            return_value={
                404: {
                    "total_earned": 350,
                    "total_paid_amount": 5000,
                    "first_paid_at": datetime(2026, 3, 6, 9, 0, 0, tzinfo=UTC),
                }
            }
        ),
        get_referral_invite_sources=AsyncMock(return_value={404: "QR"}),
    )
    service = _build_service(partner_service=partner_service)

    page_snapshot = asyncio.run(
        service.list_referrals(
            current_user=SimpleNamespace(telegram_id=101),
            page=1,
            limit=20,
        )
    )

    assert page_snapshot.total == 1
    assert page_snapshot.referrals[0].telegram_id == 404
    assert page_snapshot.referrals[0].level == 2
    assert page_snapshot.referrals[0].invite_source == "QR"
    assert page_snapshot.referrals[0].is_paid is True
    assert page_snapshot.referrals[0].total_earned == 350
    assert page_snapshot.referrals[0].total_paid_amount == 5000


def test_list_withdrawals_normalizes_status_aliases() -> None:
    withdrawal = SimpleNamespace(
        id=9,
        amount=1500,
        requested_amount=None,
        requested_currency=None,
        quote_rate=None,
        quote_source=None,
        status="cancelled",
        method="sbp",
        requisites="+79990000000",
        admin_comment=None,
        created_at=datetime(2026, 3, 7, 11, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 7, 11, 5, 0, tzinfo=UTC),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(id=77)),
        get_partner_withdrawals=AsyncMock(return_value=[withdrawal]),
    )
    service = _build_service(partner_service=partner_service)

    snapshot = asyncio.run(
        service.list_withdrawals(current_user=SimpleNamespace(telegram_id=101))
    )

    assert len(snapshot.withdrawals) == 1
    assert snapshot.withdrawals[0].status == "CANCELED"


def test_request_withdrawal_blocks_inactive_partner() -> None:
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(
            return_value=SimpleNamespace(id=77, is_active=False, balance=10000)
        )
    )
    service = _build_service(partner_service=partner_service)

    with pytest.raises(PartnerPortalWithdrawalDisabledError):
        asyncio.run(
            service.request_withdrawal(
                current_user=SimpleNamespace(telegram_id=101, username=None, name="User 101"),
                amount=Decimal("120.00"),
                method="sbp",
                requisites="+79990000000",
            )
        )
