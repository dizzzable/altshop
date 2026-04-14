from datetime import timedelta
from typing import Optional, Sequence
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis
from remnawave.enums.users import TrafficLimitStrategy

from src.core.config import AppConfig
from src.core.enums import SubscriptionStatus
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PlanDto, SubscriptionDto, UserDto
from src.infrastructure.redis import RedisRepository
from src.services.user import UserService

from .base import BaseService
from .subscription_core import (
    create as _create_impl,
)
from .subscription_core import (
    delete_subscription as _delete_subscription_impl,
)
from .subscription_core import (
    get as _get_impl,
)
from .subscription_core import (
    get_by_remna_id as _get_by_remna_id_impl,
)
from .subscription_core import (
    rebind_user as _rebind_user_impl,
)
from .subscription_core import (
    update as _update_impl,
)
from .subscription_plan_sync import get_traffic_reset_delta as _get_traffic_reset_delta_impl
from .subscription_plan_sync import sync_plan_snapshot_metadata as _sync_plan_snapshot_metadata_impl
from .subscription_queries import (
    get_all as _get_all_impl,
)
from .subscription_queries import (
    get_all_by_user as _get_all_by_user_impl,
)
from .subscription_queries import (
    get_by_ids as _get_by_ids_impl,
)
from .subscription_queries import (
    get_current as _get_current_impl,
)
from .subscription_queries import (
    get_expired_subscriptions_older_than as _get_expired_subscriptions_older_than_impl,
)
from .subscription_queries import (
    get_expired_users as _get_expired_users_impl,
)
from .subscription_queries import (
    get_subscribed_users as _get_subscribed_users_impl,
)
from .subscription_queries import (
    get_trial_users as _get_trial_users_impl,
)
from .subscription_queries import (
    get_unsubscribed_users as _get_unsubscribed_users_impl,
)
from .subscription_queries import (
    get_users_by_plan as _get_users_by_plan_impl,
)
from .subscription_queries import (
    has_any_subscription as _has_any_subscription_impl,
)
from .subscription_queries import (
    has_used_trial as _has_used_trial_impl,
)


class SubscriptionService(BaseService):
    uow: UnitOfWork
    user_service: UserService
    _CREATE_EXCLUDE_FIELDS = {
        "id",
        "user",
        "user_telegram_id",
        "traffic_used",
        "devices_count",
        "created_at",
        "updated_at",
    }
    _UPDATE_ALLOWED_FIELDS = {
        "user_telegram_id",
        "status",
        "is_trial",
        "traffic_limit",
        "device_limit",
        "internal_squads",
        "external_squad",
        "expire_at",
        "url",
        "device_type",
    }

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        user_service: UserService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.user_service = user_service

    @staticmethod
    def _deleted_status() -> SubscriptionStatus:
        return SubscriptionStatus.DELETED

    @staticmethod
    def _active_status() -> SubscriptionStatus:
        return SubscriptionStatus.ACTIVE

    @staticmethod
    def _expired_status() -> SubscriptionStatus:
        return SubscriptionStatus.EXPIRED

    async def create(
        self,
        user: UserDto,
        subscription: SubscriptionDto,
        *,
        auto_commit: bool = True,
    ) -> SubscriptionDto:
        return await _create_impl(self, user, subscription, auto_commit=auto_commit)

    async def get(self, subscription_id: int) -> Optional[SubscriptionDto]:
        return await _get_impl(self, subscription_id)

    async def get_by_remna_id(self, user_remna_id: UUID) -> Optional[SubscriptionDto]:
        return await _get_by_remna_id_impl(self, user_remna_id)

    async def get_current(self, telegram_id: int) -> Optional[SubscriptionDto]:
        return await _get_current_impl(self, telegram_id)

    async def get_all_by_user(self, telegram_id: int) -> list[SubscriptionDto]:
        return await _get_all_by_user_impl(self, telegram_id)

    async def get_all(self) -> list[SubscriptionDto]:
        return await _get_all_impl(self)

    async def get_by_ids(self, subscription_ids: Sequence[int]) -> list[SubscriptionDto]:
        return await _get_by_ids_impl(self, subscription_ids)

    async def update(
        self,
        subscription: SubscriptionDto,
        *,
        auto_commit: bool = True,
    ) -> Optional[SubscriptionDto]:
        return await _update_impl(self, subscription, auto_commit=auto_commit)

    async def rebind_user(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
        previous_user_telegram_id: int | None = None,
        auto_commit: bool = True,
    ) -> Optional[SubscriptionDto]:
        return await _rebind_user_impl(
            self,
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
            previous_user_telegram_id=previous_user_telegram_id,
            auto_commit=auto_commit,
        )

    async def sync_plan_snapshot_metadata(self, plan: PlanDto) -> int:
        return await _sync_plan_snapshot_metadata_impl(self, plan)

    async def get_subscribed_users(self) -> list[UserDto]:
        return await _get_subscribed_users_impl(self)

    async def get_users_by_plan(self, plan_id: int) -> list[UserDto]:
        return await _get_users_by_plan_impl(self, plan_id)

    async def get_unsubscribed_users(self) -> list[UserDto]:
        return await _get_unsubscribed_users_impl(self)

    async def get_expired_users(self) -> list[UserDto]:
        return await _get_expired_users_impl(self)

    async def get_trial_users(self) -> list[UserDto]:
        return await _get_trial_users_impl(self)

    async def has_any_subscription(self, user: UserDto) -> bool:
        return await _has_any_subscription_impl(self, user)

    async def has_used_trial(self, user: UserDto) -> bool:
        return await _has_used_trial_impl(self, user)

    async def get_expired_subscriptions_older_than(self, days: int) -> list[SubscriptionDto]:
        return await _get_expired_subscriptions_older_than_impl(self, days)

    async def delete_subscription(self, subscription_id: int) -> bool:
        return await _delete_subscription_impl(self, subscription_id)

    @staticmethod
    def get_traffic_reset_delta(
        strategy: TrafficLimitStrategy,
    ) -> Optional[timedelta]:
        return _get_traffic_reset_delta_impl(strategy)
