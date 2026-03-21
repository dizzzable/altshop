import asyncio
from typing import Any, Optional, cast

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.__version__ import __version__
from src.bot.keyboards import get_remnashop_keyboard
from src.bot.states import Notification
from src.core.config import AppConfig
from src.core.enums import (
    Locale,
    MessageEffect,
    SystemNotificationType,
    UserNotificationType,
    UserRole,
)
from src.core.i18n.translator import get_translated_kwargs, safe_i18n_get
from src.core.utils.formatters import i18n_postprocess_text
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import AnyKeyboard
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.redis.repository import RedisRepository
from src.services.settings import SettingsService
from src.services.user_notification_event import UserNotificationEventService

from .base import BaseService
from .user import UserService


class NotificationService(BaseService):
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

    async def notify_user(
        self,
        user: Optional[BaseUserDto],
        payload: MessagePayload,
        ntf_type: Optional[UserNotificationType] = None,
    ) -> Optional[Message]:
        if not user:
            logger.warning("Skipping user notification: user object is empty")
            return None

        if ntf_type and not await self.settings_service.is_notification_enabled(ntf_type):
            logger.debug(
                f"Skipping user notification for '{user.telegram_id}': "
                f"notification type is disabled in settings"
            )
            return None

        logger.debug(
            f"Attempting to send user notification '{payload.i18n_key}' to '{user.telegram_id}'"
        )

        close_notification_id: Optional[int] = None
        if ntf_type:
            try:
                rendered_text = self._get_translated_text(
                    locale=user.language,
                    i18n_key=payload.i18n_key,
                    i18n_kwargs=payload.i18n_kwargs,
                )
                event = await self.user_notification_event_service.create_event(
                    user_telegram_id=user.telegram_id,
                    ntf_type=ntf_type,
                    i18n_key=payload.i18n_key,
                    i18n_kwargs=payload.i18n_kwargs,
                    rendered_text=rendered_text,
                )
                close_notification_id = event.id
            except Exception as exception:
                logger.error(
                    f"Failed to create notification event for user "
                    f"'{user.telegram_id}': {exception}",
                    exc_info=True,
                )

        sent_message = await self._send_message(
            user,
            payload,
            close_notification_id=close_notification_id,
        )

        if sent_message and close_notification_id is not None:
            try:
                await self.user_notification_event_service.set_bot_delivery_meta(
                    notification_id=close_notification_id,
                    bot_chat_id=user.telegram_id,
                    bot_message_id=sent_message.message_id,
                )
            except Exception as exception:
                logger.error(
                    f"Failed to save delivery meta for notification "
                    f"'{close_notification_id}': {exception}",
                    exc_info=True,
                )

        return sent_message

    async def system_notify(
        self,
        payload: MessagePayload,
        ntf_type: SystemNotificationType,
    ) -> list[bool]:
        devs = await self.user_service.get_by_role(role=UserRole.DEV)

        if not devs:
            devs = [self._get_temp_dev()]

        if not await self.settings_service.is_notification_enabled(ntf_type):
            logger.debug("Skipping system notification: notification type is disabled in settings")
            return []

        logger.debug(
            f"Attempting to send system notification '{payload.i18n_key}' to '{len(devs)}' devs"
        )

        async def send_to_dev(dev: UserDto) -> bool:
            return bool(await self._send_message(user=dev, payload=payload))

        tasks = [send_to_dev(dev) for dev in devs]
        results = await asyncio.gather(*tasks)

        return cast(list[bool], results)

    async def notify_super_dev(self, payload: MessagePayload) -> bool:
        dev = await self.user_service.get(telegram_id=self.config.bot.dev_id[0])

        if not dev:
            dev = self._get_temp_dev()

        logger.debug(
            f"Attempting to send super dev notification '{payload.i18n_key}' to '{dev.telegram_id}'"
        )

        return bool(await self._send_message(user=dev, payload=payload))

    async def remnashop_notify(self) -> bool:
        dev = await self.user_service.get(self.config.bot.dev_id[0]) or self._get_temp_dev()
        payload = MessagePayload(
            i18n_key="ntf-remnashop-info",
            i18n_kwargs={"version": __version__},
            reply_markup=get_remnashop_keyboard(),
            auto_delete_after=None,
            add_close_button=True,
            message_effect=MessageEffect.LOVE,
        )
        return bool(await self._send_message(user=dev, payload=payload))

    #

    async def _send_message(
        self,
        user: BaseUserDto,
        payload: MessagePayload,
        close_notification_id: Optional[int] = None,
    ) -> Optional[Message]:
        try:
            reply_markup = self._prepare_reply_markup(
                payload.reply_markup,
                payload.add_close_button,
                payload.auto_delete_after,
                user.language,
                user.telegram_id,
                close_notification_id,
            )

            if (payload.media or payload.media_id) and payload.media_type:
                sent_message = await self._send_media_message(user, payload, reply_markup)
            else:
                if (payload.media or payload.media_id) and not payload.media_type:
                    logger.warning(
                        f"Validation warning: Media provided without media_type "
                        f"for chat '{user.telegram_id}'. Sending as text message"
                    )
                sent_message = await self._send_text_message(user, payload, reply_markup)

            if payload.auto_delete_after is not None and sent_message:
                asyncio.create_task(
                    self._schedule_message_deletion(
                        chat_id=user.telegram_id,
                        message_id=sent_message.message_id,
                        delay=payload.auto_delete_after,
                    )
                )

            return sent_message

        except Exception as exception:
            logger.error(
                f"Failed to send notification '{payload.i18n_key}' "
                f"to '{user.telegram_id}': {exception}",
                exc_info=True,
            )
            return None

    async def _send_media_message(
        self,
        user: BaseUserDto,
        payload: MessagePayload,
        reply_markup: Optional[AnyKeyboard],
    ) -> Message:
        message_text = self._get_translated_text(
            locale=user.language,
            i18n_key=payload.i18n_key,
            i18n_kwargs=payload.i18n_kwargs,
        )

        assert payload.media_type
        send_func = payload.media_type.get_function(self.bot)
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

    async def _send_text_message(
        self,
        user: BaseUserDto,
        payload: MessagePayload,
        reply_markup: Optional[AnyKeyboard],
    ) -> Message:
        message_text = self._get_translated_text(
            locale=user.language,
            i18n_key=payload.i18n_key,
            i18n_kwargs=payload.i18n_kwargs,
        )

        return await self.bot.send_message(
            chat_id=user.telegram_id,
            text=message_text,
            message_effect_id=payload.message_effect,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )

    def _prepare_reply_markup(
        self,
        reply_markup: Optional[AnyKeyboard],
        add_close_button: bool,
        auto_delete_after: Optional[int],
        locale: Locale,
        chat_id: int,
        close_notification_id: Optional[int] = None,
    ) -> Optional[AnyKeyboard]:
        if reply_markup is None:
            if add_close_button and auto_delete_after is None:
                close_button = self._get_close_notification_button(
                    locale=locale,
                    close_notification_id=close_notification_id,
                )
                return self._get_close_notification_keyboard(close_button)
            return None

        if not add_close_button or auto_delete_after is not None:
            return self._translate_keyboard_texts(reply_markup, locale)

        close_button = self._get_close_notification_button(
            locale=locale,
            close_notification_id=close_notification_id,
        )

        if isinstance(reply_markup, InlineKeyboardMarkup):
            translated_markup = self._translate_keyboard_texts(reply_markup, locale)
            translated_markup = cast(InlineKeyboardMarkup, translated_markup)
            builder = InlineKeyboardBuilder.from_markup(translated_markup)
            builder.row(close_button)
            return builder.as_markup()

        if isinstance(reply_markup, ReplyKeyboardMarkup):
            return self._translate_keyboard_texts(reply_markup, locale)

        logger.warning(
            f"Unsupported reply_markup type '{type(reply_markup).__name__}' "
            f"for chat '{chat_id}'. Close button will not be added"
        )
        return reply_markup

    def _get_close_notification_button(
        self,
        locale: Locale,
        close_notification_id: Optional[int] = None,
    ) -> InlineKeyboardButton:
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        button_text = i18n.get("btn-notification-close")
        callback_data = Notification.CLOSE.state
        if close_notification_id is not None:
            callback_data = f"{Notification.CLOSE.state}:{close_notification_id}"
        return InlineKeyboardButton(text=button_text, callback_data=callback_data)

    def _get_close_notification_keyboard(
        self,
        button: InlineKeyboardButton,
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(button)
        return builder.as_markup()

    async def _schedule_message_deletion(self, chat_id: int, message_id: int, delay: int) -> None:
        logger.debug(
            f"Scheduling message '{message_id}' for auto-deletion in '{delay}' (chat '{chat_id}')"
        )
        try:
            await asyncio.sleep(delay)
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug(
                f"Message '{message_id}' in chat '{chat_id}' deleted after '{delay}' seconds"
            )
        except Exception as exception:
            logger.error(
                f"Failed to delete message '{message_id}' in chat '{chat_id}': {exception}"
            )

    def _get_translated_text(
        self,
        locale: Locale,
        i18n_key: str,
        i18n_kwargs: dict[str, Any] = {},
    ) -> str:
        if not i18n_key:
            return i18n_key

        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        kwargs = get_translated_kwargs(i18n, i18n_kwargs)
        return i18n_postprocess_text(safe_i18n_get(i18n, i18n_key, **kwargs))

    def _translate_keyboard_texts(self, keyboard: AnyKeyboard, locale: Locale) -> AnyKeyboard:
        if isinstance(keyboard, InlineKeyboardMarkup):
            return self._translate_inline_keyboard(keyboard, locale)

        if isinstance(keyboard, ReplyKeyboardMarkup):
            return self._translate_reply_keyboard(keyboard, locale)

        return keyboard

    def _translate_inline_keyboard(
        self, keyboard: InlineKeyboardMarkup, locale: Locale
    ) -> InlineKeyboardMarkup:
        new_inline_keyboard = []
        for row_inline in keyboard.inline_keyboard:
            new_row_inline = []
            for button_inline in row_inline:
                button_inline.text = self._translate_button_text(locale, button_inline.text)
                new_row_inline.append(button_inline)
            new_inline_keyboard.append(new_row_inline)
        return InlineKeyboardMarkup(inline_keyboard=new_inline_keyboard)

    def _translate_reply_keyboard(
        self, keyboard: ReplyKeyboardMarkup, locale: Locale
    ) -> ReplyKeyboardMarkup:
        new_keyboard = []
        for row in keyboard.keyboard:
            new_row = []
            for button in row:
                button.text = self._translate_button_text(locale, button.text)
                new_row.append(button)
            new_keyboard.append(new_row)

        return ReplyKeyboardMarkup(
            keyboard=new_keyboard,
            **keyboard.model_dump(exclude={"keyboard"}),
        )

    def _translate_button_text(self, locale: Locale, text: Optional[str]) -> str:
        if not text:
            return ""

        try:
            return self._get_translated_text(locale, text)
        except Exception:
            return text

    def _get_temp_dev(self) -> UserDto:
        temp_dev = UserDto(
            telegram_id=self.config.bot.dev_id[0],
            name="TempDev",
            role=UserRole.DEV,
        )

        logger.warning("Fallback to temporary dev user from environment for notifications")
        return temp_dev
