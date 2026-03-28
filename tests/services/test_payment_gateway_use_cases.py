from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import src.services.payment_gateway_use_cases as payment_use_cases_module
from src.core.enums import (
    Currency,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionDto,
    UserDto,
)
from src.services.payment_gateway_use_cases import (
    PaymentCreationUseCase,
    PaymentFinalizationUseCase,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


class FakeTranslator:
    def get(self, key: str, **kwargs: object) -> str:
        return f"{key}:{kwargs}"


def build_gateway() -> PaymentGatewayDto:
    return PaymentGatewayDto(
        order_index=1,
        type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=True,
    )


def build_user(*, telegram_id: int = 100) -> UserDto:
    return UserDto(telegram_id=telegram_id, name="Test User")


def build_config(*, web_app_url: str = "https://example.test/webapp") -> SimpleNamespace:
    return SimpleNamespace(
        web_app=SimpleNamespace(url_str=web_app_url),
        domain=SimpleNamespace(get_secret_value=lambda: "example.test"),
        bot=SimpleNamespace(mini_app_url=False),
    )


async def echo_payment_result(*args, **kwargs) -> PaymentResult:
    return PaymentResult(id=kwargs["payment_id"], url="https://pay.example.test")


def test_create_payment_uses_default_telegram_redirects_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow = SimpleNamespace(commit=AsyncMock())
    transaction_service = SimpleNamespace(create=AsyncMock())
    gateway = SimpleNamespace(
        gateway=build_gateway(),
        handle_create_payment=AsyncMock(side_effect=echo_payment_result),
    )
    use_case = PaymentCreationUseCase(
        config=MagicMock(),
        bot=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="test_bot"))),
        translator_hub=SimpleNamespace(get_translator_by_locale=lambda locale: FakeTranslator()),
        uow=uow,
        transaction_service=transaction_service,
        settings_service=SimpleNamespace(get=AsyncMock()),
        get_gateway_instance=AsyncMock(return_value=gateway),
    )
    monkeypatch.setattr(
        use_case,
        "_resolve_telegram_payment_redirect_urls",
        AsyncMock(
            return_value=(
                "https://t.me/test_bot?startapp=payment-success",
                "https://t.me/test_bot?startapp=payment-failed",
            )
        ),
    )

    result = run_async(
        use_case.create_payment(
            user=build_user(),
            plan=PlanSnapshotDto.test(),
            pricing=PriceDetailsDto(
                original_amount=Decimal("100"),
                final_amount=Decimal("100"),
            ),
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.PLATEGA,
            channel=PurchaseChannel.TELEGRAM,
        )
    )

    assert result.url == "https://pay.example.test"
    gateway.handle_create_payment.assert_awaited_once()
    assert (
        gateway.handle_create_payment.await_args.kwargs["success_redirect_url"]
        == "https://t.me/test_bot?startapp=payment-success"
    )
    assert (
        gateway.handle_create_payment.await_args.kwargs["fail_redirect_url"]
        == "https://t.me/test_bot?startapp=payment-failed"
    )
    assert result.id == gateway.handle_create_payment.await_args.kwargs["payment_id"]
    transaction_service.create.assert_awaited_once()
    uow.commit.assert_awaited_once()


def test_create_payment_replaces_unapproved_web_redirects_with_defaults() -> None:
    uow = SimpleNamespace(commit=AsyncMock())
    transaction_service = SimpleNamespace(create=AsyncMock())
    gateway = SimpleNamespace(
        gateway=build_gateway(),
        handle_create_payment=AsyncMock(side_effect=echo_payment_result),
    )
    use_case = PaymentCreationUseCase(
        config=build_config(),
        bot=MagicMock(),
        translator_hub=SimpleNamespace(get_translator_by_locale=lambda locale: FakeTranslator()),
        uow=uow,
        transaction_service=transaction_service,
        settings_service=SimpleNamespace(get=AsyncMock()),
        get_gateway_instance=AsyncMock(return_value=gateway),
    )

    result = run_async(
        use_case.create_payment(
            user=build_user(),
            plan=PlanSnapshotDto.test(),
            pricing=PriceDetailsDto(
                original_amount=Decimal("100"),
                final_amount=Decimal("100"),
            ),
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.PLATEGA,
            channel=PurchaseChannel.WEB,
            success_redirect_url="https://evil.test/success",
            fail_redirect_url="https://evil.test/fail",
        )
    )

    assert result.id == gateway.handle_create_payment.await_args.kwargs["payment_id"]
    assert (
        gateway.handle_create_payment.await_args.kwargs["success_redirect_url"]
        == "https://example.test/webapp/dashboard/subscription?payment=success"
    )
    assert (
        gateway.handle_create_payment.await_args.kwargs["fail_redirect_url"]
        == "https://example.test/webapp/dashboard/subscription/purchase?payment=failed"
    )


def test_create_payment_replaces_unapproved_telegram_redirects_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow = SimpleNamespace(commit=AsyncMock())
    transaction_service = SimpleNamespace(create=AsyncMock())
    gateway = SimpleNamespace(
        gateway=build_gateway(),
        handle_create_payment=AsyncMock(side_effect=echo_payment_result),
    )
    use_case = PaymentCreationUseCase(
        config=build_config(),
        bot=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="test_bot"))),
        translator_hub=SimpleNamespace(get_translator_by_locale=lambda locale: FakeTranslator()),
        uow=uow,
        transaction_service=transaction_service,
        settings_service=SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(bot_menu=SimpleNamespace(mini_app_url=None)))
        ),
        get_gateway_instance=AsyncMock(return_value=gateway),
    )
    monkeypatch.setattr(
        use_case,
        "_resolve_telegram_payment_redirect_urls",
        AsyncMock(
            return_value=(
                "https://t.me/test_bot?startapp=payment-success",
                "https://t.me/test_bot?startapp=payment-failed",
            )
        ),
    )

    result = run_async(
        use_case.create_payment(
            user=build_user(),
            plan=PlanSnapshotDto.test(),
            pricing=PriceDetailsDto(
                original_amount=Decimal("100"),
                final_amount=Decimal("100"),
            ),
            purchase_type=PurchaseType.NEW,
            gateway_type=PaymentGatewayType.PLATEGA,
            channel=PurchaseChannel.TELEGRAM,
            success_redirect_url="https://evil.test/success",
            fail_redirect_url="https://evil.test/fail",
        )
    )

    assert result.id == gateway.handle_create_payment.await_args.kwargs["payment_id"]
    assert (
        gateway.handle_create_payment.await_args.kwargs["success_redirect_url"]
        == "https://t.me/test_bot?startapp=payment-success"
    )
    assert (
        gateway.handle_create_payment.await_args.kwargs["fail_redirect_url"]
        == "https://t.me/test_bot?startapp=payment-failed"
    )


def test_handle_payment_succeeded_runs_post_payment_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment_id = uuid4()
    current_user = build_user(telegram_id=321)
    discounted_user = build_user(telegram_id=321)
    discounted_user.purchase_discount = 50
    transaction = TransactionDto(
        id=42,
        payment_id=payment_id,
        status=TransactionStatus.PENDING,
        purchase_type=PurchaseType.NEW,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(
            original_amount=Decimal("100"),
            discount_percent=20,
            discount_source=DiscountSource.PURCHASE,
            final_amount=Decimal("80"),
        ),
        currency=Currency.RUB,
        plan=PlanSnapshotDto.test(),
        user=current_user,
    )
    uow = SimpleNamespace(commit=AsyncMock())
    transaction_service = SimpleNamespace(
        get=AsyncMock(return_value=transaction),
        update=AsyncMock(side_effect=lambda updated_transaction: updated_transaction),
    )
    subscription_service = SimpleNamespace(get=AsyncMock(), get_current=AsyncMock())
    referral_service = SimpleNamespace(assign_referral_rewards=AsyncMock())
    partner_service = SimpleNamespace(process_partner_earning=AsyncMock())
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=discounted_user),
        set_purchase_discount=AsyncMock(),
    )
    use_case = PaymentFinalizationUseCase(
        uow=uow,
        transaction_service=transaction_service,
        subscription_service=subscription_service,
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=user_service,
    )

    send_notification = AsyncMock()
    enqueue_purchase = AsyncMock()
    monkeypatch.setattr(
        payment_use_cases_module.send_system_notification_task,
        "kiq",
        send_notification,
    )
    monkeypatch.setattr(
        payment_use_cases_module.purchase_subscription_task,
        "kiq",
        enqueue_purchase,
    )
    monkeypatch.setattr(payment_use_cases_module, "get_user_keyboard", lambda _telegram_id: None)

    run_async(use_case.handle_payment_succeeded(payment_id))

    assert transaction.status == TransactionStatus.COMPLETED
    assert transaction.discount_consumed_at is not None
    assert transaction.subscription_notification_sent_at is not None
    assert transaction.subscription_purchase_enqueued_at is not None
    assert transaction_service.update.await_count == 4
    assert uow.commit.await_count == 4
    user_service.set_purchase_discount.assert_awaited_once_with(
        user=discounted_user,
        discount=30,
    )
    send_notification.assert_awaited_once()
    enqueue_purchase.assert_awaited_once()
    assert enqueue_purchase.await_args.args[1] is None
    assert enqueue_purchase.await_args.kwargs["subscriptions_to_renew"] is None
    referral_service.assign_referral_rewards.assert_awaited_once_with(transaction=transaction)
    partner_service.process_partner_earning.assert_awaited_once_with(
        payer_user_id=current_user.telegram_id,
        payment_amount=Decimal("80"),
        gateway_type=PaymentGatewayType.PLATEGA,
        source_transaction_id=42,
    )


def test_handle_payment_canceled_marks_transaction_terminal() -> None:
    payment_id = uuid4()
    transaction = TransactionDto(
        id=7,
        payment_id=payment_id,
        status=TransactionStatus.PENDING,
        purchase_type=PurchaseType.RENEW,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(),
        currency=Currency.RUB,
        plan=PlanSnapshotDto.test(),
        user=build_user(),
    )
    uow = SimpleNamespace(commit=AsyncMock())
    transaction_service = SimpleNamespace(
        get=AsyncMock(return_value=transaction),
        update=AsyncMock(side_effect=lambda updated_transaction: updated_transaction),
    )
    use_case = PaymentFinalizationUseCase(
        uow=uow,
        transaction_service=transaction_service,
        subscription_service=SimpleNamespace(),
        referral_service=SimpleNamespace(),
        partner_service=SimpleNamespace(),
        user_service=SimpleNamespace(),
    )

    run_async(use_case.handle_payment_canceled(payment_id))

    assert transaction.status == TransactionStatus.CANCELED
    transaction_service.update.assert_awaited_once_with(transaction)
    uow.commit.assert_awaited_once()


def test_handle_payment_succeeded_resumes_only_missing_dispatches_for_completed_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment_id = uuid4()
    transaction = TransactionDto(
        id=99,
        payment_id=payment_id,
        status=TransactionStatus.COMPLETED,
        purchase_type=PurchaseType.NEW,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=PriceDetailsDto(
            original_amount=Decimal("100"),
            final_amount=Decimal("100"),
        ),
        currency=Currency.RUB,
        plan=PlanSnapshotDto.test(),
        user=build_user(telegram_id=456),
        discount_consumed_at=datetime.now(timezone.utc),
        subscription_notification_sent_at=datetime.now(timezone.utc),
    )
    uow = SimpleNamespace(commit=AsyncMock())
    transaction_service = SimpleNamespace(
        get=AsyncMock(return_value=transaction),
        update=AsyncMock(side_effect=lambda updated_transaction: updated_transaction),
    )
    referral_service = SimpleNamespace(assign_referral_rewards=AsyncMock())
    partner_service = SimpleNamespace(process_partner_earning=AsyncMock())
    use_case = PaymentFinalizationUseCase(
        uow=uow,
        transaction_service=transaction_service,
        subscription_service=SimpleNamespace(get=AsyncMock(), get_current=AsyncMock()),
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=SimpleNamespace(get=AsyncMock(), set_purchase_discount=AsyncMock()),
    )

    send_notification = AsyncMock()
    enqueue_purchase = AsyncMock()
    monkeypatch.setattr(
        payment_use_cases_module.send_system_notification_task,
        "kiq",
        send_notification,
    )
    monkeypatch.setattr(
        payment_use_cases_module.purchase_subscription_task,
        "kiq",
        enqueue_purchase,
    )
    monkeypatch.setattr(payment_use_cases_module, "get_user_keyboard", lambda _telegram_id: None)

    run_async(use_case.handle_payment_succeeded(payment_id))

    send_notification.assert_not_awaited()
    enqueue_purchase.assert_awaited_once()
    assert transaction.subscription_purchase_enqueued_at is not None
    transaction_service.update.assert_awaited_once_with(transaction)
    uow.commit.assert_awaited_once()
