from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import HTTPException

from src.api.presenters.user_account import (
    _build_device_list_response,
    _build_generated_device_response,
    _build_plan_response,
    _build_promocode_activation_history_response,
    _build_promocode_activation_response,
    _build_transaction_history_response,
    _build_user_notification_list_response,
    _build_user_profile_response,
    _raise_purchase_access_http_error,
    _raise_subscription_device_http_error,
    build_subscription_response,
)
from src.core.enums import Currency, DeviceType, SubscriptionStatus
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto
from src.services.plan_catalog import (
    PlanCatalogDurationSnapshot,
    PlanCatalogItemSnapshot,
    PlanCatalogPriceSnapshot,
)
from src.services.promocode_portal import PromocodeActivationSnapshot, PromocodeRewardSnapshot
from src.services.purchase_access import PurchaseAccessError
from src.services.subscription_device import (
    GeneratedSubscriptionDeviceLink,
    SubscriptionDeviceAccessDeniedError,
    SubscriptionDeviceItem,
    SubscriptionDeviceListResult,
)
from src.services.user_activity_portal import (
    PromocodeActivationHistoryItemSnapshot,
    PromocodeActivationHistoryPageSnapshot,
    PromocodeActivationRewardSnapshot,
    TransactionHistoryItemSnapshot,
    TransactionHistoryPageSnapshot,
    TransactionPricingSnapshot,
    UserNotificationItemSnapshot,
    UserNotificationPageSnapshot,
)
from src.services.user_profile import UserProfileSnapshot


def test_build_user_profile_response_maps_snapshot_fields() -> None:
    response = _build_user_profile_response(
        UserProfileSnapshot(
            telegram_id=1001,
            username="tester",
            name="Tester",
            safe_name="Tester",
            role="USER",
            points=150,
            language="ru",
            default_currency=Currency.RUB.value,
            personal_discount=5,
            purchase_discount=10,
            is_blocked=False,
            is_bot_blocked=False,
            created_at="2026-03-01T10:00:00+00:00",
            updated_at="2026-03-02T10:00:00+00:00",
            email="user@example.com",
            email_verified=True,
            telegram_linked=True,
            linked_telegram_id=2002,
            show_link_prompt=False,
            requires_password_change=False,
            effective_max_subscriptions=3,
            active_subscriptions_count=2,
            is_partner=True,
            is_partner_active=True,
            partner_balance_currency_override=Currency.USDT.value,
            effective_partner_balance_currency=Currency.USDT.value,
            has_web_account=True,
            needs_web_credentials_bootstrap=True,
        )
    )

    assert response.telegram_id == 1001
    assert response.email_verified is True
    assert response.effective_max_subscriptions == 3
    assert response.is_partner_active is True
    assert response.default_currency == Currency.RUB.value
    assert response.partner_balance_currency_override == Currency.USDT.value
    assert response.effective_partner_balance_currency == Currency.USDT.value
    assert response.needs_web_credentials_bootstrap is True


def test_build_plan_response_maps_nested_duration_prices() -> None:
    response = _build_plan_response(
        PlanCatalogItemSnapshot(
            id=7,
            name="Premium",
            description="Full access",
            tag="TOP",
            type="MONTHLY",
            availability="PUBLIC",
            traffic_limit=1024,
            device_limit=5,
            order_index=1,
            is_active=True,
            allowed_user_ids=[],
            internal_squads=["alpha"],
            external_squad="public",
            durations=[
                PlanCatalogDurationSnapshot(
                    id=11,
                    plan_id=7,
                    days=30,
                    prices=[
                        PlanCatalogPriceSnapshot(
                            id=22,
                            duration_id=11,
                            gateway_type="CARD",
                            price=499.0,
                            original_price=599.0,
                            currency="RUB",
                            discount_percent=15,
                            discount_source="PERSONAL",
                            discount=15,
                            supported_payment_assets=["USDT", "BTC"],
                        )
                    ],
                )
            ],
            created_at="2026-03-01T00:00:00+00:00",
            updated_at="2026-03-02T00:00:00+00:00",
        )
    )

    assert response.id == 7
    assert response.durations[0].days == 30
    assert response.durations[0].prices[0].gateway_type == "CARD"
    assert response.durations[0].prices[0].discount == 15
    assert response.durations[0].prices[0].original_price == 599.0
    assert response.durations[0].prices[0].discount_source == "PERSONAL"
    assert response.durations[0].prices[0].supported_payment_assets == ["USDT", "BTC"]


def test_build_subscription_and_transaction_responses_map_nested_fields() -> None:
    subscription_response = build_subscription_response(
        SubscriptionDto(
            id=77,
            user_remna_id=UUID("00000000-0000-0000-0000-000000000123"),
            user_telegram_id=0,
            status=SubscriptionStatus.ACTIVE,
            is_trial=False,
            traffic_limit=1024,
            traffic_used=128,
            device_limit=3,
            devices_count=2,
            internal_squads=[UUID("00000000-0000-0000-0000-000000000124")],
            external_squad=UUID("00000000-0000-0000-0000-000000000125"),
            expire_at=datetime(2026, 4, 1, tzinfo=UTC),
            url="https://example.test/subscription",
            device_type=DeviceType.IPHONE,
            plan=PlanSnapshotDto.test(),
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            updated_at=datetime(2026, 3, 2, tzinfo=UTC),
        ),
        fallback_user_telegram_id=1001,
    )
    transaction_response = _build_transaction_history_response(
        TransactionHistoryPageSnapshot(
            transactions=[
                TransactionHistoryItemSnapshot(
                    payment_id="pay_1",
                    user_telegram_id=1001,
                    status="PAID",
                    purchase_type="NEW",
                    channel="WEB",
                    gateway_type="CARD",
                    pricing=TransactionPricingSnapshot(
                        original_amount=499.0,
                        discount_percent=10,
                        final_amount=449.1,
                    ),
                    currency="RUB",
                    payment_asset="USDT",
                    plan={"id": 7},
                    renew_subscription_id=None,
                    renew_subscription_ids=None,
                    device_types=["IOS"],
                    is_test=False,
                    created_at="2026-03-01T10:00:00+00:00",
                    updated_at="2026-03-01T10:05:00+00:00",
                )
            ],
            total=1,
            page=1,
            limit=20,
        )
    )

    assert subscription_response.user_telegram_id == 1001
    assert subscription_response.device_type == "IPHONE"
    assert transaction_response.transactions[0].pricing.final_amount == 449.1
    assert transaction_response.transactions[0].payment_asset == "USDT"
    assert transaction_response.transactions[0].device_types == ["IOS"]


def test_build_notification_and_promocode_history_responses() -> None:
    notification_response = _build_user_notification_list_response(
        UserNotificationPageSnapshot(
            notifications=[
                UserNotificationItemSnapshot(
                    id=1,
                    type="INFO",
                    title="Hello",
                    message="World",
                    is_read=False,
                    read_at=None,
                    created_at="2026-03-01T10:00:00+00:00",
                )
            ],
            total=1,
            page=1,
            limit=20,
            unread=1,
        )
    )
    history_response = _build_promocode_activation_history_response(
        PromocodeActivationHistoryPageSnapshot(
            activations=[
                PromocodeActivationHistoryItemSnapshot(
                    id=5,
                    code="WELCOME",
                    reward=PromocodeActivationRewardSnapshot(type="DAYS", value=30),
                    target_subscription_id=77,
                    activated_at="2026-03-03T12:00:00+00:00",
                )
            ],
            total=1,
            page=1,
            limit=20,
        )
    )

    assert notification_response.unread == 1
    assert notification_response.notifications[0].title == "Hello"
    assert history_response.activations[0].reward.value == 30
    assert history_response.activations[0].target_subscription_id == 77


def test_build_device_and_promocode_activation_responses() -> None:
    device_response = _build_device_list_response(
        SubscriptionDeviceListResult(
            devices=[
                SubscriptionDeviceItem(
                    hwid="HWID-1",
                    device_type="WINDOWS",
                    first_connected="2026-03-01T10:00:00+00:00",
                    last_connected="2026-03-02T10:00:00+00:00",
                    country="RU",
                    ip="127.0.0.1",
                )
            ],
            subscription_id=77,
            device_limit=3,
            devices_count=1,
        )
    )
    generated_response = _build_generated_device_response(
        GeneratedSubscriptionDeviceLink(
            hwid="HWID-NEW",
            connection_url="vless://example",
            device_type="IOS",
        )
    )
    promocode_response = _build_promocode_activation_response(
        PromocodeActivationSnapshot(
            message="Activated",
            reward=PromocodeRewardSnapshot(type="DAYS", value=14),
            next_step=None,
            available_subscriptions=[77],
        )
    )

    assert device_response.devices[0].country == "RU"
    assert generated_response.connection_url == "vless://example"
    assert promocode_response.reward is not None
    assert promocode_response.reward.value == 14


def test_http_error_adapters_preserve_status_codes() -> None:
    with pytest.raises(HTTPException) as purchase_exc:
        _raise_purchase_access_http_error(
            PurchaseAccessError(status_code=403, detail="Purchases disabled")
        )
    with pytest.raises(HTTPException) as device_exc:
        _raise_subscription_device_http_error(SubscriptionDeviceAccessDeniedError("Forbidden"))

    assert purchase_exc.value.status_code == 403
    assert purchase_exc.value.detail == "Purchases disabled"
    assert device_exc.value.status_code == 403
    assert device_exc.value.detail == "Forbidden"
