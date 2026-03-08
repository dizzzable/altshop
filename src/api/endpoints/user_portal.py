"""User portal endpoints: referral and partner flows."""

from __future__ import annotations

from typing import Any, cast

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.api.contracts.user_portal import (
    PartnerWithdrawalRequest,
    ReferralExchangeExecuteRequest,
)
from src.api.dependencies.web_auth import get_current_user, require_web_product_access
from src.api.presenters.user_portal import (
    PartnerEarningsListResponse,
    PartnerInfoResponse,
    PartnerReferralsListResponse,
    PartnerWithdrawalResponse,
    PartnerWithdrawalsListResponse,
    ReferralAboutResponse,
    ReferralExchangeExecuteResponse,
    ReferralExchangeOptionsResponse,
    ReferralInfoResponse,
    ReferralListResponse,
    _build_partner_earnings_response,
    _build_partner_info_response,
    _build_partner_referrals_response,
    _build_partner_withdrawal_response,
    _build_partner_withdrawals_response,
    _build_referral_about_response,
    _build_referral_exchange_execute_response,
    _build_referral_exchange_options_response,
    _build_referral_info_response,
    _build_referral_list_response,
    _raise_partner_portal_http_error,
    _raise_referral_portal_http_error,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.partner_portal import (
    PartnerPortalBadRequestError,
    PartnerPortalNotPartnerError,
    PartnerPortalService,
    PartnerPortalStateError,
    PartnerPortalWithdrawalDisabledError,
)
from src.services.referral_exchange import ReferralExchangeError
from src.services.referral_portal import (
    ReferralPortalAccessDeniedError,
    ReferralPortalService,
)

router = APIRouter(prefix="/api/v1", tags=["User API"])
_DISHKA_DEFAULT = cast(Any, None)


@router.get("/referral/info", response_model=ReferralInfoResponse)
@inject
async def get_referral_info(
    current_user: UserDto = Depends(get_current_user),
    referral_portal_service: FromDishka[ReferralPortalService] = _DISHKA_DEFAULT,
) -> ReferralInfoResponse:
    """Get user's referral information."""
    try:
        snapshot = await referral_portal_service.get_info(current_user)
    except ReferralPortalAccessDeniedError as exception:
        _raise_referral_portal_http_error(exception)

    return _build_referral_info_response(snapshot)


@router.get("/referral/qr")
@inject
async def get_referral_qr(
    target: str = Query("telegram", pattern="^(telegram|web)$"),
    current_user: UserDto = Depends(get_current_user),
    referral_portal_service: FromDishka[ReferralPortalService] = _DISHKA_DEFAULT,
) -> Response:
    """Generate referral QR code for Telegram bot or web invite link."""
    try:
        qr_bytes = await referral_portal_service.build_qr_image(
            target=target,
            current_user=current_user,
        )
    except ReferralPortalAccessDeniedError as exception:
        _raise_referral_portal_http_error(exception)

    return Response(content=qr_bytes, media_type="image/png")


@router.get("/referral/list", response_model=ReferralListResponse)
@inject
async def list_referrals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserDto = Depends(get_current_user),
    referral_portal_service: FromDishka[ReferralPortalService] = _DISHKA_DEFAULT,
) -> ReferralListResponse:
    """Get user's referrals list."""
    try:
        page_snapshot = await referral_portal_service.list_referrals(
            current_user=current_user,
            page=page,
            limit=limit,
        )
    except ReferralPortalAccessDeniedError as exception:
        _raise_referral_portal_http_error(exception)

    return _build_referral_list_response(page_snapshot)


@router.get("/referral/exchange/options", response_model=ReferralExchangeOptionsResponse)
@inject
async def get_referral_exchange_options(
    current_user: UserDto = Depends(get_current_user),
    referral_portal_service: FromDishka[ReferralPortalService] = _DISHKA_DEFAULT,
) -> ReferralExchangeOptionsResponse:
    try:
        options = await referral_portal_service.get_exchange_options(current_user)
    except ReferralPortalAccessDeniedError as exception:
        _raise_referral_portal_http_error(exception)

    return _build_referral_exchange_options_response(options)


@router.post("/referral/exchange/execute", response_model=ReferralExchangeExecuteResponse)
@inject
async def execute_referral_exchange(
    request: ReferralExchangeExecuteRequest,
    current_user: UserDto = Depends(require_web_product_access),
    referral_portal_service: FromDishka[ReferralPortalService] = _DISHKA_DEFAULT,
) -> ReferralExchangeExecuteResponse:
    try:
        execution_result = await referral_portal_service.execute_exchange(
            current_user=current_user,
            exchange_type=request.exchange_type,
            subscription_id=request.subscription_id,
            gift_plan_id=request.gift_plan_id,
        )
    except ReferralPortalAccessDeniedError as exception:
        _raise_referral_portal_http_error(exception)
    except ReferralExchangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return _build_referral_exchange_execute_response(execution_result)


@router.get("/referral/about", response_model=ReferralAboutResponse)
@inject
async def get_referral_about(
    current_user: UserDto = Depends(get_current_user),
    referral_portal_service: FromDishka[ReferralPortalService] = _DISHKA_DEFAULT,
) -> ReferralAboutResponse:
    """Get referral program information."""
    del current_user
    return _build_referral_about_response(referral_portal_service.get_about())


@router.get("/partner/info", response_model=PartnerInfoResponse)
@inject
async def get_partner_info(
    current_user: UserDto = Depends(get_current_user),
    partner_portal_service: FromDishka[PartnerPortalService] = _DISHKA_DEFAULT,
) -> PartnerInfoResponse:
    """Get partner information."""
    snapshot = await partner_portal_service.get_info(current_user)
    return _build_partner_info_response(snapshot)


@router.get("/partner/referrals", response_model=PartnerReferralsListResponse)
@inject
async def list_partner_referrals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserDto = Depends(get_current_user),
    partner_portal_service: FromDishka[PartnerPortalService] = _DISHKA_DEFAULT,
) -> PartnerReferralsListResponse:
    """Get partner's referrals list."""
    page_snapshot = await partner_portal_service.list_referrals(
        current_user=current_user,
        page=page,
        limit=limit,
    )
    return _build_partner_referrals_response(page_snapshot)


@router.get("/partner/earnings", response_model=PartnerEarningsListResponse)
@inject
async def list_partner_earnings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserDto = Depends(get_current_user),
    partner_portal_service: FromDishka[PartnerPortalService] = _DISHKA_DEFAULT,
) -> PartnerEarningsListResponse:
    """Get partner's earnings history."""
    try:
        page_snapshot = await partner_portal_service.list_earnings(
            current_user=current_user,
            page=page,
            limit=limit,
        )
    except PartnerPortalStateError as exception:
        _raise_partner_portal_http_error(exception)

    return _build_partner_earnings_response(page_snapshot)


@router.post("/partner/withdraw", response_model=PartnerWithdrawalResponse)
@inject
async def request_withdrawal(
    request: PartnerWithdrawalRequest,
    current_user: UserDto = Depends(require_web_product_access),
    partner_portal_service: FromDishka[PartnerPortalService] = _DISHKA_DEFAULT,
) -> PartnerWithdrawalResponse:
    """Request withdrawal from partner balance."""
    try:
        withdrawal_snapshot = await partner_portal_service.request_withdrawal(
            current_user=current_user,
            amount=request.amount,
            method=request.method,
            requisites=request.requisites,
        )
    except (
        PartnerPortalBadRequestError,
        PartnerPortalNotPartnerError,
        PartnerPortalStateError,
        PartnerPortalWithdrawalDisabledError,
    ) as exception:
        _raise_partner_portal_http_error(exception)

    return _build_partner_withdrawal_response(withdrawal_snapshot)


@router.get("/partner/withdrawals", response_model=PartnerWithdrawalsListResponse)
@inject
async def list_partner_withdrawals(
    current_user: UserDto = Depends(get_current_user),
    partner_portal_service: FromDishka[PartnerPortalService] = _DISHKA_DEFAULT,
) -> PartnerWithdrawalsListResponse:
    """Get partner's withdrawal history."""
    try:
        withdrawals_snapshot = await partner_portal_service.list_withdrawals(
            current_user=current_user
        )
    except PartnerPortalStateError as exception:
        _raise_partner_portal_http_error(exception)

    return _build_partner_withdrawals_response(withdrawals_snapshot)
