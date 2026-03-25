from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from dishka.integrations.taskiq import CONTAINER_NAME

from src.core.enums import PaymentGatewayType, TransactionStatus
from src.infrastructure.taskiq.tasks.payments import handle_payment_transaction_task


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_handle_payment_transaction_task_skips_stale_lookup_after_restore() -> None:
    payment_id = uuid4()
    payment_gateway_service = SimpleNamespace(
        handle_payment_succeeded=AsyncMock(),
        handle_payment_canceled=AsyncMock(
            side_effect=LookupError(f"Transaction '{payment_id}' not found")
        ),
    )
    payment_webhook_event_service = SimpleNamespace(
        mark_processing=AsyncMock(),
        mark_enqueued=AsyncMock(),
        mark_processed=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    container = SimpleNamespace(
        get=AsyncMock(
            side_effect=[payment_gateway_service, payment_webhook_event_service]
        )
    )

    run_async(
        handle_payment_transaction_task(
            str(payment_id),
            TransactionStatus.CANCELED.value,
            PaymentGatewayType.PLATEGA.value,
            **{CONTAINER_NAME: container},
        )
    )

    payment_webhook_event_service.mark_processing.assert_awaited_once()
    payment_gateway_service.handle_payment_canceled.assert_awaited_once_with(payment_id)
    payment_webhook_event_service.mark_failed.assert_awaited_once()
    assert "stale_after_restore" in payment_webhook_event_service.mark_failed.await_args.kwargs[
        "error_message"
    ]
    payment_webhook_event_service.mark_processed.assert_not_awaited()


def test_handle_payment_transaction_task_reraises_unexpected_errors() -> None:
    payment_id = uuid4()
    payment_gateway_service = SimpleNamespace(
        handle_payment_succeeded=AsyncMock(side_effect=RuntimeError("boom")),
        handle_payment_canceled=AsyncMock(),
    )
    payment_webhook_event_service = SimpleNamespace(
        mark_processing=AsyncMock(),
        mark_enqueued=AsyncMock(),
        mark_processed=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    container = SimpleNamespace(
        get=AsyncMock(
            side_effect=[payment_gateway_service, payment_webhook_event_service]
        )
    )

    try:
        run_async(
            handle_payment_transaction_task(
                str(payment_id),
                TransactionStatus.COMPLETED.value,
                PaymentGatewayType.PLATEGA.value,
                **{CONTAINER_NAME: container},
            )
        )
    except RuntimeError as exception:
        assert str(exception) == "boom"
    else:
        raise AssertionError("Expected unexpected task error to bubble up")

    payment_webhook_event_service.mark_failed.assert_awaited_once_with(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=payment_id,
        error_message="boom",
    )
