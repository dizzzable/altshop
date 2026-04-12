from dataclasses import dataclass

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis
from remnawave import RemnawaveSDK

from src.core.config import AppConfig
from src.infrastructure.redis import RedisRepository
from src.services.plan import PlanService
from src.services.remnawave_client import RemnawaveClientMixin
from src.services.remnawave_events import RemnawaveEventsMixin
from src.services.remnawave_fetch import RemnawaveFetchMixin
from src.services.remnawave_sync import RemnawaveSyncMixin
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .base import BaseService


@dataclass(slots=True)
class PanelSyncStats:
    user_created: bool = False
    subscriptions_created: int = 0
    subscriptions_updated: int = 0
    errors: int = 0


class RemnawaveService(
    RemnawaveEventsMixin,
    RemnawaveSyncMixin,
    RemnawaveFetchMixin,
    RemnawaveClientMixin,
    BaseService,
):
    remnawave: RemnawaveSDK
    user_service: UserService
    subscription_service: SubscriptionService
    plan_service: PlanService
    settings_service: SettingsService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        *,
        remnawave: RemnawaveSDK,
        user_service: UserService,
        subscription_service: SubscriptionService,
        plan_service: PlanService,
        settings_service: SettingsService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.remnawave = remnawave
        self.user_service = user_service
        self.subscription_service = subscription_service
        self.plan_service = plan_service
        self.settings_service = settings_service
