from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .user import User

from datetime import datetime

from sqlalchemy import ARRAY, JSON, BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import PromocodeAvailability, PromocodeRewardType
from src.infrastructure.database.models.dto import PlanSnapshotDto

from .base import BaseSql
from .timestamp import NOW_FUNC, TimestampMixin


class Promocode(BaseSql, TimestampMixin):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    availability: Mapped[PromocodeAvailability] = mapped_column(
        Enum(
            PromocodeAvailability,
            name="promocode_availability",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=PromocodeAvailability.ALL,
    )

    reward_type: Mapped[PromocodeRewardType] = mapped_column(
        Enum(
            PromocodeRewardType,
            name="promocode_reward_type",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    reward: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan: Mapped[PlanSnapshotDto] = mapped_column(JSON, nullable=True)

    lifetime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=-1)
    max_activations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=-1)
    allowed_user_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=True, default=[])

    activations: Mapped[list["PromocodeActivation"]] = relationship(
        "PromocodeActivation",
        back_populates="promocode",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PromocodeActivation(BaseSql):
    __tablename__ = "promocode_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    promocode_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("promocodes.id"),
        nullable=False,
    )
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=NOW_FUNC,
        nullable=False,
    )

    promocode: Mapped["Promocode"] = relationship("Promocode", back_populates="activations")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_telegram_id], lazy="selectin")
