from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from aiogram.types import FSInputFile, Message
from loguru import logger

from src.core.enums import Locale
from src.services.backup_models import BackupInfo

if TYPE_CHECKING:
    from .backup import BackupService


async def _send_backup_file_to_chat(
    service: BackupService,
    file_path: str,
    *,
    backup_info: BackupInfo,
    locale: Locale | None = None,
) -> Optional[Message]:
    try:
        if not service.config.backup.is_send_enabled():
            return None

        chat_id = service.config.backup.send_chat_id
        if not chat_id:
            return None

        document = FSInputFile(file_path)
        caption = service._build_backup_caption(
            backup_info=backup_info,
            locale=locale,
        )

        if service.config.backup.send_topic_id:
            message = await service.bot.send_document(
                chat_id=chat_id,
                document=document,
                caption=caption,
                parse_mode="HTML",
                message_thread_id=service.config.backup.send_topic_id,
            )
        else:
            message = await service.bot.send_document(
                chat_id=chat_id,
                document=document,
                caption=caption,
                parse_mode="HTML",
            )
        logger.info(f"Бэкап отправлен в чат {chat_id}")
        return message

    except Exception as exc:
        logger.error(f"Ошибка отправки бэкапа в чат: {exc}")
        return None
