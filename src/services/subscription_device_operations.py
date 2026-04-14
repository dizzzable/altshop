from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.core.enums import DeviceType
    from src.infrastructure.database.models.dto import SubscriptionDto

    from .subscription_device import (
        GeneratedSubscriptionDeviceLink,
        RevokedSubscriptionDevice,
        SubscriptionDeviceListResult,
        SubscriptionDeviceService,
    )


async def list_devices(
    service: SubscriptionDeviceService,
    *,
    subscription_id: int,
    user_telegram_id: int,
) -> SubscriptionDeviceListResult:
    subscription = await service._get_owned_subscription(
        subscription_id=subscription_id,
        user_telegram_id=user_telegram_id,
    )

    cached_devices_snapshot = await service.get_cached_device_list(subscription.user_remna_id)
    if cached_devices_snapshot and service.is_cached_device_list_fresh(cached_devices_snapshot):
        from src.core.observability import emit_counter  # noqa: PLC0415

        emit_counter("subscription_device_list_cache_hits_total")
        return service._device_list_result(
            devices=list(cached_devices_snapshot.devices),
            subscription_id=subscription_id,
            device_limit=subscription.device_limit,
            devices_count=len(cached_devices_snapshot.devices),
        )

    from src.core.observability import emit_counter  # noqa: PLC0415

    if cached_devices_snapshot:
        emit_counter("subscription_device_list_cache_stale_total")
    else:
        emit_counter("subscription_device_list_cache_misses_total")

    devices = []
    devices_count = await service._resolve_cached_devices_count(subscription)
    try:
        hwid_devices = await service.remnawave_service.get_devices_by_subscription_uuid(
            subscription.user_remna_id
        )
        devices = [
            service._device_item(
                hwid=device.hwid,
                device_type=service._normalize_platform_to_device_type(device.platform),
                first_connected=device.created_at.isoformat() if device.created_at else None,
                last_connected=device.updated_at.isoformat() if device.updated_at else None,
            )
            for device in hwid_devices
        ]
        devices_count = len(hwid_devices)
        await service._store_cached_device_list(
            user_remna_id=subscription.user_remna_id,
            devices=devices,
        )
        await service.subscription_runtime_service.apply_observed_devices_count_to_cached_runtime(
            user_remna_id=subscription.user_remna_id,
            devices_count=devices_count,
        )
    except Exception as exception:
        logger.warning(
            "Failed to fetch devices from Remnawave for subscription '{}' "
            "(remna_id='{}'): {}",
            subscription.id,
            subscription.user_remna_id,
            exception,
        )
        if cached_devices_snapshot is not None:
            devices = list(cached_devices_snapshot.devices)
            devices_count = max(len(devices), devices_count)

    return service._device_list_result(
        devices=devices,
        subscription_id=subscription_id,
        device_limit=subscription.device_limit,
        devices_count=devices_count,
    )


async def generate_device_link(
    service: SubscriptionDeviceService,
    *,
    subscription_id: int,
    user_telegram_id: int,
    device_type: DeviceType | None,
) -> GeneratedSubscriptionDeviceLink:
    subscription = await service._get_owned_subscription(
        subscription_id=subscription_id,
        user_telegram_id=user_telegram_id,
    )
    subscription = await service.subscription_runtime_service.prepare_for_detail(subscription)
    actual_devices_count = max(subscription.devices_count, 0)

    if subscription.device_limit > 0 and actual_devices_count >= subscription.device_limit:
        raise service._limit_reached_error(
            devices_count=actual_devices_count,
            device_limit=subscription.device_limit,
        )

    try:
        normalized_subscription_url = (subscription.url or "").strip()
        if not normalized_subscription_url:
            subscription_url = await service.remnawave_service.get_subscription_url(
                subscription.user_remna_id
            )
            normalized_subscription_url = subscription_url.strip() if subscription_url else ""

        if not normalized_subscription_url:
            raise service._operation_error("Failed to get subscription URL from Remnawave")

        await service._persist_subscription_url_if_changed(
            subscription=subscription,
            normalized_subscription_url=normalized_subscription_url,
        )

        resolved_device_type = service._resolve_requested_device_type(device_type)
        hwid_source = f"{subscription.user_remna_id}:{user_telegram_id}:{resolved_device_type}"
        hwid = hashlib.md5(hwid_source.encode()).hexdigest()[:16]

        return service._generated_device_link(
            hwid=hwid,
            connection_url=normalized_subscription_url,
            device_type=resolved_device_type,
        )
    except Exception as exception:
        if service._is_device_error(exception):
            raise
        logger.exception("Failed to generate device link: {}", exception)
        raise service._operation_error(
            f"Failed to generate connection link: {exception}"
        ) from exception


async def revoke_device(
    service: SubscriptionDeviceService,
    *,
    subscription_id: int,
    user_telegram_id: int,
    hwid: str,
) -> RevokedSubscriptionDevice:
    subscription = await service._get_owned_subscription(
        subscription_id=subscription_id,
        user_telegram_id=user_telegram_id,
    )

    try:
        deleted_count = await service.remnawave_service.delete_device_by_subscription_uuid(
            user_remna_id=subscription.user_remna_id,
            hwid=hwid,
        )
    except Exception as exception:
        logger.exception("Failed to revoke device: {}", exception)
        raise service._operation_error(f"Failed to revoke device: {exception}") from exception

    if deleted_count is None or deleted_count == 0:
        raise service._not_found_error(f"Device {hwid} not found")

    cached_devices_snapshot = await service.apply_device_event_to_cached_list(
        user_remna_id=subscription.user_remna_id,
        event=service._deleted_device_event(),
        hwid_device=type("DeletedDeviceEvent", (), {"hwid": hwid})(),
    )
    if cached_devices_snapshot is not None:
        await service.subscription_runtime_service.apply_observed_devices_count_to_cached_runtime(
            user_remna_id=subscription.user_remna_id,
            devices_count=len(cached_devices_snapshot.devices),
        )

    return service._revoked_device(
        success=True,
        message=f"Device {hwid} revoked successfully",
    )


async def get_owned_subscription(
    service: SubscriptionDeviceService,
    *,
    subscription_id: int,
    user_telegram_id: int,
) -> SubscriptionDto:
    subscription = await service.subscription_service.get(subscription_id)
    if not subscription:
        raise service._not_found_error("Subscription not found")
    if subscription.user_telegram_id != user_telegram_id:
        raise service._access_denied_error("Access denied to this subscription")
    return subscription


async def persist_subscription_url_if_changed(
    service: SubscriptionDeviceService,
    *,
    subscription: SubscriptionDto,
    normalized_subscription_url: str,
) -> None:
    if (subscription.url or "").strip() == normalized_subscription_url:
        return

    subscription.url = normalized_subscription_url
    try:
        await service.subscription_service.update(subscription)
    except Exception as sync_exception:
        logger.warning(
            "Failed to persist refreshed URL after device link generation for "
            "subscription '{}': {}",
            subscription.id,
            sync_exception,
        )


def resolve_requested_device_type(device_type: DeviceType | None) -> str:
    if device_type is None:
        return "UNKNOWN"
    return device_type.value if hasattr(device_type, "value") else str(device_type)
