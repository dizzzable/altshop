from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from src.core.enums import PointsExchangeType
from src.services.partner_portal import (
    PartnerEarningsPageSnapshot,
    PartnerInfoSnapshot,
    PartnerPortalBadRequestError,
    PartnerPortalNotPartnerError,
    PartnerPortalStateError,
    PartnerPortalWithdrawalDisabledError,
    PartnerReferralsPageSnapshot,
    PartnerWithdrawalSnapshot,
    PartnerWithdrawalsSnapshot,
)
from src.services.referral_exchange import (
    ReferralExchangeExecutionResult,
    ReferralExchangeOptions,
)
from src.services.referral_portal import (
    ReferralAboutSnapshot,
    ReferralInfoSnapshot,
    ReferralListPageSnapshot,
    ReferralPortalAccessDeniedError,
)


class ReferralInfoResponse(BaseModel):
    """Referral info response."""

    referral_count: int
    qualified_referral_count: int
    reward_count: int
    referral_link: str
    telegram_referral_link: str
    web_referral_link: str
    referral_code: str | None = None
    invite_expires_at: str | None = None
    remaining_slots: int | None = None
    total_capacity: int | None = None
    requires_regeneration: bool = False
    invite_block_reason: str | None = None
    refill_step_progress: int | None = None
    refill_step_target: int | None = None
    points: int


class ReferralEventResponse(BaseModel):
    type: str
    at: str
    source: str | None = None
    channel: str | None = None


class ReferralItemResponse(BaseModel):
    """Referral item response."""

    telegram_id: int
    username: str | None
    name: str | None
    level: int
    invited_at: str
    joined_at: str
    invite_source: str
    is_active: bool
    is_qualified: bool
    qualified_at: str | None = None
    qualified_purchase_channel: str | None = None
    rewards_issued: int
    rewards_earned: int
    events: list[ReferralEventResponse] = Field(default_factory=list)


class ReferralListResponse(BaseModel):
    """Referral list response."""

    referrals: list[ReferralItemResponse]
    total: int
    page: int
    limit: int


class ReferralGiftPlanOptionResponse(BaseModel):
    plan_id: int
    plan_name: str


class ReferralExchangeTypeOptionResponse(BaseModel):
    type: PointsExchangeType
    enabled: bool
    available: bool
    points_cost: int
    min_points: int
    max_points: int
    computed_value: int
    requires_subscription: bool
    gift_plan_id: int | None = None
    gift_duration_days: int | None = None
    max_discount_percent: int | None = None
    max_traffic_gb: int | None = None


class ReferralExchangeOptionsResponse(BaseModel):
    exchange_enabled: bool
    points_balance: int
    types: list[ReferralExchangeTypeOptionResponse]
    gift_plans: list[ReferralGiftPlanOptionResponse] = Field(default_factory=list)


class ReferralExchangeExecuteResultPayload(BaseModel):
    days_added: int | None = None
    traffic_gb_added: int | None = None
    discount_percent_added: int | None = None
    gift_promocode: str | None = None
    gift_plan_name: str | None = None
    gift_duration_days: int | None = None


class ReferralExchangeExecuteResponse(BaseModel):
    success: bool
    exchange_type: PointsExchangeType
    points_spent: int
    points_balance_after: int
    result: ReferralExchangeExecuteResultPayload


class ReferralAboutResponse(BaseModel):
    """Referral about/FAQ response."""

    title: str
    description: str
    how_it_works: list[str]
    rewards: dict[str, str]
    faq: list[dict[str, str]]


class PartnerLevelSettingResponse(BaseModel):
    """Partner level settings resolved from global + individual config."""

    level: int
    referrals_count: int = 0
    earned_amount: int = 0
    global_percent: float
    individual_percent: float | None = None
    individual_fixed_amount: int | None = None
    effective_percent: float | None = None
    effective_fixed_amount: int | None = None
    uses_global_value: bool = True


class PartnerInfoResponse(BaseModel):
    """Partner info response."""

    is_partner: bool
    is_active: bool = False
    can_withdraw: bool = False
    apply_support_url: str | None = None
    effective_currency: str = "RUB"
    min_withdrawal_rub: float = 0
    min_withdrawal_display: float = 0
    balance: int
    balance_display: float = 0
    total_earned: int
    total_earned_display: float = 0
    total_withdrawn: int
    total_withdrawn_display: float = 0
    referrals_count: int
    level2_referrals_count: int
    level3_referrals_count: int
    referral_link: str | None = None
    telegram_referral_link: str | None = None
    web_referral_link: str | None = None
    use_global_settings: bool = True
    effective_reward_type: str = "PERCENT"
    effective_accrual_strategy: str = "ON_EACH_PAYMENT"
    level_settings: list[PartnerLevelSettingResponse] = Field(default_factory=list)


class PartnerEarningResponse(BaseModel):
    """Partner earning item response."""

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


class PartnerEarningsListResponse(BaseModel):
    """Partner earnings list response."""

    earnings: list[PartnerEarningResponse]
    total: int
    page: int
    limit: int


class PartnerReferralResponse(BaseModel):
    """Partner referral item response."""

    telegram_id: int
    username: str | None
    name: str | None
    level: int
    joined_at: str
    invite_source: str = "UNKNOWN"
    is_active: bool
    is_paid: bool = False
    first_paid_at: str | None = None
    total_paid_amount: int = 0
    total_earned: int
    total_paid_amount_display: float = 0
    total_earned_display: float = 0
    display_currency: str = "RUB"


class PartnerReferralsListResponse(BaseModel):
    """Partner referrals list response."""

    referrals: list[PartnerReferralResponse]
    total: int
    page: int
    limit: int


class PartnerWithdrawalResponse(BaseModel):
    """Partner withdrawal response."""

    id: int
    amount: int
    display_amount: float
    display_currency: str
    requested_amount: float | None = None
    requested_currency: str | None = None
    quote_rate: float | None = None
    quote_source: str | None = None
    status: str
    method: str
    requisites: str
    admin_comment: str | None
    created_at: str
    updated_at: str


class PartnerWithdrawalsListResponse(BaseModel):
    """Partner withdrawals list response."""

    withdrawals: list[PartnerWithdrawalResponse]


def _raise_referral_portal_http_error(exception: ReferralPortalAccessDeniedError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": exception.code,
            "message": exception.message,
        },
    ) from exception


def _build_referral_info_response(snapshot: ReferralInfoSnapshot) -> ReferralInfoResponse:
    return ReferralInfoResponse(
        referral_count=snapshot.referral_count,
        qualified_referral_count=snapshot.qualified_referral_count,
        reward_count=snapshot.reward_count,
        referral_link=snapshot.referral_link,
        telegram_referral_link=snapshot.telegram_referral_link,
        web_referral_link=snapshot.web_referral_link,
        referral_code=snapshot.referral_code,
        invite_expires_at=snapshot.invite_expires_at,
        remaining_slots=snapshot.remaining_slots,
        total_capacity=snapshot.total_capacity,
        requires_regeneration=snapshot.requires_regeneration,
        invite_block_reason=snapshot.invite_block_reason,
        refill_step_progress=snapshot.refill_step_progress,
        refill_step_target=snapshot.refill_step_target,
        points=snapshot.points,
    )


def _build_referral_list_response(page_snapshot: ReferralListPageSnapshot) -> ReferralListResponse:
    return ReferralListResponse(
        referrals=[
            ReferralItemResponse(
                telegram_id=referral.telegram_id,
                username=referral.username,
                name=referral.name,
                level=referral.level,
                invited_at=referral.invited_at,
                joined_at=referral.joined_at,
                invite_source=referral.invite_source,
                is_active=referral.is_active,
                is_qualified=referral.is_qualified,
                qualified_at=referral.qualified_at,
                qualified_purchase_channel=referral.qualified_purchase_channel,
                rewards_issued=referral.rewards_issued,
                rewards_earned=referral.rewards_earned,
                events=[
                    ReferralEventResponse(
                        type=event.type,
                        at=event.at,
                        source=event.source,
                        channel=event.channel,
                    )
                    for event in referral.events
                ],
            )
            for referral in page_snapshot.referrals
        ],
        total=page_snapshot.total,
        page=page_snapshot.page,
        limit=page_snapshot.limit,
    )


def _build_referral_exchange_options_response(
    options: ReferralExchangeOptions,
) -> ReferralExchangeOptionsResponse:
    return ReferralExchangeOptionsResponse(
        exchange_enabled=options.exchange_enabled,
        points_balance=options.points_balance,
        types=[
            ReferralExchangeTypeOptionResponse(
                type=option.type,
                enabled=option.enabled,
                available=option.available,
                points_cost=option.points_cost,
                min_points=option.min_points,
                max_points=option.max_points,
                computed_value=option.computed_value,
                requires_subscription=option.requires_subscription,
                gift_plan_id=option.gift_plan_id,
                gift_duration_days=option.gift_duration_days,
                max_discount_percent=option.max_discount_percent,
                max_traffic_gb=option.max_traffic_gb,
            )
            for option in options.types
        ],
        gift_plans=[
            ReferralGiftPlanOptionResponse(plan_id=plan.plan_id, plan_name=plan.plan_name)
            for plan in options.gift_plans
        ],
    )


def _build_referral_exchange_execute_response(
    execution_result: ReferralExchangeExecutionResult,
) -> ReferralExchangeExecuteResponse:
    return ReferralExchangeExecuteResponse(
        success=True,
        exchange_type=execution_result.exchange_type,
        points_spent=execution_result.points_spent,
        points_balance_after=execution_result.points_balance_after,
        result=ReferralExchangeExecuteResultPayload(
            days_added=execution_result.result.days_added,
            traffic_gb_added=execution_result.result.traffic_gb_added,
            discount_percent_added=execution_result.result.discount_percent_added,
            gift_promocode=execution_result.result.gift_promocode,
            gift_plan_name=execution_result.result.gift_plan_name,
            gift_duration_days=execution_result.result.gift_duration_days,
        ),
    )


def _build_referral_about_response(snapshot: ReferralAboutSnapshot) -> ReferralAboutResponse:
    return ReferralAboutResponse(
        title=snapshot.title,
        description=snapshot.description,
        how_it_works=snapshot.how_it_works,
        rewards=snapshot.rewards,
        faq=snapshot.faq,
    )


def _raise_partner_portal_http_error(
    exception: (
        PartnerPortalBadRequestError
        | PartnerPortalNotPartnerError
        | PartnerPortalStateError
        | PartnerPortalWithdrawalDisabledError
    ),
) -> NoReturn:
    if isinstance(exception, PartnerPortalBadRequestError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    if isinstance(exception, PartnerPortalNotPartnerError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exception),
        ) from exception
    if isinstance(exception, PartnerPortalWithdrawalDisabledError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": exception.code,
                "message": exception.message,
            },
        ) from exception
    if isinstance(exception, PartnerPortalStateError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exception),
        ) from exception


def _build_partner_info_response(snapshot: PartnerInfoSnapshot) -> PartnerInfoResponse:
    return PartnerInfoResponse(
        is_partner=snapshot.is_partner,
        is_active=snapshot.is_active,
        can_withdraw=snapshot.can_withdraw,
        apply_support_url=snapshot.apply_support_url,
        effective_currency=snapshot.effective_currency,
        min_withdrawal_rub=snapshot.min_withdrawal_rub,
        min_withdrawal_display=snapshot.min_withdrawal_display,
        balance=snapshot.balance,
        balance_display=snapshot.balance_display,
        total_earned=snapshot.total_earned,
        total_earned_display=snapshot.total_earned_display,
        total_withdrawn=snapshot.total_withdrawn,
        total_withdrawn_display=snapshot.total_withdrawn_display,
        referrals_count=snapshot.referrals_count,
        level2_referrals_count=snapshot.level2_referrals_count,
        level3_referrals_count=snapshot.level3_referrals_count,
        referral_link=snapshot.referral_link,
        telegram_referral_link=snapshot.telegram_referral_link,
        web_referral_link=snapshot.web_referral_link,
        use_global_settings=snapshot.use_global_settings,
        effective_reward_type=snapshot.effective_reward_type,
        effective_accrual_strategy=snapshot.effective_accrual_strategy,
        level_settings=[
            PartnerLevelSettingResponse(
                level=level_setting.level,
                referrals_count=level_setting.referrals_count,
                earned_amount=level_setting.earned_amount,
                global_percent=level_setting.global_percent,
                individual_percent=level_setting.individual_percent,
                individual_fixed_amount=level_setting.individual_fixed_amount,
                effective_percent=level_setting.effective_percent,
                effective_fixed_amount=level_setting.effective_fixed_amount,
                uses_global_value=level_setting.uses_global_value,
            )
            for level_setting in snapshot.level_settings
        ],
    )


def _build_partner_referrals_response(
    page_snapshot: PartnerReferralsPageSnapshot,
) -> PartnerReferralsListResponse:
    return PartnerReferralsListResponse(
        referrals=[
            PartnerReferralResponse(
                telegram_id=referral.telegram_id,
                username=referral.username,
                name=referral.name,
                level=referral.level,
                joined_at=referral.joined_at,
                invite_source=referral.invite_source,
                is_active=referral.is_active,
                is_paid=referral.is_paid,
                first_paid_at=referral.first_paid_at,
                total_paid_amount=referral.total_paid_amount,
                total_earned=referral.total_earned,
                total_paid_amount_display=referral.total_paid_amount_display,
                total_earned_display=referral.total_earned_display,
                display_currency=referral.display_currency,
            )
            for referral in page_snapshot.referrals
        ],
        total=page_snapshot.total,
        page=page_snapshot.page,
        limit=page_snapshot.limit,
    )


def _build_partner_earnings_response(
    page_snapshot: PartnerEarningsPageSnapshot,
) -> PartnerEarningsListResponse:
    return PartnerEarningsListResponse(
        earnings=[
            PartnerEarningResponse(
                id=earning.id,
                referral_telegram_id=earning.referral_telegram_id,
                referral_username=earning.referral_username,
                level=earning.level,
                payment_amount=earning.payment_amount,
                payment_amount_display=earning.payment_amount_display,
                percent=earning.percent,
                earned_amount=earning.earned_amount,
                earned_amount_display=earning.earned_amount_display,
                display_currency=earning.display_currency,
                created_at=earning.created_at,
            )
            for earning in page_snapshot.earnings
        ],
        total=page_snapshot.total,
        page=page_snapshot.page,
        limit=page_snapshot.limit,
    )


def _build_partner_withdrawal_response(
    snapshot: PartnerWithdrawalSnapshot,
) -> PartnerWithdrawalResponse:
    return PartnerWithdrawalResponse(
        id=snapshot.id,
        amount=snapshot.amount,
        display_amount=snapshot.display_amount,
        display_currency=snapshot.display_currency,
        requested_amount=snapshot.requested_amount,
        requested_currency=snapshot.requested_currency,
        quote_rate=snapshot.quote_rate,
        quote_source=snapshot.quote_source,
        status=snapshot.status,
        method=snapshot.method,
        requisites=snapshot.requisites,
        admin_comment=snapshot.admin_comment,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def _build_partner_withdrawals_response(
    snapshot: PartnerWithdrawalsSnapshot,
) -> PartnerWithdrawalsListResponse:
    return PartnerWithdrawalsListResponse(
        withdrawals=[
            _build_partner_withdrawal_response(withdrawal)
            for withdrawal in snapshot.withdrawals
        ]
    )
