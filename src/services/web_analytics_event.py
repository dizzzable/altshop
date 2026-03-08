from __future__ import annotations

from typing import Any, Optional

from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import WebAnalyticsEventDto
from src.infrastructure.database.models.sql import WebAnalyticsEvent


class WebAnalyticsEventService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_event(
        self,
        *,
        event_name: str,
        source_path: str,
        session_id: str,
        device_mode: str,
        is_in_telegram: bool,
        has_init_data: bool,
        has_query_id: bool,
        user_telegram_id: Optional[int] = None,
        start_param: Optional[str] = None,
        chat_type: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> WebAnalyticsEventDto:
        async with self.uow:
            event = await self.uow.repository.web_analytics_events.create(
                WebAnalyticsEvent(
                    event_name=event_name,
                    source_path=source_path,
                    session_id=session_id,
                    user_telegram_id=user_telegram_id,
                    device_mode=device_mode,
                    is_in_telegram=is_in_telegram,
                    has_init_data=has_init_data,
                    start_param=start_param,
                    has_query_id=has_query_id,
                    chat_type=chat_type,
                    meta=meta or {},
                )
            )
            await self.uow.commit()
            dto = WebAnalyticsEventDto.from_model(event)
            if not dto:
                raise ValueError("Failed to create web analytics event")
            return dto
