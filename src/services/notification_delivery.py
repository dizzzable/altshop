from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Optional, cast

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from loguru import logger

from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import AnyKeyboard
from src.infrastructure.database.models.dto.user import BaseUserDto

if TYPE_CHECKING:
    from .notification import NotificationService


async def send_message(
    service: NotificationService,
    user: BaseUserDto,
    payload: MessagePayload,
    close_notification_id: Optional[int] = None,
) -> Optional[Message]:
    try:
        reply_markup = service._prepare_reply_markup(
            payload.reply_markup,
            payload.add_close_button,
            payload.auto_delete_after,
            user.language,
            user.telegram_id,
            close_notification_id,
        )

        if (payload.media or payload.media_id) and payload.media_type:
            sent_message = await service._send_media_message(user, payload, reply_markup)
        else:
            if (payload.media or payload.media_id) and not payload.media_type:
                logger.warning(
                    "Validation warning: Media provided without media_type for chat '{}'. "
                    "Sending as text message",
                    user.telegram_id,
                )
            sent_message = await service._send_text_message(user, payload, reply_markup)

        if payload.auto_delete_after is not None and sent_message:
            asyncio.create_task(
                service._schedule_message_deletion(
                    chat_id=user.telegram_id,
                    message_id=sent_message.message_id,
                    delay=payload.auto_delete_after,
                )
            )

        return sent_message
    except (TelegramForbiddenError, TelegramBadRequest) as exception:
        if not service._is_unreachable_chat_error(exception):
            logger.error(
                "Failed to send notification '{}' to '{}': {}",
                payload.i18n_key,
                user.telegram_id,
                exception,
                exc_info=True,
            )
            return None

        logger.info(
            "Skipping notification '{}' for '{}': Telegram chat is unreachable ({})",
            payload.i18n_key,
            user.telegram_id,
            exception,
        )
        await service._mark_user_as_bot_blocked(user.telegram_id)
        return None
    except Exception as exception:
        logger.error(
            "Failed to send notification '{}' to '{}': {}",
            payload.i18n_key,
            user.telegram_id,
            exception,
            exc_info=True,
        )
        return None


async def mark_user_as_bot_blocked(service: NotificationService, telegram_id: int) -> None:
    try:
        user = await service.user_service.get(telegram_id)
        if user and not user.is_bot_blocked:
            await service.user_service.set_bot_blocked(user=user, blocked=True)
    except Exception as exc:
        logger.warning(
            "Failed to mark user '{}' as bot-blocked after Telegram send error: {}",
            telegram_id,
            exc,
        )


def is_unreachable_chat_error(service: NotificationService, exception: Exception) -> bool:
    del service
    if isinstance(exception, TelegramForbiddenError):
        return True
    if isinstance(exception, TelegramBadRequest):
        return "chat not found" in str(exception).lower()
    return False


async def send_media_message(
    service: NotificationService,
    user: BaseUserDto,
    payload: MessagePayload,
    reply_markup: Optional[AnyKeyboard],
) -> Message:
    message_text = service._get_translated_text(
        locale=user.language,
        i18n_key=payload.i18n_key,
        i18n_kwargs=payload.i18n_kwargs,
    )
    message_text = service._truncate_telegram_text(
        message_text,
        service.TELEGRAM_CAPTION_LIMIT,
    )

    assert payload.media_type
    send_func = payload.media_type.get_function(service.bot)
    media_arg_name = payload.media_type.lower()

    media_input = payload.media or payload.media_id
    if media_input is None:
        raise ValueError(f"Missing media content for {payload.media_type}")

    tg_payload = {
        "chat_id": user.telegram_id,
        "caption": message_text,
        "reply_markup": reply_markup,
        "message_effect_id": payload.message_effect,
        media_arg_name: media_input,
    }
    return cast(Message, await send_func(**tg_payload))


async def send_text_message(
    service: NotificationService,
    user: BaseUserDto,
    payload: MessagePayload,
    reply_markup: Optional[AnyKeyboard],
) -> Message:
    message_text = service._get_translated_text(
        locale=user.language,
        i18n_key=payload.i18n_key,
        i18n_kwargs=payload.i18n_kwargs,
    )
    message_text = service._truncate_telegram_text(
        message_text,
        service.TELEGRAM_TEXT_LIMIT,
    )

    return await service.bot.send_message(
        chat_id=user.telegram_id,
        text=message_text,
        message_effect_id=payload.message_effect,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


def truncate_telegram_text(service: NotificationService, text: str, limit: int) -> str:
    del service
    if len(text) <= limit:
        return text

    text = re.sub(r"<[^>]+>", "", text)
    truncated_limit = max(limit - 3, 0)
    return f"{text[:truncated_limit].rstrip()}..."
