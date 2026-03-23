from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel

from src.infrastructure.database.models.dto import SubscriptionDto
from src.services.plan_catalog import PlanCatalogItemSnapshot
from src.services.promocode_portal import PromocodeActivationSnapshot
from src.services.purchase_access import PurchaseAccessError
from src.services.subscription_device import (
    GeneratedSubscriptionDeviceLink,
    SubscriptionDeviceAccessDeniedError,
    SubscriptionDeviceError,
    SubscriptionDeviceLimitReachedError,
    SubscriptionDeviceListResult,
    SubscriptionDeviceNotFoundError,
)
from src.services.subscription_portal import (
    SubscriptionPortalAccessDeniedError,
    SubscriptionPortalBadRequestError,
    SubscriptionPortalNotFoundError,
    SubscriptionPortalStateError,
)
from src.services.subscription_purchase import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseQuoteResult,
    SubscriptionPurchaseResult,
)
from src.services.subscription_purchase_policy import (
    SubscriptionActionPolicy,
    SubscriptionPurchaseOptionsResult,
)
from src.services.subscription_trial import TrialEligibilitySnapshot
from src.services.user_activity_portal import (
    PromocodeActivationHistoryPageSnapshot,
    TransactionHistoryPageSnapshot,
    UserNotificationPageSnapshot,
)
from src.services.user_profile import UserProfileSnapshot


class UserProfileResponse(BaseModel):
    """User profile response."""

    telegram_id: int
    username: str | None
    web_login: str | None = None
    name: str | None
    role: str
    points: int
    language: str
    default_currency: str
    personal_discount: int
    purchase_discount: int
    partner_balance_currency_override: str | None = None
    effective_partner_balance_currency: str = "RUB"
    is_blocked: bool
    is_bot_blocked: bool
    created_at: str
    updated_at: str
    email: str | None = None
    email_verified: bool = False
    telegram_linked: bool = False
    linked_telegram_id: int | None = None
    show_link_prompt: bool = False
    requires_password_change: bool = False
    effective_max_subscriptions: int = 1
    active_subscriptions_count: int = 0
    is_partner: bool = False
    is_partner_active: bool = False
    has_web_account: bool = False
    needs_web_credentials_bootstrap: bool = False


class PlanPriceResponse(BaseModel):
    """Plan price response."""

    id: int
    duration_id: int
    gateway_type: str
    price: float
    original_price: float
    currency: str
    discount_percent: int
    discount_source: str
    discount: int = 0
    supported_payment_assets: list[str] | None = None


class PlanDurationResponse(BaseModel):
    """Plan duration response."""

    id: int
    plan_id: int
    days: int
    prices: list[PlanPriceResponse]


class PlanResponse(BaseModel):
    """Plan response."""

    id: int
    name: str
    description: str | None
    tag: str | None
    type: str
    availability: str
    traffic_limit: int
    device_limit: int
    order_index: int
    is_active: bool
    allowed_user_ids: list[int]
    internal_squads: list[str]
    external_squad: str | None
    durations: list[PlanDurationResponse]
    created_at: str
    updated_at: str


class SubscriptionResponse(BaseModel):
    """Subscription response."""

    id: int
    user_remna_id: UUID
    user_telegram_id: int
    status: str
    is_trial: bool
    traffic_limit: int
    traffic_used: int
    device_limit: int
    devices_count: int
    internal_squads: list[str]
    external_squad: str | None
    expire_at: str
    url: str
    device_type: str | None
    can_renew: bool = False
    can_upgrade: bool = False
    can_multi_renew: bool = False
    renew_mode: str | None = None
    plan: dict
    created_at: str
    updated_at: str


class SubscriptionListResponse(BaseModel):
    """Subscription list response."""

    subscriptions: list[SubscriptionResponse]


class TransactionPricingResponse(BaseModel):
    """Transaction price snapshot."""

    original_amount: float
    discount_percent: int
    final_amount: float


class TransactionHistoryItemResponse(BaseModel):
    """Single transaction item for user history."""

    payment_id: str
    user_telegram_id: int
    status: str
    purchase_type: str
    channel: str | None = None
    gateway_type: str
    pricing: TransactionPricingResponse
    currency: str
    payment_asset: str | None = None
    plan: dict
    renew_subscription_id: int | None = None
    renew_subscription_ids: list[int] | None = None
    device_types: list[str] | None = None
    is_test: bool
    created_at: str
    updated_at: str


class TransactionHistoryResponse(BaseModel):
    """Paginated transaction history response."""

    transactions: list[TransactionHistoryItemResponse]
    total: int
    page: int
    limit: int


class UserNotificationItemResponse(BaseModel):
    id: int
    type: str
    title: str
    message: str
    is_read: bool
    read_at: str | None = None
    created_at: str


class UserNotificationListResponse(BaseModel):
    notifications: list[UserNotificationItemResponse]
    total: int
    page: int
    limit: int
    unread: int


class UnreadCountResponse(BaseModel):
    unread: int


class MarkReadResponse(BaseModel):
    updated: int


class PurchaseResponse(BaseModel):
    """Purchase response."""

    transaction_id: str
    payment_url: str | None
    url: str | None = None
    status: str
    message: str


class PurchaseQuoteResponse(BaseModel):
    price: float
    original_price: float
    currency: str
    settlement_price: float
    settlement_original_price: float
    settlement_currency: str
    discount_percent: int
    discount_source: str
    payment_asset: str | None = None
    quote_source: str
    quote_expires_at: str
    quote_provider_count: int


class SubscriptionPurchaseOptionsResponse(BaseModel):
    purchase_type: str
    subscription_id: int
    source_plan_missing: bool
    selection_locked: bool
    renew_mode: str | None = None
    warning_code: str | None = None
    warning_message: str | None = None
    plans: list[PlanResponse]


class TrialEligibilityResponse(BaseModel):
    """Trial eligibility snapshot for web purchase UI."""

    eligible: bool
    reason_code: str | None = None
    reason_message: str | None = None
    requires_telegram_link: bool = False
    trial_plan_id: int | None = None


class DeviceResponse(BaseModel):
    """Device response."""

    hwid: str
    device_type: str
    first_connected: str | None
    last_connected: str | None
    country: str | None
    ip: str | None


class DeviceListResponse(BaseModel):
    """Device list response."""

    devices: list[DeviceResponse]
    subscription_id: int
    device_limit: int
    devices_count: int


class GenerateDeviceResponse(BaseModel):
    """Generate device link response."""

    hwid: str
    connection_url: str
    device_type: str


class PromocodeReward(BaseModel):
    """Promocode reward details."""

    type: str
    value: int


class PromocodeActivateResponse(BaseModel):
    """Activate promocode response."""

    message: str
    reward: PromocodeReward | None = None
    next_step: str | None = None
    available_subscriptions: list[int] | None = None


class PromocodeActivationHistoryReward(BaseModel):
    """Promocode activation reward snapshot."""

    type: str
    value: int


class PromocodeActivationHistoryItem(BaseModel):
    """Promocode activation history item."""

    id: int
    code: str
    reward: PromocodeActivationHistoryReward
    target_subscription_id: int | None = None
    activated_at: str


class PromocodeActivationHistoryResponse(BaseModel):
    """Paginated promocode activation history response."""

    activations: list[PromocodeActivationHistoryItem]
    total: int
    page: int
    limit: int


def _build_user_profile_response(profile: UserProfileSnapshot) -> UserProfileResponse:
    return UserProfileResponse(
        telegram_id=profile.telegram_id,
        username=profile.username,
        web_login=profile.web_login,
        name=profile.safe_name,
        role=profile.role,
        points=profile.points,
        language=profile.language,
        default_currency=profile.default_currency,
        personal_discount=profile.personal_discount,
        purchase_discount=profile.purchase_discount,
        partner_balance_currency_override=profile.partner_balance_currency_override,
        effective_partner_balance_currency=profile.effective_partner_balance_currency,
        is_blocked=profile.is_blocked,
        is_bot_blocked=profile.is_bot_blocked,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        email=profile.email,
        email_verified=profile.email_verified,
        telegram_linked=profile.telegram_linked,
        linked_telegram_id=profile.linked_telegram_id,
        show_link_prompt=profile.show_link_prompt,
        requires_password_change=profile.requires_password_change,
        effective_max_subscriptions=profile.effective_max_subscriptions,
        active_subscriptions_count=profile.active_subscriptions_count,
        is_partner=profile.is_partner,
        is_partner_active=profile.is_partner_active,
        has_web_account=profile.has_web_account,
        needs_web_credentials_bootstrap=profile.needs_web_credentials_bootstrap,
    )


def _build_plan_response(snapshot: PlanCatalogItemSnapshot) -> PlanResponse:
    return PlanResponse(
        id=snapshot.id,
        name=snapshot.name,
        description=snapshot.description,
        tag=snapshot.tag,
        type=snapshot.type,
        availability=snapshot.availability,
        traffic_limit=snapshot.traffic_limit,
        device_limit=snapshot.device_limit,
        order_index=snapshot.order_index,
        is_active=snapshot.is_active,
        allowed_user_ids=snapshot.allowed_user_ids,
        internal_squads=snapshot.internal_squads,
        external_squad=snapshot.external_squad,
        durations=[
            PlanDurationResponse(
                id=duration.id,
                plan_id=duration.plan_id,
                days=duration.days,
                prices=[
                    PlanPriceResponse(
                        id=price.id,
                        duration_id=price.duration_id,
                        gateway_type=price.gateway_type,
                        price=price.price,
                        original_price=price.original_price,
                        currency=price.currency,
                        discount_percent=price.discount_percent,
                        discount_source=price.discount_source,
                        discount=price.discount,
                        supported_payment_assets=price.supported_payment_assets,
                    )
                    for price in duration.prices
                ],
            )
            for duration in snapshot.durations
        ],
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def build_subscription_response(
    subscription: SubscriptionDto,
    fallback_user_telegram_id: int | None = None,
    action_policy: SubscriptionActionPolicy | None = None,
) -> SubscriptionResponse:
    """Serialize subscription DTO to API response."""
    user_telegram_id = subscription.user_telegram_id or fallback_user_telegram_id or 0

    return SubscriptionResponse(
        id=subscription.id or 0,
        user_remna_id=subscription.user_remna_id,
        user_telegram_id=user_telegram_id,
        status=subscription.status.value
        if hasattr(subscription.status, "value")
        else str(subscription.status),
        is_trial=subscription.is_trial,
        traffic_limit=subscription.traffic_limit,
        traffic_used=subscription.traffic_used,
        device_limit=subscription.device_limit,
        devices_count=subscription.devices_count,
        internal_squads=[str(squad) for squad in subscription.internal_squads],
        external_squad=str(subscription.external_squad) if subscription.external_squad else None,
        expire_at=subscription.expire_at.isoformat(),
        url=subscription.url or "",
        device_type=(
            subscription.device_type.value
            if subscription.device_type and hasattr(subscription.device_type, "value")
            else subscription.device_type
        ),
        can_renew=action_policy.can_renew if action_policy else False,
        can_upgrade=action_policy.can_upgrade if action_policy else False,
        can_multi_renew=action_policy.can_multi_renew if action_policy else False,
        renew_mode=action_policy.renew_mode.value
        if action_policy and action_policy.renew_mode
        else None,
        plan=subscription.plan.model_dump(mode="json") if subscription.plan else {},
        created_at=subscription.created_at.isoformat() if subscription.created_at else "",
        updated_at=subscription.updated_at.isoformat() if subscription.updated_at else "",
    )


def _build_subscription_purchase_options_response(
    result: SubscriptionPurchaseOptionsResult,
) -> SubscriptionPurchaseOptionsResponse:
    return SubscriptionPurchaseOptionsResponse(
        purchase_type=result.purchase_type.value,
        subscription_id=result.subscription_id,
        source_plan_missing=result.source_plan_missing,
        selection_locked=result.selection_locked,
        renew_mode=result.renew_mode.value if result.renew_mode else None,
        warning_code=result.warning_code,
        warning_message=result.warning_message,
        plans=[_build_plan_response(plan) for plan in result.plans],
    )


def _build_transaction_history_response(
    snapshot: TransactionHistoryPageSnapshot,
) -> TransactionHistoryResponse:
    return TransactionHistoryResponse(
        transactions=[
            TransactionHistoryItemResponse(
                payment_id=item.payment_id,
                user_telegram_id=item.user_telegram_id,
                status=item.status,
                purchase_type=item.purchase_type,
                channel=item.channel,
                gateway_type=item.gateway_type,
                pricing=TransactionPricingResponse(
                    original_amount=item.pricing.original_amount,
                    discount_percent=item.pricing.discount_percent,
                    final_amount=item.pricing.final_amount,
                ),
                currency=item.currency,
                payment_asset=item.payment_asset,
                plan=item.plan,
                renew_subscription_id=item.renew_subscription_id,
                renew_subscription_ids=item.renew_subscription_ids,
                device_types=item.device_types,
                is_test=item.is_test,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in snapshot.transactions
        ],
        total=snapshot.total,
        page=snapshot.page,
        limit=snapshot.limit,
    )


def _build_user_notification_list_response(
    snapshot: UserNotificationPageSnapshot,
) -> UserNotificationListResponse:
    return UserNotificationListResponse(
        notifications=[
            UserNotificationItemResponse(
                id=item.id,
                type=item.type,
                title=item.title,
                message=item.message,
                is_read=item.is_read,
                read_at=item.read_at,
                created_at=item.created_at,
            )
            for item in snapshot.notifications
        ],
        total=snapshot.total,
        page=snapshot.page,
        limit=snapshot.limit,
        unread=snapshot.unread,
    )


def _build_promocode_activation_history_response(
    snapshot: PromocodeActivationHistoryPageSnapshot,
) -> PromocodeActivationHistoryResponse:
    return PromocodeActivationHistoryResponse(
        activations=[
            PromocodeActivationHistoryItem(
                id=item.id,
                code=item.code,
                reward=PromocodeActivationHistoryReward(
                    type=item.reward.type,
                    value=item.reward.value,
                ),
                target_subscription_id=item.target_subscription_id,
                activated_at=item.activated_at,
            )
            for item in snapshot.activations
        ],
        total=snapshot.total,
        page=snapshot.page,
        limit=snapshot.limit,
    )


def _raise_subscription_portal_http_error(
    exception: SubscriptionPortalNotFoundError
    | SubscriptionPortalAccessDeniedError
    | SubscriptionPortalBadRequestError
    | SubscriptionPortalStateError,
) -> NoReturn:
    if isinstance(exception, SubscriptionPortalNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exception.message,
        ) from exception
    if isinstance(exception, SubscriptionPortalAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exception.message,
        ) from exception
    if isinstance(exception, SubscriptionPortalBadRequestError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exception),
    ) from exception


def _build_purchase_response(result: SubscriptionPurchaseResult) -> PurchaseResponse:
    return PurchaseResponse(
        transaction_id=result.transaction_id,
        payment_url=result.payment_url,
        url=result.url,
        status=result.status,
        message=result.message,
    )


def _build_purchase_quote_response(
    result: SubscriptionPurchaseQuoteResult,
) -> PurchaseQuoteResponse:
    return PurchaseQuoteResponse(
        price=result.price,
        original_price=result.original_price,
        currency=result.currency,
        settlement_price=result.settlement_price,
        settlement_original_price=result.settlement_original_price,
        settlement_currency=result.settlement_currency,
        discount_percent=result.discount_percent,
        discount_source=result.discount_source,
        payment_asset=result.payment_asset,
        quote_source=result.quote_source,
        quote_expires_at=result.quote_expires_at,
        quote_provider_count=result.quote_provider_count,
    )


def _raise_subscription_purchase_http_error(
    exception: SubscriptionPurchaseError,
) -> NoReturn:
    raise HTTPException(
        status_code=exception.status_code,
        detail=exception.detail,
    ) from exception


def _raise_purchase_access_http_error(exception: PurchaseAccessError) -> NoReturn:
    raise HTTPException(
        status_code=exception.status_code,
        detail=exception.detail,
    ) from exception


def _build_trial_eligibility_response(
    snapshot: TrialEligibilitySnapshot,
) -> TrialEligibilityResponse:
    return TrialEligibilityResponse(
        eligible=snapshot.eligible,
        reason_code=snapshot.reason_code,
        reason_message=snapshot.reason_message,
        requires_telegram_link=snapshot.requires_telegram_link,
        trial_plan_id=snapshot.trial_plan_id,
    )


def _raise_subscription_device_http_error(exception: SubscriptionDeviceError) -> NoReturn:
    if isinstance(exception, SubscriptionDeviceAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exception),
        ) from exception
    if isinstance(exception, SubscriptionDeviceNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception
    if isinstance(exception, SubscriptionDeviceLimitReachedError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exception),
        ) from exception
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exception),
    ) from exception


def _build_device_list_response(result: SubscriptionDeviceListResult) -> DeviceListResponse:
    return DeviceListResponse(
        devices=[
            DeviceResponse(
                hwid=device.hwid,
                device_type=device.device_type,
                first_connected=device.first_connected,
                last_connected=device.last_connected,
                country=device.country,
                ip=device.ip,
            )
            for device in result.devices
        ],
        subscription_id=result.subscription_id,
        device_limit=result.device_limit,
        devices_count=result.devices_count,
    )


def _build_generated_device_response(
    result: GeneratedSubscriptionDeviceLink,
) -> GenerateDeviceResponse:
    return GenerateDeviceResponse(
        hwid=result.hwid,
        connection_url=result.connection_url,
        device_type=result.device_type,
    )


def _build_promocode_activation_response(
    snapshot: PromocodeActivationSnapshot,
) -> PromocodeActivateResponse:
    return PromocodeActivateResponse(
        message=snapshot.message,
        reward=PromocodeReward(type=snapshot.reward.type, value=snapshot.reward.value)
        if snapshot.reward
        else None,
        next_step=snapshot.next_step,
        available_subscriptions=snapshot.available_subscriptions,
    )
