from typing import Any

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import TIME_10M
from src.core.enums import AccessMode, Currency, SystemNotificationType, UserNotificationType
from src.core.storage.key_builder import build_key
from src.core.utils.types import AnyNotification
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PartnerSettingsDto, ReferralSettingsDto, SettingsDto, UserDto
from src.infrastructure.database.models.dto.settings import MultiSubscriptionSettingsDto
from src.infrastructure.database.models.sql import Settings
from src.infrastructure.redis import RedisRepository
from src.infrastructure.redis.cache import redis_cache

from .base import BaseService


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
        return SettingsDto.from_model(db_settings)  # type: ignore[return-value]

    @redis_cache(prefix="get_settings", ttl=TIME_10M)
    async def get(self) -> SettingsDto:
        db_settings = await self.uow.repository.settings.get()
        if not db_settings:
            return await self.create()
        else:
            logger.debug("Retrieved settings from DB")

        return SettingsDto.from_model(db_settings)  # type: ignore[return-value]

    async def update(self, settings: SettingsDto) -> SettingsDto:
        if settings.user_notifications.changed_data:
            settings.user_notifications = settings.user_notifications  # FIXME: Fix this shit

        if settings.system_notifications.changed_data:
            settings.system_notifications = settings.system_notifications

        if settings.referral.changed_data or settings.referral.reward:
            settings.referral = settings.referral

        if settings.partner.changed_data:
            settings.partner = settings.partner

        if settings.multi_subscription.changed_data:
            settings.multi_subscription = settings.multi_subscription

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
        settings.access_mode = mode
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

    async def is_multi_subscription_enabled(self) -> bool:
        """Проверить, включены ли мультиподписки глобально."""
        settings = await self.get()
        return settings.multi_subscription.enabled

    async def get_max_subscriptions_for_user(self, user: UserDto) -> int:
        """
        Получить максимальное количество подписок для пользователя.
        
        Приоритет:
        1. Индивидуальная настройка пользователя (если установлена)
        2. Глобальная настройка из settings
        
        Возвращает:
        - -1 = безлимитно
        - >0 = конкретный лимит
        """
        # Если у пользователя установлен индивидуальный лимит
        if user.max_subscriptions is not None:
            if user.max_subscriptions == -1:
                logger.debug(f"User '{user.telegram_id}' has unlimited subscriptions (individual setting)")
                return -1
            logger.debug(f"User '{user.telegram_id}' has individual limit: {user.max_subscriptions}")
            return user.max_subscriptions
        
        # Иначе используем глобальную настройку
        settings = await self.get()
        
        if not settings.multi_subscription.enabled:
            # Мультиподписки отключены - только 1 подписка
            logger.debug(f"Multi-subscription disabled, user '{user.telegram_id}' limited to 1")
            return 1
        
        logger.debug(
            f"User '{user.telegram_id}' uses global limit: "
            f"{settings.multi_subscription.default_max_subscriptions}"
        )
        return settings.multi_subscription.default_max_subscriptions

    #

    async def _clear_cache(self) -> None:
        settings_cache_key: str = build_key("cache", "get_settings")
        logger.debug(f"Cache '{settings_cache_key}' cleared")
        await self.redis_client.delete(settings_cache_key)
