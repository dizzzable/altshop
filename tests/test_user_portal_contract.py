from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.api.contracts.user_portal import (
    PartnerWithdrawalRequest,
    ReferralExchangeExecuteRequest,
)
from src.core.enums import PointsExchangeType


def test_referral_exchange_execute_request_keeps_optional_targets() -> None:
    payload = ReferralExchangeExecuteRequest(
        exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
        subscription_id=77,
    )

    assert payload.exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS
    assert payload.subscription_id == 77
    assert payload.gift_plan_id is None


def test_partner_withdrawal_request_accepts_positive_amount() -> None:
    payload = PartnerWithdrawalRequest(
        amount=Decimal("123.45"),
        method="sbp",
        requisites="+79990000000",
    )

    assert payload.amount == Decimal("123.45")
    assert payload.method == "sbp"
    assert payload.requisites == "+79990000000"


def test_partner_withdrawal_request_rejects_zero_amount() -> None:
    with pytest.raises(ValidationError):
        PartnerWithdrawalRequest(
            amount=Decimal("0"),
            method="sbp",
            requisites="+79990000000",
        )
