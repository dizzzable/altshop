from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseSql
from .timestamp import NOW_FUNC


class WebAnalyticsEvent(BaseSql):
    __tablename__ = "web_analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=NOW_FUNC,
        nullable=False,
    )
    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_path: Mapped[str] = mapped_column(String(255), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    device_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    is_in_telegram: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    has_init_data: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    start_param: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    has_query_id: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    chat_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
