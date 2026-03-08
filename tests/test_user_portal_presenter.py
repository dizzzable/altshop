from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.presenters.user_portal import (
    _build_partner_info_response,
    _build_referral_exchange_options_response,
    _raise_referral_portal_http_error,
)
from src.core.enums import PointsExchangeType
from src.services.partner_portal import (
    PartnerInfoSnapshot,
    PartnerLevelSettingSnapshot,
)
from src.services.referral_exchange import (
    ReferralExchangeOptions,
    ReferralExchangeTypeOption,
    ReferralGiftPlanOption,
)
from src.services.referral_portal import ReferralPortalAccessDeniedError


def test_build_referral_exchange_options_response_maps_nested_items() -> None:
    response = _build_referral_exchange_options_response(
        ReferralExchangeOptions(
            exchange_enabled=True,
            points_balance=180,
            types=[
                ReferralExchangeTypeOption(
                    type=PointsExchangeType.GIFT_SUBSCRIPTION,
                    enabled=True,
                    available=True,
                    points_cost=20,
                    min_points=100,
                    max_points=500,
                    computed_value=30,
                    requires_subscription=False,
                    gift_plan_id=7,
                    gift_duration_days=30,
                )
            ],
            gift_plans=[ReferralGiftPlanOption(plan_id=7, plan_name="Gift Plan")],
        )
    )

    assert response.exchange_enabled is True
    assert response.points_balance == 180
    assert len(response.types) == 1
    assert response.types[0].gift_plan_id == 7
    assert response.types[0].gift_duration_days == 30
    assert response.gift_plans[0].model_dump() == {"plan_id": 7, "plan_name": "Gift Plan"}


def test_build_partner_info_response_maps_level_settings() -> None:
    response = _build_partner_info_response(
        PartnerInfoSnapshot(
            is_partner=True,
            is_active=True,
            can_withdraw=True,
            apply_support_url="https://t.me/support",
            min_withdrawal_rub=100.0,
            balance=2500,
            total_earned=5000,
            total_withdrawn=2500,
            referrals_count=4,
            level2_referrals_count=2,
            level3_referrals_count=1,
            referral_link="https://t.me/ref",
            telegram_referral_link="https://t.me/ref",
            web_referral_link="https://site/ref",
            use_global_settings=False,
            effective_reward_type="FIXED",
            effective_accrual_strategy="ON_FIRST_PAYMENT",
            level_settings=[
                PartnerLevelSettingSnapshot(
                    level=1,
                    referrals_count=4,
                    earned_amount=5000,
                    global_percent=10.0,
                    individual_percent=12.5,
                    individual_fixed_amount=None,
                    effective_percent=12.5,
                    effective_fixed_amount=None,
                    uses_global_value=False,
                )
            ],
        )
    )

    assert response.is_partner is True
    assert response.balance == 2500
    assert len(response.level_settings) == 1
    assert response.level_settings[0].level == 1
    assert response.level_settings[0].effective_percent == 12.5


def test_raise_referral_portal_http_error_preserves_code_and_message() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _raise_referral_portal_http_error(
            ReferralPortalAccessDeniedError(
                code="REFERRAL_DISABLED",
                message="Referral API disabled",
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {
        "code": "REFERRAL_DISABLED",
        "message": "Referral API disabled",
    }
