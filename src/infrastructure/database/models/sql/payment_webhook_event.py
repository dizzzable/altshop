from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import UUID as PG_UUID
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseSql
from .timestamp import NOW_FUNC, TimestampMixin


class PaymentWebhookEvent(BaseSql, TimestampMixin):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "gateway_type",
            "payment_id",
            name="uq_payment_webhook_events_gateway_payment",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gateway_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=NOW_FUNC,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
