from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.core.enums import PaymentGatewayType
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.services.payment_webhook_event import (
    PAYMENT_WEBHOOK_STATUS_ENQUEUED,
    PAYMENT_WEBHOOK_STATUS_FAILED,
    PAYMENT_WEBHOOK_STATUS_RECEIVED,
    PaymentWebhookEventService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self, repository: SimpleNamespace) -> None:
        self.repository = repository
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def test_record_received_treats_enqueued_payment_as_in_flight_duplicate() -> None:
    payment_id = uuid4()
    existing = PaymentWebhookEvent(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=payment_id,
        status=PAYMENT_WEBHOOK_STATUS_ENQUEUED,
        payload_hash="existing",
        attempts=1,
        last_error=None,
        received_at=datetime_now(),
    )
    repository = SimpleNamespace(
        payment_webhook_events=SimpleNamespace(
            get_by_gateway_and_payment_id=AsyncMock(return_value=existing),
            update=AsyncMock(),
            create=AsyncMock(),
        )
    )
    service = PaymentWebhookEventService(DummyUow(repository))

    result = run_async(
        service.record_received(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=payment_id,
            payload_hash="next",
        )
    )

    assert result.event is existing
    assert result.already_processed is False
    assert result.already_in_flight is True
    repository.payment_webhook_events.update.assert_not_awaited()
    repository.payment_webhook_events.create.assert_not_awaited()
    service.uow.commit.assert_not_awaited()


def test_record_received_retries_failed_payment_event() -> None:
    payment_id = uuid4()
    existing = PaymentWebhookEvent(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=payment_id,
        status=PAYMENT_WEBHOOK_STATUS_FAILED,
        payload_hash="old",
        attempts=2,
        last_error="boom",
        received_at=datetime_now(),
    )
    updated = PaymentWebhookEvent(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=payment_id,
        status=PAYMENT_WEBHOOK_STATUS_RECEIVED,
        payload_hash="new",
        attempts=3,
        last_error=None,
        received_at=datetime_now(),
    )
    repository = SimpleNamespace(
        payment_webhook_events=SimpleNamespace(
            get_by_gateway_and_payment_id=AsyncMock(return_value=existing),
            update=AsyncMock(return_value=updated),
            create=AsyncMock(),
        )
    )
    service = PaymentWebhookEventService(DummyUow(repository))

    result = run_async(
        service.record_received(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=payment_id,
            payload_hash="new",
        )
    )

    assert result.event is updated
    assert result.already_processed is False
    assert result.already_in_flight is False
    repository.payment_webhook_events.update.assert_awaited_once()
    assert (
        repository.payment_webhook_events.update.await_args.kwargs["status"]
        == PAYMENT_WEBHOOK_STATUS_RECEIVED
    )
    assert repository.payment_webhook_events.update.await_args.kwargs["attempts"] == 3
    service.uow.commit.assert_awaited_once()
