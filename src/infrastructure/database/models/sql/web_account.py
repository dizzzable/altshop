from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseSql
from .timestamp import TimestampMixin

if TYPE_CHECKING:
    from .user import User


class WebAccount(BaseSql, TimestampMixin):
    __tablename__ = "web_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_normalized: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        unique=True,
        index=True,
    )
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    credentials_bootstrapped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    requires_password_change: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
    )
    temporary_password_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    link_prompt_snooze_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_telegram_id],
        lazy="selectin",
        back_populates="web_account",
    )
    challenges: Mapped[list["AuthChallenge"]] = relationship(
        "AuthChallenge",
        back_populates="web_account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AuthChallenge(BaseSql, TimestampMixin):
    __tablename__ = "auth_challenges"

    id: Mapped[UUID] = mapped_column(PG_UUID, primary_key=True)
    web_account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("web_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purpose: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False, index=True)

    code_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    token_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts_left: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    web_account: Mapped["WebAccount"] = relationship(
        "WebAccount",
        back_populates="challenges",
        foreign_keys=[web_account_id],
        lazy="selectin",
    )
