from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, select, update

from src.infrastructure.database.models.sql import UserNotificationEvent

from .base import BaseRepository


class UserNotificationEventRepository(BaseRepository):
    async def create(self, event: UserNotificationEvent) -> UserNotificationEvent:
        return await self.create_instance(event)

    async def get_by_id_for_user(
        self,
        *,
        notification_id: int,
        user_telegram_id: int,
    ) -> Optional[UserNotificationEvent]:
        return await self._get_one(
            UserNotificationEvent,
            UserNotificationEvent.id == notification_id,
            UserNotificationEvent.user_telegram_id == user_telegram_id,
        )

    async def list_by_user(
        self,
        *,
        user_telegram_id: int,
        limit: int,
        offset: int,
    ) -> list[UserNotificationEvent]:
        return await self._get_many(
            UserNotificationEvent,
            UserNotificationEvent.user_telegram_id == user_telegram_id,
            order_by=[UserNotificationEvent.created_at.desc(), UserNotificationEvent.id.desc()],
            limit=limit,
            offset=offset,
        )

    async def count_by_user(self, *, user_telegram_id: int) -> int:
        return await self._count(
            UserNotificationEvent,
            UserNotificationEvent.user_telegram_id == user_telegram_id,
        )

    async def count_unread_by_user(self, *, user_telegram_id: int) -> int:
        return await self._count(
            UserNotificationEvent,
            and_(
                UserNotificationEvent.user_telegram_id == user_telegram_id,
                UserNotificationEvent.is_read.is_(False),
            ),
        )

    async def mark_read(
        self,
        *,
        notification_id: int,
        user_telegram_id: int,
        read_source: str,
        read_at: datetime,
    ) -> bool:
        query = (
            update(UserNotificationEvent)
            .where(
                UserNotificationEvent.id == notification_id,
                UserNotificationEvent.user_telegram_id == user_telegram_id,
                UserNotificationEvent.is_read.is_(False),
            )
            .values(
                is_read=True,
                read_at=read_at,
                read_source=read_source,
            )
        )
        result = await self.session.execute(query)
        return self._rowcount(result) > 0

    async def mark_all_read(
        self,
        *,
        user_telegram_id: int,
        read_source: str,
        read_at: datetime,
    ) -> int:
        query = (
            update(UserNotificationEvent)
            .where(
                UserNotificationEvent.user_telegram_id == user_telegram_id,
                UserNotificationEvent.is_read.is_(False),
            )
            .values(
                is_read=True,
                read_at=read_at,
                read_source=read_source,
            )
        )
        result = await self.session.execute(query)
        return self._rowcount(result)

    async def mark_read_by_id(
        self,
        *,
        notification_id: int,
        read_source: str,
        read_at: datetime,
    ) -> bool:
        query = (
            update(UserNotificationEvent)
            .where(
                UserNotificationEvent.id == notification_id,
                UserNotificationEvent.is_read.is_(False),
            )
            .values(
                is_read=True,
                read_at=read_at,
                read_source=read_source,
            )
        )
        result = await self.session.execute(query)
        return self._rowcount(result) > 0

    async def set_bot_delivery_meta(
        self,
        *,
        notification_id: int,
        bot_chat_id: int,
        bot_message_id: int,
    ) -> bool:
        query = (
            update(UserNotificationEvent)
            .where(UserNotificationEvent.id == notification_id)
            .values(
                bot_chat_id=bot_chat_id,
                bot_message_id=bot_message_id,
            )
        )
        result = await self.session.execute(query)
        return self._rowcount(result) > 0

    async def cleanup_older_than(self, *, threshold: datetime) -> int:
        query = (
            select(func.count())
            .select_from(UserNotificationEvent)
            .where(UserNotificationEvent.created_at < threshold)
        )
        to_delete = int((await self.session.scalar(query)) or 0)
        if to_delete == 0:
            return 0

        await self._delete(UserNotificationEvent, UserNotificationEvent.created_at < threshold)
        return to_delete
