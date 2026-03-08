"""Request contracts for referral and partner portal endpoints."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from src.core.enums import PointsExchangeType


class ReferralExchangeExecuteRequest(BaseModel):
    exchange_type: PointsExchangeType
    subscription_id: int | None = None
    gift_plan_id: int | None = None


class PartnerWithdrawalRequest(BaseModel):
    """Partner withdrawal request."""

    amount: Decimal = Field(..., gt=Decimal("0"), max_digits=12, decimal_places=2)
    method: str = Field(..., description="Withdrawal method")
    requisites: str = Field(..., description="Payment requisites")


__all__ = [
    "PartnerWithdrawalRequest",
    "ReferralExchangeExecuteRequest",
]
