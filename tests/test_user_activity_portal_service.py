from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import (
    CryptoAsset,
    Currency,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PromocodeRewardType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
    UserNotificationType,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanDurationDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    PromocodeActivationBaseDto,
    TransactionDto,
    UserDto,
    UserNotificationEventDto,
)
from src.services.user_activity_portal import UserActivityPortalService


def _build_user(*, telegram_id: int = 1001) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        referral_code=f"ref{telegram_id}",
        name=f"User {telegram_id}",
    )


def _build_plan_snapshot(plan_id: int = 77) -> PlanSnapshotDto:
    plan = PlanDto(
        id=plan_id,
        name=f"Plan {plan_id}",
        type=PlanType.UNLIMITED,
        availability=PlanAvailability.ALL,
        is_active=True,
        traffic_limit=-1,
        device_limit=3,
        subscription_count=1,
        durations=[PlanDurationDto(days=30, prices=[])],
        internal_squads=[],
    )
    return PlanSnapshotDto.from_plan(plan, 30)


def _build_service(
) -> tuple[
    UserActivityPortalService,
    SimpleNamespace,
    SimpleNamespace,
    SimpleNamespace,
]:
    transaction_service = SimpleNamespace(
        get_by_user_paginated=AsyncMock(return_value=[]),
        count_by_user=AsyncMock(return_value=0),
    )
    user_notification_event_service = SimpleNamespace(
        list_by_user=AsyncMock(return_value=([], 0, 0)),
        count_unread=AsyncMock(return_value=0),
        mark_read=AsyncMock(return_value=False),
        mark_all_read=AsyncMock(return_value=0),
    )
    promocode_service = SimpleNamespace(
        get_user_activation_history=AsyncMock(return_value=([], 0)),
    )
    service = UserActivityPortalService(
        transaction_service=transaction_service,
        user_notification_event_service=user_notification_event_service,
        promocode_service=promocode_service,
    )
    return service, transaction_service, user_notification_event_service, promocode_service


def test_list_transactions_builds_serialized_page() -> None:
    service, transaction_service, _, _ = _build_service()
    transaction_service.get_by_user_paginated.return_value = [
        TransactionDto(
            payment_id=uuid4(),
            status=TransactionStatus.COMPLETED,
            purchase_type=PurchaseType.NEW,
            channel=PurchaseChannel.WEB,
            gateway_type=PaymentGatewayType.CRYPTOPAY,
            pricing=PriceDetailsDto(
                original_amount=Decimal("499"),
                discount_percent=10,
                final_amount=Decimal("449.10"),
            ),
            currency=Currency.USD,
            payment_asset=CryptoAsset.USDT,
            plan=_build_plan_snapshot(),
            renew_subscription_id=5,
            renew_subscription_ids=[5, 6],
            created_at=datetime_now(),
            updated_at=datetime_now(),
            is_test=False,
        )
    ]
    transaction_service.count_by_user.return_value = 3

    snapshot = asyncio.run(
        service.list_transactions(
            current_user=_build_user(),
            page=2,
            limit=1,
        )
    )

    assert snapshot.total == 3
    assert snapshot.page == 2
    assert snapshot.transactions[0].user_telegram_id == 1001
    assert snapshot.transactions[0].pricing.final_amount == 449.10
    assert snapshot.transactions[0].payment_asset == "USDT"
    assert snapshot.transactions[0].plan["id"] == 77
    assert transaction_service.get_by_user_paginated.await_args.kwargs["offset"] == 1


def test_list_notifications_builds_titles_and_counts() -> None:
    service, _, user_notification_event_service, _ = _build_service()
    user_notification_event_service.list_by_user.return_value = (
        [
            UserNotificationEventDto(
                id=10,
                user_telegram_id=1001,
                ntf_type=UserNotificationType.EXPIRED_1_DAY_AGO,
                i18n_key="expired",
                rendered_text="Subscription expired",
                is_read=False,
                created_at=datetime_now(),
                read_at=datetime_now() + timedelta(minutes=1),
            )
        ],
        5,
        2,
    )

    snapshot = asyncio.run(
        service.list_notifications(
            current_user=_build_user(),
            page=1,
            limit=20,
        )
    )

    assert snapshot.total == 5
    assert snapshot.unread == 2
    assert snapshot.notifications[0].type == UserNotificationType.EXPIRED_1_DAY_AGO.value
    assert snapshot.notifications[0].title == "Expired 1 Day Ago"


def test_get_notifications_unread_count_delegates_to_service() -> None:
    service, _, user_notification_event_service, _ = _build_service()
    user_notification_event_service.count_unread.return_value = 7

    unread = asyncio.run(service.get_notifications_unread_count(current_user=_build_user()))

    assert unread == 7


def test_mark_notification_methods_return_updated_counts() -> None:
    service, _, user_notification_event_service, _ = _build_service()
    user_notification_event_service.mark_read.return_value = True
    user_notification_event_service.mark_all_read.return_value = 4

    updated_one = asyncio.run(
        service.mark_notification_read(
            current_user=_build_user(),
            notification_id=123,
        )
    )
    updated_all = asyncio.run(service.mark_all_notifications_read(current_user=_build_user()))

    assert updated_one == 1
    assert updated_all == 4
    assert user_notification_event_service.mark_read.await_args.kwargs["read_source"] == "WEB"
    assert user_notification_event_service.mark_all_read.await_args.kwargs["read_source"] == "WEB"


def test_list_promocode_activations_builds_serialized_page() -> None:
    service, _, _, promocode_service = _build_service()
    promocode_service.get_user_activation_history.return_value = (
        [
            PromocodeActivationBaseDto(
                id=9,
                promocode_id=5,
                user_telegram_id=1001,
                promocode_code="WELCOME",
                reward_type=PromocodeRewardType.DURATION,
                reward_value=30,
                target_subscription_id=44,
                activated_at=datetime_now(),
            )
        ],
        1,
    )

    snapshot = asyncio.run(
        service.list_promocode_activations(
            current_user=_build_user(),
            page=1,
            limit=20,
        )
    )

    assert snapshot.total == 1
    assert snapshot.activations[0].code == "WELCOME"
    assert snapshot.activations[0].reward.type == PromocodeRewardType.DURATION.value
    assert snapshot.activations[0].target_subscription_id == 44
