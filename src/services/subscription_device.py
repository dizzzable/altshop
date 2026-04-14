from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from src.core.enums import DeviceType, RemnaUserHwidDevicesEvent
from src.infrastructure.database.models.dto import SubscriptionDto
from src.infrastructure.redis import RedisRepository
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.subscription_runtime import SubscriptionRuntimeService

from .subscription_device_cache import (
    apply_device_event_to_cached_list as _apply_device_event_to_cached_list_impl,
)
from .subscription_device_cache import (
    get_cached_device_list as _get_cached_device_list_impl,
)
from .subscription_device_cache import (
    is_cached_device_list_fresh as _is_cached_device_list_fresh_impl,
)
from .subscription_device_cache import (
    map_panel_device_to_device_item as _map_panel_device_to_device_item_impl,
)
from .subscription_device_cache import (
    normalize_platform_to_device_type as _normalize_platform_to_device_type_impl,
)
from .subscription_device_cache import (
    resolve_cached_devices_count as _resolve_cached_devices_count_impl,
)
from .subscription_device_cache import (
    store_cached_device_list as _store_cached_device_list_impl,
)
from .subscription_device_operations import (
    generate_device_link as _generate_device_link_impl,
)
from .subscription_device_operations import (
    get_owned_subscription as _get_owned_subscription_impl,
)
from .subscription_device_operations import (
    list_devices as _list_devices_impl,
)
from .subscription_device_operations import (
    persist_subscription_url_if_changed as _persist_subscription_url_if_changed_impl,
)
from .subscription_device_operations import (
    resolve_requested_device_type as _resolve_requested_device_type_impl,
)
from .subscription_device_operations import (
    revoke_device as _revoke_device_impl,
)

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

    @staticmethod
    def _device_list_cache_ttl_seconds() -> int:
        return SUBSCRIPTION_DEVICE_LIST_CACHE_TTL_SECONDS

    @staticmethod
    def _device_list_snapshot_type() -> type[SubscriptionDeviceListSnapshot]:
        return SubscriptionDeviceListSnapshot

    @staticmethod
    def _device_list_snapshot(
        *,
        user_remna_id: str,
        devices: list[SubscriptionDeviceItem],
        refreshed_at: datetime,
    ) -> SubscriptionDeviceListSnapshot:
        return SubscriptionDeviceListSnapshot(
            user_remna_id=user_remna_id,
            devices=devices,
            refreshed_at=refreshed_at,
        )

    @staticmethod
    def _device_item(
        *,
        hwid: str,
        device_type: str,
        first_connected: str | None,
        last_connected: str | None,
        country: str | None = None,
        ip: str | None = None,
    ) -> SubscriptionDeviceItem:
        return SubscriptionDeviceItem(
            hwid=hwid,
            device_type=device_type,
            first_connected=first_connected,
            last_connected=last_connected,
            country=country,
            ip=ip,
        )

    @staticmethod
    def _device_list_result(
        *,
        devices: list[SubscriptionDeviceItem],
        subscription_id: int,
        device_limit: int,
        devices_count: int,
    ) -> SubscriptionDeviceListResult:
        return SubscriptionDeviceListResult(
            devices=devices,
            subscription_id=subscription_id,
            device_limit=device_limit,
            devices_count=devices_count,
        )

    @staticmethod
    def _generated_device_link(
        *,
        hwid: str,
        connection_url: str,
        device_type: str,
    ) -> GeneratedSubscriptionDeviceLink:
        return GeneratedSubscriptionDeviceLink(
            hwid=hwid,
            connection_url=connection_url,
            device_type=device_type,
        )

    @staticmethod
    def _revoked_device(*, success: bool, message: str) -> RevokedSubscriptionDevice:
        return RevokedSubscriptionDevice(success=success, message=message)

    @staticmethod
    def _not_found_error(message: str) -> SubscriptionDeviceNotFoundError:
        return SubscriptionDeviceNotFoundError(message)

    @staticmethod
    def _access_denied_error(message: str) -> SubscriptionDeviceAccessDeniedError:
        return SubscriptionDeviceAccessDeniedError(message)

    @staticmethod
    def _limit_reached_error(
        *,
        devices_count: int,
        device_limit: int,
    ) -> SubscriptionDeviceLimitReachedError:
        return SubscriptionDeviceLimitReachedError(devices_count, device_limit)

    @staticmethod
    def _operation_error(message: str) -> SubscriptionDeviceOperationError:
        return SubscriptionDeviceOperationError(message)

    @staticmethod
    def _deleted_device_event() -> RemnaUserHwidDevicesEvent:
        return RemnaUserHwidDevicesEvent.DELETED

    @staticmethod
    def _is_device_error(exception: Exception) -> bool:
        return isinstance(exception, SubscriptionDeviceError)

    async def list_devices(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
    ) -> SubscriptionDeviceListResult:
        return await _list_devices_impl(
            self,
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
        )

    async def generate_device_link(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
        device_type: DeviceType | None,
    ) -> GeneratedSubscriptionDeviceLink:
        return await _generate_device_link_impl(
            self,
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
            device_type=device_type,
        )

    async def revoke_device(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
        hwid: str,
    ) -> RevokedSubscriptionDevice:
        return await _revoke_device_impl(
            self,
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
            hwid=hwid,
        )

    async def get_cached_device_list(
        self,
        user_remna_id: object,
    ) -> SubscriptionDeviceListSnapshot | None:
        return await _get_cached_device_list_impl(self, user_remna_id)

    @staticmethod
    def is_cached_device_list_fresh(snapshot: SubscriptionDeviceListSnapshot) -> bool:
        return _is_cached_device_list_fresh_impl(
            snapshot,
            ttl_seconds=SUBSCRIPTION_DEVICE_LIST_CACHE_TTL_SECONDS,
        )

    async def apply_device_event_to_cached_list(
        self,
        *,
        user_remna_id: object,
        event: str,
        hwid_device: object | None,
    ) -> SubscriptionDeviceListSnapshot | None:
        return await _apply_device_event_to_cached_list_impl(
            self,
            user_remna_id=user_remna_id,
            event=event,
            hwid_device=hwid_device,
        )

    async def _get_owned_subscription(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
    ) -> SubscriptionDto:
        return await _get_owned_subscription_impl(
            self,
            subscription_id=subscription_id,
            user_telegram_id=user_telegram_id,
        )

    async def _resolve_cached_devices_count(self, subscription: SubscriptionDto) -> int:
        return await _resolve_cached_devices_count_impl(self, subscription)

    async def _store_cached_device_list(
        self,
        *,
        user_remna_id: object,
        devices: list[SubscriptionDeviceItem],
        refreshed_at: datetime | None = None,
    ) -> None:
        await _store_cached_device_list_impl(
            self,
            user_remna_id=user_remna_id,
            devices=devices,
            refreshed_at=refreshed_at,
        )

    async def _persist_subscription_url_if_changed(
        self,
        *,
        subscription: SubscriptionDto,
        normalized_subscription_url: str,
    ) -> None:
        await _persist_subscription_url_if_changed_impl(
            self,
            subscription=subscription,
            normalized_subscription_url=normalized_subscription_url,
        )

    @staticmethod
    def _resolve_requested_device_type(device_type: DeviceType | None) -> str:
        return _resolve_requested_device_type_impl(device_type)

    def _map_panel_device_to_device_item(self, device: object) -> SubscriptionDeviceItem:
        return _map_panel_device_to_device_item_impl(self, device)

    @staticmethod
    def _normalize_platform_to_device_type(platform: str | None) -> str:
        return _normalize_platform_to_device_type_impl(platform)
