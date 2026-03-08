from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .base import BaseDto


class WebAnalyticsEventDto(BaseDto):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    event_name: str
    source_path: str
    session_id: str
    user_telegram_id: Optional[int] = None
    device_mode: str
    is_in_telegram: bool
    has_init_data: bool
    start_param: Optional[str] = None
    has_query_id: bool
    chat_type: Optional[str] = None
    meta: dict[str, Any] = {}
