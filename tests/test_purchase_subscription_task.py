from __future__ import annotations

import asyncio
import inspect
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.enums import (
    Currency,
    DeviceType,
    PaymentGatewayType,
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
from src.infrastructure.taskiq.tasks import subscriptions as subscriptions_tasks
from src.infrastructure.taskiq.tasks.subscriptions import purchase_subscription_task

PURCHASE_SUBSCRIPTION_TASK = getattr(
    inspect.unwrap(purchase_subscription_task),
    "__dishka_orig_func__",
    inspect.unwrap(purchase_subscription_task),
)


def _build_user() -> UserDto:
    return UserDto(
        telegram_id=1001,
        referral_code="ref1001",
        name="Task User",
    )


def _build_plan(*, subscription_count: int = 1, duration: int = 30) -> PlanSnapshotDto:
    return PlanSnapshotDto.test().model_copy(
        update={
            "duration": duration,
            "traffic_limit": 50,
            "device_limit": 3,
        }
    )


def _build_subscription(
    *,
    user_telegram_id: int,
    plan: PlanSnapshotDto,
    is_trial: bool = False,
) -> SubscriptionDto:
    return SubscriptionDto(
        id=501,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        status=SubscriptionStatus.ACTIVE,
        is_trial=is_trial,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url="https://sub.local/current",
        device_type=DeviceType.OTHER,
        plan=plan,
    )


def _build_transaction(
    *,
    user: UserDto,
    plan: PlanSnapshotDto,
    purchase_type: PurchaseType,
    device_types: list[DeviceType] | None = None,
) -> TransactionDto:
    return TransactionDto(
        payment_id=uuid4(),
        status=TransactionStatus.PENDING,
        purchase_type=purchase_type,
        gateway_type=PaymentGatewayType.YOOKASSA,
        pricing=PriceDetailsDto(
            original_amount=Decimal("100"),
            final_amount=Decimal("100"),
            discount_percent=0,
        ),
        currency=Currency.RUB,
        plan=plan,
        device_types=device_types,
        user=user,
    )


def _patch_task_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    success_task = SimpleNamespace(kiq=AsyncMock(return_value=None))
    fail_task = SimpleNamespace(kiq=AsyncMock(return_value=None))
    error_task = SimpleNamespace(kiq=AsyncMock(return_value=None))

    monkeypatch.setattr(subscriptions_tasks, "redirect_to_successed_payment_task", success_task)
    monkeypatch.setattr(subscriptions_tasks, "redirect_to_failed_subscription_task", fail_task)
    monkeypatch.setattr(subscriptions_tasks, "send_error_notification_task", error_task)

    return success_task, fail_task


def test_purchase_task_renew_uses_current_subscription_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    success_task, fail_task = _patch_task_notifications(monkeypatch)
    user = _build_user()
    plan = _build_plan(subscription_count=1, duration=30)
    transaction = _build_transaction(user=user, plan=plan, purchase_type=PurchaseType.RENEW)
    current_subscription = _build_subscription(user_telegram_id=user.telegram_id, plan=plan)

    remnawave_service = SimpleNamespace(
        updated_user=AsyncMock(
            return_value=SimpleNamespace(
                expire_at=current_subscription.expire_at + timedelta(days=30),
            )
        ),
    )
    subscription_service = SimpleNamespace(
        get_current=AsyncMock(return_value=current_subscription),
        update=AsyncMock(return_value=current_subscription),
    )
    settings_service = SimpleNamespace(
        get_max_subscriptions_for_user=AsyncMock(return_value=10),
        get_all_by_user=AsyncMock(return_value=[current_subscription]),
    )
    transaction_service = SimpleNamespace(update=AsyncMock(return_value=transaction))
    plan_service = SimpleNamespace(get_available_plans=AsyncMock(return_value=[]))

    asyncio.run(
        PURCHASE_SUBSCRIPTION_TASK(
            transaction=transaction,
            subscription=None,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            settings_service=settings_service,
            transaction_service=transaction_service,
            plan_service=plan_service,
        )
    )

    remnawave_service.updated_user.assert_awaited_once()
    assert (
        remnawave_service.updated_user.await_args.kwargs["uuid"]
        == current_subscription.user_remna_id
    )
    subscription_service.update.assert_awaited_once()
    success_task.kiq.assert_awaited_once_with(user, PurchaseType.RENEW)
    fail_task.kiq.assert_not_awaited()


def test_purchase_task_new_with_trial_upgrades_and_creates_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    success_task, _fail_task = _patch_task_notifications(monkeypatch)
    user = _build_user()
    plan = _build_plan(subscription_count=2, duration=30)
    transaction = _build_transaction(
        user=user,
        plan=plan,
        purchase_type=PurchaseType.NEW,
        device_types=[DeviceType.ANDROID, DeviceType.IPHONE],
    )
    trial_subscription = _build_subscription(
        user_telegram_id=user.telegram_id,
        plan=plan,
        is_trial=True,
    )

    remnawave_service = SimpleNamespace(
        updated_user=AsyncMock(
            return_value=SimpleNamespace(
                uuid=trial_subscription.user_remna_id,
                status=SubscriptionStatus.ACTIVE,
                expire_at=trial_subscription.expire_at + timedelta(days=30),
                subscription_url="https://sub.local/trial-updated",
            )
        ),
        create_user=AsyncMock(
            return_value=SimpleNamespace(
                uuid=uuid4(),
                status=SubscriptionStatus.ACTIVE,
                expire_at=datetime_now() + timedelta(days=30),
                subscription_url="https://sub.local/extra",
            )
        ),
        get_subscription_url=AsyncMock(return_value=None),
    )
    subscription_service = SimpleNamespace(
        get_current=AsyncMock(return_value=trial_subscription),
        get_all_by_user=AsyncMock(return_value=[trial_subscription]),
        update=AsyncMock(return_value=trial_subscription),
        create=AsyncMock(
            return_value=_build_subscription(user_telegram_id=user.telegram_id, plan=plan)
        ),
    )
    settings_service = SimpleNamespace(get_max_subscriptions_for_user=AsyncMock(return_value=10))
    transaction_service = SimpleNamespace(update=AsyncMock(return_value=transaction))
    plan_service = SimpleNamespace(get_available_plans=AsyncMock(return_value=[]))

    asyncio.run(
        PURCHASE_SUBSCRIPTION_TASK(
            transaction=transaction,
            subscription=None,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            settings_service=settings_service,
            transaction_service=transaction_service,
            plan_service=plan_service,
        )
    )

    remnawave_service.updated_user.assert_awaited_once()
    remnawave_service.create_user.assert_awaited_once()
    subscription_service.update.assert_awaited_once()
    subscription_service.create.assert_awaited_once()
    success_task.kiq.assert_awaited_once_with(user, PurchaseType.NEW)


def test_purchase_task_limit_guardrail_raises_before_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    success_task, _fail_task = _patch_task_notifications(monkeypatch)
    user = _build_user()
    plan = _build_plan(subscription_count=2, duration=30)
    transaction = _build_transaction(
        user=user,
        plan=plan,
        purchase_type=PurchaseType.ADDITIONAL,
    )
    existing_subscription = _build_subscription(user_telegram_id=user.telegram_id, plan=plan)

    remnawave_service = SimpleNamespace(
        create_user=AsyncMock(),
        get_subscription_url=AsyncMock(),
        updated_user=AsyncMock(),
    )
    subscription_service = SimpleNamespace(
        get_current=AsyncMock(return_value=None),
        get_all_by_user=AsyncMock(return_value=[existing_subscription]),
        update=AsyncMock(),
        create=AsyncMock(),
    )
    settings_service = SimpleNamespace(get_max_subscriptions_for_user=AsyncMock(return_value=1))
    transaction_service = SimpleNamespace(update=AsyncMock(return_value=transaction))
    plan_service = SimpleNamespace(get_available_plans=AsyncMock(return_value=[]))

    with pytest.raises(ValueError):
        asyncio.run(
            PURCHASE_SUBSCRIPTION_TASK(
                transaction=transaction,
                subscription=None,
                remnawave_service=remnawave_service,
                subscription_service=subscription_service,
                settings_service=settings_service,
                transaction_service=transaction_service,
                plan_service=plan_service,
            )
        )

    success_task.kiq.assert_not_awaited()
    remnawave_service.create_user.assert_not_awaited()
