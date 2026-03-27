from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import (
    Currency,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionDto,
    UserDto,
)
from src.services.subscription_purchase_flows import (
    PartnerBalancePurchaseFlow,
    PurchaseFlowError,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(telegram_id=telegram_id, name="Test User")


def build_gateway() -> PaymentGatewayDto:
    return PaymentGatewayDto(
        order_index=1,
        type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=True,
    )


def build_transaction(payment_id) -> TransactionDto:
    return TransactionDto(
        payment_id=payment_id,
        status=TransactionStatus.PENDING,
        purchase_type=PurchaseType.NEW,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(final_amount=Decimal("10")),
        currency=Currency.RUB,
        plan=PlanSnapshotDto.test(),
        user=build_user(),
    )


def test_partner_balance_flow_marks_transaction_failed_when_balance_is_insufficient() -> None:
    payment_id = uuid4()
    transaction = build_transaction(payment_id)
    transaction_service = SimpleNamespace(
        create=AsyncMock(),
        get=AsyncMock(return_value=transaction),
        update=AsyncMock(),
    )
    payment_gateway_service = SimpleNamespace(
        transaction_service=transaction_service,
        handle_payment_succeeded=AsyncMock(),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True)),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=False),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    flow = PartnerBalancePurchaseFlow(
        payment_gateway_service=payment_gateway_service,
        partner_service=partner_service,
    )

    try:
        run_async(
            flow.handle(
                current_user=build_user(),
                channel=PurchaseChannel.WEB,
                purchase_type=PurchaseType.NEW,
                gateway=build_gateway(),
                gateway_type=PaymentGatewayType.PLATEGA,
                is_gateway_explicitly_selected=True,
                final_price=PriceDetailsDto(final_amount=Decimal("10")),
                payment_asset=None,
                plan_snapshot=PlanSnapshotDto.test(),
                renew_subscription_id=None,
                renew_subscription_ids=None,
                device_types=None,
            )
        )
    except PurchaseFlowError as error:
        assert error.status_code == 400
        assert error.detail["code"] == "INSUFFICIENT_PARTNER_BALANCE"
    else:
        raise AssertionError("Expected insufficient partner balance purchase to fail")

    assert transaction.status == TransactionStatus.FAILED
    transaction_service.update.assert_awaited_once_with(transaction)
    payment_gateway_service.handle_payment_succeeded.assert_not_awaited()
    partner_service.credit_balance_for_failed_subscription_purchase.assert_not_awaited()


def test_partner_balance_flow_refunds_balance_when_downstream_processing_fails() -> None:
    payment_id = uuid4()
    transaction = build_transaction(payment_id)
    transaction_service = SimpleNamespace(
        create=AsyncMock(),
        get=AsyncMock(return_value=transaction),
        update=AsyncMock(),
    )
    payment_gateway_service = SimpleNamespace(
        transaction_service=transaction_service,
        handle_payment_succeeded=AsyncMock(side_effect=RuntimeError("boom")),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True)),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=True),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    flow = PartnerBalancePurchaseFlow(
        payment_gateway_service=payment_gateway_service,
        partner_service=partner_service,
    )

    try:
        run_async(
            flow.handle(
                current_user=build_user(telegram_id=777),
                channel=PurchaseChannel.WEB,
                purchase_type=PurchaseType.NEW,
                gateway=build_gateway(),
                gateway_type=PaymentGatewayType.PLATEGA,
                is_gateway_explicitly_selected=True,
                final_price=PriceDetailsDto(final_amount=Decimal("12.50")),
                payment_asset=None,
                plan_snapshot=PlanSnapshotDto.test(),
                renew_subscription_id=None,
                renew_subscription_ids=None,
                device_types=None,
            )
        )
    except PurchaseFlowError as error:
        assert error.status_code == 500
        assert error.detail == "Failed to process partner balance payment"
    else:
        raise AssertionError("Expected downstream partner balance processing to fail")

    partner_service.credit_balance_for_failed_subscription_purchase.assert_awaited_once_with(
        user_telegram_id=777,
        amount_kopecks=1250,
    )
