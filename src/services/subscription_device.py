from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from pydantic import BaseModel

from src.core.enums import DeviceType, RemnaUserHwidDevicesEvent
from src.core.observability import emit_counter
from src.core.storage.keys import SubscriptionDeviceListSnapshotKey
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import SubscriptionDto
from src.infrastructure.redis import RedisRepository
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.subscription_runtime import SubscriptionRuntimeService

SUBSCRIPTION_DEVICE_LIST_CACHE_TTL_SECONDS = 30


class SubscriptionDeviceError(Exception):
    """Base error for subscription device flows."""


class SubscriptionDeviceNotFoundError(SubscriptionDeviceError):
    """Raised when subscription or device is missing."""


class SubscriptionDeviceAccessDeniedError(SubscriptionDeviceError):
    """Raised when the subscription does not belong to the current user."""


class SubscriptionDeviceLimitReachedError(SubscriptionDeviceError):
    def __init__(self, devices_count: int, device_limit: int) -> None:
        self.devices_count = devices_count
        self.device_limit = device_limit
        super().__init__(f"Device limit reached: {devices_count}/{device_limit}")


class SubscriptionDeviceOperationError(SubscriptionDeviceError):
    """Raised when a device operation cannot be completed."""


class SubscriptionDeviceItem(BaseModel):
    hwid: str
    device_type: str
    first_connected: str | None
    last_connected: str | None
    country: str | None = None
    ip: str | None = None


class SubscriptionDeviceListSnapshot(BaseModel):
    user_remna_id: str
    devices: list[SubscriptionDeviceItem]
    refreshed_at: datetime


@dataclass(slots=True, frozen=True)
class SubscriptionDeviceListResult:
    devices: list[SubscriptionDeviceItem]
    subscription_id: int
    device_limit: int
    devices_count: int


@dataclass(slots=True, frozen=True)
class GeneratedSubscriptionDeviceLink:
    hwid: str
    connection_url: str
    device_type: str


@dataclass(slots=True, frozen=True)
class RevokedSubscriptionDevice:
    success: bool
    message: str


class SubscriptionDeviceService:
    subscription_service: SubscriptionService
    subscription_runtime_service: SubscriptionRuntimeService
    remnawave_service: RemnawaveService
    redis_repository: RedisRepository

    def __init__(
        self,
        subscription_service: SubscriptionService,
        subscription_runtime_service: SubscriptionRuntimeService,
        remnawave_service: RemnawaveService,
        redis_repository: RedisRepository,
    ) -> None:
        self.subscription_service = subscription_service
        self.subscription_runtime_service = subscription_runtime_service
        self.remnawave_service = remnawave_service
        self.redis_repository = redis_repository

    async def list_devices(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
    ) -> SubscriptionDeviceListResult:
        subscription = await self._get_owned_subscription(
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
        )

        cached_devices_snapshot = await self.get_cached_device_list(subscription.user_remna_id)
        if cached_devices_snapshot and self.is_cached_device_list_fresh(cached_devices_snapshot):
            emit_counter("subscription_device_list_cache_hits_total")
            return SubscriptionDeviceListResult(
                devices=list(cached_devices_snapshot.devices),
                subscription_id=subscription_id,
                device_limit=subscription.device_limit,
                devices_count=len(cached_devices_snapshot.devices),
            )

        if cached_devices_snapshot:
            emit_counter("subscription_device_list_cache_stale_total")
        else:
            emit_counter("subscription_device_list_cache_misses_total")

        devices: list[SubscriptionDeviceItem] = []
        devices_count = await self._resolve_cached_devices_count(subscription)
        try:
            hwid_devices = await self.remnawave_service.get_devices_by_subscription_uuid(
                subscription.user_remna_id
            )
            devices = [
                SubscriptionDeviceItem(
                    hwid=device.hwid,
                    device_type=self._normalize_platform_to_device_type(device.platform),
                    first_connected=device.created_at.isoformat() if device.created_at else None,
                    last_connected=device.updated_at.isoformat() if device.updated_at else None,
                )
                for device in hwid_devices
            ]
            devices_count = len(hwid_devices)
            await self._store_cached_device_list(
                user_remna_id=subscription.user_remna_id,
                devices=devices,
            )
            await self.subscription_runtime_service.apply_observed_devices_count_to_cached_runtime(
                user_remna_id=subscription.user_remna_id,
                devices_count=devices_count,
            )
        except Exception as exception:
            logger.warning(
                f"Failed to fetch devices from Remnawave for subscription '{subscription.id}' "
                f"(remna_id='{subscription.user_remna_id}'): {exception}"
            )
            if cached_devices_snapshot is not None:
                devices = list(cached_devices_snapshot.devices)
                devices_count = max(len(devices), devices_count)

        return SubscriptionDeviceListResult(
            devices=devices,
            subscription_id=subscription_id,
            device_limit=subscription.device_limit,
            devices_count=devices_count,
        )

    async def generate_device_link(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
        device_type: DeviceType | None,
    ) -> GeneratedSubscriptionDeviceLink:
        subscription = await self._get_owned_subscription(
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
        )
        subscription = await self.subscription_runtime_service.prepare_for_detail(subscription)
        actual_devices_count = max(subscription.devices_count, 0)

        if subscription.device_limit > 0 and actual_devices_count >= subscription.device_limit:
            raise SubscriptionDeviceLimitReachedError(
                devices_count=actual_devices_count,
                device_limit=subscription.device_limit,
            )

        try:
            normalized_subscription_url = (subscription.url or "").strip()
            if not normalized_subscription_url:
                subscription_url = await self.remnawave_service.get_subscription_url(
                    subscription.user_remna_id
                )
                normalized_subscription_url = subscription_url.strip() if subscription_url else ""

            if not normalized_subscription_url:
                raise SubscriptionDeviceOperationError(
                    "Failed to get subscription URL from Remnawave"
                )

            await self._persist_subscription_url_if_changed(
                subscription=subscription,
                normalized_subscription_url=normalized_subscription_url,
            )

            resolved_device_type = self._resolve_requested_device_type(device_type)
            hwid_source = (
                f"{subscription.user_remna_id}:{user_telegram_id}:{resolved_device_type}"
            )
            hwid = hashlib.md5(hwid_source.encode()).hexdigest()[:16]

            return GeneratedSubscriptionDeviceLink(
                hwid=hwid,
                connection_url=normalized_subscription_url,
                device_type=resolved_device_type,
            )
        except SubscriptionDeviceError:
            raise
        except Exception as exception:
            logger.exception(f"Failed to generate device link: {exception}")
            raise SubscriptionDeviceOperationError(
                f"Failed to generate connection link: {exception}"
            ) from exception

    async def revoke_device(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
        hwid: str,
    ) -> RevokedSubscriptionDevice:
        subscription = await self._get_owned_subscription(
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
        )

        try:
            deleted_count = await self.remnawave_service.delete_device_by_subscription_uuid(
                user_remna_id=subscription.user_remna_id,
                hwid=hwid,
            )
        except Exception as exception:
            logger.exception(f"Failed to revoke device: {exception}")
            raise SubscriptionDeviceOperationError(
                f"Failed to revoke device: {exception}"
            ) from exception

        if deleted_count is None or deleted_count == 0:
            raise SubscriptionDeviceNotFoundError(f"Device {hwid} not found")

        cached_devices_snapshot = await self.apply_device_event_to_cached_list(
            user_remna_id=subscription.user_remna_id,
            event=RemnaUserHwidDevicesEvent.DELETED,
            hwid_device=type("DeletedDeviceEvent", (), {"hwid": hwid})(),
        )
        if cached_devices_snapshot is not None:
            await self.subscription_runtime_service.apply_observed_devices_count_to_cached_runtime(
                user_remna_id=subscription.user_remna_id,
                devices_count=len(cached_devices_snapshot.devices),
            )

        return RevokedSubscriptionDevice(
            success=True,
            message=f"Device {hwid} revoked successfully",
        )

    async def get_cached_device_list(
        self,
        user_remna_id: object,
    ) -> SubscriptionDeviceListSnapshot | None:
        return await self.redis_repository.get(
            SubscriptionDeviceListSnapshotKey(user_remna_id=str(user_remna_id)),
            SubscriptionDeviceListSnapshot,
            default=None,
        )

    @staticmethod
    def is_cached_device_list_fresh(snapshot: SubscriptionDeviceListSnapshot) -> bool:
        return datetime_now() - snapshot.refreshed_at <= timedelta(
            seconds=SUBSCRIPTION_DEVICE_LIST_CACHE_TTL_SECONDS
        )

    async def apply_device_event_to_cached_list(
        self,
        *,
        user_remna_id: object,
        event: str,
        hwid_device: object | None,
    ) -> SubscriptionDeviceListSnapshot | None:
        snapshot = await self.get_cached_device_list(user_remna_id)
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
            device_item = self._map_panel_device_to_device_item(hwid_device)
            next_devices = [device for device in next_devices if device.hwid != device_item.hwid]
            next_devices.append(device_item)
        else:
            next_devices = [device for device in next_devices if device.hwid != hwid]

        snapshot.devices = next_devices
        snapshot.refreshed_at = datetime_now()
        await self._store_cached_device_list(
            user_remna_id=user_remna_id,
            devices=next_devices,
            refreshed_at=snapshot.refreshed_at,
        )
        emit_counter("subscription_device_list_cache_mutations_total", event=event)
        return snapshot

    async def _get_owned_subscription(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
    ) -> SubscriptionDto:
        subscription = await self.subscription_service.get(subscription_id)
        if not subscription:
            raise SubscriptionDeviceNotFoundError("Subscription not found")
        if subscription.user_telegram_id != user_telegram_id:
            raise SubscriptionDeviceAccessDeniedError("Access denied to this subscription")
        return subscription

    async def _resolve_cached_devices_count(self, subscription: SubscriptionDto) -> int:
        devices_count = max(subscription.devices_count, 0)
        cached_runtime = await self.subscription_runtime_service.get_cached_runtime(
            subscription.user_remna_id
        )
        if cached_runtime is not None:
            return max(cached_runtime.devices_count, 0)
        return devices_count

    async def _store_cached_device_list(
        self,
        *,
        user_remna_id: object,
        devices: list[SubscriptionDeviceItem],
        refreshed_at: datetime | None = None,
    ) -> None:
        await self.redis_repository.set(
            SubscriptionDeviceListSnapshotKey(user_remna_id=str(user_remna_id)),
            SubscriptionDeviceListSnapshot(
                user_remna_id=str(user_remna_id),
                devices=devices,
                refreshed_at=refreshed_at or datetime_now(),
            ),
            ex=SUBSCRIPTION_DEVICE_LIST_CACHE_TTL_SECONDS,
        )

    async def _persist_subscription_url_if_changed(
        self,
        *,
        subscription: SubscriptionDto,
        normalized_subscription_url: str,
    ) -> None:
        if (subscription.url or "").strip() == normalized_subscription_url:
            return

        subscription.url = normalized_subscription_url
        try:
            await self.subscription_service.update(subscription)
        except Exception as sync_exception:
            logger.warning(
                f"Failed to persist refreshed URL after device link generation for "
                f"subscription '{subscription.id}': {sync_exception}"
            )

    @staticmethod
    def _resolve_requested_device_type(device_type: DeviceType | None) -> str:
        if device_type is None:
            return "UNKNOWN"
        return device_type.value if hasattr(device_type, "value") else str(device_type)

    @classmethod
    def _map_panel_device_to_device_item(cls, device: object) -> SubscriptionDeviceItem:
        created_at = getattr(device, "created_at", None)
        updated_at = getattr(device, "updated_at", None)
        return SubscriptionDeviceItem(
            hwid=str(getattr(device, "hwid", "")),
            device_type=cls._normalize_platform_to_device_type(getattr(device, "platform", None)),
            first_connected=created_at.isoformat() if created_at else None,
            last_connected=updated_at.isoformat() if updated_at else None,
        )

    @staticmethod
    def _normalize_platform_to_device_type(platform: str | None) -> str:
        platform_upper = (platform or "").upper()

        if "ANDROID" in platform_upper:
            return DeviceType.ANDROID.value
        if "IPHONE" in platform_upper or "IOS" in platform_upper:
            return DeviceType.IPHONE.value
        if "WINDOWS" in platform_upper:
            return DeviceType.WINDOWS.value
        if any(marker in platform_upper for marker in ("MAC", "MACOS", "OS X", "OSX", "DARWIN")):
            return DeviceType.MAC.value

        return DeviceType.OTHER.value
