from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.core.enums import RemnaUserHwidDevicesEvent
from src.core.observability import emit_counter
from src.core.storage.keys import SubscriptionDeviceListSnapshotKey
from src.core.utils.time import datetime_now

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import SubscriptionDto

    from .subscription_device import (
        SubscriptionDeviceItem,
        SubscriptionDeviceListSnapshot,
        SubscriptionDeviceService,
    )


async def get_cached_device_list(
    service: SubscriptionDeviceService,
    user_remna_id: object,
) -> SubscriptionDeviceListSnapshot | None:
    return await service.redis_repository.get(
        SubscriptionDeviceListSnapshotKey(user_remna_id=str(user_remna_id)),
        service._device_list_snapshot_type(),
        default=None,
    )


def is_cached_device_list_fresh(
    snapshot: SubscriptionDeviceListSnapshot,
    *,
    ttl_seconds: int,
) -> bool:
    return datetime_now() - snapshot.refreshed_at <= timedelta(seconds=ttl_seconds)


async def apply_device_event_to_cached_list(
    service: SubscriptionDeviceService,
    *,
    user_remna_id: object,
    event: str,
    hwid_device: object | None,
) -> SubscriptionDeviceListSnapshot | None:
    snapshot = await service.get_cached_device_list(user_remna_id)
    if snapshot is None:
        return None

    try:
        normalized_event = RemnaUserHwidDevicesEvent(event)
    except ValueError:
        return None

    next_devices = list(snapshot.devices)
    hwid = (getattr(hwid_device, "hwid", None) or "").strip()
    if not hwid:
        return None

    if normalized_event == RemnaUserHwidDevicesEvent.ADDED:
        device_item = service._map_panel_device_to_device_item(hwid_device)
        next_devices = [device for device in next_devices if device.hwid != device_item.hwid]
        next_devices.append(device_item)
    else:
        next_devices = [device for device in next_devices if device.hwid != hwid]

    snapshot.devices = next_devices
    snapshot.refreshed_at = datetime_now()
    await service._store_cached_device_list(
        user_remna_id=user_remna_id,
        devices=next_devices,
        refreshed_at=snapshot.refreshed_at,
    )
    emit_counter("subscription_device_list_cache_mutations_total", event=event)
    return snapshot


async def resolve_cached_devices_count(
    service: SubscriptionDeviceService,
    subscription: SubscriptionDto,
) -> int:
    devices_count = max(subscription.devices_count, 0)
    cached_runtime = await service.subscription_runtime_service.get_cached_runtime(
        subscription.user_remna_id
    )
    if cached_runtime is not None:
        return max(cached_runtime.devices_count, 0)
    return devices_count


async def store_cached_device_list(
    service: SubscriptionDeviceService,
    *,
    user_remna_id: object,
    devices: list[SubscriptionDeviceItem],
    refreshed_at: datetime | None = None,
) -> None:
    await service.redis_repository.set(
        SubscriptionDeviceListSnapshotKey(user_remna_id=str(user_remna_id)),
        service._device_list_snapshot(
            user_remna_id=str(user_remna_id),
            devices=devices,
            refreshed_at=refreshed_at or datetime_now(),
        ),
        ex=service._device_list_cache_ttl_seconds(),
    )


def map_panel_device_to_device_item(
    service: SubscriptionDeviceService,
    device: object,
) -> SubscriptionDeviceItem:
    created_at = getattr(device, "created_at", None)
    updated_at = getattr(device, "updated_at", None)
    return service._device_item(
        hwid=str(getattr(device, "hwid", "")),
        device_type=service._normalize_platform_to_device_type(getattr(device, "platform", None)),
        first_connected=created_at.isoformat() if created_at else None,
        last_connected=updated_at.isoformat() if updated_at else None,
    )


def normalize_platform_to_device_type(platform: str | None) -> str:
    platform_upper = (platform or "").upper()

    if "ANDROID" in platform_upper:
        return "ANDROID"
    if "IPHONE" in platform_upper or "IOS" in platform_upper:
        return "IPHONE"
    if "WINDOWS" in platform_upper:
        return "WINDOWS"
    if any(marker in platform_upper for marker in ("MAC", "MACOS", "OS X", "OSX", "DARWIN")):
        return "MAC"

    return "OTHER"
