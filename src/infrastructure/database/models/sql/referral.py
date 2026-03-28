from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transaction import Transaction
    from .user import User

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import PurchaseChannel, ReferralInviteSource, ReferralLevel, ReferralRewardType

from .base import BaseSql
from .timestamp import TimestampMixin


class ReferralInvite(BaseSql, TimestampMixin):
    __tablename__ = "referral_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inviter_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    inviter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[inviter_telegram_id],
        lazy="selectin",
    )


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
    invite_source: Mapped[ReferralInviteSource] = mapped_column(
        Enum(
            ReferralInviteSource,
            name="referral_invite_source",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ReferralInviteSource.UNKNOWN,
    )
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qualified_purchase_channel: Mapped[PurchaseChannel | None] = mapped_column(
        Enum(
            PurchaseChannel,
            name="purchasechannel",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    qualified_transaction_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
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
    qualified_transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        foreign_keys=[qualified_transaction_id],
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
    source_transaction_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

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
    source_transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        foreign_keys=[source_transaction_id],
        lazy="selectin",
    )
