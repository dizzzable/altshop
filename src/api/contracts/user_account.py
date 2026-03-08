"""Request contracts for user account endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.core.enums import Currency


class SetSecurityEmailRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)


class SetPartnerBalanceCurrencyRequest(BaseModel):
    currency: Currency | None = None


__all__ = [
    "SetPartnerBalanceCurrencyRequest",
    "SetSecurityEmailRequest",
]
