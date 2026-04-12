from __future__ import annotations

from dataclasses import dataclass

from src.core.enums import (
    CryptoAsset,
    DeviceType,
    PaymentSource,
    PurchaseChannel,
    PurchaseType,
    SubscriptionRenewMode,
)
from src.infrastructure.database.models.dto import (
    PlanDto,
    SubscriptionDto,
    TransactionRenewItemDto,
)

PurchaseErrorDetail = str | dict[str, str]
ARCHIVED_PLAN_NOT_PURCHASABLE_CODE = "ARCHIVED_PLAN_NOT_PURCHASABLE"
ARCHIVED_PLAN_NOT_PURCHASABLE_MESSAGE = "Archived plans cannot be purchased as a new subscription"
TRIAL_UPGRADE_REQUIRED_CODE = "TRIAL_UPGRADE_REQUIRED"
TRIAL_UPGRADE_REQUIRED_MESSAGE = "An existing trial subscription can only be continued via upgrade"
TRIAL_UPGRADE_SELECTION_REQUIRED_CODE = "TRIAL_UPGRADE_SELECTION_REQUIRED"
TRIAL_UPGRADE_SELECTION_REQUIRED_MESSAGE = (
    "Multiple active trial subscriptions found. "
    "Open subscriptions and upgrade the required one explicitly."
)
TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_CODE = "TRIAL_UPGRADE_QUANTITY_UNSUPPORTED"
TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_MESSAGE = (
    "A trial subscription can only be converted to a paid plan one at a time."
)


class SubscriptionPurchaseError(Exception):
    def __init__(self, *, status_code: int, detail: PurchaseErrorDetail) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseRequest:
    purchase_type: PurchaseType = PurchaseType.NEW
    payment_source: PaymentSource = PaymentSource.EXTERNAL
    channel: PurchaseChannel = PurchaseChannel.WEB
    plan_id: int | None = None
    duration_days: int | None = None
    device_type: DeviceType | None = None
    gateway_type: str | None = None
    renew_subscription_id: int | None = None
    renew_subscription_ids: tuple[int, ...] | None = None
    device_types: tuple[DeviceType, ...] | None = None
    quantity: int = 1
    promocode: str | None = None
    payment_asset: CryptoAsset | None = None
    success_redirect_url: str | None = None
    fail_redirect_url: str | None = None


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseResult:
    transaction_id: str
    payment_url: str | None
    url: str | None
    status: str
    message: str
    renew_items: tuple[TransactionRenewItemDto, ...] = ()


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseQuoteResult:
    price: float
    original_price: float
    currency: str
    settlement_price: float
    settlement_original_price: float
    settlement_currency: str
    discount_percent: int
    discount_source: str
    payment_asset: str | None
    quote_source: str
    quote_expires_at: str
    quote_provider_count: int
    renew_items: tuple[TransactionRenewItemDto, ...] = ()


@dataclass(slots=True, frozen=True)
class ResolvedRenewItemContext:
    subscription_id: int
    source_subscription: SubscriptionDto
    renew_mode: SubscriptionRenewMode
    target_plan: PlanDto


@dataclass(slots=True, frozen=True)
class ValidatedPurchaseContext:
    plan: PlanDto
    source_subscription: SubscriptionDto | None = None
    renew_items: tuple[ResolvedRenewItemContext, ...] = ()
