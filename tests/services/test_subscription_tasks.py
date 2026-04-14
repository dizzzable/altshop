from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import (
    Currency,
    Locale,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    SubscriptionDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.transaction import PriceDetailsDto
from src.infrastructure.taskiq.tasks import subscriptions_purchase as subscriptions_purchase_tasks
from src.infrastructure.taskiq.tasks.subscriptions import (
    cleanup_expired_subscriptions_task,
    delete_current_subscription_task,
    purchase_subscription_task,
    update_status_current_subscription_task,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def unwrap_task(function):
    while hasattr(function, "__dishka_orig_func__"):
        function = function.__dishka_orig_func__
    while hasattr(function, "__wrapped__"):
        function = function.__wrapped__
    return function


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=f"User {telegram_id}",
        language=Locale.EN,
    )


def build_plan_snapshot(*, plan_id: int = 10, duration: int = 30) -> PlanSnapshotDto:
    snapshot = PlanSnapshotDto.test()
    snapshot.id = plan_id
    snapshot.name = f"Plan {plan_id}"
    snapshot.duration = duration
    return snapshot


def build_subscription(
    *,
    subscription_id: int,
    user: UserDto,
    plan: PlanSnapshotDto,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user.telegram_id,
        status=status,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=plan.internal_squads,
        external_squad=plan.external_squad,
        expire_at=datetime_now() + timedelta(days=plan.duration),
        url=f"https://example.test/subscriptions/{subscription_id}",
        plan=plan.model_copy(deep=True),
    )


def build_transaction(
    *,
    user: UserDto,
    plan: PlanSnapshotDto,
    purchase_type: PurchaseType,
) -> TransactionDto:
    return TransactionDto(
        id=501,
        payment_id=uuid4(),
        status=TransactionStatus.PENDING,
        purchase_type=purchase_type,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(
            original_amount=Decimal("199"),
            final_amount=Decimal("199"),
        ),
        currency=Currency.RUB,
        plan=plan,
        user=user,
    )


def test_purchase_subscription_task_uses_current_subscription_fallback_for_renew(
    monkeypatch,
) -> None:
    user = build_user(telegram_id=701)
    plan = build_plan_snapshot(plan_id=41)
    transaction = build_transaction(user=user, plan=plan, purchase_type=PurchaseType.RENEW)
    current_subscription = build_subscription(subscription_id=11, user=user, plan=plan)
    updated_expire_at = datetime_now() + timedelta(days=60)

    redirect_to_success = AsyncMock()
    monkeypatch.setattr(
        subscriptions_purchase_tasks.redirect_to_successed_payment_task,
        "kiq",
        redirect_to_success,
    )

    remnawave_service = SimpleNamespace(
        updated_user=AsyncMock(
            return_value=SimpleNamespace(
                expire_at=updated_expire_at,
                status=SubscriptionStatus.ACTIVE,
            )
        )
    )
    subscription_service = SimpleNamespace(
        get_current=AsyncMock(return_value=current_subscription),
        get_all_by_user=AsyncMock(return_value=[current_subscription]),
        update=AsyncMock(),
    )
    settings_service = SimpleNamespace(get_max_subscriptions_for_user=AsyncMock(return_value=5))

    run_async(
        unwrap_task(purchase_subscription_task)(
            transaction=transaction,
            subscription=None,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            settings_service=settings_service,
            transaction_service=SimpleNamespace(update=AsyncMock()),
            plan_service=SimpleNamespace(),
        )
    )

    assert remnawave_service.updated_user.await_args.kwargs["subscription"] is current_subscription
    redirect_to_success.assert_awaited_once_with(user, PurchaseType.RENEW)


def test_purchase_subscription_task_marks_failed_and_redirects_when_upgrade_has_no_selection(
    monkeypatch,
) -> None:
    user = build_user(telegram_id=702)
    plan = build_plan_snapshot(plan_id=42)
    transaction = build_transaction(user=user, plan=plan, purchase_type=PurchaseType.UPGRADE)
    current_subscription = build_subscription(subscription_id=12, user=user, plan=plan)

    failed_redirect = AsyncMock()
    error_notification = AsyncMock()
    monkeypatch.setattr(
        subscriptions_purchase_tasks.redirect_to_failed_subscription_task,
        "kiq",
        failed_redirect,
    )
    monkeypatch.setattr(
        subscriptions_purchase_tasks.send_error_notification_task,
        "kiq",
        error_notification,
    )

    remnawave_service = SimpleNamespace(updated_user=AsyncMock())
    subscription_service = SimpleNamespace(
        get_current=AsyncMock(return_value=current_subscription),
        update=AsyncMock(),
    )
    transaction_service = SimpleNamespace(update=AsyncMock())

    run_async(
        unwrap_task(purchase_subscription_task)(
            transaction=transaction,
            subscription=None,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            settings_service=SimpleNamespace(get_max_subscriptions_for_user=AsyncMock(return_value=5)),
            transaction_service=transaction_service,
            plan_service=SimpleNamespace(),
        )
    )

    assert transaction.status == TransactionStatus.FAILED
    transaction_service.update.assert_awaited_once_with(transaction)
    remnawave_service.updated_user.assert_not_awaited()
    failed_redirect.assert_awaited_once_with(user)
    error_notification.assert_awaited_once()


def test_purchase_subscription_task_checks_guardrail_before_panel_writes_for_new_purchase(
    monkeypatch,
) -> None:
    user = build_user(telegram_id=703)
    plan = build_plan_snapshot(plan_id=43)
    transaction = build_transaction(user=user, plan=plan, purchase_type=PurchaseType.NEW)
    events: list[str] = []

    monkeypatch.setattr(
        subscriptions_purchase_tasks.redirect_to_successed_payment_task,
        "kiq",
        AsyncMock(),
    )

    async def max_subscriptions(_: UserDto) -> int:
        events.append("guard")
        return 5

    async def all_subscriptions(_: int) -> list[SubscriptionDto]:
        events.append("existing")
        return []

    async def create_user(_: UserDto, __: PlanSnapshotDto) -> SimpleNamespace:
        events.append("panel")
        return SimpleNamespace(
            uuid=uuid4(),
            status=SubscriptionStatus.ACTIVE,
            expire_at=datetime_now() + timedelta(days=plan.duration),
            subscription_url="https://example.test/panel",
        )

    remnawave_service = SimpleNamespace(
        create_user=AsyncMock(side_effect=create_user),
        get_subscription_url=AsyncMock(return_value="https://example.test/panel"),
    )
    subscription_service = SimpleNamespace(
        get_current=AsyncMock(return_value=None),
        get_all_by_user=AsyncMock(side_effect=all_subscriptions),
        create=AsyncMock(),
    )

    run_async(
        unwrap_task(purchase_subscription_task)(
            transaction=transaction,
            subscription=None,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            settings_service=SimpleNamespace(
                get_max_subscriptions_for_user=AsyncMock(side_effect=max_subscriptions)
            ),
            transaction_service=SimpleNamespace(update=AsyncMock()),
            plan_service=SimpleNamespace(),
        )
    )

    assert events == ["guard", "existing", "panel"]


def test_delete_current_subscription_task_resolves_matching_current_subscription_by_user_remna_id(
) -> None:
    user = build_user(telegram_id=704)
    plan = build_plan_snapshot(plan_id=44)
    current_subscription = build_subscription(subscription_id=13, user=user, plan=plan)
    next_subscription = build_subscription(subscription_id=14, user=user, plan=plan)

    user_service = SimpleNamespace(
        get=AsyncMock(return_value=user),
        set_current_subscription=AsyncMock(),
        delete_current_subscription=AsyncMock(),
    )
    subscription_service = SimpleNamespace(
        get_by_remna_id=AsyncMock(return_value=None),
        get_current=AsyncMock(side_effect=[current_subscription, current_subscription]),
        get_all_by_user=AsyncMock(return_value=[current_subscription, next_subscription]),
        update=AsyncMock(),
    )

    run_async(
        unwrap_task(delete_current_subscription_task)(
            user_telegram_id=user.telegram_id,
            user_service=user_service,
            subscription_service=subscription_service,
            user_remna_id=current_subscription.user_remna_id,
        )
    )

    assert current_subscription.status == SubscriptionStatus.DELETED
    subscription_service.update.assert_awaited_once_with(current_subscription)
    user_service.set_current_subscription.assert_awaited_once_with(
        user.telegram_id,
        next_subscription.id,
    )


def test_update_status_current_subscription_task_uses_matching_current_subscription_by_remna_id(
) -> None:
    user = build_user(telegram_id=705)
    plan = build_plan_snapshot(plan_id=45)
    current_subscription = build_subscription(subscription_id=15, user=user, plan=plan)

    subscription_service = SimpleNamespace(
        get_by_remna_id=AsyncMock(return_value=None),
        get_current=AsyncMock(return_value=current_subscription),
        update=AsyncMock(),
    )

    run_async(
        unwrap_task(update_status_current_subscription_task)(
            user_telegram_id=user.telegram_id,
            status=SubscriptionStatus.DISABLED,
            user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
            subscription_service=subscription_service,
            user_remna_id=current_subscription.user_remna_id,
        )
    )

    assert current_subscription.status == SubscriptionStatus.DISABLED
    subscription_service.update.assert_awaited_once_with(current_subscription)


def test_cleanup_expired_subscriptions_task_continues_after_panel_delete_failure() -> None:
    first = build_subscription(
        subscription_id=16,
        user=build_user(telegram_id=706),
        plan=build_plan_snapshot(plan_id=46),
    )
    second = build_subscription(
        subscription_id=17,
        user=build_user(telegram_id=707),
        plan=build_plan_snapshot(plan_id=47),
    )

    delete_user = AsyncMock(
        side_effect=[RuntimeError("boom"), SimpleNamespace(is_deleted=True)]
    )
    subscription_service = SimpleNamespace(
        get_expired_subscriptions_older_than=AsyncMock(return_value=[first, second]),
        delete_subscription=AsyncMock(),
    )
    remnawave = SimpleNamespace(users=SimpleNamespace(delete_user=delete_user))

    run_async(
        unwrap_task(cleanup_expired_subscriptions_task)(
            subscription_service=subscription_service,
            remnawave=remnawave,
        )
    )

    assert delete_user.await_count == 2
    subscription_service.delete_subscription.assert_awaited_once_with(second.id)
