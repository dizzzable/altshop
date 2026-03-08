from __future__ import annotations

from datetime import timedelta
from typing import Any

from loguru import logger

from src.core.enums import UserNotificationType
from src.core.utils.time import datetime_now
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import UserNotificationEventDto
from src.infrastructure.database.models.sql import UserNotificationEvent


class UserNotificationEventService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_event(
        self,
        *,
        user_telegram_id: int,
        ntf_type: UserNotificationType,
        i18n_key: str,
        i18n_kwargs: dict[str, Any],
        rendered_text: str,
    ) -> UserNotificationEventDto:
        async with self.uow:
            event = await self.uow.repository.user_notification_events.create(
                UserNotificationEvent(
                    user_telegram_id=user_telegram_id,
                    ntf_type=ntf_type.value,
                    i18n_key=i18n_key,
                    i18n_kwargs=i18n_kwargs,
                    rendered_text=rendered_text,
                    is_read=False,
                )
            )
            await self.uow.commit()
            dto = UserNotificationEventDto.from_model(event)
            if not dto:
                raise ValueError("Failed to create notification event")
            return dto

    async def set_bot_delivery_meta(
        self,
        *,
        notification_id: int,
        bot_chat_id: int,
        bot_message_id: int,
    ) -> bool:
        async with self.uow:
            updated = await self.uow.repository.user_notification_events.set_bot_delivery_meta(
                notification_id=notification_id,
                bot_chat_id=bot_chat_id,
                bot_message_id=bot_message_id,
            )
            if updated:
                await self.uow.commit()
            return updated

    async def list_by_user(
        self,
        *,
        user_telegram_id: int,
        page: int,
        limit: int,
    ) -> tuple[list[UserNotificationEventDto], int, int]:
        safe_page = max(page, 1)
        safe_limit = min(max(limit, 1), 100)
        offset = (safe_page - 1) * safe_limit

        async with self.uow:
            events = await self.uow.repository.user_notification_events.list_by_user(
                user_telegram_id=user_telegram_id,
                limit=safe_limit,
                offset=offset,
            )
            total = await self.uow.repository.user_notification_events.count_by_user(
                user_telegram_id=user_telegram_id
            )
            unread = await self.uow.repository.user_notification_events.count_unread_by_user(
                user_telegram_id=user_telegram_id
            )
        return UserNotificationEventDto.from_model_list(events), total, unread

    async def count_unread(self, *, user_telegram_id: int) -> int:
        async with self.uow:
            return await self.uow.repository.user_notification_events.count_unread_by_user(
                user_telegram_id=user_telegram_id
            )

    async def mark_read(
        self,
        *,
        notification_id: int,
        user_telegram_id: int,
        read_source: str,
    ) -> bool:
        async with self.uow:
            updated = await self.uow.repository.user_notification_events.mark_read(
                notification_id=notification_id,
                user_telegram_id=user_telegram_id,
                read_source=read_source,
                read_at=datetime_now(),
            )
            if updated:
                await self.uow.commit()
            return updated

    async def mark_read_by_id(
        self,
        *,
        notification_id: int,
        read_source: str,
    ) -> bool:
        async with self.uow:
            updated = await self.uow.repository.user_notification_events.mark_read_by_id(
                notification_id=notification_id,
                read_source=read_source,
                read_at=datetime_now(),
            )
            if updated:
                await self.uow.commit()
            return updated

    async def mark_all_read(
        self,
        *,
        user_telegram_id: int,
        read_source: str,
    ) -> int:
        async with self.uow:
            updated = await self.uow.repository.user_notification_events.mark_all_read(
                user_telegram_id=user_telegram_id,
                read_source=read_source,
                read_at=datetime_now(),
            )
            if updated:
                await self.uow.commit()
            return updated

    async def cleanup_older_than(self, *, days: int) -> int:
        threshold = datetime_now() - timedelta(days=days)
        async with self.uow:
            deleted = await self.uow.repository.user_notification_events.cleanup_older_than(
                threshold=threshold
            )
            if deleted:
                await self.uow.commit()
                logger.info(f"Cleaned up '{deleted}' notification events older than '{days}' days")
            return deleted
