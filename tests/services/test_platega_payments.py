from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pydantic import SecretStr

from src.core.enums import (
    Currency,
    MessageEffect,
    PaymentGatewayType,
    PurchaseType,
    TransactionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PaymentGatewayDto, PlategaGatewaySettingsDto
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.infrastructure.payment_gateways.platega import (
    PlategaGateway,
    PlategaTransactionAccessDeniedError,
    PlategaTransactionNotFoundError,
    PlategaWebhookResolutionError,
)
from src.services.payment_gateway import PaymentGatewayService


def run_async(coroutine):
    return asyncio.run(coroutine)


class FakeRequest:
    def __init__(self, payload: bytes, headers: dict[str, str]) -> None:
        self._payload = payload
        self.headers = headers

    async def body(self) -> bytes:
        return self._payload


def build_platega_gateway() -> PlategaGateway:
    gateway = PaymentGatewayDto(
        order_index=1,
        type=PaymentGatewayType.PLATEGA,
        currency=Currency.RUB,
        is_active=True,
        settings=PlategaGatewaySettingsDto(
            merchant_id="merchant-id",
            secret=SecretStr("merchant-secret"),
            payment_method=2,
        ),
    )
    return PlategaGateway(gateway=gateway, bot=MagicMock())


def build_payment_gateway_service(
    *,
    transaction_service: object | None = None,
    payment_webhook_event_service: object | None = None,
    settings_service: object | None = None,
) -> PaymentGatewayService:
    return PaymentGatewayService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=MagicMock(),
        transaction_service=transaction_service or SimpleNamespace(),
        subscription_service=MagicMock(),
        payment_gateway_factory=MagicMock(),
        payment_webhook_event_service=payment_webhook_event_service or SimpleNamespace(),
        referral_service=MagicMock(),
        partner_service=MagicMock(),
        user_service=MagicMock(),
        settings_service=settings_service or SimpleNamespace(get=AsyncMock()),
    )


def test_platega_webhook_resolves_internal_payment_id_from_transaction_payload() -> None:
    external_transaction_id = uuid4()
    internal_payment_id = uuid4()
    gateway = build_platega_gateway()
    gateway.get_transaction = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "id": str(external_transaction_id),
            "status": "CONFIRMED",
            "payload": str(internal_payment_id),
        }
    )
    request = FakeRequest(
        payload=(
            f'{{"id":"{external_transaction_id}","status":"CONFIRMED"}}'.encode("utf-8")
        ),
        headers={
            "X-MerchantId": "merchant-id",
            "X-Secret": "merchant-secret",
        },
    )

    payment_id, payment_status = run_async(gateway.handle_webhook(request))

    assert payment_id == internal_payment_id
    assert payment_status == TransactionStatus.COMPLETED
    gateway.get_transaction.assert_awaited_once_with(str(external_transaction_id))


def test_platega_webhook_raises_resolution_error_for_invalid_payload_uuid() -> None:
    external_transaction_id = uuid4()
    gateway = build_platega_gateway()
    gateway.get_transaction = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "id": str(external_transaction_id),
            "status": "CONFIRMED",
            "payload": "not-a-uuid",
        }
    )
    request = FakeRequest(
        payload=(
            f'{{"id":"{external_transaction_id}","status":"CONFIRMED"}}'.encode("utf-8")
        ),
        headers={
            "X-MerchantId": "merchant-id",
            "X-Secret": "merchant-secret",
        },
    )

    try:
        run_async(gateway.handle_webhook(request))
    except PlategaWebhookResolutionError as exception:
        assert "internal payment UUID" in str(exception)
    else:
        raise AssertionError("Expected Platega webhook resolution to fail for invalid payload")


def test_platega_resolution_wraps_forbidden_lookup_as_compact_error() -> None:
    external_transaction_id = uuid4()
    gateway = build_platega_gateway()
    gateway.get_transaction = AsyncMock(  # type: ignore[method-assign]
        side_effect=PlategaTransactionAccessDeniedError("forbidden")
    )

    try:
        run_async(gateway.resolve_internal_payment_id(external_transaction_id))
    except PlategaWebhookResolutionError as exception:
        assert "lookup forbidden" in str(exception).lower()
    else:
        raise AssertionError("Expected forbidden Platega lookup to raise resolution error")


def test_handle_payment_succeeded_raises_when_transaction_is_missing() -> None:
    service = build_payment_gateway_service(
        transaction_service=SimpleNamespace(get=AsyncMock(return_value=None))
    )

    try:
        run_async(service.handle_payment_succeeded(uuid4()))
    except LookupError as exception:
        assert "not found" in str(exception)
    else:
        raise AssertionError("Expected missing transaction to raise LookupError")


def test_handle_payment_canceled_raises_when_transaction_user_is_missing() -> None:
    transaction = SimpleNamespace(user=None)
    service = build_payment_gateway_service(
        transaction_service=SimpleNamespace(get=AsyncMock(return_value=transaction))
    )

    try:
        run_async(service.handle_payment_canceled(uuid4()))
    except LookupError as exception:
        assert "missing user context" in str(exception)
    else:
        raise AssertionError("Expected missing transaction user to raise LookupError")


def test_send_subscription_notification_uses_upgrade_template_and_confetti_effect() -> None:
    service = build_payment_gateway_service()
    send_task = SimpleNamespace(kiq=AsyncMock())
    transaction = SimpleNamespace(
        payment_id=uuid4(),
        purchase_type=PurchaseType.UPGRADE,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing=SimpleNamespace(
            final_amount=250,
            discount_percent=0,
            original_amount=250,
        ),
        currency=Currency.RUB,
        user=SimpleNamespace(
            telegram_id=777000,
            name="Upgrade User",
            username="upgrade_user",
        ),
        plan=SimpleNamespace(
            name="Standard",
            type="MONTH",
            traffic_limit=0,
            device_limit=1,
            duration=30,
        ),
    )

    with patch("src.services.payment_gateway.send_system_notification_task", send_task):
        run_async(service._send_subscription_notification(transaction=transaction))

    payload = send_task.kiq.await_args.kwargs["payload"]
    assert payload.i18n_key == "ntf-event-subscription-upgrade"
    assert payload.message_effect == MessageEffect.CONFETTI
    assert send_task.kiq.await_args.kwargs["ntf_type"].value == "SUBSCRIPTION"


def test_recover_stuck_platega_payments_reconciles_legacy_webhook_event() -> None:
    external_transaction_id = uuid4()
    internal_payment_id = uuid4()
    legacy_event = PaymentWebhookEvent(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=external_transaction_id,
        status="PROCESSED",
        payload_hash="legacy",
        attempts=1,
        last_error=None,
        received_at=datetime_now(),
    )
    payment_webhook_event_service = SimpleNamespace(
        get_platega_orphan_events=AsyncMock(return_value=[legacy_event]),
        record_received=AsyncMock(return_value=SimpleNamespace(already_processed=False)),
        mark_processing=AsyncMock(),
        mark_processed=AsyncMock(),
        mark_failed=AsyncMock(),
        mark_reconciled=AsyncMock(),
        mark_reconcile_failed=AsyncMock(),
    )
    transaction_service = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                status=TransactionStatus.PENDING,
                is_completed=False,
            )
        )
    )
    service = build_payment_gateway_service(
        transaction_service=transaction_service,
        payment_webhook_event_service=payment_webhook_event_service,
    )
    gateway = build_platega_gateway()
    gateway.get_transaction = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "id": str(external_transaction_id),
            "status": "CONFIRMED",
            "payload": str(internal_payment_id),
        }
    )
    service._get_gateway_instance = AsyncMock(return_value=gateway)  # type: ignore[method-assign]
    service.handle_payment_succeeded = AsyncMock()  # type: ignore[method-assign]

    recovered = run_async(service.recover_stuck_platega_payments(limit=10))

    assert recovered == 1
    service.handle_payment_succeeded.assert_awaited_once_with(internal_payment_id)
    payment_webhook_event_service.record_received.assert_awaited_once()
    payment_webhook_event_service.mark_processed.assert_awaited_once_with(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=internal_payment_id,
    )
    payment_webhook_event_service.mark_reconciled.assert_awaited_once_with(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=external_transaction_id,
        diagnostic=f"recovered_to:{internal_payment_id}",
    )


def test_recover_stuck_platega_payments_is_idempotent_for_terminal_transactions() -> None:
    external_transaction_id = uuid4()
    internal_payment_id = uuid4()
    legacy_event = PaymentWebhookEvent(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=external_transaction_id,
        status="PROCESSED",
        payload_hash="legacy",
        attempts=1,
        last_error=None,
        received_at=datetime_now(),
    )
    payment_webhook_event_service = SimpleNamespace(
        get_platega_orphan_events=AsyncMock(return_value=[legacy_event]),
        mark_reconciled=AsyncMock(),
        mark_reconcile_failed=AsyncMock(),
        record_received=AsyncMock(),
        mark_processing=AsyncMock(),
        mark_processed=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    transaction_service = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                status=TransactionStatus.COMPLETED,
                is_completed=True,
            )
        )
    )
    service = build_payment_gateway_service(
        transaction_service=transaction_service,
        payment_webhook_event_service=payment_webhook_event_service,
    )
    gateway = build_platega_gateway()
    gateway.get_transaction = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "id": str(external_transaction_id),
            "status": "CONFIRMED",
            "payload": str(internal_payment_id),
        }
    )
    service._get_gateway_instance = AsyncMock(return_value=gateway)  # type: ignore[method-assign]
    service.handle_payment_succeeded = AsyncMock()  # type: ignore[method-assign]

    recovered = run_async(service.recover_stuck_platega_payments(limit=10))

    assert recovered == 1
    service.handle_payment_succeeded.assert_not_awaited()
    payment_webhook_event_service.mark_reconciled.assert_awaited_once_with(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=external_transaction_id,
        diagnostic=f"already_terminal:{internal_payment_id}:{TransactionStatus.COMPLETED.value}",
    )


def test_recover_stuck_platega_payments_skips_remote_404_transaction() -> None:
    external_transaction_id = uuid4()
    legacy_event = PaymentWebhookEvent(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=external_transaction_id,
        status="PROCESSED",
        payload_hash="legacy",
        attempts=1,
        last_error=None,
        received_at=datetime_now(),
    )
    payment_webhook_event_service = SimpleNamespace(
        get_platega_orphan_events=AsyncMock(return_value=[legacy_event]),
        mark_reconciled=AsyncMock(),
        mark_reconcile_failed=AsyncMock(),
        record_received=AsyncMock(),
        mark_processing=AsyncMock(),
        mark_processed=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    service = build_payment_gateway_service(
        payment_webhook_event_service=payment_webhook_event_service,
    )
    gateway = build_platega_gateway()
    gateway.get_transaction = AsyncMock(  # type: ignore[method-assign]
        side_effect=PlategaTransactionNotFoundError("missing remote transaction")
    )
    service._get_gateway_instance = AsyncMock(return_value=gateway)  # type: ignore[method-assign]
    service.handle_payment_succeeded = AsyncMock()  # type: ignore[method-assign]

    recovered = run_async(service.recover_stuck_platega_payments(limit=10))

    assert recovered == 0
    service.handle_payment_succeeded.assert_not_awaited()
    payment_webhook_event_service.mark_reconcile_failed.assert_awaited_once_with(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=external_transaction_id,
        diagnostic=f"remote_transaction_missing:{external_transaction_id}",
    )
