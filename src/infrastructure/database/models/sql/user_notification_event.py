from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseSql
from .timestamp import TimestampMixin


class UserNotificationEvent(BaseSql, TimestampMixin):
    __tablename__ = "user_notification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
    )
    ntf_type: Mapped[str] = mapped_column(String(128), nullable=False)
    i18n_key: Mapped[str] = mapped_column(String(255), nullable=False)
    i18n_kwargs: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    rendered_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    bot_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    bot_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
