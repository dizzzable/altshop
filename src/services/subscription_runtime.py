from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable, Sequence
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from pydantic import BaseModel, model_validator
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import SubscriptionDto
from src.infrastructure.redis import RedisRepository
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService

from . import subscription_runtime_cache as _cache_impl
from . import subscription_runtime_refresh as _refresh_impl
from .base import BaseService

SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS = 60
SUBSCRIPTION_RUNTIME_REFRESH_LOCK_TTL_SECONDS = 30
SUBSCRIPTION_RUNTIME_REFRESH_CONCURRENCY = 5
SubscriptionRuntimeRefreshEnqueuer = Callable[[list[int]], Awaitable[None]]


class SubscriptionRuntimeSnapshot(BaseModel):
    user_remna_id: UUID
    traffic_used: int = 0
    traffic_limit: int
    device_limit: int
    devices_count: int = 0
    url: str = ""
    refreshed_at: datetime
    core_refreshed_at: datetime | None = None
    devices_refreshed_at: datetime | None = None

    @model_validator(mode="after")
    def _normalize_refresh_timestamps(self) -> "SubscriptionRuntimeSnapshot":
        if self.core_refreshed_at is None:
            self.core_refreshed_at = self.refreshed_at
        if self.devices_refreshed_at is None:
            self.devices_refreshed_at = self.core_refreshed_at
        return self


class SubscriptionRuntimeService(BaseService):
    subscription_service: SubscriptionService
    remnawave_service: RemnawaveService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        subscription_service: SubscriptionService,
        remnawave_service: RemnawaveService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.subscription_service = subscription_service
        self.remnawave_service = remnawave_service

    @staticmethod
    def _runtime_snapshot_type() -> type[SubscriptionRuntimeSnapshot]:
        return SubscriptionRuntimeSnapshot

    @staticmethod
    def _runtime_snapshot(
        *,
        user_remna_id: UUID,
        traffic_used: int,
        traffic_limit: int,
        device_limit: int,
        devices_count: int,
        url: str,
        refreshed_at: datetime,
        core_refreshed_at: datetime | None = None,
        devices_refreshed_at: datetime | None = None,
    ) -> SubscriptionRuntimeSnapshot:
        return SubscriptionRuntimeSnapshot(
            user_remna_id=user_remna_id,
            traffic_used=traffic_used,
            traffic_limit=traffic_limit,
            device_limit=device_limit,
            devices_count=devices_count,
            url=url,
            refreshed_at=refreshed_at,
            core_refreshed_at=core_refreshed_at,
            devices_refreshed_at=devices_refreshed_at,
        )

    @staticmethod
    def _runtime_cache_ttl_seconds() -> int:
        return SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS

    @staticmethod
    def _refresh_lock_ttl_seconds() -> int:
        return SUBSCRIPTION_RUNTIME_REFRESH_LOCK_TTL_SECONDS

    @staticmethod
    def _refresh_concurrency() -> int:
        return SUBSCRIPTION_RUNTIME_REFRESH_CONCURRENCY

    @staticmethod
    def _now() -> datetime:
        return datetime_now()

    async def get_cached_runtime(
        self,
        user_remna_id: UUID,
    ) -> SubscriptionRuntimeSnapshot | None:
        return await _cache_impl.get_cached_runtime(self, user_remna_id)

    async def apply_observed_devices_count_to_cached_runtime(
        self,
        *,
        user_remna_id: UUID,
        devices_count: int,
    ) -> bool:
        return await _cache_impl.apply_observed_devices_count_to_cached_runtime(
            self,
            user_remna_id=user_remna_id,
            devices_count=devices_count,
        )

    @staticmethod
    def is_fresh(snapshot: SubscriptionRuntimeSnapshot) -> bool:
        return _cache_impl.is_fresh(
            snapshot,
            ttl_seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS,
        )

    @staticmethod
    def is_core_fresh(snapshot: SubscriptionRuntimeSnapshot) -> bool:
        return _cache_impl.is_core_fresh(
            snapshot,
            ttl_seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS,
        )

    @staticmethod
    def is_devices_fresh(snapshot: SubscriptionRuntimeSnapshot) -> bool:
        return _cache_impl.is_devices_fresh(
            snapshot,
            ttl_seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS,
        )

    @staticmethod
    def apply_runtime_snapshot(
        subscription: SubscriptionDto,
        snapshot: SubscriptionRuntimeSnapshot,
    ) -> SubscriptionDto:
        return _cache_impl.apply_runtime_snapshot(subscription, snapshot)

    async def apply_device_event_to_cached_runtime(
        self,
        *,
        user_remna_id: UUID,
        event: str,
    ) -> bool:
        return await _cache_impl.apply_device_event_to_cached_runtime(
            self,
            user_remna_id=user_remna_id,
            event=event,
        )

    @staticmethod
    def _resolve_devices_count_after_event(
        devices_count: int,
        event: str,
    ) -> int | None:
        return _cache_impl.resolve_devices_count_after_event(devices_count, event)

    async def prepare_for_list(
        self,
        subscription: SubscriptionDto,
    ) -> tuple[SubscriptionDto, bool]:
        return await _refresh_impl.prepare_for_list(self, subscription)

    async def prepare_for_list_batch(
        self,
        subscriptions: Sequence[SubscriptionDto],
        *,
        user_telegram_id: int,
        enqueue_runtime_refresh: SubscriptionRuntimeRefreshEnqueuer,
    ) -> list[SubscriptionDto]:
        return await _refresh_impl.prepare_for_list_batch(
            self,
            subscriptions,
            user_telegram_id=user_telegram_id,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )

    async def prepare_for_detail(self, subscription: SubscriptionDto) -> SubscriptionDto:
        return await _refresh_impl.prepare_for_detail(self, subscription)

    async def acquire_refresh_lock(self, user_telegram_id: int) -> bool:
        return await _refresh_impl.acquire_refresh_lock(self, user_telegram_id)

    async def _enqueue_runtime_refresh_if_needed(
        self,
        *,
        user_telegram_id: int,
        subscription_ids: Sequence[int],
        enqueue_runtime_refresh: SubscriptionRuntimeRefreshEnqueuer,
    ) -> None:
        await _refresh_impl.enqueue_runtime_refresh_if_needed(
            self,
            user_telegram_id=user_telegram_id,
            subscription_ids=subscription_ids,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )

    async def refresh_user_subscriptions_runtime(self, subscription_ids: Sequence[int]) -> None:
        await _refresh_impl.refresh_user_subscriptions_runtime(self, subscription_ids)

    async def refresh_subscription_runtime_snapshot(self, subscription_id: int) -> None:
        await _refresh_impl.refresh_subscription_runtime_snapshot(self, subscription_id)

    async def _refresh_runtime_snapshots_for_user(
        self,
        subscriptions: Sequence[SubscriptionDto],
    ) -> None:
        await _refresh_impl.refresh_runtime_snapshots_for_user(self, subscriptions)

    async def _get_prefetched_remna_users_by_uuid(
        self,
        user_telegram_id: int,
    ) -> dict[UUID, object]:
        return await _refresh_impl.get_prefetched_remna_users_by_uuid(self, user_telegram_id)

    async def _refresh_runtime_snapshot_for_subscription(
        self,
        subscription: SubscriptionDto,
        *,
        remna_user: object | None = None,
    ) -> SubscriptionRuntimeSnapshot | None:
        return await _refresh_impl.refresh_runtime_snapshot_for_subscription(
            self,
            subscription,
            remna_user=remna_user,
        )

    async def _store_runtime_snapshot(
        self,
        snapshot: SubscriptionRuntimeSnapshot,
        *,
        preserve_existing_ttl: bool = False,
    ) -> None:
        await _cache_impl.store_runtime_snapshot(
            self,
            snapshot,
            preserve_existing_ttl=preserve_existing_ttl,
        )

    def _build_snapshot(
        self,
        *,
        subscription: SubscriptionDto,
        remna_user: object,
        devices_count: int,
    ) -> SubscriptionRuntimeSnapshot:
        return _refresh_impl.build_snapshot(
            self,
            subscription=subscription,
            remna_user=remna_user,
            devices_count=devices_count,
        )

    @staticmethod
    def _resolve_traffic_limit(subscription: SubscriptionDto, remna_user: object) -> int:
        return _refresh_impl.resolve_traffic_limit(subscription, remna_user)

    @staticmethod
    def _resolve_device_limit(subscription: SubscriptionDto, remna_user: object) -> int:
        return _refresh_impl.resolve_device_limit(subscription, remna_user)

    async def _persist_url_if_changed(
        self,
        subscription: SubscriptionDto,
        runtime_url: str,
    ) -> None:
        await _refresh_impl.persist_url_if_changed(self, subscription, runtime_url)
