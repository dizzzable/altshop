"""Request contracts and request mappers for user subscription endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.core.enums import CryptoAsset, DeviceType, PaymentSource, PurchaseChannel, PurchaseType
from src.services.subscription_portal import SubscriptionAssignmentUpdate
from src.services.subscription_purchase import SubscriptionPurchaseRequest


class SubscriptionAssignmentRequest(BaseModel):
    """Manual assignment update for subscription snapshot/device type."""

    plan_id: int | None = None
    device_type: DeviceType | None = None


def build_subscription_assignment_update(
    payload: SubscriptionAssignmentRequest,
) -> SubscriptionAssignmentUpdate:
    return SubscriptionAssignmentUpdate(
        plan_id=payload.plan_id,
        plan_id_provided="plan_id" in payload.model_fields_set,
        device_type=payload.device_type,
        device_type_provided="device_type" in payload.model_fields_set,
    )


class PurchaseRequest(BaseModel):
    """Purchase subscription request."""

    purchase_type: PurchaseType = Field(default=PurchaseType.NEW)
    payment_source: PaymentSource = Field(default=PaymentSource.EXTERNAL)
    channel: PurchaseChannel = Field(default=PurchaseChannel.WEB)
    plan_id: int | None = None
    duration_days: int | None = None
    device_type: DeviceType | None = None
    gateway_type: str | None = None
    renew_subscription_id: int | None = None
    renew_subscription_ids: list[int] | None = None
    device_types: list[DeviceType] | None = None
    quantity: int = Field(default=1, ge=1)
    promocode: str | None = None
    payment_asset: CryptoAsset | None = None
    success_redirect_url: str | None = None
    fail_redirect_url: str | None = None


class PurchaseQuoteRequest(PurchaseRequest):
    """Final purchase quote request."""


def build_subscription_purchase_request(
    request: PurchaseRequest,
) -> SubscriptionPurchaseRequest:
    return SubscriptionPurchaseRequest(
        purchase_type=request.purchase_type,
        payment_source=request.payment_source,
        channel=request.channel,
        plan_id=request.plan_id,
        duration_days=request.duration_days,
        device_type=request.device_type,
        gateway_type=request.gateway_type,
        renew_subscription_id=request.renew_subscription_id,
        renew_subscription_ids=tuple(request.renew_subscription_ids or [])
        if request.renew_subscription_ids
        else None,
        device_types=tuple(request.device_types or []) if request.device_types else None,
        quantity=request.quantity,
        promocode=request.promocode,
        payment_asset=request.payment_asset,
        success_redirect_url=request.success_redirect_url,
        fail_redirect_url=request.fail_redirect_url,
    )


class TrialRequest(BaseModel):
    """Trial subscription request."""

    plan_id: int | None = None


class GenerateDeviceRequest(BaseModel):
    """Generate device link request."""

    subscription_id: int
    device_type: DeviceType | None = None


class PromocodeActivateRequest(BaseModel):
    """Activate promocode request."""

    code: str = Field(..., description="Promocode")
    subscription_id: int | None = Field(None, description="Subscription ID for applying days")
    create_new: bool = Field(False, description="Create new subscription if promocode allows")


__all__ = [
    "GenerateDeviceRequest",
    "PurchaseQuoteRequest",
    "PromocodeActivateRequest",
    "PurchaseRequest",
    "SubscriptionAssignmentRequest",
    "TrialRequest",
    "build_subscription_assignment_update",
    "build_subscription_purchase_request",
]
