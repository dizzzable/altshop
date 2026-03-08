from typing import Any, Optional

from src.infrastructure.database.models.sql import Settings

from .base import BaseRepository


class SettingsRepository(BaseRepository):
    async def create(self, settings: Settings) -> Settings:
        return await self.create_instance(settings)

    async def get(self) -> Optional[Settings]:
        return await self._get_one(Settings)

    async def update(self, **data: Any) -> Optional[Settings]:
        return await self._update(Settings, **data)
