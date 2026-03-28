from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from src.core.enums import (
    CryptoAsset,
    Currency,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import PlanSnapshotDto, PriceDetailsDto

from .base import BaseSql
from .timestamp import TimestampMixin


class Transaction(BaseSql, TimestampMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        Index(
            "ix_transactions_user_telegram_id_created_at_desc",
            "user_telegram_id",
            text("created_at DESC"),
        ),
        Index("ix_transactions_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False, unique=True)

    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(
            TransactionStatus,
            name="transaction_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False)

    purchase_type: Mapped[PurchaseType] = mapped_column(Enum(PurchaseType), nullable=False)
    channel: Mapped[PurchaseChannel | None] = mapped_column(
        Enum(
            PurchaseChannel,
            name="purchasechannel",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    gateway_type: Mapped[PaymentGatewayType] = mapped_column(
        Enum(
            PaymentGatewayType,
            name="payment_gateway_type",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    pricing: Mapped[PriceDetailsDto] = mapped_column(JSON, nullable=False)
    currency: Mapped[Currency] = mapped_column(
        Enum(
            Currency,
            name="currency",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    payment_asset: Mapped[CryptoAsset | None] = mapped_column(
        Enum(
            CryptoAsset,
            name="crypto_asset",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    plan: Mapped[PlanSnapshotDto] = mapped_column(JSON, nullable=False)

    # ID подписки для продления (используется при PurchaseType.RENEW)
    renew_subscription_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Список ID подписок для множественного продления
    renew_subscription_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    # Список типов устройств для новых подписок (хранится как массив строк)
    device_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    discount_consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    test_notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    subscription_notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    subscription_purchase_enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_telegram_id], lazy="selectin")
