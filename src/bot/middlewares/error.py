import traceback
from typing import Any, Awaitable, Callable, Optional, cast

from aiogram.types import ErrorEvent, TelegramObject
from aiogram.types import User as AiogramUser
from aiogram.utils.formatting import Text
from dishka import AsyncContainer

from src.bot.keyboards import get_user_keyboard
from src.core.constants import CONTAINER_KEY
from src.core.enums import MiddlewareEventType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.user import UserService

from .base import EventTypedMiddleware


class ErrorMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.ERROR]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: Optional[AiogramUser] = self._get_aiogram_user(event)

        user_data = (
            {
                "user": True,
                "user_id": str(aiogram_user.id),
                "user_name": aiogram_user.full_name,
                "username": aiogram_user.username or False,
            }
            if aiogram_user
            else {"user": False}
        )

        user_id = user_data.get("user_id")
        error_event = cast(ErrorEvent, event)
        traceback_str = traceback.format_exc()
        error_type_name = type(error_event.exception).__name__
        error_message = Text(str(error_event.exception)[:512])

        if aiogram_user:
            reply_markup = get_user_keyboard(aiogram_user.id)
            container: AsyncContainer = data[CONTAINER_KEY]
            user_service: UserService = await container.get(UserService)
            user: Optional[UserDto] = await user_service.get(telegram_id=aiogram_user.id)

            if user:
                await redirect_to_main_menu_task.kiq(aiogram_user.id)

        else:
            reply_markup = None

        await send_error_notification_task.kiq(
            error_id=user_id or error_event.update.update_id,
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    **user_data,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
                reply_markup=reply_markup,
            ),
        )

        # return await handler(event, data)
