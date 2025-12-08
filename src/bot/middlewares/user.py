from typing import Any, Awaitable, Callable, Optional

from aiogram.types import TelegramObject
from aiogram.types import User as AiogramUser
from aiogram_dialog.api.internal import FakeUser
from dishka import AsyncContainer
from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.constants import CONTAINER_KEY, IS_NEW_USER, IS_SUPER_DEV_KEY, USER_KEY
from src.core.enums import MiddlewareEventType, SystemNotificationType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.referral import ReferralService
from src.services.user import UserService

from .base import EventTypedMiddleware


class UserMiddleware(EventTypedMiddleware):
    __event_types__ = [
        MiddlewareEventType.MESSAGE,
        MiddlewareEventType.CALLBACK_QUERY,
        MiddlewareEventType.ERROR,
        MiddlewareEventType.AIOGD_UPDATE,
        MiddlewareEventType.MY_CHAT_MEMBER,
        MiddlewareEventType.PRE_CHECKOUT_QUERY,
    ]

    async def middleware_logic(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        aiogram_user: Optional[AiogramUser] = self._get_aiogram_user(event)

        if aiogram_user is None or aiogram_user.is_bot:
            logger.warning("Terminating middleware: event from bot or missing user")
            return

        container: AsyncContainer = data[CONTAINER_KEY]
        notification_service: NotificationService = await container.get(NotificationService)
        config: AppConfig = await container.get(AppConfig)
        user_service: UserService = await container.get(UserService)
        referral_service: ReferralService = await container.get(ReferralService)
        user: Optional[UserDto] = await user_service.get(telegram_id=aiogram_user.id)
        is_new_user = user is None

        if user is None:
            user = await user_service.create(aiogram_user)
            referrer = await referral_service.get_referrer_by_event(event, user.telegram_id)

            base_i18n_kwargs = {
                "user_id": str(user.telegram_id),
                "user_name": user.name,
                "username": user.username or False,
            }

            if referrer:
                referrer_i18n_kwargs = {
                    "has_referrer": True,
                    "referrer_user_id": str(referrer.telegram_id),
                    "referrer_user_name": referrer.name,
                    "referrer_username": referrer.username or False,
                }
            else:
                referrer_i18n_kwargs = {"has_referrer": False}

            await notification_service.system_notify(
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-new-user",
                    i18n_kwargs={**base_i18n_kwargs, **referrer_i18n_kwargs},
                    reply_markup=get_user_keyboard(user.telegram_id),
                ),
                ntf_type=SystemNotificationType.USER_REGISTERED,
            )
        elif not isinstance(aiogram_user, FakeUser):
            await user_service.compare_and_update(user, aiogram_user)

        await user_service.update_recent_activity(telegram_id=user.telegram_id)
        data[USER_KEY] = user
        data[IS_SUPER_DEV_KEY] = user.telegram_id in config.bot.dev_id
        data[IS_NEW_USER] = is_new_user

        return await handler(event, data)
