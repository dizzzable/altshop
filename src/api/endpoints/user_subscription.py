"""User subscription endpoints: subscriptions, purchases, devices, and promocodes."""

from __future__ import annotations

from typing import Any, cast

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.contracts.user_subscription import (
    GenerateDeviceRequest,
    PurchaseQuoteRequest,
    PromocodeActivateRequest,
    PurchaseRequest,
    SubscriptionAssignmentRequest,
    TrialRequest,
)
from src.api.contracts.user_subscription import (
    build_subscription_assignment_update as _build_subscription_assignment_update,
)
from src.api.contracts.user_subscription import (
    build_subscription_purchase_request as _build_subscription_purchase_request,
)
from src.api.dependencies.web_auth import get_current_user, require_web_product_access
from src.api.presenters.user_account import (
    DeviceListResponse,
    GenerateDeviceResponse,
    PromocodeActivateResponse,
    PromocodeActivationHistoryResponse,
    PurchaseResponse,
    PurchaseQuoteResponse,
    SubscriptionListResponse,
    SubscriptionResponse,
    TrialEligibilityResponse,
    _build_device_list_response,
    _build_generated_device_response,
    _build_promocode_activation_history_response,
    _build_promocode_activation_response,
    _build_purchase_response,
    _build_purchase_quote_response,
    _build_trial_eligibility_response,
    _raise_purchase_access_http_error,
    _raise_subscription_device_http_error,
    _raise_subscription_portal_http_error,
    _raise_subscription_purchase_http_error,
    build_subscription_response,
)
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.subscriptions import (
    refresh_user_subscriptions_runtime_task,
)
from src.services.promocode_portal import (
    PromocodePortalError,
    PromocodePortalService,
)
from src.services.purchase_access import PurchaseAccessError
from src.services.subscription import SubscriptionService
from src.services.subscription_device import (
    SubscriptionDeviceError,
    SubscriptionDeviceService,
)
from src.services.subscription_portal import (
    SubscriptionPortalAccessDeniedError,
    SubscriptionPortalBadRequestError,
    SubscriptionPortalNotFoundError,
    SubscriptionPortalService,
    SubscriptionPortalStateError,
)
from src.services.subscription_purchase import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseService,
)
from src.services.subscription_runtime import SubscriptionRuntimeService
from src.services.subscription_trial import (
    SubscriptionTrialError,
    SubscriptionTrialService,
)
from src.services.user_activity_portal import UserActivityPortalService

router = APIRouter(prefix="/api/v1", tags=["User API"])
_DISHKA_DEFAULT = cast(Any, None)


@router.get("/subscription/list", response_model=SubscriptionListResponse)
@inject
async def list_subscriptions(
    current_user: UserDto = Depends(require_web_product_access),
    subscription_service: FromDishka[SubscriptionService] = _DISHKA_DEFAULT,
    subscription_runtime_service: FromDishka[SubscriptionRuntimeService] = _DISHKA_DEFAULT,
) -> SubscriptionListResponse:
    """Get all user subscriptions."""
    subscriptions = await subscription_service.get_all_by_user(current_user.telegram_id)

    async def enqueue_runtime_refresh(subscription_ids: list[int]) -> None:
        await refresh_user_subscriptions_runtime_task.kiq(subscription_ids)

    refreshed_subscriptions = await subscription_runtime_service.prepare_for_list_batch(
        subscriptions=subscriptions,
        user_telegram_id=current_user.telegram_id,
        enqueue_runtime_refresh=enqueue_runtime_refresh,
    )

    return SubscriptionListResponse(
        subscriptions=[
            build_subscription_response(sub, fallback_user_telegram_id=current_user.telegram_id)
            for sub in refreshed_subscriptions
        ]
    )


@router.get("/subscription/{subscription_id}", response_model=SubscriptionResponse)
@inject
async def get_subscription(
    subscription_id: int,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_portal_service: FromDishka[SubscriptionPortalService] = _DISHKA_DEFAULT,
) -> SubscriptionResponse:
    """Get subscription by ID."""
    try:
        refreshed_subscription = await subscription_portal_service.get_detail(
            subscription_id=subscription_id,
            current_user=current_user,
        )
    except (
        SubscriptionPortalNotFoundError,
        SubscriptionPortalAccessDeniedError,
        SubscriptionPortalBadRequestError,
        SubscriptionPortalStateError,
    ) as exception:
        _raise_subscription_portal_http_error(exception)
    return build_subscription_response(
        refreshed_subscription,
        fallback_user_telegram_id=current_user.telegram_id,
)


@router.patch("/subscription/{subscription_id}/assignment", response_model=SubscriptionResponse)
@inject
async def update_subscription_assignment(
    subscription_id: int,
    payload: SubscriptionAssignmentRequest,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_portal_service: FromDishka[SubscriptionPortalService] = _DISHKA_DEFAULT,
) -> SubscriptionResponse:
    try:
        updated_subscription = await subscription_portal_service.update_assignment(
            subscription_id=subscription_id,
            current_user=current_user,
            update=_build_subscription_assignment_update(payload),
        )
    except (
        SubscriptionPortalNotFoundError,
        SubscriptionPortalAccessDeniedError,
        SubscriptionPortalBadRequestError,
        SubscriptionPortalStateError,
    ) as exception:
        _raise_subscription_portal_http_error(exception)

    return build_subscription_response(
        updated_subscription,
        fallback_user_telegram_id=current_user.telegram_id,
    )


@router.delete("/subscription/{subscription_id}")
@inject
async def delete_subscription(
    subscription_id: int,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_portal_service: FromDishka[SubscriptionPortalService] = _DISHKA_DEFAULT,
) -> dict:
    """Delete subscription by ID."""
    try:
        result = await subscription_portal_service.delete_subscription(
            subscription_id=subscription_id,
            current_user=current_user,
        )
    except (
        SubscriptionPortalNotFoundError,
        SubscriptionPortalAccessDeniedError,
        SubscriptionPortalBadRequestError,
        SubscriptionPortalStateError,
    ) as exception:
        _raise_subscription_portal_http_error(exception)
    return {"success": result.success, "message": result.message}


@router.post("/subscription/purchase", response_model=PurchaseResponse)
@inject
async def purchase_subscription(
    request: PurchaseRequest,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService] = _DISHKA_DEFAULT,
) -> PurchaseResponse:
    """
    Purchase a new subscription or renew existing one.

    Supports:
    - NEW: Purchase new subscription
    - RENEW: Renew single or multiple subscriptions
    - ADDITIONAL: Purchase additional subscription
    """
    try:
        result = await subscription_purchase_service.execute(
            request=_build_subscription_purchase_request(request),
            current_user=current_user,
        )
    except PurchaseAccessError as exception:
        _raise_purchase_access_http_error(exception)
    except SubscriptionPurchaseError as exception:
        _raise_subscription_purchase_http_error(exception)

    return _build_purchase_response(result)


@router.post("/subscription/quote", response_model=PurchaseQuoteResponse)
@inject
async def quote_subscription(
    request: PurchaseQuoteRequest,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService] = _DISHKA_DEFAULT,
) -> PurchaseQuoteResponse:
    try:
        result = await subscription_purchase_service.quote(
            request=_build_subscription_purchase_request(request),
            current_user=current_user,
        )
    except PurchaseAccessError as exception:
        _raise_purchase_access_http_error(exception)
    except SubscriptionPurchaseError as exception:
        _raise_subscription_purchase_http_error(exception)

    return _build_purchase_quote_response(result)


@router.post("/subscription/{subscription_id}/renew", response_model=PurchaseResponse)
@inject
async def renew_subscription(
    subscription_id: int,
    request: PurchaseRequest,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService] = _DISHKA_DEFAULT,
) -> PurchaseResponse:
    """Renew subscription via dedicated endpoint alias."""
    try:
        result = await subscription_purchase_service.execute_renewal_alias(
            subscription_id=subscription_id,
            request=_build_subscription_purchase_request(request),
            current_user=current_user,
        )
    except PurchaseAccessError as exception:
        _raise_purchase_access_http_error(exception)
    except SubscriptionPurchaseError as exception:
        _raise_subscription_purchase_http_error(exception)

    return _build_purchase_response(result)


@router.get("/subscription/trial/eligibility", response_model=TrialEligibilityResponse)
@inject
async def get_trial_subscription_eligibility(
    current_user: UserDto = Depends(require_web_product_access),
    subscription_trial_service: FromDishka[SubscriptionTrialService] = _DISHKA_DEFAULT,
) -> TrialEligibilityResponse:
    """Get trial eligibility for current user without activating trial."""
    try:
        snapshot = await subscription_trial_service.get_eligibility(current_user)
    except PurchaseAccessError as exception:
        _raise_purchase_access_http_error(exception)

    return _build_trial_eligibility_response(snapshot)


@router.post("/subscription/trial", response_model=SubscriptionResponse)
@inject
async def get_trial_subscription(
    request: TrialRequest | None = None,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_trial_service: FromDishka[SubscriptionTrialService] = _DISHKA_DEFAULT,
) -> SubscriptionResponse:
    """Create trial subscription for current user."""
    try:
        created_subscription = await subscription_trial_service.create_trial_subscription(
            current_user=current_user,
            plan_id=request.plan_id if request else None,
        )
    except PurchaseAccessError as exception:
        _raise_purchase_access_http_error(exception)
    except SubscriptionTrialError as exception:
        raise HTTPException(
            status_code=exception.status_code,
            detail=exception.detail,
        ) from exception

    return build_subscription_response(
        created_subscription,
        fallback_user_telegram_id=current_user.telegram_id,
    )


@router.get("/devices", response_model=DeviceListResponse)
@inject
async def list_devices(
    subscription_id: int = Query(..., description="Subscription ID"),
    current_user: UserDto = Depends(require_web_product_access),
    subscription_device_service: FromDishka[SubscriptionDeviceService] = _DISHKA_DEFAULT,
) -> DeviceListResponse:
    """Get devices for a subscription."""
    try:
        result = await subscription_device_service.list_devices(
            subscription_id=subscription_id,
            user_telegram_id=current_user.telegram_id,
        )
    except SubscriptionDeviceError as exception:
        _raise_subscription_device_http_error(exception)

    return _build_device_list_response(result)


@router.post("/devices/generate", response_model=GenerateDeviceResponse)
@inject
async def generate_device_link(
    request: GenerateDeviceRequest,
    current_user: UserDto = Depends(require_web_product_access),
    subscription_device_service: FromDishka[SubscriptionDeviceService] = _DISHKA_DEFAULT,
) -> GenerateDeviceResponse:
    try:
        result = await subscription_device_service.generate_device_link(
            subscription_id=request.subscription_id,
            user_telegram_id=current_user.telegram_id,
            device_type=request.device_type,
        )
    except SubscriptionDeviceError as exception:
        _raise_subscription_device_http_error(exception)

    return _build_generated_device_response(result)


@router.delete("/devices/{hwid}")
@inject
async def revoke_device(
    hwid: str,
    subscription_id: int = Query(..., description="Subscription ID"),
    current_user: UserDto = Depends(require_web_product_access),
    subscription_device_service: FromDishka[SubscriptionDeviceService] = _DISHKA_DEFAULT,
) -> dict:
    """Revoke device access."""
    try:
        result = await subscription_device_service.revoke_device(
            subscription_id=subscription_id,
            user_telegram_id=current_user.telegram_id,
            hwid=hwid,
        )
    except SubscriptionDeviceError as exception:
        _raise_subscription_device_http_error(exception)

    return {"success": result.success, "message": result.message}


@router.post("/promocode/activate", response_model=PromocodeActivateResponse)
@inject
async def activate_promocode(
    request: PromocodeActivateRequest,
    current_user: UserDto = Depends(require_web_product_access),
    promocode_portal_service: FromDishka[PromocodePortalService] = _DISHKA_DEFAULT,
) -> PromocodeActivateResponse:
    try:
        snapshot = await promocode_portal_service.activate(
            current_user=current_user,
            code=request.code,
            subscription_id=request.subscription_id,
            create_new=request.create_new,
        )
    except PurchaseAccessError as exception:
        _raise_purchase_access_http_error(exception)
    except PromocodePortalError as exception:
        raise HTTPException(
            status_code=exception.status_code,
            detail=exception.detail,
        ) from exception

    return _build_promocode_activation_response(snapshot)


@router.get("/promocode/activations", response_model=PromocodeActivationHistoryResponse)
@inject
async def list_promocode_activations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserDto = Depends(get_current_user),
    user_activity_portal_service: FromDishka[UserActivityPortalService] = _DISHKA_DEFAULT,
) -> PromocodeActivationHistoryResponse:
    """Get paginated promocode activation history for current user."""
    snapshot = await user_activity_portal_service.list_promocode_activations(
        current_user=current_user,
        page=page,
        limit=limit,
    )
    return _build_promocode_activation_history_response(snapshot)
