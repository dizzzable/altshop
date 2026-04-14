from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Sequence
from uuid import UUID

from loguru import logger

from src.core.observability import emit_counter
from src.core.storage.keys import SubscriptionRuntimeRefreshLockKey
from src.core.utils.formatters import format_bytes_to_gb, format_device_count

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import SubscriptionDto

    from .subscription_runtime import (
        SubscriptionRuntimeRefreshEnqueuer,
        SubscriptionRuntimeService,
        SubscriptionRuntimeSnapshot,
    )


async def prepare_for_list(
    service: SubscriptionRuntimeService,
    subscription: SubscriptionDto,
) -> tuple[SubscriptionDto, bool]:
    snapshot = await service.get_cached_runtime(subscription.user_remna_id)
    if snapshot and service.is_core_fresh(snapshot):
        emit_counter("subscription_runtime_cache_hits_total")
        return service.apply_runtime_snapshot(subscription, snapshot), False

    if snapshot:
        emit_counter("subscription_runtime_cache_stale_total")
        return service.apply_runtime_snapshot(subscription, snapshot), True

    emit_counter("subscription_runtime_cache_misses_total")
    return subscription, True


async def prepare_for_list_batch(
    service: SubscriptionRuntimeService,
    subscriptions: Sequence[SubscriptionDto],
    *,
    user_telegram_id: int,
    enqueue_runtime_refresh: SubscriptionRuntimeRefreshEnqueuer,
) -> list[SubscriptionDto]:
    prepared_results = await asyncio.gather(
        *(service.prepare_for_list(subscription) for subscription in subscriptions)
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

    await service._enqueue_runtime_refresh_if_needed(
        user_telegram_id=user_telegram_id,
        subscription_ids=subscription_ids_to_refresh,
        enqueue_runtime_refresh=enqueue_runtime_refresh,
    )
    return prepared_subscriptions


async def prepare_for_detail(
    service: SubscriptionRuntimeService,
    subscription: SubscriptionDto,
) -> SubscriptionDto:
    snapshot = await service.get_cached_runtime(subscription.user_remna_id)
    if snapshot and service.is_core_fresh(snapshot):
        emit_counter("subscription_runtime_cache_hits_total", scope="detail")
        return service.apply_runtime_snapshot(subscription, snapshot)

    if snapshot:
        emit_counter("subscription_runtime_cache_stale_total", scope="detail")
    else:
        emit_counter("subscription_runtime_cache_misses_total", scope="detail")

    refreshed_snapshot = await service._refresh_runtime_snapshot_for_subscription(subscription)
    if refreshed_snapshot is not None:
        return service.apply_runtime_snapshot(subscription, refreshed_snapshot)

    if snapshot is not None:
        return service.apply_runtime_snapshot(subscription, snapshot)

    return subscription


async def acquire_refresh_lock(service: SubscriptionRuntimeService, user_telegram_id: int) -> bool:
    lock_key = SubscriptionRuntimeRefreshLockKey(user_telegram_id=user_telegram_id)
    acquired = await service.redis_client.set(
        lock_key.pack(),
        "1",
        ex=service._refresh_lock_ttl_seconds(),
        nx=True,
    )
    return bool(acquired)


async def enqueue_runtime_refresh_if_needed(
    service: SubscriptionRuntimeService,
    *,
    user_telegram_id: int,
    subscription_ids: Sequence[int],
    enqueue_runtime_refresh: SubscriptionRuntimeRefreshEnqueuer,
) -> None:
    unique_subscription_ids = list(dict.fromkeys(subscription_ids))
    if not unique_subscription_ids:
        return

    try:
        lock_acquired = await service.acquire_refresh_lock(user_telegram_id)
        if lock_acquired:
            await enqueue_runtime_refresh(unique_subscription_ids)
    except Exception as exception:
        emit_counter("subscription_runtime_refresh_failures_total", stage="enqueue")
        logger.warning(
            "Failed to enqueue runtime refresh for user '{}': {}",
            user_telegram_id,
            exception,
        )


async def refresh_user_subscriptions_runtime(
    service: SubscriptionRuntimeService,
    subscription_ids: Sequence[int],
) -> None:
    unique_subscription_ids = list(dict.fromkeys(subscription_ids))
    if not unique_subscription_ids:
        return
    subscriptions = await service.subscription_service.get_by_ids(unique_subscription_ids)
    if not subscriptions:
        return

    subscriptions_by_user: dict[int, list[SubscriptionDto]] = defaultdict(list)
    for subscription in subscriptions:
        subscriptions_by_user[subscription.user_telegram_id].append(subscription)

    for grouped_subscriptions in subscriptions_by_user.values():
        await service._refresh_runtime_snapshots_for_user(grouped_subscriptions)


async def refresh_subscription_runtime_snapshot(
    service: SubscriptionRuntimeService,
    subscription_id: int,
) -> None:
    subscription = await service.subscription_service.get(subscription_id)
    if not subscription:
        logger.debug("Skipping runtime refresh for missing subscription '{}'", subscription_id)
        return

    await service._refresh_runtime_snapshot_for_subscription(subscription)


async def refresh_runtime_snapshots_for_user(
    service: SubscriptionRuntimeService,
    subscriptions: Sequence[SubscriptionDto],
) -> None:
    if not subscriptions:
        return

    user_telegram_id = subscriptions[0].user_telegram_id
    prefetched_users = await service._get_prefetched_remna_users_by_uuid(user_telegram_id)
    semaphore = asyncio.Semaphore(service._refresh_concurrency())

    async def refresh_with_limit(subscription: SubscriptionDto) -> None:
        async with semaphore:
            try:
                prefetched_user = prefetched_users.get(subscription.user_remna_id)
                await service._refresh_runtime_snapshot_for_subscription(
                    subscription,
                    remna_user=prefetched_user,
                )
            except Exception as exception:
                emit_counter("subscription_runtime_refresh_failures_total", stage="batch")
                logger.warning(
                    "Unexpected runtime refresh failure for subscription '{}': {}",
                    subscription.id,
                    exception,
                )

    await asyncio.gather(*(refresh_with_limit(subscription) for subscription in subscriptions))


async def get_prefetched_remna_users_by_uuid(
    service: SubscriptionRuntimeService,
    user_telegram_id: int,
) -> dict[UUID, object]:
    try:
        remna_users = await service.remnawave_service.get_users_by_telegram_id(user_telegram_id)
    except Exception as exception:
        logger.warning(
            "Failed to prefetch Remnawave users for user '{}': {}",
            user_telegram_id,
            exception,
        )
        return {}

    return {
        user.uuid: user
        for user in remna_users
        if getattr(user, "uuid", None) is not None
    }


async def refresh_runtime_snapshot_for_subscription(
    service: SubscriptionRuntimeService,
    subscription: SubscriptionDto,
    *,
    remna_user: object | None = None,
) -> SubscriptionRuntimeSnapshot | None:
    try:
        panel_user = remna_user or await service.remnawave_service.get_user(
            subscription.user_remna_id
        )
        if panel_user is None:
            raise ValueError(f"Remnawave user '{subscription.user_remna_id}' not found")
        devices = await service.remnawave_service.get_devices_by_subscription_uuid(
            subscription.user_remna_id
        )
        snapshot = service._build_snapshot(
            subscription=subscription,
            remna_user=panel_user,
            devices_count=len(devices),
        )
        await service._store_runtime_snapshot(snapshot)
    except Exception as exception:
        emit_counter("subscription_runtime_refresh_failures_total", stage="refresh")
        logger.warning(
            "Failed to refresh runtime snapshot for subscription '{}' (remna_id='{}'): {}",
            subscription.id,
            subscription.user_remna_id,
            exception,
        )
        return None

    await service._persist_url_if_changed(subscription, snapshot.url)
    return snapshot


def build_snapshot(
    service: SubscriptionRuntimeService,
    *,
    subscription: SubscriptionDto,
    remna_user: object,
    devices_count: int,
) -> SubscriptionRuntimeSnapshot:
    refreshed_at = service._now()
    return service._runtime_snapshot(
        user_remna_id=subscription.user_remna_id,
        traffic_used=max(
            int(getattr(getattr(remna_user, "user_traffic", None), "used_traffic_bytes", 0) or 0),
            0,
        ),
        traffic_limit=service._resolve_traffic_limit(subscription, remna_user),
        device_limit=service._resolve_device_limit(subscription, remna_user),
        devices_count=devices_count,
        url=(getattr(remna_user, "subscription_url", "") or "").strip() or subscription.url,
        refreshed_at=refreshed_at,
        core_refreshed_at=refreshed_at,
        devices_refreshed_at=refreshed_at,
    )


def resolve_traffic_limit(subscription: SubscriptionDto, remna_user: object) -> int:
    traffic_limit_bytes = getattr(remna_user, "traffic_limit_bytes", None)
    if traffic_limit_bytes is None:
        return subscription.traffic_limit
    return format_bytes_to_gb(int(traffic_limit_bytes))


def resolve_device_limit(subscription: SubscriptionDto, remna_user: object) -> int:
    device_limit = getattr(remna_user, "hwid_device_limit", None)
    if device_limit is None:
        return subscription.device_limit
    return format_device_count(int(device_limit))


async def persist_url_if_changed(
    service: SubscriptionRuntimeService,
    subscription: SubscriptionDto,
    runtime_url: str,
) -> None:
    normalized_url = runtime_url.strip()
    if not normalized_url or normalized_url == (subscription.url or "").strip():
        return

    subscription.url = normalized_url
    try:
        await service.subscription_service.update(subscription)
    except Exception as exception:
        emit_counter("subscription_runtime_refresh_failures_total", stage="persist_url")
        logger.warning(
            "Failed to persist refreshed URL for subscription '{}' (remna_id='{}'): {}",
            subscription.id,
            subscription.user_remna_id,
            exception,
        )
