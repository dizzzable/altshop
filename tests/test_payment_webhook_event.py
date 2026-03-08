import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.services.payment_webhook_event import (
    PAYMENT_WEBHOOK_STATUS_FAILED,
    PAYMENT_WEBHOOK_STATUS_PROCESSED,
    PAYMENT_WEBHOOK_STATUS_RECEIVED,
    PaymentWebhookEventService,
)


class _FakeUnitOfWork:
    def __init__(self, repository: SimpleNamespace) -> None:
        self.repository = repository
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> "_FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def test_record_received_returns_processed_duplicate_without_requeue() -> None:
    payment_id = uuid4()
    existing = PaymentWebhookEvent(
        id=1,
        gateway_type="PAYPALYCH",
        payment_id=payment_id,
        status=PAYMENT_WEBHOOK_STATUS_PROCESSED,
        payload_hash="old-hash",
        attempts=2,
    )
    repo = SimpleNamespace(
        payment_webhook_events=SimpleNamespace(
            get_by_gateway_and_payment_id=AsyncMock(return_value=existing),
            update=AsyncMock(),
            create=AsyncMock(),
        )
    )
    service = PaymentWebhookEventService(_FakeUnitOfWork(repo))

    result = asyncio.run(
        service.record_received(
            gateway_type="PAYPALYCH",
            payment_id=payment_id,
            payload_hash="new-hash",
        )
    )

    assert result.already_processed is True
    assert result.event.status == PAYMENT_WEBHOOK_STATUS_PROCESSED
    repo.payment_webhook_events.update.assert_not_awaited()
    repo.payment_webhook_events.create.assert_not_awaited()


def test_record_received_reopens_failed_event_and_increments_attempts() -> None:
    payment_id = uuid4()
    existing = PaymentWebhookEvent(
        id=4,
        gateway_type="PAYPALYCH",
        payment_id=payment_id,
        status=PAYMENT_WEBHOOK_STATUS_FAILED,
        payload_hash="old-hash",
        attempts=2,
    )
    updated = PaymentWebhookEvent(
        id=4,
        gateway_type="PAYPALYCH",
        payment_id=payment_id,
        status=PAYMENT_WEBHOOK_STATUS_RECEIVED,
        payload_hash="new-hash",
        attempts=3,
    )
    repo = SimpleNamespace(
        payment_webhook_events=SimpleNamespace(
            get_by_gateway_and_payment_id=AsyncMock(return_value=existing),
            update=AsyncMock(return_value=updated),
            create=AsyncMock(),
        )
    )
    uow = _FakeUnitOfWork(repo)
    service = PaymentWebhookEventService(uow)

    result = asyncio.run(
        service.record_received(
            gateway_type="PAYPALYCH",
            payment_id=payment_id,
            payload_hash="new-hash",
        )
    )

    assert result.already_processed is False
    assert result.event.status == PAYMENT_WEBHOOK_STATUS_RECEIVED
    assert result.event.attempts == 3
    repo.payment_webhook_events.update.assert_awaited_once()
    uow.commit.assert_awaited_once()
