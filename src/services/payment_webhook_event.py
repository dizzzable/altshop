from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.infrastructure.database.uow import UnitOfWork

PAYMENT_WEBHOOK_STATUS_RECEIVED = "RECEIVED"
PAYMENT_WEBHOOK_STATUS_ENQUEUED = "ENQUEUED"
PAYMENT_WEBHOOK_STATUS_PROCESSING = "PROCESSING"
PAYMENT_WEBHOOK_STATUS_PROCESSED = "PROCESSED"
PAYMENT_WEBHOOK_STATUS_FAILED = "FAILED"
PAYMENT_WEBHOOK_STATUS_RECONCILED = "RECONCILED"
PAYMENT_WEBHOOK_STATUS_RECONCILE_FAILED = "RECONCILE_FAILED"


@dataclass(slots=True)
class PaymentWebhookReceiveResult:
    event: PaymentWebhookEvent
    already_processed: bool


class PaymentWebhookEventService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def record_received(
        self,
        *,
        gateway_type: str,
        payment_id: UUID,
        payload_hash: str,
    ) -> PaymentWebhookReceiveResult:
        async with self.uow:
            existing = (
                await self.uow.repository.payment_webhook_events.get_by_gateway_and_payment_id(
                    gateway_type,
                    payment_id,
                )
            )

            if existing and existing.status == PAYMENT_WEBHOOK_STATUS_PROCESSED:
                return PaymentWebhookReceiveResult(event=existing, already_processed=True)

            if existing:
                updated = await self.uow.repository.payment_webhook_events.update(
                    existing.id,
                    status=PAYMENT_WEBHOOK_STATUS_RECEIVED,
                    payload_hash=payload_hash,
                    attempts=max(existing.attempts, 0) + 1,
                    last_error=None,
                    received_at=datetime_now(),
                    processed_at=None,
                )
                if updated is None:
                    raise RuntimeError("Failed to update payment webhook inbox event")
                await self.uow.commit()
                return PaymentWebhookReceiveResult(event=updated, already_processed=False)

            event = PaymentWebhookEvent(
                gateway_type=gateway_type,
                payment_id=payment_id,
                status=PAYMENT_WEBHOOK_STATUS_RECEIVED,
                payload_hash=payload_hash,
                attempts=1,
                last_error=None,
                received_at=datetime_now(),
            )

            try:
                created = await self.uow.repository.payment_webhook_events.create(event)
            except IntegrityError:
                await self.uow.rollback()
                existing = (
                    await self.uow.repository.payment_webhook_events.get_by_gateway_and_payment_id(
                        gateway_type,
                        payment_id,
                    )
                )
                if existing is None:
                    raise
                return PaymentWebhookReceiveResult(
                    event=existing,
                    already_processed=existing.status == PAYMENT_WEBHOOK_STATUS_PROCESSED,
                )

            await self.uow.commit()
            return PaymentWebhookReceiveResult(event=created, already_processed=False)

    async def mark_enqueued(self, *, gateway_type: str, payment_id: UUID) -> None:
        await self._mark_status(
            gateway_type=gateway_type,
            payment_id=payment_id,
            status=PAYMENT_WEBHOOK_STATUS_ENQUEUED,
            last_error=None,
        )

    async def mark_processing(self, *, gateway_type: str, payment_id: UUID) -> None:
        await self._mark_status(
            gateway_type=gateway_type,
            payment_id=payment_id,
            status=PAYMENT_WEBHOOK_STATUS_PROCESSING,
            last_error=None,
        )

    async def mark_processed(self, *, gateway_type: str, payment_id: UUID) -> None:
        await self._mark_status(
            gateway_type=gateway_type,
            payment_id=payment_id,
            status=PAYMENT_WEBHOOK_STATUS_PROCESSED,
            processed_at=datetime_now(),
            last_error=None,
        )

    async def mark_failed(
        self,
        *,
        gateway_type: str,
        payment_id: UUID,
        error_message: str,
    ) -> None:
        await self._mark_status(
            gateway_type=gateway_type,
            payment_id=payment_id,
            status=PAYMENT_WEBHOOK_STATUS_FAILED,
            last_error=error_message[:2048],
        )

    async def mark_reconciled(
        self,
        *,
        gateway_type: str,
        payment_id: UUID,
        diagnostic: str | None = None,
    ) -> None:
        await self._mark_status(
            gateway_type=gateway_type,
            payment_id=payment_id,
            status=PAYMENT_WEBHOOK_STATUS_RECONCILED,
            processed_at=datetime_now(),
            last_error=diagnostic[:2048] if diagnostic else None,
        )

    async def mark_reconcile_failed(
        self,
        *,
        gateway_type: str,
        payment_id: UUID,
        diagnostic: str,
    ) -> None:
        await self._mark_status(
            gateway_type=gateway_type,
            payment_id=payment_id,
            status=PAYMENT_WEBHOOK_STATUS_RECONCILE_FAILED,
            processed_at=datetime_now(),
            last_error=diagnostic[:2048],
        )

    async def get_platega_orphan_events(self, *, limit: int = 100) -> list[PaymentWebhookEvent]:
        async with self.uow:
            return await self.uow.repository.payment_webhook_events.get_platega_orphan_events(
                limit=limit
            )

    async def _mark_status(
        self,
        *,
        gateway_type: str,
        payment_id: UUID,
        status: str,
        processed_at: object | None = None,
        last_error: str | None,
    ) -> None:
        async with self.uow:
            event = await self.uow.repository.payment_webhook_events.get_by_gateway_and_payment_id(
                gateway_type,
                payment_id,
            )
            if event is None:
                logger.warning(
                    (
                        "Payment webhook inbox event is missing for gateway='{}' "
                        "payment_id='{}' while setting status='{}'"
                    ),
                    gateway_type,
                    payment_id,
                    status,
                )
                return

            update_data: dict[str, object | None] = {
                "status": status,
                "last_error": last_error,
            }
            if processed_at is not None or status == PAYMENT_WEBHOOK_STATUS_PROCESSED:
                update_data["processed_at"] = processed_at

            await self.uow.repository.payment_webhook_events.update(event.id, **update_data)
            await self.uow.commit()
