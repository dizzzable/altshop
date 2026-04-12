import traceback
from typing import Any, Awaitable, Callable, Optional, cast

from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import CallbackQuery, ErrorEvent, TelegramObject
from aiogram.types import User as AiogramUser
from aiogram.utils.formatting import Text
from aiogram_dialog.api.exceptions import (
    InvalidStackIdError,
    OutdatedIntent,
    UnknownIntent,
    UnknownState,
)
from dishka import AsyncContainer

from src.bot.keyboards import get_user_keyboard
from src.core.constants import CONTAINER_KEY
from src.core.enums import Locale, MiddlewareEventType
from src.core.utils.message_payload import MessagePayload
from src.core.utils.system_events import build_system_event_payload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.notification import NotificationService
from src.services.user import UserService

from .base import EventTypedMiddleware


class ErrorMiddleware(EventTypedMiddleware):
    __event_types__ = [MiddlewareEventType.ERROR]

    @staticmethod
    def _get_lost_context_callback_text(locale: Optional[Locale]) -> str:
        if locale == Locale.EN:
            return "⚠️ An error occurred. Dialog restarted."
        return "⚠️ Произошла ошибка. Диалог перезапущен."

    @staticmethod
    def _is_blocked_bot_exception(exception: Exception) -> bool:
        return isinstance(exception, TelegramForbiddenError) and (
            "blocked by the user" in str(exception).lower()
        )

    async def _handle_lost_context_callback(
        self, callback: CallbackQuery, user: Optional[UserDto]
    ) -> None:
        locale: Optional[Locale] = user.language if user else None
        text = self._get_lost_context_callback_text(locale)

        try:
            # Acknowledge callback_query to stop Telegram loading spinner
            await callback.answer(text=text)
        except Exception:
            pass

        try:
            # Best-effort: remove stale inline keyboard to prevent repeated clicks
            if callback.message is not None and hasattr(callback.message, "edit_reply_markup"):
                await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

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

        error_event = cast(ErrorEvent, event)
        exception = error_event.exception
        is_lost_context = isinstance(
            exception,
            (UnknownIntent, UnknownState, OutdatedIntent, InvalidStackIdError),
        )

        container: Optional[AsyncContainer] = data.get(CONTAINER_KEY)
        if container is None:
            # If DI container is missing, we can't notify/redirect safely.
            # Still mark the error as handled to avoid propagating exception further.
            return True

        user_id = user_data.get("user_id")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        user: Optional[UserDto] = None
        user_service: Optional[UserService] = None
        if aiogram_user:
            user_service = await container.get(UserService)
            user = await user_service.get(telegram_id=aiogram_user.id)

        if self._is_blocked_bot_exception(exception):
            if user and user_service and not user.is_bot_blocked:
                await user_service.set_bot_blocked(user=user, blocked=True)
            return True

        if is_lost_context:
            if error_event.update.callback_query:
                await self._handle_lost_context_callback(error_event.update.callback_query, user)

            if user:
                notification_service: NotificationService = await container.get(NotificationService)
                await notification_service.notify_user(
                    user=user,
                    payload=MessagePayload(i18n_key="ntf-error-lost-context"),
                )
                await redirect_to_main_menu_task.kiq(user.telegram_id)

            # Do not send dev error notifications for expected dialog context errors.
            return True

        if aiogram_user:
            reply_markup = get_user_keyboard(aiogram_user.id)
            if user:
                await redirect_to_main_menu_task.kiq(aiogram_user.id)

        else:
            reply_markup = None

        await send_error_notification_task.kiq(
            error_id=user_id or error_event.update.update_id,
            traceback_str=traceback_str,
            payload=build_system_event_payload(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    **user_data,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
                severity="ERROR",
                event_source="bot.middleware.error",
                entry_surface="BOT",
                operation="update_dispatch",
                impact="A user-triggered bot update failed before the flow could complete.",
                operator_hint=(
                    "Inspect the attached traceback and replay the last bot action for this user."
                ),
                reply_markup=reply_markup,
            ),
        )

        # Mark as handled to prevent bubbling original exception and spamming logs.
        return True
