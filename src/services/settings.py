from typing import Any, cast

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import MAX_SUBSCRIPTIONS_PER_USER, TIME_10M
from src.core.enums import (
    AccessMode,
    Currency,
    Locale,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.storage.key_builder import build_key
from src.core.utils.branding import (
    render_template as render_branding_template,
)
from src.core.utils.branding import (
    resolve_branding_locale as resolve_branding_locale_value,
)
from src.core.utils.branding import (
    resolve_localized_text as resolve_localized_branding_text,
)
from src.core.utils.time import datetime_now
from src.core.utils.types import AnyNotification
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    BotMenuSettingsDto,
    BrandingSettingsDto,
    LocalizedTextDto,
    PartnerSettingsDto,
    ReferralSettingsDto,
    SettingsDto,
    UserDto,
)
from src.infrastructure.database.models.dto.settings import MultiSubscriptionSettingsDto
from src.infrastructure.database.models.sql import Settings
from src.infrastructure.redis import RedisRepository
from src.infrastructure.redis.cache import redis_cache

from .base import BaseService
from .settings_helpers import (
    normalize_settings_for_update,
    resolve_effective_max_subscriptions,
    resolve_partner_balance_currency,
)


class SettingsService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    async def create(self) -> SettingsDto:
        settings = SettingsDto()
        db_settings = Settings(**settings.prepare_init_data())
        db_settings = await self.uow.repository.settings.create(db_settings)

        await self._clear_cache()
        logger.info("Default settings created in DB")
        return cast(SettingsDto, SettingsDto.from_model(db_settings))

    @redis_cache(prefix="get_settings", ttl=TIME_10M)
    async def get(self) -> SettingsDto:
        db_settings = await self.uow.repository.settings.get()
        if not db_settings:
            return await self.create()
        else:
            logger.debug("Retrieved settings from DB")

        settings = cast(SettingsDto, SettingsDto.from_model(db_settings))
        if (
            settings is not None
            and settings.access_mode == AccessMode.INVITED
            and settings.invite_mode_started_at is None
        ):
            logger.info(
                "Backfilling invite_mode_started_at for already active INVITED access mode"
            )
            db_settings = await self.uow.repository.settings.update(
                invite_mode_started_at=datetime_now()
            )
            await self._clear_cache()
            return cast(SettingsDto, SettingsDto.from_model(db_settings))

        return settings

    async def update(self, settings: SettingsDto) -> SettingsDto:
        settings = normalize_settings_for_update(settings)
        changed_data = settings.prepare_changed_data()
        db_updated_settings = await self.uow.repository.settings.update(**changed_data)
        await self._clear_cache()

        if changed_data:
            logger.info("Settings updated in DB")
        else:
            logger.warning("Settings update called, but no fields were actually changed")

        return SettingsDto.from_model(db_updated_settings)  # type: ignore[return-value]

    #

    async def is_rules_required(self) -> bool:
        settings = await self.get()
        return settings.rules_required

    async def is_channel_required(self) -> bool:
        settings = await self.get()
        return settings.channel_required

    #

    async def get_access_mode(self) -> AccessMode:
        settings = await self.get()
        mode = settings.access_mode
        logger.debug(f"Retrieved access mode '{mode}'")
        return mode

    async def set_access_mode(self, mode: AccessMode) -> None:
        settings = await self.get()
        current_mode = settings.access_mode
        settings.access_mode = mode
        if mode == AccessMode.INVITED and (
            current_mode != AccessMode.INVITED or settings.invite_mode_started_at is None
        ):
            settings.invite_mode_started_at = datetime_now()
        await self.update(settings)
        logger.debug(f"Set access mode '{mode}'")

    #

    async def get_default_currency(self) -> Currency:
        settings = await self.get()
        currency = settings.default_currency
        logger.debug(f"Retrieved default currency '{currency}'")
        return currency

    async def set_default_currency(self, currency: Currency) -> None:
        settings = await self.get()
        settings.default_currency = currency
        await self.update(settings)
        logger.debug(f"Set default currency '{currency}'")

    async def resolve_partner_balance_currency(self, user: UserDto) -> Currency:
        settings = await self.get()
        return resolve_partner_balance_currency(settings.default_currency, user)

    #

    async def toggle_notification(self, notification_type: AnyNotification) -> bool:
        settings = await self.get()
        field_name = notification_type.value.lower()

        if isinstance(notification_type, UserNotificationType):
            current_value = getattr(settings.user_notifications, field_name, False)
            setattr(settings.user_notifications, field_name, not current_value)
            new_value = not current_value
        elif isinstance(notification_type, SystemNotificationType):
            current_value = getattr(settings.system_notifications, field_name, False)
            setattr(settings.system_notifications, field_name, not current_value)
            new_value = not current_value
        else:
            raise ValueError(f"Unknown notification type: '{notification_type}'")

        await self.update(settings)
        logger.debug(f"Toggled notification '{field_name}' -> '{new_value}'")
        return new_value

    async def is_notification_enabled(self, ntf_type: AnyNotification) -> bool:
        settings = await self.get()

        if isinstance(ntf_type, UserNotificationType):
            return settings.user_notifications.is_enabled(ntf_type)
        elif isinstance(ntf_type, SystemNotificationType):
            return settings.system_notifications.is_enabled(ntf_type)
        else:
            logger.critical(f"Unknown notification type: '{ntf_type}'")
            return False

    async def list_user_notifications(self) -> list[dict[str, Any]]:
        settings = await self.get()
        return [
            {
                "type": field.upper(),
                "enabled": value,
            }
            for field, value in settings.user_notifications.model_dump().items()
        ]

    async def list_system_notifications(self) -> list[dict[str, Any]]:
        settings = await self.get()
        return [
            {
                "type": field.upper(),
                "enabled": value,
            }
            for field, value in settings.system_notifications.model_dump().items()
        ]

    #

    async def get_referral_settings(self) -> ReferralSettingsDto:
        settings = await self.get()
        return settings.referral

    async def is_referral_enable(self) -> bool:
        settings = await self.get()
        return settings.referral.enable

    #

    async def get_partner_settings(self) -> PartnerSettingsDto:
        settings = await self.get()
        return settings.partner

    async def is_partner_enabled(self) -> bool:
        settings = await self.get()
        return settings.partner.enabled

    #

    async def get_multi_subscription_settings(self) -> MultiSubscriptionSettingsDto:
        """Получить настройки мультиподписок."""
        settings = await self.get()
        return settings.multi_subscription

    async def get_bot_menu_settings(self) -> BotMenuSettingsDto:
        settings = await self.get()
        return settings.bot_menu

    async def get_branding_settings(self) -> BrandingSettingsDto:
        settings = await self.get()
        return settings.branding

    @staticmethod
    def resolve_branding_locale(language: Locale | str | None) -> str:
        return resolve_branding_locale_value(language)

    @staticmethod
    def resolve_localized_branding_text(
        localized_text: LocalizedTextDto,
        *,
        language: Locale | str | None,
    ) -> str:
        return resolve_localized_branding_text(localized_text, language=language)

    @staticmethod
    def render_branding_text(template: str, *, placeholders: dict[str, object]) -> str:
        return render_branding_template(template, placeholders)

    async def is_multi_subscription_enabled(self) -> bool:
        """Проверить, включены ли мультиподписки глобально."""
        settings = await self.get()
        return settings.multi_subscription.enabled

    async def get_max_subscriptions_for_user(self, user: UserDto) -> int:
        """
        Get effective max subscriptions limit for user.

        Priority:
        1. Individual user limit (if set)
        2. Global multi-subscription settings
        3. Hard safety ceiling (MAX_SUBSCRIPTIONS_PER_USER)
        """
        settings = await self.get()
        effective_limit = resolve_effective_max_subscriptions(
            user=user,
            multi_subscription_enabled=settings.multi_subscription.enabled,
            default_max_subscriptions=settings.multi_subscription.default_max_subscriptions,
            hard_ceiling=MAX_SUBSCRIPTIONS_PER_USER,
        )
        logger.debug(f"User '{user.telegram_id}' effective max subscriptions: {effective_limit}")
        return effective_limit

    #
    async def _clear_cache(self) -> None:
        settings_cache_key: str = build_key("cache", "get_settings")
        logger.debug(f"Cache '{settings_cache_key}' cleared")
        await self.redis_client.delete(settings_cache_key)
