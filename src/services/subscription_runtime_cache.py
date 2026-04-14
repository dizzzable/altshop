from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from src.core.enums import RemnaUserHwidDevicesEvent
from src.core.observability import emit_counter
from src.core.storage.keys import SubscriptionRuntimeSnapshotKey
from src.core.utils.time import datetime_now

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import SubscriptionDto

    from .subscription_runtime import SubscriptionRuntimeService, SubscriptionRuntimeSnapshot


async def get_cached_runtime(
    service: SubscriptionRuntimeService,
    user_remna_id: UUID,
) -> SubscriptionRuntimeSnapshot | None:
    return await service.redis_repository.get(
        SubscriptionRuntimeSnapshotKey(user_remna_id=str(user_remna_id)),
        service._runtime_snapshot_type(),
        default=None,
    )


async def apply_observed_devices_count_to_cached_runtime(
    service: SubscriptionRuntimeService,
    *,
    user_remna_id: UUID,
    devices_count: int,
) -> bool:
    snapshot = await service.get_cached_runtime(user_remna_id)
    if snapshot is None:
        return False

    snapshot.devices_count = max(devices_count, 0)
    snapshot.devices_refreshed_at = datetime_now()
    await service._store_runtime_snapshot(snapshot, preserve_existing_ttl=True)
    emit_counter(
        "subscription_runtime_cache_mutations_total",
        scope="devices",
        event="observed_count",
    )
    return True


def is_fresh(
    snapshot: SubscriptionRuntimeSnapshot,
    *,
    ttl_seconds: int,
) -> bool:
    return is_core_fresh(snapshot, ttl_seconds=ttl_seconds)


def is_core_fresh(
    snapshot: SubscriptionRuntimeSnapshot,
    *,
    ttl_seconds: int,
) -> bool:
    core_refreshed_at = snapshot.core_refreshed_at or snapshot.refreshed_at
    return datetime_now() - core_refreshed_at <= timedelta(seconds=ttl_seconds)


def is_devices_fresh(
    snapshot: SubscriptionRuntimeSnapshot,
    *,
    ttl_seconds: int,
) -> bool:
    devices_refreshed_at = (
        snapshot.devices_refreshed_at or snapshot.core_refreshed_at or snapshot.refreshed_at
    )
    return datetime_now() - devices_refreshed_at <= timedelta(seconds=ttl_seconds)


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
    service: SubscriptionRuntimeService,
    *,
    user_remna_id: UUID,
    event: str,
) -> bool:
    snapshot = await service.get_cached_runtime(user_remna_id)
    if snapshot is None:
        return False

    next_devices_count = service._resolve_devices_count_after_event(snapshot.devices_count, event)
    if next_devices_count is None:
        return False

    snapshot.devices_count = next_devices_count
    snapshot.devices_refreshed_at = datetime_now()
    await service._store_runtime_snapshot(snapshot, preserve_existing_ttl=True)
    emit_counter("subscription_runtime_cache_mutations_total", scope="devices", event=event)
    return True


def resolve_devices_count_after_event(devices_count: int, event: str) -> int | None:
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


async def store_runtime_snapshot(
    service: SubscriptionRuntimeService,
    snapshot: SubscriptionRuntimeSnapshot,
    *,
    preserve_existing_ttl: bool = False,
) -> None:
    snapshot_key = SubscriptionRuntimeSnapshotKey(user_remna_id=str(snapshot.user_remna_id))
    ttl_seconds = service._runtime_cache_ttl_seconds()
    if preserve_existing_ttl:
        ttl_getter = getattr(service.redis_client, "ttl", None)
        if ttl_getter is not None:
            remaining_ttl = await ttl_getter(snapshot_key.pack())
            if isinstance(remaining_ttl, int) and remaining_ttl > 0:
                ttl_seconds = remaining_ttl

    await service.redis_repository.set(
        snapshot_key,
        snapshot,
        ex=ttl_seconds,
    )
