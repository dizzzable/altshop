import re

from aiogram import Bot
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as AiogramUser
from aiogram_dialog.utils import remove_intent_id
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.bot.keyboards import CALLBACK_CHANNEL_CONFIRM, CALLBACK_RULES_ACCEPT
from src.core.config import AppConfig
from src.core.constants import PURCHASE_PREFIX, REFERRAL_PREFIX
from src.core.enums import AccessMode, Locale
from src.core.i18n.translator import safe_i18n_get
from src.core.storage.keys import AccessWaitListKey
from src.core.utils.formatters import i18n_postprocess_text
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_access_denied_notification_task,
    send_access_opened_notifications_task,
)
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.access_policy import AccessModePolicyService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.user import UserService

from .base import BaseService

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ACCESS_DENY_NOTICE_COOLDOWN_SECONDS = 10


class AccessService(BaseService):
    settings_service: SettingsService
    user_service: UserService
    referral_service: ReferralService
    access_mode_policy_service: AccessModePolicyService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        settings_service: SettingsService,
        user_service: UserService,
        referral_service: ReferralService,
        access_mode_policy_service: AccessModePolicyService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.settings_service = settings_service
        self.user_service = user_service
        self.referral_service = referral_service
        self.access_mode_policy_service = access_mode_policy_service

    async def is_access_allowed(self, aiogram_user: AiogramUser, event: TelegramObject) -> bool:
        user = await self.user_service.get(aiogram_user.id)
        mode = await self.settings_service.get_access_mode()

        if not user:
            return await self._handle_new_user_access(
                aiogram_user=aiogram_user,
                event=event,
                mode=mode,
            )

        if user.is_blocked:
            logger.info(f"Access denied for user '{user.telegram_id} '(blocked)")
            return False

        if mode == AccessMode.PUBLIC:
            logger.info(f"Access allowed for user '{user.telegram_id}' (mode: PUBLIC)")
            return True

        if user.is_privileged:
            logger.info(f"Access allowed for user '{user.telegram_id}' (privileged)")
            return True

        return await self._handle_existing_user_access(user=user, mode=mode, event=event)

    async def is_invite_locked(
        self,
        user: UserDto,
        *,
        mode: AccessMode | None = None,
    ) -> bool:
        settings = await self.settings_service.get()
        if mode is not None:
            settings.access_mode = mode
        policy = self.access_mode_policy_service.resolve(user=user, settings=settings)
        return policy.invite_locked

    async def _handle_new_user_access(
        self,
        aiogram_user: AiogramUser,
        event: TelegramObject,
        mode: AccessMode,
    ) -> bool:
        if mode == AccessMode.INVITED and await self.referral_service.is_referral_event(
            event, aiogram_user.id
        ):
            logger.info(f"Access allowed for referral event for user '{aiogram_user.id}'")
            return True

        if mode == AccessMode.INVITED:
            logger.info(f"Soft access allowed for new user '{aiogram_user.id}' (mode: INVITED)")
            return True

        if mode not in (AccessMode.REG_BLOCKED, AccessMode.RESTRICTED):
            return True

        logger.info(f"Access denied for new user '{aiogram_user.id}' (mode: {mode})")
        i18n_key = self._get_new_user_denied_i18n_key(mode)
        temp_user = UserDto(
            telegram_id=aiogram_user.id,
            name=aiogram_user.full_name,
            language=aiogram_user.language_code or Locale.EN,
        )
        await send_access_denied_notification_task.kiq(
            user=temp_user,
            i18n_key=i18n_key,
        )
        return False

    @staticmethod
    def _get_new_user_denied_i18n_key(mode: AccessMode) -> str:
        if mode == AccessMode.REG_BLOCKED:
            return "ntf-access-denied-registration"
        if mode == AccessMode.INVITED:
            return "ntf-access-denied-only-invited"
        return "ntf-access-denied"

    async def _handle_existing_user_access(
        self,
        user: UserDto,
        mode: AccessMode,
        event: TelegramObject,
    ) -> bool:
        settings = await self.settings_service.get()
        settings.access_mode = mode
        policy = self.access_mode_policy_service.resolve(user=user, settings=settings)

        if mode == AccessMode.RESTRICTED:
            logger.info(f"Access denied for user '{user.telegram_id}' (mode: RESTRICTED)")
            await self._deny_existing_user(
                user=user,
                event=event,
                i18n_key="ntf-access-denied",
            )
            return False

        if mode == AccessMode.PURCHASE_BLOCKED:
            return await self._handle_purchase_blocked_access(user=user, event=event)

        if mode == AccessMode.INVITED:
            if not policy.invite_locked:
                logger.info(
                    f"Access allowed for user '{user.telegram_id}' (mode: INVITED)"
                )
                return True

            if self._is_safe_invited_mode_event(event):
                logger.info(
                    f"Access allowed for safe invite-only event for user '{user.telegram_id}'"
                )
                return True

            logger.info(
                f"Access denied for locked invite-only user '{user.telegram_id}' "
                "(product action blocked)"
            )
            await self._deny_existing_user(
                user=user,
                event=event,
                i18n_key="ntf-access-denied-only-invited-soft",
            )
            return False

        logger.warning(f"Unknown access mode '{mode}'")
        return True

    async def _handle_purchase_blocked_access(self, user: UserDto, event: TelegramObject) -> bool:
        if not self._is_purchase_action(event):
            logger.info(
                f"Access allowed for user '{user.telegram_id}' (mode: PURCHASE_BLOCKED)"
            )
            return True

        logger.info(f"Access denied for user '{user.telegram_id}' (purchase event)")
        await self._deny_existing_user(
            user=user,
            event=event,
            i18n_key="ntf-access-denied-purchasing",
        )

        if await self._can_add_to_waitlist(user.telegram_id):
            await self.add_user_to_waitlist(user.telegram_id)

        return False

    async def get_available_modes(self) -> list[AccessMode]:
        current = await self.settings_service.get_access_mode()
        available = [mode for mode in AccessMode if mode != current]
        logger.debug(f"Available access modes (excluding current '{current}'): {available}")
        return available

    async def set_mode(self, mode: AccessMode) -> None:
        await self.settings_service.set_access_mode(mode)
        logger.info(f"Access mode changed to '{mode}'")

        if mode in (AccessMode.PUBLIC, AccessMode.INVITED):
            waiting_users = await self.get_all_waiting_users()

            if waiting_users:
                logger.info(f"Notifying '{len(waiting_users)}' waiting users about access opening")
                await send_access_opened_notifications_task.kiq(waiting_users)

        await self._refresh_recent_non_privileged_users_main_menu()
        await self.clear_all_waiting_users()

    async def _refresh_recent_non_privileged_users_main_menu(self) -> int:
        recent_users = await self.user_service.get_recent_activity_users()
        redirected = 0
        seen_ids: set[int] = set()

        for user in recent_users:
            if user.telegram_id in seen_ids:
                continue
            seen_ids.add(user.telegram_id)

            if user.is_privileged or user.is_blocked:
                continue

            await redirect_to_main_menu_task.kiq(user.telegram_id)
            redirected += 1

        logger.info(f"Refreshed main menu for '{redirected}' recent non-privileged user(s)")
        return redirected

    async def _deny_existing_user(
        self,
        *,
        user: UserDto,
        event: TelegramObject,
        i18n_key: str,
    ) -> None:
        if isinstance(event, CallbackQuery):
            await self._answer_callback_denied(user=user, callback=event, i18n_key=i18n_key)
            return

        if not await self._should_send_denied_notice(user.telegram_id, i18n_key):
            logger.debug(
                "Skipped duplicate access-denied notice for '{}' and key '{}'",
                user.telegram_id,
                i18n_key,
            )
            return

        await send_access_denied_notification_task.kiq(user=user, i18n_key=i18n_key)

    async def _answer_callback_denied(
        self,
        *,
        user: UserDto,
        callback: CallbackQuery,
        i18n_key: str,
    ) -> None:
        try:
            text = self._render_plain_i18n(locale=user.language, i18n_key=i18n_key)
            await callback.answer(text=text[:180], show_alert=True)
        except Exception as exc:
            logger.debug(
                "Failed to answer access-denied callback for '{}': {}",
                user.telegram_id,
                exc,
            )

    async def _should_send_denied_notice(self, telegram_id: int, i18n_key: str) -> bool:
        cooldown_key = f"access_deny_notice:{telegram_id}:{i18n_key}"
        try:
            result = await self.redis_client.set(
                cooldown_key,
                "1",
                ex=_ACCESS_DENY_NOTICE_COOLDOWN_SECONDS,
                nx=True,
            )
        except Exception as exc:
            logger.warning(
                "Failed to set access-deny cooldown for '{}': {}",
                telegram_id,
                exc,
            )
            return True

        return bool(result)

    def _render_plain_i18n(self, *, locale: Locale, i18n_key: str) -> str:
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        raw_text = i18n_postprocess_text(safe_i18n_get(i18n, i18n_key))
        plain_text = _HTML_TAG_RE.sub("", raw_text)
        return " ".join(plain_text.split())

    async def add_user_to_waitlist(self, telegram_id: int) -> bool:
        added_count = await self.redis_repository.collection_add(AccessWaitListKey(), telegram_id)

        if added_count > 0:
            logger.info(f"User '{telegram_id}' added to access waitlist")
            return True

        logger.debug(f"User '{telegram_id}' already in access waitlist")
        return False

    async def remove_user_from_waitlist(self, telegram_id: int) -> bool:
        removed_count = await self.redis_repository.collection_remove(
            AccessWaitListKey(),
            telegram_id,
        )

        if removed_count > 0:
            logger.info(f"User '{telegram_id}' removed from access waitlist")
            return True

        logger.debug(f"User '{telegram_id}' not found in access waitlist")
        return False

    async def get_all_waiting_users(self) -> list[int]:
        members_str = await self.redis_repository.collection_members(key=AccessWaitListKey())
        users = [int(member) for member in members_str]
        logger.debug(f"Retrieved '{len(users)}' users from access waitlist")
        return users

    async def clear_all_waiting_users(self) -> None:
        await self.redis_repository.delete(key=AccessWaitListKey())
        logger.info("Access waitlist completely cleared")

    async def _can_add_to_waitlist(self, telegram_id: int) -> bool:
        is_member = await self.redis_repository.collection_is_member(
            key=AccessWaitListKey(),
            value=telegram_id,
        )

        if is_member:
            logger.debug(f"User '{telegram_id}' already in access waitlist")
            return False

        logger.debug(f"User '{telegram_id}' can be added to access waitlist")
        return True

    def _is_purchase_action(self, event: TelegramObject) -> bool:
        if not isinstance(event, CallbackQuery) or not event.data:
            return False

        callback_data = remove_intent_id(event.data)
        if callback_data[-1].startswith(PURCHASE_PREFIX):
            logger.debug(f"Detected purchase action: {callback_data}")
            return True

        return False

    @staticmethod
    def _is_safe_invited_mode_event(event: TelegramObject) -> bool:
        if isinstance(event, Message):
            text = (event.text or "").strip()
            if not text:
                return False

            return text.startswith("/start") or text.startswith(f"/start {REFERRAL_PREFIX}")

        if isinstance(event, CallbackQuery):
            callback_data = remove_intent_id(event.data or "")
            if not callback_data:
                return False

            return callback_data[-1] in {CALLBACK_RULES_ACCEPT, CALLBACK_CHANNEL_CONFIRM}

        return False
