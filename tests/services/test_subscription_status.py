from __future__ import annotations

from types import SimpleNamespace

from src.infrastructure.database.models.dto import SubscriptionDto
from src.services.subscription_status import (
    is_deleted_subscription,
    is_deleted_subscription_status,
)


def test_is_deleted_subscription_status_accepts_plain_string_and_enum_like_value() -> None:
    assert is_deleted_subscription_status("DELETED") is True
    assert is_deleted_subscription_status("ACTIVE") is False
    assert is_deleted_subscription_status(SimpleNamespace(value="DELETED")) is True
    assert is_deleted_subscription_status(SimpleNamespace(value="ACTIVE")) is False


def test_is_deleted_subscription_reads_status_from_subscription_object() -> None:
    deleted_subscription = SubscriptionDto.model_construct(status="DELETED")
    active_subscription = SubscriptionDto.model_construct(status="ACTIVE")

    assert is_deleted_subscription(deleted_subscription) is True
    assert is_deleted_subscription(active_subscription) is False
