from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select

from src.core.enums import PaymentGatewayType
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.infrastructure.database.models.sql.transaction import Transaction

from .base import BaseRepository


class PaymentWebhookEventRepository(BaseRepository):
    async def create(self, event: PaymentWebhookEvent) -> PaymentWebhookEvent:
        return await self.create_instance(event)

    async def get(self, event_id: int) -> Optional[PaymentWebhookEvent]:
        return await self._get_one(PaymentWebhookEvent, PaymentWebhookEvent.id == event_id)

    async def get_by_gateway_and_payment_id(
        self,
        gateway_type: str,
        payment_id: UUID,
    ) -> Optional[PaymentWebhookEvent]:
        return await self._get_one(
            PaymentWebhookEvent,
            PaymentWebhookEvent.gateway_type == gateway_type,
            PaymentWebhookEvent.payment_id == payment_id,
        )

    async def update(self, event_id: int, **data: Any) -> Optional[PaymentWebhookEvent]:
        return await self._update(PaymentWebhookEvent, PaymentWebhookEvent.id == event_id, **data)

    async def get_platega_orphan_events(
        self,
        *,
        limit: int = 100,
    ) -> list[PaymentWebhookEvent]:
        query = (
            select(PaymentWebhookEvent)
            .outerjoin(Transaction, PaymentWebhookEvent.payment_id == Transaction.payment_id)
            .where(
                PaymentWebhookEvent.gateway_type == PaymentGatewayType.PLATEGA.value,
                Transaction.id.is_(None),
                PaymentWebhookEvent.status.notin_(("RECONCILED", "RECONCILE_FAILED")),
            )
            .order_by(PaymentWebhookEvent.received_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.unique().scalars().all())
