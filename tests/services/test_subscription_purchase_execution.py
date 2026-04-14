from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from httpx import HTTPStatusError, Request, Response

from src.api.utils.web_app_urls import build_web_payment_redirect_urls
from src.core.enums import (
    ArchivedPlanRenewMode,
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PaymentSource,
    PlanAvailability,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionDto,
    UserDto,
)
from src.services.subscription_purchase import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(telegram_id=telegram_id, name="Test User")


def build_plan(*, plan_id: int = 1, name: str = "Starter") -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name,
        is_active=True,
        is_archived=False,
        availability=PlanAvailability.ALL,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
        durations=[],
        allowed_user_ids=[],
        internal_squads=[],
    )


def build_gateway(
    *,
    gateway_type: PaymentGatewayType = PaymentGatewayType.ROBOKASSA,
    currency: Currency = Currency.RUB,
) -> PaymentGatewayDto:
    return PaymentGatewayDto(
        order_index=1,
        type=gateway_type,
        currency=currency,
        is_active=True,
    )


def build_pricing(*, amount: str = "10.00") -> PriceDetailsDto:
    return PriceDetailsDto(
        original_amount=Decimal(amount),
        discount_percent=0,
        discount_source=DiscountSource.NONE,
        final_amount=Decimal(amount),
    )


def build_config() -> Any:
    return SimpleNamespace(
        web_app=SimpleNamespace(url_str="https://cabinet.example.test"),
        domain=SimpleNamespace(get_secret_value=lambda: "example.test"),
    )


class FakeTransactionService:
    def __init__(self) -> None:
        self._transactions: dict[UUID, TransactionDto] = {}
        self.created: list[TransactionDto] = []
        self.updated: list[TransactionDto] = []
        self.create = AsyncMock(side_effect=self._create)
        self.get = AsyncMock(side_effect=self._get)
        self.update = AsyncMock(side_effect=self._update)

    async def _create(self, _user: UserDto, transaction: TransactionDto) -> None:
        self._transactions[transaction.payment_id] = transaction
        self.created.append(transaction)

    async def _get(self, payment_id: UUID) -> TransactionDto | None:
        return self._transactions.get(payment_id)

    async def _update(self, transaction: TransactionDto) -> None:
        self._transactions[transaction.payment_id] = transaction
        self.updated.append(transaction)


def build_service(
    *,
    payment_gateway_service: Any,
    partner_service: Any,
    config: Any | None = None,
) -> SubscriptionPurchaseService:
    return SubscriptionPurchaseService(
        config=cast(Any, config or build_config()),
        plan_service=cast(Any, object()),
        pricing_service=cast(Any, object()),
        purchase_access_service=cast(Any, object()),
        subscription_service=cast(Any, object()),
        subscription_purchase_policy_service=cast(Any, object()),
        settings_service=cast(Any, object()),
        payment_gateway_service=cast(Any, payment_gateway_service),
        partner_service=cast(Any, partner_service),
        market_quote_service=cast(Any, object()),
    )


def build_partner_balance_request() -> SubscriptionPurchaseRequest:
    return SubscriptionPurchaseRequest(
        purchase_type=PurchaseType.NEW,
        payment_source=PaymentSource.PARTNER_BALANCE,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.ROBOKASSA.value,
    )


def build_external_request() -> SubscriptionPurchaseRequest:
    return SubscriptionPurchaseRequest(
        purchase_type=PurchaseType.NEW,
        payment_source=PaymentSource.EXTERNAL,
        channel=PurchaseChannel.WEB,
    )


def test_handle_partner_balance_purchase_completes_without_payment_url() -> None:
    user = build_user()
    plan_snapshot = PlanSnapshotDto.from_plan(build_plan(), 30)
    gateway = build_gateway()
    pricing = build_pricing(amount="12.34")
    transaction_service = FakeTransactionService()
    payment_gateway_service = SimpleNamespace(
        transaction_service=transaction_service,
        handle_payment_succeeded=AsyncMock(),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True)),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=True),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    service = build_service(
        payment_gateway_service=payment_gateway_service,
        partner_service=partner_service,
    )

    result = run_async(
        service._handle_partner_balance_purchase(
            request=build_partner_balance_request(),
            current_user=user,
            gateway=gateway,
            gateway_type=gateway.type,
            final_price=pricing,
            payment_asset=None,
            plan_snapshot=plan_snapshot,
            renew_items=(),
            device_types=None,
        )
    )

    assert result.status == TransactionStatus.COMPLETED.value
    assert result.payment_url is None
    assert len(transaction_service.created) == 1


def test_handle_partner_balance_purchase_marks_pending_transaction_failed_on_insufficient_balance(
) -> None:
    user = build_user()
    plan_snapshot = PlanSnapshotDto.from_plan(build_plan(), 30)
    gateway = build_gateway()
    pricing = build_pricing(amount="10.00")
    transaction_service = FakeTransactionService()
    payment_gateway_service = SimpleNamespace(
        transaction_service=transaction_service,
        handle_payment_succeeded=AsyncMock(),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True)),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=False),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    service = build_service(
        payment_gateway_service=payment_gateway_service,
        partner_service=partner_service,
    )

    try:
        run_async(
            service._handle_partner_balance_purchase(
                request=build_partner_balance_request(),
                current_user=user,
                gateway=gateway,
                gateway_type=gateway.type,
                final_price=pricing,
                payment_asset=None,
                plan_snapshot=plan_snapshot,
                renew_items=(),
                device_types=None,
            )
        )
    except SubscriptionPurchaseError as error:
        assert error.status_code == 400
        assert error.detail == {
            "code": "INSUFFICIENT_PARTNER_BALANCE",
            "message": "Insufficient partner balance for this purchase",
        }
    else:
        raise AssertionError("Expected insufficient balance error")

    assert len(transaction_service.updated) == 1
    assert transaction_service.updated[0].status == TransactionStatus.FAILED


def test_handle_partner_balance_purchase_compensates_balance_on_unexpected_post_debit_failure(
) -> None:
    user = build_user()
    plan_snapshot = PlanSnapshotDto.from_plan(build_plan(), 30)
    gateway = build_gateway()
    pricing = build_pricing(amount="25.00")
    transaction_service = FakeTransactionService()

    async def fail_after_debit(_payment_id: UUID) -> None:
        raise RuntimeError("boom")

    payment_gateway_service = SimpleNamespace(
        transaction_service=transaction_service,
        handle_payment_succeeded=fail_after_debit,
    )
    credited_amounts: list[int] = []

    async def credit_balance_for_failed_subscription_purchase(
        *,
        user_telegram_id: int,
        amount_kopecks: int,
    ) -> None:
        assert user_telegram_id == user.telegram_id
        credited_amounts.append(amount_kopecks)

    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True)),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=True),
        credit_balance_for_failed_subscription_purchase=credit_balance_for_failed_subscription_purchase,
    )
    service = build_service(
        payment_gateway_service=payment_gateway_service,
        partner_service=partner_service,
    )

    try:
        run_async(
            service._handle_partner_balance_purchase(
                request=build_partner_balance_request(),
                current_user=user,
                gateway=gateway,
                gateway_type=gateway.type,
                final_price=pricing,
                payment_asset=None,
                plan_snapshot=plan_snapshot,
                renew_items=(),
                device_types=None,
            )
        )
    except SubscriptionPurchaseError as error:
        assert error.status_code == 500
        assert error.detail == "Failed to process partner balance payment"
    else:
        raise AssertionError("Expected unexpected partner balance failure")

    assert credited_amounts == [2500]
    assert len(transaction_service.updated) == 1
    assert transaction_service.updated[0].status == TransactionStatus.FAILED


def test_handle_external_purchase_uses_default_web_redirect_urls() -> None:
    user = build_user()
    config = build_config()
    plan_snapshot = PlanSnapshotDto.from_plan(build_plan(), 30)
    pricing = build_pricing(amount="9.99")
    captured_kwargs: dict[str, Any] = {}
    payment_result = SimpleNamespace(id=uuid4(), url="https://pay.example.test")

    async def create_payment(**kwargs: Any) -> Any:
        captured_kwargs.update(kwargs)
        return payment_result

    payment_gateway_service = SimpleNamespace(
        transaction_service=FakeTransactionService(),
        create_payment=create_payment,
    )
    partner_service = SimpleNamespace()
    service = build_service(
        payment_gateway_service=payment_gateway_service,
        partner_service=partner_service,
        config=config,
    )

    result = run_async(
        service._handle_external_purchase(
            request=build_external_request(),
            current_user=user,
            gateway_type=PaymentGatewayType.STRIPE,
            final_price=pricing,
            payment_asset=None,
            plan_snapshot=plan_snapshot,
            renew_items=(),
            device_types=None,
        )
    )

    expected_success_url, expected_fail_url = build_web_payment_redirect_urls(config)
    assert result.status == TransactionStatus.PENDING.value
    assert captured_kwargs["success_redirect_url"] == expected_success_url
    assert captured_kwargs["fail_redirect_url"] == expected_fail_url


def test_handle_external_purchase_maps_provider_http_status_error_to_bad_gateway() -> None:
    user = build_user()
    plan_snapshot = PlanSnapshotDto.from_plan(build_plan(), 30)
    pricing = build_pricing()
    request = Request("POST", "https://provider.example.test/pay")
    response = Response(503, request=request)

    async def create_payment(**_kwargs: Any) -> Any:
        raise HTTPStatusError("provider error", request=request, response=response)

    payment_gateway_service = SimpleNamespace(
        transaction_service=FakeTransactionService(),
        create_payment=create_payment,
    )
    service = build_service(
        payment_gateway_service=payment_gateway_service,
        partner_service=SimpleNamespace(),
    )

    try:
        run_async(
            service._handle_external_purchase(
                request=build_external_request(),
                current_user=user,
                gateway_type=PaymentGatewayType.STRIPE,
                final_price=pricing,
                payment_asset=None,
                plan_snapshot=plan_snapshot,
                renew_items=(),
                device_types=None,
            )
        )
    except SubscriptionPurchaseError as error:
        assert error.status_code == 502
        assert error.detail == "Payment provider 'STRIPE' rejected the request (503)"
    else:
        raise AssertionError("Expected provider HTTPStatusError to be mapped")


def test_handle_external_purchase_maps_generic_exception_to_internal_error() -> None:
    user = build_user()
    plan_snapshot = PlanSnapshotDto.from_plan(build_plan(), 30)
    pricing = build_pricing()

    async def create_payment(**_kwargs: Any) -> Any:
        raise RuntimeError("bad gateway state")

    payment_gateway_service = SimpleNamespace(
        transaction_service=FakeTransactionService(),
        create_payment=create_payment,
    )
    service = build_service(
        payment_gateway_service=payment_gateway_service,
        partner_service=SimpleNamespace(),
    )

    try:
        run_async(
            service._handle_external_purchase(
                request=build_external_request(),
                current_user=user,
                gateway_type=PaymentGatewayType.STRIPE,
                final_price=pricing,
                payment_asset=None,
                plan_snapshot=plan_snapshot,
                renew_items=(),
                device_types=None,
            )
        )
    except SubscriptionPurchaseError as error:
        assert error.status_code == 500
        assert error.detail == "Failed to create payment: bad gateway state"
    else:
        raise AssertionError("Expected generic payment creation error to be mapped")
