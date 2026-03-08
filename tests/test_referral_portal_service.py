from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.services.referral_portal import (
    REFERRAL_DISABLED_FOR_ACTIVE_PARTNER,
    ReferralPortalAccessDeniedError,
    ReferralPortalService,
)


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        web_app=SimpleNamespace(url_str="https://example.com/webapp"),
        domain=SimpleNamespace(get_secret_value=lambda: "example.com"),
    )


def _build_service(
    *,
    referral_service: object | None = None,
    referral_exchange_service: object | None = None,
    partner_service: object | None = None,
    user_service: object | None = None,
) -> ReferralPortalService:
    return ReferralPortalService(
        config=_build_config(),
        referral_service=referral_service
        or SimpleNamespace(
            get_ref_link=AsyncMock(return_value="https://t.me/ref"),
            get_referrals_page_by_referrer=AsyncMock(return_value=([], 0)),
            get_issued_rewards_map_for_referrer=AsyncMock(return_value={}),
            generate_ref_qr_bytes=Mock(return_value=b""),
        ),
        referral_exchange_service=referral_exchange_service
        or SimpleNamespace(
            get_options=AsyncMock(return_value=SimpleNamespace()),
            execute=AsyncMock(),
        ),
        partner_service=partner_service
        or SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
        user_service=user_service
        or SimpleNamespace(
            ensure_referral_code=AsyncMock(side_effect=lambda user: user),
            get=AsyncMock(return_value=None),
        ),
    )


def test_list_referrals_maps_events_rewards_and_qualification() -> None:
    current_user = SimpleNamespace(telegram_id=9001)
    referral = SimpleNamespace(
        id=1,
        referred=SimpleNamespace(
            telegram_id=7002,
            username="friend_user",
            name="Friend User",
            is_blocked=False,
        ),
        level=SimpleNamespace(value=1),
        invite_source=SimpleNamespace(value="TELEGRAM"),
        qualified_at=datetime(2026, 3, 7, 12, 0, 0, tzinfo=UTC),
        qualified_purchase_channel=SimpleNamespace(value="WEB"),
        created_at=datetime(2026, 3, 6, 10, 0, 0, tzinfo=UTC),
        is_qualified=True,
    )
    referral_service = SimpleNamespace(
        get_ref_link=AsyncMock(return_value="https://t.me/ref"),
        get_referrals_page_by_referrer=AsyncMock(return_value=([referral], 1)),
        get_issued_rewards_map_for_referrer=AsyncMock(return_value={1: 75}),
        generate_ref_qr_bytes=Mock(return_value=b""),
    )
    service = _build_service(referral_service=referral_service)

    page = asyncio.run(service.list_referrals(current_user=current_user, page=1, limit=20))

    assert page.total == 1
    assert page.referrals[0].telegram_id == 7002
    assert page.referrals[0].invite_source == "TELEGRAM"
    assert page.referrals[0].qualified_purchase_channel == "WEB"
    assert page.referrals[0].rewards_issued == 75
    assert page.referrals[0].events[0].type == "INVITED"
    assert page.referrals[0].events[1].type == "QUALIFIED"


def test_get_exchange_options_blocks_active_partner() -> None:
    current_user = SimpleNamespace(telegram_id=9002)
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True))
    )
    service = _build_service(partner_service=partner_service)

    with pytest.raises(ReferralPortalAccessDeniedError) as exc_info:
        asyncio.run(service.get_exchange_options(current_user))

    assert exc_info.value.code == REFERRAL_DISABLED_FOR_ACTIVE_PARTNER
