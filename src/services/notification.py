from __future__ import annotations

from typing import Any, Optional, cast

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import Locale, MessageEffect, SystemNotificationType, UserNotificationType
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import AnyKeyboard
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.redis.repository import RedisRepository
from src.services.settings import SettingsService
from src.services.user_notification_event import UserNotificationEventService

from .base import BaseService
from .notification_delivery import (
    is_unreachable_chat_error as _is_unreachable_chat_error_impl,
)
from .notification_delivery import (
    mark_user_as_bot_blocked as _mark_user_as_bot_blocked_impl,
)
from .notification_delivery import (
    send_media_message as _send_media_message_impl,
)
from .notification_delivery import (
    send_message as _send_message_impl,
)
from .notification_delivery import (
    send_text_message as _send_text_message_impl,
)
from .notification_delivery import (
    truncate_telegram_text as _truncate_telegram_text_impl,
)
from .notification_entrypoints import (
    acquire_system_event_dedupe as _acquire_system_event_dedupe_impl,
)
from .notification_entrypoints import (
    get_temp_dev as _get_temp_dev_impl,
)
from .notification_entrypoints import (
    notify_super_dev as _notify_super_dev_impl,
)
from .notification_entrypoints import (
    notify_user as _notify_user_impl,
)
from .notification_entrypoints import (
    remnashop_notify as _remnashop_notify_impl,
)
from .notification_entrypoints import (
    system_notify as _system_notify_impl,
)
from .notification_scheduling import schedule_message_deletion as _schedule_message_deletion_impl
from .notification_translation import (
    get_close_notification_button as _get_close_notification_button_impl,
)
from .notification_translation import (
    get_close_notification_keyboard as _get_close_notification_keyboard_impl,
)
from .notification_translation import (
    get_translated_text as _get_translated_text_impl,
)
from .notification_translation import (
    prepare_reply_markup as _prepare_reply_markup_impl,
)
from .notification_translation import (
    translate_button_text as _translate_button_text_impl,
)
from .notification_translation import (
    translate_inline_keyboard as _translate_inline_keyboard_impl,
)
from .notification_translation import (
    translate_keyboard_texts as _translate_keyboard_texts_impl,
)
from .notification_translation import (
    translate_reply_keyboard as _translate_reply_keyboard_impl,
)
from .user import UserService


class NotificationService(BaseService):
    TELEGRAM_TEXT_LIMIT = 4096
    TELEGRAM_CAPTION_LIMIT = 1024

    user_service: UserService
    settings_service: SettingsService
    user_notification_event_service: UserNotificationEventService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        user_service: UserService,
        settings_service: SettingsService,
        user_notification_event_service: UserNotificationEventService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.user_service = user_service
        self.settings_service = settings_service
        self.user_notification_event_service = user_notification_event_service

    @staticmethod
    def _love_effect() -> MessageEffect:
        return MessageEffect.LOVE

    async def notify_user(
        self,
        user: Optional[BaseUserDto],
        payload: MessagePayload,
        ntf_type: Optional[UserNotificationType] = None,
    ) -> Optional[Message]:
        return await _notify_user_impl(self, user, payload, ntf_type)

    async def system_notify(
        self,
        payload: MessagePayload,
        ntf_type: SystemNotificationType,
    ) -> list[bool]:
        return await _system_notify_impl(self, payload, ntf_type)

    async def _acquire_system_event_dedupe(
        self,
        *,
        dedupe_key: str,
        ttl_seconds: int | None,
    ) -> bool:
        return await _acquire_system_event_dedupe_impl(
            self,
            dedupe_key=dedupe_key,
            ttl_seconds=ttl_seconds,
        )

    async def notify_super_dev(self, payload: MessagePayload) -> bool:
        return await _notify_super_dev_impl(self, payload)

    async def remnashop_notify(self) -> bool:
        return await _remnashop_notify_impl(self)

    async def _send_message(
        self,
        user: BaseUserDto,
        payload: MessagePayload,
        close_notification_id: Optional[int] = None,
    ) -> Optional[Message]:
        return await _send_message_impl(
            self,
            user,
            payload,
            close_notification_id=close_notification_id,
        )

    async def _mark_user_as_bot_blocked(self, telegram_id: int) -> None:
        await _mark_user_as_bot_blocked_impl(self, telegram_id)

    def _is_unreachable_chat_error(self, exception: Exception) -> bool:
        return _is_unreachable_chat_error_impl(self, exception)

    async def _send_media_message(
        self,
        user: BaseUserDto,
        payload: MessagePayload,
        reply_markup: Optional[AnyKeyboard],
    ) -> Message:
        return await _send_media_message_impl(self, user, payload, reply_markup)

    async def _send_text_message(
        self,
        user: BaseUserDto,
        payload: MessagePayload,
        reply_markup: Optional[AnyKeyboard],
    ) -> Message:
        return await _send_text_message_impl(self, user, payload, reply_markup)

    @staticmethod
    def _truncate_telegram_text(text: str, limit: int) -> str:
        return _truncate_telegram_text_impl(cast(Any, None), text, limit)

    def _prepare_reply_markup(
        self,
        reply_markup: Optional[AnyKeyboard],
        add_close_button: bool,
        auto_delete_after: Optional[int],
        locale: Locale,
        chat_id: int,
        close_notification_id: Optional[int] = None,
    ) -> Optional[AnyKeyboard]:
        return _prepare_reply_markup_impl(
            self,
            reply_markup,
            add_close_button,
            auto_delete_after,
            locale,
            chat_id,
            close_notification_id,
        )

    def _get_close_notification_button(
        self,
        locale: Locale,
        close_notification_id: Optional[int] = None,
    ) -> InlineKeyboardButton:
        return _get_close_notification_button_impl(
            self,
            locale,
            close_notification_id=close_notification_id,
        )

    def _get_close_notification_keyboard(
        self,
        button: InlineKeyboardButton,
    ) -> InlineKeyboardMarkup:
        return _get_close_notification_keyboard_impl(self, button)

    async def _schedule_message_deletion(self, chat_id: int, message_id: int, delay: int) -> None:
        await _schedule_message_deletion_impl(self, chat_id, message_id, delay)

    def _get_translated_text(
        self,
        locale: Locale,
        i18n_key: str,
        i18n_kwargs: dict[str, Any] = {},
    ) -> str:
        return _get_translated_text_impl(self, locale, i18n_key, i18n_kwargs)

    def _translate_keyboard_texts(self, keyboard: AnyKeyboard, locale: Locale) -> AnyKeyboard:
        return _translate_keyboard_texts_impl(self, keyboard, locale)

    def _translate_inline_keyboard(
        self,
        keyboard: InlineKeyboardMarkup,
        locale: Locale,
    ) -> InlineKeyboardMarkup:
        return _translate_inline_keyboard_impl(self, keyboard, locale)

    def _translate_reply_keyboard(
        self,
        keyboard: ReplyKeyboardMarkup,
        locale: Locale,
    ) -> ReplyKeyboardMarkup:
        return _translate_reply_keyboard_impl(self, keyboard, locale)

    def _translate_button_text(self, locale: Locale, text: Optional[str]) -> str:
        return _translate_button_text_impl(self, locale, text)

    def _get_temp_dev(self) -> UserDto:
        return _get_temp_dev_impl(self)
