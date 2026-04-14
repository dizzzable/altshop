from __future__ import annotations

from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto import SubscriptionDto


def is_deleted_subscription_status(status: object) -> bool:
    if hasattr(status, "value"):
        return str(getattr(status, "value")) == SubscriptionStatus.DELETED.value
    return str(status) == SubscriptionStatus.DELETED.value


def is_deleted_subscription(subscription: SubscriptionDto) -> bool:
    return is_deleted_subscription_status(subscription.status)
