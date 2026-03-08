from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Sequence
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from pydantic import BaseModel, model_validator
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import RemnaUserHwidDevicesEvent
from src.core.observability import emit_counter
from src.core.storage.keys import (
    SubscriptionRuntimeRefreshLockKey,
    SubscriptionRuntimeSnapshotKey,
)
from src.core.utils.formatters import format_bytes_to_gb, format_device_count
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import SubscriptionDto
from src.infrastructure.redis import RedisRepository
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService

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

    async def get_cached_runtime(
        self,
        user_remna_id: UUID,
    ) -> SubscriptionRuntimeSnapshot | None:
        return await self.redis_repository.get(
            SubscriptionRuntimeSnapshotKey(user_remna_id=str(user_remna_id)),
            SubscriptionRuntimeSnapshot,
            default=None,
        )

    async def apply_observed_devices_count_to_cached_runtime(
        self,
        *,
        user_remna_id: UUID,
        devices_count: int,
    ) -> bool:
        snapshot = await self.get_cached_runtime(user_remna_id)
        if snapshot is None:
            return False

        snapshot.devices_count = max(devices_count, 0)
        snapshot.devices_refreshed_at = datetime_now()
        await self._store_runtime_snapshot(snapshot, preserve_existing_ttl=True)
        emit_counter(
            "subscription_runtime_cache_mutations_total",
            scope="devices",
            event="observed_count",
        )
        return True

    @staticmethod
    def is_fresh(snapshot: SubscriptionRuntimeSnapshot) -> bool:
        return SubscriptionRuntimeService.is_core_fresh(snapshot)

    @staticmethod
    def is_core_fresh(snapshot: SubscriptionRuntimeSnapshot) -> bool:
        core_refreshed_at = snapshot.core_refreshed_at or snapshot.refreshed_at
        return datetime_now() - core_refreshed_at <= timedelta(
            seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS
        )

    @staticmethod
    def is_devices_fresh(snapshot: SubscriptionRuntimeSnapshot) -> bool:
        devices_refreshed_at = (
            snapshot.devices_refreshed_at or snapshot.core_refreshed_at or snapshot.refreshed_at
        )
        return datetime_now() - devices_refreshed_at <= timedelta(
            seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS
        )

    @staticmethod
    def apply_runtime_snapshot(
        subscription: SubscriptionDto,
        snapshot: SubscriptionRuntimeSnapshot,
    ) -> SubscriptionDto:
        subscription.traffic_used = max(snapshot.traffic_used, 0)
        subscription.traffic_limit = snapshot.traffic_limit
        subscription.device_limit = snapshot.device_limit
        subscription.devices_count = max(snapshot.devices_count, 0)
        subscription.url = snapshot.url or subscription.url
        return subscription

    async def apply_device_event_to_cached_runtime(
        self,
        *,
        user_remna_id: UUID,
        event: str,
    ) -> bool:
        snapshot = await self.get_cached_runtime(user_remna_id)
        if snapshot is None:
            return False

        next_devices_count = self._resolve_devices_count_after_event(
            snapshot.devices_count,
            event,
        )
        if next_devices_count is None:
            return False

        snapshot.devices_count = next_devices_count
        snapshot.devices_refreshed_at = datetime_now()
        await self._store_runtime_snapshot(snapshot, preserve_existing_ttl=True)
        emit_counter("subscription_runtime_cache_mutations_total", scope="devices", event=event)
        return True

    @staticmethod
    def _resolve_devices_count_after_event(
        devices_count: int,
        event: str,
    ) -> int | None:
        try:
            normalized_event = RemnaUserHwidDevicesEvent(event)
        except ValueError:
            return None

        normalized_devices_count = max(devices_count, 0)
        if normalized_event == RemnaUserHwidDevicesEvent.ADDED:
            return normalized_devices_count + 1
        if normalized_event == RemnaUserHwidDevicesEvent.DELETED:
            return max(normalized_devices_count - 1, 0)
        return None

    async def prepare_for_list(
        self,
        subscription: SubscriptionDto,
    ) -> tuple[SubscriptionDto, bool]:
        snapshot = await self.get_cached_runtime(subscription.user_remna_id)
        if snapshot and self.is_core_fresh(snapshot):
            emit_counter("subscription_runtime_cache_hits_total")
            return self.apply_runtime_snapshot(subscription, snapshot), False

        if snapshot:
            emit_counter("subscription_runtime_cache_stale_total")
            return self.apply_runtime_snapshot(subscription, snapshot), True

        emit_counter("subscription_runtime_cache_misses_total")
        return subscription, True

    async def prepare_for_list_batch(
        self,
        subscriptions: Sequence[SubscriptionDto],
        *,
        user_telegram_id: int,
        enqueue_runtime_refresh: SubscriptionRuntimeRefreshEnqueuer,
    ) -> list[SubscriptionDto]:
        prepared_results = await asyncio.gather(
            *(self.prepare_for_list(subscription) for subscription in subscriptions)
        )
        prepared_subscriptions: list[SubscriptionDto] = []
        subscription_ids_to_refresh: list[int] = []

        for subscription, (prepared_subscription, should_refresh) in zip(
            subscriptions,
            prepared_results,
            strict=False,
        ):
            prepared_subscriptions.append(prepared_subscription)
            if should_refresh and subscription.id is not None:
                subscription_ids_to_refresh.append(subscription.id)

        await self._enqueue_runtime_refresh_if_needed(
            user_telegram_id=user_telegram_id,
            subscription_ids=subscription_ids_to_refresh,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )
        return prepared_subscriptions

    async def prepare_for_detail(self, subscription: SubscriptionDto) -> SubscriptionDto:
        snapshot = await self.get_cached_runtime(subscription.user_remna_id)
        if snapshot and self.is_core_fresh(snapshot):
            emit_counter("subscription_runtime_cache_hits_total", scope="detail")
            return self.apply_runtime_snapshot(subscription, snapshot)

        if snapshot:
            emit_counter("subscription_runtime_cache_stale_total", scope="detail")
        else:
            emit_counter("subscription_runtime_cache_misses_total", scope="detail")

        refreshed_snapshot = await self._refresh_runtime_snapshot_for_subscription(subscription)
        if refreshed_snapshot is not None:
            return self.apply_runtime_snapshot(subscription, refreshed_snapshot)

        if snapshot is not None:
            return self.apply_runtime_snapshot(subscription, snapshot)

        return subscription

    async def acquire_refresh_lock(self, user_telegram_id: int) -> bool:
        lock_key = SubscriptionRuntimeRefreshLockKey(user_telegram_id=user_telegram_id)
        acquired = await self.redis_client.set(
            lock_key.pack(),
            "1",
            ex=SUBSCRIPTION_RUNTIME_REFRESH_LOCK_TTL_SECONDS,
            nx=True,
        )
        return bool(acquired)

    async def _enqueue_runtime_refresh_if_needed(
        self,
        *,
        user_telegram_id: int,
        subscription_ids: Sequence[int],
        enqueue_runtime_refresh: SubscriptionRuntimeRefreshEnqueuer,
    ) -> None:
        unique_subscription_ids = list(dict.fromkeys(subscription_ids))
        if not unique_subscription_ids:
            return

        try:
            lock_acquired = await self.acquire_refresh_lock(user_telegram_id)
            if lock_acquired:
                await enqueue_runtime_refresh(unique_subscription_ids)
        except Exception as exception:
            emit_counter(
                "subscription_runtime_refresh_failures_total",
                stage="enqueue",
            )
            logger.warning(
                f"Failed to enqueue runtime refresh for user '{user_telegram_id}': "
                f"{exception}"
            )

    async def refresh_user_subscriptions_runtime(self, subscription_ids: Sequence[int]) -> None:
        unique_subscription_ids = list(dict.fromkeys(subscription_ids))
        if not unique_subscription_ids:
            return
        subscriptions = await self.subscription_service.get_by_ids(unique_subscription_ids)
        if not subscriptions:
            return

        subscriptions_by_user: dict[int, list[SubscriptionDto]] = defaultdict(list)
        for subscription in subscriptions:
            subscriptions_by_user[subscription.user_telegram_id].append(subscription)

        for grouped_subscriptions in subscriptions_by_user.values():
            await self._refresh_runtime_snapshots_for_user(grouped_subscriptions)

    async def refresh_subscription_runtime_snapshot(self, subscription_id: int) -> None:
        subscription = await self.subscription_service.get(subscription_id)
        if not subscription:
            logger.debug(f"Skipping runtime refresh for missing subscription '{subscription_id}'")
            return

        await self._refresh_runtime_snapshot_for_subscription(subscription)

    async def _refresh_runtime_snapshots_for_user(
        self,
        subscriptions: Sequence[SubscriptionDto],
    ) -> None:
        if not subscriptions:
            return

        user_telegram_id = subscriptions[0].user_telegram_id
        prefetched_users = await self._get_prefetched_remna_users_by_uuid(user_telegram_id)
        semaphore = asyncio.Semaphore(SUBSCRIPTION_RUNTIME_REFRESH_CONCURRENCY)

        async def refresh_with_limit(subscription: SubscriptionDto) -> None:
            async with semaphore:
                try:
                    prefetched_user = prefetched_users.get(subscription.user_remna_id)
                    await self._refresh_runtime_snapshot_for_subscription(
                        subscription,
                        remna_user=prefetched_user,
                    )
                except Exception as exception:
                    emit_counter(
                        "subscription_runtime_refresh_failures_total",
                        stage="batch",
                    )
                    logger.warning(
                        f"Unexpected runtime refresh failure for subscription "
                        f"'{subscription.id}': {exception}"
                    )

        await asyncio.gather(*(refresh_with_limit(subscription) for subscription in subscriptions))

    async def _get_prefetched_remna_users_by_uuid(
        self,
        user_telegram_id: int,
    ) -> dict[UUID, object]:
        try:
            remna_users = await self.remnawave_service.get_users_by_telegram_id(user_telegram_id)
        except Exception as exception:
            logger.warning(
                f"Failed to prefetch Remnawave users for user '{user_telegram_id}': {exception}"
            )
            return {}

        return {
            user.uuid: user
            for user in remna_users
            if getattr(user, "uuid", None) is not None
        }

    async def _refresh_runtime_snapshot_for_subscription(
        self,
        subscription: SubscriptionDto,
        *,
        remna_user: object | None = None,
    ) -> SubscriptionRuntimeSnapshot | None:
        try:
            panel_user = remna_user or await self.remnawave_service.get_user(
                subscription.user_remna_id
            )
            if panel_user is None:
                raise ValueError(f"Remnawave user '{subscription.user_remna_id}' not found")
            devices = await self.remnawave_service.get_devices_by_subscription_uuid(
                subscription.user_remna_id
            )
            snapshot = self._build_snapshot(
                subscription=subscription,
                remna_user=panel_user,
                devices_count=len(devices),
            )
            await self._store_runtime_snapshot(snapshot)
        except Exception as exception:
            emit_counter(
                "subscription_runtime_refresh_failures_total",
                stage="refresh",
            )
            logger.warning(
                f"Failed to refresh runtime snapshot for subscription '{subscription.id}' "
                f"(remna_id='{subscription.user_remna_id}'): {exception}"
            )
            return None

        await self._persist_url_if_changed(subscription, snapshot.url)
        return snapshot

    async def _store_runtime_snapshot(
        self,
        snapshot: SubscriptionRuntimeSnapshot,
        *,
        preserve_existing_ttl: bool = False,
    ) -> None:
        snapshot_key = SubscriptionRuntimeSnapshotKey(user_remna_id=str(snapshot.user_remna_id))
        ttl_seconds = SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS
        if preserve_existing_ttl:
            ttl_getter = getattr(self.redis_client, "ttl", None)
            if ttl_getter is not None:
                remaining_ttl = await ttl_getter(snapshot_key.pack())
                if isinstance(remaining_ttl, int) and remaining_ttl > 0:
                    ttl_seconds = remaining_ttl

        await self.redis_repository.set(
            snapshot_key,
            snapshot,
            ex=ttl_seconds,
        )

    def _build_snapshot(
        self,
        *,
        subscription: SubscriptionDto,
        remna_user: object,
        devices_count: int,
    ) -> SubscriptionRuntimeSnapshot:
        refreshed_at = datetime_now()
        return SubscriptionRuntimeSnapshot(
            user_remna_id=subscription.user_remna_id,
            traffic_used=max(
                int(
                    getattr(getattr(remna_user, "user_traffic", None), "used_traffic_bytes", 0)
                    or 0
                ),
                0,
            ),
            traffic_limit=self._resolve_traffic_limit(subscription, remna_user),
            device_limit=self._resolve_device_limit(subscription, remna_user),
            devices_count=devices_count,
            url=(getattr(remna_user, "subscription_url", "") or "").strip() or subscription.url,
            refreshed_at=refreshed_at,
            core_refreshed_at=refreshed_at,
            devices_refreshed_at=refreshed_at,
        )

    @staticmethod
    def _resolve_traffic_limit(subscription: SubscriptionDto, remna_user: object) -> int:
        traffic_limit_bytes = getattr(remna_user, "traffic_limit_bytes", None)
        if traffic_limit_bytes is None:
            return subscription.traffic_limit
        return format_bytes_to_gb(int(traffic_limit_bytes))

    @staticmethod
    def _resolve_device_limit(subscription: SubscriptionDto, remna_user: object) -> int:
        device_limit = getattr(remna_user, "hwid_device_limit", None)
        if device_limit is None:
            return subscription.device_limit
        return format_device_count(int(device_limit))

    async def _persist_url_if_changed(
        self,
        subscription: SubscriptionDto,
        runtime_url: str,
    ) -> None:
        normalized_url = runtime_url.strip()
        if not normalized_url or normalized_url == (subscription.url or "").strip():
            return

        subscription.url = normalized_url
        try:
            await self.subscription_service.update(subscription)
        except Exception as exception:
            emit_counter(
                "subscription_runtime_refresh_failures_total",
                stage="persist_url",
            )
            logger.warning(
                f"Failed to persist refreshed URL for subscription '{subscription.id}' "
                f"(remna_id='{subscription.user_remna_id}'): {exception}"
            )
