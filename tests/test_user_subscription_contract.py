from __future__ import annotations

from src.api.contracts.user_subscription import (
    PurchaseRequest,
    SubscriptionAssignmentRequest,
    build_subscription_assignment_update,
    build_subscription_purchase_request,
)
from src.core.enums import DeviceType, PaymentSource, PurchaseChannel, PurchaseType


def test_assignment_update_marks_provided_fields() -> None:
    update = build_subscription_assignment_update(
        SubscriptionAssignmentRequest(device_type=DeviceType.WINDOWS)
    )

    assert update.plan_id is None
    assert update.plan_id_provided is False
    assert update.device_type == DeviceType.WINDOWS
    assert update.device_type_provided is True


def test_assignment_update_preserves_explicit_null_plan() -> None:
    update = build_subscription_assignment_update(SubscriptionAssignmentRequest(plan_id=None))

    assert update.plan_id is None
    assert update.plan_id_provided is True
    assert update.device_type is None
    assert update.device_type_provided is False


def test_purchase_request_mapper_normalizes_list_fields_to_tuples() -> None:
    request = build_subscription_purchase_request(
        PurchaseRequest(
            purchase_type=PurchaseType.RENEW,
            payment_source=PaymentSource.PARTNER_BALANCE,
            channel=PurchaseChannel.TELEGRAM,
            renew_subscription_ids=[10, 11],
            device_types=[DeviceType.WINDOWS, DeviceType.IPHONE],
            quantity=2,
            promocode="PROMO10",
            success_redirect_url="https://example.test/success",
            fail_redirect_url="https://example.test/fail",
        )
    )

    assert request.purchase_type == PurchaseType.RENEW
    assert request.payment_source == PaymentSource.PARTNER_BALANCE
    assert request.channel == PurchaseChannel.TELEGRAM
    assert request.renew_subscription_ids == (10, 11)
    assert request.device_types == (DeviceType.WINDOWS, DeviceType.IPHONE)
    assert request.quantity == 2
    assert request.promocode == "PROMO10"
    assert request.success_redirect_url == "https://example.test/success"
    assert request.fail_redirect_url == "https://example.test/fail"


def test_purchase_request_mapper_keeps_optional_sequences_none() -> None:
    request = build_subscription_purchase_request(PurchaseRequest())

    assert request.renew_subscription_ids is None
    assert request.device_types is None
