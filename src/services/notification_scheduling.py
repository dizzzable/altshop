from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .notification import NotificationService


async def schedule_message_deletion(
    service: NotificationService,
    chat_id: int,
    message_id: int,
    delay: int,
) -> None:
    logger.debug(
        "Scheduling message '{}' for auto-deletion in '{}' (chat '{}')",
        message_id,
        delay,
        chat_id,
    )
    try:
        await asyncio.sleep(delay)
        await service.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.debug(
            "Message '{}' in chat '{}' deleted after '{}' seconds",
            message_id,
            chat_id,
            delay,
        )
    except Exception as exception:
        logger.error(
            "Failed to delete message '{}' in chat '{}': {}",
            message_id,
            chat_id,
            exception,
        )
