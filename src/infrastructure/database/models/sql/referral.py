from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import ReferralLevel, ReferralRewardType

from .base import BaseSql
from .timestamp import TimestampMixin


class Referral(BaseSql, TimestampMixin):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )
    referred_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    level: Mapped[ReferralLevel] = mapped_column(
        Enum(
            ReferralLevel,
            name="referral_level",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    referrer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[referrer_telegram_id],
        lazy="selectin",
    )
    referred: Mapped["User"] = relationship(
        "User",
        back_populates="referral",
        foreign_keys=[referred_telegram_id],
        lazy="selectin",
    )
    rewards: Mapped[list["ReferralReward"]] = relationship(
        "ReferralReward",
        back_populates="referral",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ReferralReward(BaseSql, TimestampMixin):
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referral_id: Mapped[int] = mapped_column(Integer, ForeignKey("referrals.id"), nullable=False)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )

    type: Mapped[ReferralRewardType] = mapped_column(
        Enum(
            ReferralRewardType,
            name="referral_reward_type",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_issued: Mapped[bool] = mapped_column(Boolean, nullable=False)

    referral: Mapped["Referral"] = relationship(
        "Referral",
        back_populates="rewards",
        foreign_keys=[referral_id],
        lazy="selectin",
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_telegram_id],
        lazy="selectin",
    )
