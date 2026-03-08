from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.core.enums import UserNotificationType

from .base import BaseDto


class UserNotificationEventDto(BaseDto):
    id: Optional[int] = None
    user_telegram_id: int
    ntf_type: UserNotificationType
    i18n_key: str
    i18n_kwargs: dict[str, Any] = {}
    rendered_text: str
    is_read: bool = False
    read_at: Optional[datetime] = None
    read_source: Optional[str] = None
    bot_chat_id: Optional[int] = None
    bot_message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
