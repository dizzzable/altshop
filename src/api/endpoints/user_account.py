"""User account endpoints: profile, plans, and activity history."""

from __future__ import annotations

from typing import Any, cast

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.contracts.user_account import (
    SetPartnerBalanceCurrencyRequest,
    SetSecurityEmailRequest,
)
from src.api.dependencies.web_auth import get_current_user
from src.api.presenters.user_account import (
    MarkReadResponse,
    PlanResponse,
    TransactionHistoryResponse,
    UnreadCountResponse,
    UserNotificationListResponse,
    UserProfileResponse,
    _build_plan_response,
    _build_transaction_history_response,
    _build_user_notification_list_response,
    _build_user_profile_response,
)
from src.core.enums import PurchaseChannel
from src.infrastructure.database.models.dto import UserDto
from src.services.email_recovery import EmailRecoveryService
from src.services.plan_catalog import PlanCatalogService
from src.services.user_activity_portal import UserActivityPortalService
from src.services.user_profile import UserProfileService
from src.services.user import UserService
from src.services.web_account import WebAccountService

router = APIRouter(prefix="/api/v1", tags=["User API"])
_DISHKA_DEFAULT = cast(Any, None)


@router.get("/user/me", response_model=UserProfileResponse)
@inject
async def get_user_profile(
    current_user: UserDto = Depends(get_current_user),
    user_profile_service: FromDishka[UserProfileService] = _DISHKA_DEFAULT,
) -> UserProfileResponse:
    """Get current user profile information."""
    profile = await user_profile_service.build_snapshot(user=current_user)
    return _build_user_profile_response(profile)


@router.patch("/user/security/email", response_model=UserProfileResponse)
@inject
async def set_security_email(
    payload: SetSecurityEmailRequest,
    current_user: UserDto = Depends(get_current_user),
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    user_profile_service: FromDishka[UserProfileService] = _DISHKA_DEFAULT,
) -> UserProfileResponse:
    web_account = await web_account_service.get_by_user_telegram_id(current_user.telegram_id)
    if not web_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Web account is required for this action",
        )

    try:
        await email_recovery_service.set_email(
            web_account_id=web_account.id or 0,
            email=payload.email,
        )
        updated_web_account = await web_account_service.get_by_user_telegram_id(
            current_user.telegram_id
        )
        if updated_web_account:
            await email_recovery_service.request_email_verification(web_account=updated_web_account)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    profile = await user_profile_service.build_snapshot(
        user=current_user,
        web_account=updated_web_account,
    )
    return _build_user_profile_response(profile)


@router.patch("/user/partner-balance-currency", response_model=UserProfileResponse)
@inject
async def set_partner_balance_currency(
    payload: SetPartnerBalanceCurrencyRequest,
    current_user: UserDto = Depends(get_current_user),
    user_service: FromDishka[UserService] = _DISHKA_DEFAULT,
    user_profile_service: FromDishka[UserProfileService] = _DISHKA_DEFAULT,
) -> UserProfileResponse:
    await user_service.set_partner_balance_currency_override(
        user=current_user,
        currency=payload.currency,
    )
    refreshed_user = await user_service.get(current_user.telegram_id)
    if refreshed_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    profile = await user_profile_service.build_snapshot(user=refreshed_user)
    return _build_user_profile_response(profile)


@router.get("/plans", response_model=list[PlanResponse])
@inject
async def list_plans(
    current_user: UserDto = Depends(get_current_user),
    channel: PurchaseChannel = Query(default=PurchaseChannel.WEB),
    plan_catalog_service: FromDishka[PlanCatalogService] = _DISHKA_DEFAULT,
) -> list[PlanResponse]:
    """Get plans available for current user."""
    snapshots = await plan_catalog_service.list_available_plans(
        current_user=current_user,
        channel=channel,
    )
    return [_build_plan_response(snapshot) for snapshot in snapshots]


@router.get("/user/transactions", response_model=TransactionHistoryResponse)
@inject
async def list_user_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserDto = Depends(get_current_user),
    user_activity_portal_service: FromDishka[UserActivityPortalService] = _DISHKA_DEFAULT,
) -> TransactionHistoryResponse:
    """Get paginated transaction history for current user."""
    snapshot = await user_activity_portal_service.list_transactions(
        current_user=current_user,
        page=page,
        limit=limit,
    )
    return _build_transaction_history_response(snapshot)


@router.get("/user/notifications", response_model=UserNotificationListResponse)
@inject
async def list_user_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserDto = Depends(get_current_user),
    user_activity_portal_service: FromDishka[UserActivityPortalService] = _DISHKA_DEFAULT,
) -> UserNotificationListResponse:
    snapshot = await user_activity_portal_service.list_notifications(
        current_user=current_user,
        page=page,
        limit=limit,
    )
    return _build_user_notification_list_response(snapshot)


@router.get("/user/notifications/unread-count", response_model=UnreadCountResponse)
@inject
async def get_user_notifications_unread_count(
    current_user: UserDto = Depends(get_current_user),
    user_activity_portal_service: FromDishka[UserActivityPortalService] = _DISHKA_DEFAULT,
) -> UnreadCountResponse:
    unread = await user_activity_portal_service.get_notifications_unread_count(
        current_user=current_user
    )
    return UnreadCountResponse(unread=unread)


@router.post("/user/notifications/{notification_id}/read", response_model=MarkReadResponse)
@inject
async def mark_user_notification_read(
    notification_id: int,
    current_user: UserDto = Depends(get_current_user),
    user_activity_portal_service: FromDishka[UserActivityPortalService] = _DISHKA_DEFAULT,
) -> MarkReadResponse:
    updated = await user_activity_portal_service.mark_notification_read(
        notification_id=notification_id,
        current_user=current_user,
    )
    return MarkReadResponse(updated=updated)


@router.post("/user/notifications/read-all", response_model=MarkReadResponse)
@inject
async def mark_all_user_notifications_read(
    current_user: UserDto = Depends(get_current_user),
    user_activity_portal_service: FromDishka[UserActivityPortalService] = _DISHKA_DEFAULT,
) -> MarkReadResponse:
    updated = await user_activity_portal_service.mark_all_notifications_read(
        current_user=current_user,
    )
    return MarkReadResponse(updated=updated)
