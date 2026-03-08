from uuid import UUID

from sqlalchemy import JSON, BigInteger, Enum, ForeignKey, Integer
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import BroadcastAudience, BroadcastMessageStatus, BroadcastStatus
from src.core.utils.message_payload import MessagePayload

from .base import BaseSql
from .timestamp import TimestampMixin


class Broadcast(BaseSql, TimestampMixin):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    task_id: Mapped[UUID] = mapped_column(PG_UUID, nullable=False, unique=True)

    status: Mapped[BroadcastStatus] = mapped_column(
        Enum(
            BroadcastStatus,
            name="broadcast_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    audience: Mapped[BroadcastAudience] = mapped_column(
        Enum(
            BroadcastAudience,
            name="broadcast_audience",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[MessagePayload] = mapped_column(JSON, nullable=False)

    messages: Mapped[list["BroadcastMessage"]] = relationship(
        back_populates="broadcast",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BroadcastMessage(BaseSql):
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id"), nullable=False)

    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

    status: Mapped[BroadcastMessageStatus] = mapped_column(
        Enum(
            BroadcastMessageStatus,
            name="broadcast_message_status",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    broadcast: Mapped["Broadcast"] = relationship(back_populates="messages")
