from __future__ import annotations

from dataclasses import dataclass


class PartnerPortalError(Exception):
    """Base error for partner portal flows."""


class PartnerPortalNotPartnerError(PartnerPortalError):
    """Raised when a write operation requires an active partner record."""


class PartnerPortalStateError(PartnerPortalError):
    """Raised when the partner record is structurally invalid."""


class PartnerPortalWithdrawalDisabledError(PartnerPortalError):
    def __init__(self) -> None:
        self.code = "PARTNER_WITHDRAW_DISABLED"
        self.message = "Withdrawals are disabled for inactive partners"
        super().__init__(self.message)


class PartnerPortalBadRequestError(PartnerPortalError):
    """Raised for validation failures on partner actions."""


@dataclass(slots=True, frozen=True)
class PartnerLevelSettingSnapshot:
    level: int
    referrals_count: int
    earned_amount: int
    global_percent: float
    individual_percent: float | None
    individual_fixed_amount: int | None
    effective_percent: float | None
    effective_fixed_amount: int | None
    uses_global_value: bool


@dataclass(slots=True, frozen=True)
class PartnerInfoSnapshot:
    is_partner: bool
    is_active: bool
    can_withdraw: bool
    apply_support_url: str | None
    effective_currency: str
    min_withdrawal_rub: float
    min_withdrawal_display: float
    balance: int
    balance_display: float
    total_earned: int
    total_earned_display: float
    total_withdrawn: int
    total_withdrawn_display: float
    referrals_count: int
    level2_referrals_count: int
    level3_referrals_count: int
    referral_link: str | None
    telegram_referral_link: str | None
    web_referral_link: str | None
    use_global_settings: bool
    effective_reward_type: str
    effective_accrual_strategy: str
    level_settings: list[PartnerLevelSettingSnapshot]


@dataclass(slots=True, frozen=True)
class PartnerReferralItemSnapshot:
    telegram_id: int
    username: str | None
    name: str | None
    level: int
    joined_at: str
    invite_source: str
    is_active: bool
    is_paid: bool
    first_paid_at: str | None
    total_paid_amount: int
    total_paid_amount_display: float
    total_earned: int
    total_earned_display: float
    display_currency: str


@dataclass(slots=True, frozen=True)
class PartnerReferralsPageSnapshot:
    referrals: list[PartnerReferralItemSnapshot]
    total: int
    page: int
    limit: int


@dataclass(slots=True, frozen=True)
class PartnerEarningItemSnapshot:
    id: int
    referral_telegram_id: int
    referral_username: str | None
    level: int
    payment_amount: int
    payment_amount_display: float
    percent: float
    earned_amount: int
    earned_amount_display: float
    display_currency: str
    created_at: str


@dataclass(slots=True, frozen=True)
class PartnerEarningsPageSnapshot:
    earnings: list[PartnerEarningItemSnapshot]
    total: int
    page: int
    limit: int


@dataclass(slots=True, frozen=True)
class PartnerWithdrawalSnapshot:
    id: int
    amount: int
    display_amount: float
    display_currency: str
    requested_amount: float | None
    requested_currency: str | None
    quote_rate: float | None
    quote_source: str | None
    status: str
    method: str
    requisites: str
    admin_comment: str | None
    created_at: str
    updated_at: str


@dataclass(slots=True, frozen=True)
class PartnerWithdrawalsSnapshot:
    withdrawals: list[PartnerWithdrawalSnapshot]
