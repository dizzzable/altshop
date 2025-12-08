from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .referral import Referral
    from .subscription import Subscription

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import Locale, UserRole

from .base import BaseSql
from .timestamp import TimestampMixin


class User(BaseSql, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    referral_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    language: Mapped[Locale] = mapped_column(
        Enum(
            Locale,
            name="locale",
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    personal_discount: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_discount: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)

    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_bot_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_rules_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    current_subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )

    current_subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        foreign_keys=[current_subscription_id],
        lazy="selectin",
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        primaryjoin="User.telegram_id==Subscription.user_telegram_id",
        foreign_keys="[Subscription.user_telegram_id]",
        lazy="selectin",
    )

    referral: Mapped[Optional["Referral"]] = relationship(
        "Referral",
        back_populates="referred",
        primaryjoin="User.telegram_id==Referral.referred_telegram_id",
        uselist=False,
        lazy="selectin",
    )
