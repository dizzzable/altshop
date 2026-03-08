from typing import cast

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from dishka import FromDishka
from dishka.integrations.aiogram import inject as aiogram_inject
from loguru import logger

from src.bot.states import Notification
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto
from src.services.user_notification_event import UserNotificationEventService

router = Router(name=__name__)


@router.callback_query(F.data.startswith(Notification.CLOSE.state))
@aiogram_inject
async def on_close_notification(
    callback: CallbackQuery,
    bot: Bot,
    user: UserDto,
    user_notification_event_service: FromDishka[UserNotificationEventService],
) -> None:
    notification: Message = cast(Message, callback.message)
    notification_id = notification.message_id
    event_id: int | None = None

    if callback.data:
        event_id_raw = callback.data.rsplit(":", maxsplit=1)[-1]
        if event_id_raw.isdigit() and callback.data != Notification.CLOSE.state:
            event_id = int(event_id_raw)

    logger.info(f"{log(user)} Closed notification '{notification_id}'")

    if event_id is not None:
        try:
            await user_notification_event_service.mark_read_by_id(
                notification_id=event_id,
                read_source="BOT",
            )
        except Exception as exception:
            logger.error(
                f"Failed to mark notification event '{event_id}' as read for bot close. "
                f"Exception: {exception}"
            )

    try:
        await notification.delete()
        await callback.answer()
        logger.debug(f"Notification '{notification_id}' for user '{user.telegram_id}' deleted")
    except Exception as exception:
        logger.error(f"Failed to delete notification '{notification_id}'. Exception: {exception}")

        try:
            logger.debug(f"Attempting to remove keyboard from notification '{notification_id}'")
            await bot.edit_message_reply_markup(
                chat_id=notification.chat.id,
                message_id=notification.message_id,
                reply_markup=None,
            )
            logger.debug(f"Keyboard removed from notification '{notification_id}'")
        except Exception as exception:
            logger.error(
                f"Failed to remove keyboard from notification '{notification_id}'. "
                f"Exception: {exception}"
            )
