from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import PaymentGatewayType, PurchaseType, TransactionStatus
from src.services.payment_gateway import PaymentGatewayService


def _build_payment_gateway_service() -> PaymentGatewayService:
    service = object.__new__(PaymentGatewayService)
    service.subscription_service = SimpleNamespace(
        get=AsyncMock(),
        get_current=AsyncMock(),
    )
    service.transaction_service = SimpleNamespace(
        get=AsyncMock(),
        update=AsyncMock(),
    )
    service.referral_service = SimpleNamespace(assign_referral_rewards=AsyncMock())
    service.partner_service = SimpleNamespace(process_partner_earning=AsyncMock())
    return service


def _build_transaction(
    *,
    purchase_type: PurchaseType = PurchaseType.RENEW,
    renew_subscription_id: int | None = None,
    renew_subscription_ids: list[int] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        user=SimpleNamespace(telegram_id=1001, name="User", username=None),
        purchase_type=purchase_type,
        renew_subscription_id=renew_subscription_id,
        renew_subscription_ids=renew_subscription_ids,
        is_completed=False,
        is_test=False,
        status=TransactionStatus.PENDING,
        pricing=SimpleNamespace(
            is_free=True,
            final_amount=Decimal("100"),
            discount_source=None,
            discount_percent=0,
            original_amount=Decimal("100"),
        ),
        payment_id=uuid4(),
        gateway_type=PaymentGatewayType.YOOKASSA,
        currency=SimpleNamespace(symbol="RUB"),
        plan=SimpleNamespace(
            name="Base Plan",
            type="BOTH",
            traffic_limit=100,
            device_limit=2,
            duration=30,
        ),
    )


def test_resolve_subscriptions_for_purchase_uses_current_fallback() -> None:
    service = _build_payment_gateway_service()
    current_subscription = SimpleNamespace(id=501)
    service.subscription_service.get_current = AsyncMock(return_value=current_subscription)
    transaction = _build_transaction()

    primary, to_renew = asyncio.run(
        service._resolve_subscriptions_for_purchase(transaction=transaction)
    )

    assert primary == current_subscription
    assert to_renew == [current_subscription]


def test_resolve_subscriptions_for_purchase_handles_single_and_multi_ids() -> None:
    service = _build_payment_gateway_service()
    current_subscription = SimpleNamespace(id=900)
    sub1 = SimpleNamespace(id=11)
    sub3 = SimpleNamespace(id=33)
    service.subscription_service.get_current = AsyncMock(return_value=current_subscription)

    single_tx = _build_transaction(renew_subscription_id=77)
    service.subscription_service.get = AsyncMock(return_value=None)
    primary_single, renew_single = asyncio.run(
        service._resolve_subscriptions_for_purchase(transaction=single_tx)
    )
    assert primary_single == current_subscription
    assert renew_single == [current_subscription]

    multi_tx = _build_transaction(renew_subscription_ids=[1, 2, 3])
    service.subscription_service.get = AsyncMock(side_effect=[sub1, None, sub3])
    primary_multi, renew_multi = asyncio.run(
        service._resolve_subscriptions_for_purchase(transaction=multi_tx)
    )
    assert primary_multi == sub1
    assert renew_multi == [sub1, sub3]


def test_handle_payment_succeeded_enqueues_resolved_subscriptions() -> None:
    service = _build_payment_gateway_service()
    payment_id = uuid4()
    transaction = _build_transaction()
    transaction.payment_id = payment_id
    transaction.gateway_type = PaymentGatewayType.YOOKASSA
    transaction.pricing.is_free = True

    primary_subscription = SimpleNamespace(id=123)
    subscriptions_to_renew = [primary_subscription, SimpleNamespace(id=124)]

    service.transaction_service.get = AsyncMock(return_value=transaction)
    service._consume_purchase_discount_if_needed = AsyncMock()
    service._resolve_subscriptions_for_purchase = AsyncMock(
        return_value=(primary_subscription, subscriptions_to_renew)
    )
    service._send_subscription_notification = AsyncMock()
    service._enqueue_subscription_purchase = AsyncMock()
    service._run_post_payment_rewards = AsyncMock()

    asyncio.run(service.handle_payment_succeeded(payment_id))

    assert transaction.status == TransactionStatus.COMPLETED
    service.transaction_service.update.assert_awaited_once_with(transaction)
    service._resolve_subscriptions_for_purchase.assert_awaited_once_with(transaction=transaction)
    service._enqueue_subscription_purchase.assert_awaited_once_with(
        transaction=transaction,
        subscription=primary_subscription,
        subscriptions_to_renew=subscriptions_to_renew,
    )
