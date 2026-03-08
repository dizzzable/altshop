from __future__ import annotations

from src.infrastructure.database.models.sql import WebAnalyticsEvent

from .base import BaseRepository


class WebAnalyticsEventRepository(BaseRepository):
    async def create(self, event: WebAnalyticsEvent) -> WebAnalyticsEvent:
        return await self.create_instance(event)
