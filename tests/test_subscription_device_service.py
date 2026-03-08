from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.enums import DeviceType
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto
from src.services.subscription_device import (
    SubscriptionDeviceAccessDeniedError,
    SubscriptionDeviceItem,
    SubscriptionDeviceLimitReachedError,
    SubscriptionDeviceListSnapshot,
    SubscriptionDeviceNotFoundError,
    SubscriptionDeviceOperationError,
    SubscriptionDeviceService,
)


def _build_subscription(
    *,
    subscription_id: int,
    user_telegram_id: int,
    devices_count: int = 0,
) -> SubscriptionDto:
    subscription = SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        traffic_limit=50,
        device_limit=3,
        devices_count=devices_count,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        url="",
        plan=PlanSnapshotDto.test(),
    )
    return subscription


def _build_service(
    *,
    subscription_service: object | None = None,
    subscription_runtime_service: object | None = None,
    remnawave_service: object | None = None,
    redis_repository: object | None = None,
) -> SubscriptionDeviceService:
    return SubscriptionDeviceService(
        subscription_service=subscription_service
        or SimpleNamespace(
            get=AsyncMock(return_value=None),
            update=AsyncMock(return_value=None),
        ),
        subscription_runtime_service=subscription_runtime_service
        or SimpleNamespace(
            get_cached_runtime=AsyncMock(return_value=None),
            prepare_for_detail=AsyncMock(),
            apply_observed_devices_count_to_cached_runtime=AsyncMock(return_value=False),
        ),
        remnawave_service=remnawave_service
        or SimpleNamespace(
            get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
            get_subscription_url=AsyncMock(return_value=None),
            delete_device_by_subscription_uuid=AsyncMock(return_value=1),
        ),
        redis_repository=redis_repository
        or SimpleNamespace(
            get=AsyncMock(return_value=None),
            set=AsyncMock(return_value=None),
        ),
    )


def test_list_devices_maps_remnawave_payload() -> None:
    subscription = _build_subscription(subscription_id=77, user_telegram_id=1001)
    remna_device = SimpleNamespace(
        hwid="HWID-001",
        platform="Windows 11",
        created_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 2, 11, 30, tzinfo=timezone.utc),
    )
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=None),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(return_value=True),
    )
    remnawave_service = SimpleNamespace(
        get_devices_by_subscription_uuid=AsyncMock(return_value=[remna_device])
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
        redis_repository=redis_repository,
    )

    result = asyncio.run(service.list_devices(subscription_id=77, user_telegram_id=1001))

    assert result.subscription_id == 77
    assert result.devices_count == 1
    assert result.devices[0].hwid == "HWID-001"
    assert result.devices[0].device_type == "WINDOWS"
    assert result.devices[0].first_connected == remna_device.created_at.isoformat()
    redis_repository.set.assert_awaited_once()
    subscription_runtime_service.apply_observed_devices_count_to_cached_runtime.assert_awaited_once_with(
        user_remna_id=subscription.user_remna_id,
        devices_count=1,
    )


def test_list_devices_uses_fresh_cached_device_list_without_panel_lookup() -> None:
    subscription = _build_subscription(subscription_id=78, user_telegram_id=1002)
    cached_snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(subscription.user_remna_id),
        devices=[
            SubscriptionDeviceItem(
                hwid="HWID-CACHED",
                device_type="ANDROID",
                first_connected="2026-03-01T10:00:00+00:00",
                last_connected="2026-03-01T11:00:00+00:00",
            )
        ],
        refreshed_at=datetime.now(timezone.utc),
    )
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(get_cached_runtime=AsyncMock(return_value=None))
    remnawave_service = SimpleNamespace(get_devices_by_subscription_uuid=AsyncMock())
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=cached_snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
        redis_repository=redis_repository,
    )

    result = asyncio.run(service.list_devices(subscription_id=78, user_telegram_id=1002))

    assert result.devices_count == 1
    assert result.devices[0].hwid == "HWID-CACHED"
    remnawave_service.get_devices_by_subscription_uuid.assert_not_awaited()
    redis_repository.set.assert_not_awaited()


def test_list_devices_uses_snapshot_count_on_remnawave_error() -> None:
    subscription = _build_subscription(subscription_id=88, user_telegram_id=2002, devices_count=0)
    runtime_snapshot = SimpleNamespace(
        user_remna_id=subscription.user_remna_id,
        traffic_used=0,
        traffic_limit=50,
        device_limit=subscription.device_limit,
        devices_count=4,
        url="https://runtime.local/subscription",
        refreshed_at=datetime(2026, 3, 2, 11, 30, tzinfo=timezone.utc),
    )
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=runtime_snapshot),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(return_value=False),
    )
    remnawave_service = SimpleNamespace(
        get_devices_by_subscription_uuid=AsyncMock(
            side_effect=RuntimeError("Remnawave unavailable")
        )
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
        redis_repository=redis_repository,
    )

    result = asyncio.run(service.list_devices(subscription_id=88, user_telegram_id=2002))

    assert result.devices == []
    assert result.devices_count == 4


def test_list_devices_uses_stale_cached_device_list_on_panel_error() -> None:
    subscription = _build_subscription(subscription_id=89, user_telegram_id=2003, devices_count=0)
    cached_snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(subscription.user_remna_id),
        devices=[
            SubscriptionDeviceItem(
                hwid="HWID-STALE",
                device_type="WINDOWS",
                first_connected="2026-03-01T10:00:00+00:00",
                last_connected="2026-03-01T11:00:00+00:00",
            )
        ],
        refreshed_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
    )
    runtime_snapshot = SimpleNamespace(
        devices_count=3,
    )
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=runtime_snapshot),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(return_value=False),
    )
    remnawave_service = SimpleNamespace(
        get_devices_by_subscription_uuid=AsyncMock(side_effect=RuntimeError("panel unavailable"))
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=cached_snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
        redis_repository=redis_repository,
    )

    result = asyncio.run(service.list_devices(subscription_id=89, user_telegram_id=2003))

    assert result.devices[0].hwid == "HWID-STALE"
    assert result.devices_count == 3


def test_list_devices_returns_access_denied_for_foreign_subscription() -> None:
    subscription = _build_subscription(subscription_id=99, user_telegram_id=9999)
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    service = _build_service(subscription_service=subscription_service)

    with pytest.raises(SubscriptionDeviceAccessDeniedError):
        asyncio.run(service.list_devices(subscription_id=99, user_telegram_id=3003))


def test_generate_device_link_reuses_runtime_snapshot_without_direct_url_lookup() -> None:
    subscription = _build_subscription(subscription_id=101, user_telegram_id=4004, devices_count=1)
    subscription.url = "https://runtime.local/subscription"
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(return_value=subscription),
    )
    subscription_runtime_service = SimpleNamespace(
        prepare_for_detail=AsyncMock(return_value=subscription)
    )
    remnawave_service = SimpleNamespace(get_subscription_url=AsyncMock())
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
    )

    result = asyncio.run(
        service.generate_device_link(
            subscription_id=101,
            user_telegram_id=4004,
            device_type=DeviceType.WINDOWS,
        )
    )

    assert result.connection_url == subscription.url
    assert result.device_type == DeviceType.WINDOWS.value
    subscription_runtime_service.prepare_for_detail.assert_awaited_once_with(subscription)
    remnawave_service.get_subscription_url.assert_not_awaited()


def test_generate_device_link_falls_back_to_direct_url_lookup_when_runtime_url_missing() -> None:
    subscription = _build_subscription(subscription_id=102, user_telegram_id=5005)
    subscription.url = ""
    prepared_subscription = subscription.model_copy(deep=True)
    prepared_subscription.url = ""
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(return_value=subscription),
    )
    subscription_runtime_service = SimpleNamespace(
        prepare_for_detail=AsyncMock(return_value=prepared_subscription)
    )
    remnawave_service = SimpleNamespace(
        get_subscription_url=AsyncMock(return_value="https://panel.local/subscription")
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
    )

    result = asyncio.run(
        service.generate_device_link(
            subscription_id=102,
            user_telegram_id=5005,
            device_type=None,
        )
    )

    assert result.connection_url == "https://panel.local/subscription"
    assert result.device_type == "UNKNOWN"
    remnawave_service.get_subscription_url.assert_awaited_once_with(subscription.user_remna_id)
    subscription_service.update.assert_awaited_once()


def test_generate_device_link_returns_limit_reached_error() -> None:
    subscription = _build_subscription(subscription_id=103, user_telegram_id=6006, devices_count=3)
    subscription.url = "https://runtime.local/full"
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(
        prepare_for_detail=AsyncMock(return_value=subscription)
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
    )

    with pytest.raises(SubscriptionDeviceLimitReachedError) as exc_info:
        asyncio.run(
            service.generate_device_link(
                subscription_id=103,
                user_telegram_id=6006,
                device_type=None,
            )
        )

    assert str(exc_info.value) == "Device limit reached: 3/3"


def test_revoke_device_returns_success_message() -> None:
    subscription = _build_subscription(subscription_id=104, user_telegram_id=7007)
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=None),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(return_value=False),
    )
    remnawave_service = SimpleNamespace(
        delete_device_by_subscription_uuid=AsyncMock(return_value=1)
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
        redis_repository=redis_repository,
    )

    result = asyncio.run(
        service.revoke_device(
            subscription_id=104,
            user_telegram_id=7007,
            hwid="HWID-001",
        )
    )

    assert result.success is True
    assert result.message == "Device HWID-001 revoked successfully"


def test_revoke_device_updates_cached_device_list_when_available() -> None:
    subscription = _build_subscription(subscription_id=107, user_telegram_id=7010)
    cached_snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(subscription.user_remna_id),
        devices=[
            SubscriptionDeviceItem(
                hwid="HWID-001",
                device_type="WINDOWS",
                first_connected="2026-03-01T10:00:00+00:00",
                last_connected="2026-03-01T11:00:00+00:00",
            ),
            SubscriptionDeviceItem(
                hwid="HWID-002",
                device_type="ANDROID",
                first_connected="2026-03-01T12:00:00+00:00",
                last_connected="2026-03-01T13:00:00+00:00",
            ),
        ],
        refreshed_at=datetime.now(timezone.utc),
    )
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    subscription_runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=None),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(return_value=True),
    )
    remnawave_service = SimpleNamespace(
        delete_device_by_subscription_uuid=AsyncMock(return_value=1)
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=cached_snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(
        subscription_service=subscription_service,
        subscription_runtime_service=subscription_runtime_service,
        remnawave_service=remnawave_service,
        redis_repository=redis_repository,
    )

    result = asyncio.run(
        service.revoke_device(
            subscription_id=107,
            user_telegram_id=7010,
            hwid="HWID-001",
        )
    )

    assert result.success is True
    redis_repository.set.assert_awaited_once()
    cached_snapshot_after_delete = redis_repository.set.await_args.args[1]
    assert len(cached_snapshot_after_delete.devices) == 1
    assert cached_snapshot_after_delete.devices[0].hwid == "HWID-002"
    subscription_runtime_service.apply_observed_devices_count_to_cached_runtime.assert_awaited_once_with(
        user_remna_id=subscription.user_remna_id,
        devices_count=1,
    )


def test_revoke_device_raises_not_found_when_panel_returns_zero() -> None:
    subscription = _build_subscription(subscription_id=105, user_telegram_id=8008)
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    remnawave_service = SimpleNamespace(
        delete_device_by_subscription_uuid=AsyncMock(return_value=0)
    )
    service = _build_service(
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )

    with pytest.raises(SubscriptionDeviceNotFoundError) as exc_info:
        asyncio.run(
            service.revoke_device(
                subscription_id=105,
                user_telegram_id=8008,
                hwid="HWID-404",
            )
        )

    assert str(exc_info.value) == "Device HWID-404 not found"


def test_revoke_device_wraps_panel_failure() -> None:
    subscription = _build_subscription(subscription_id=106, user_telegram_id=9009)
    subscription_service = SimpleNamespace(get=AsyncMock(return_value=subscription))
    remnawave_service = SimpleNamespace(
        delete_device_by_subscription_uuid=AsyncMock(side_effect=RuntimeError("panel unavailable"))
    )
    service = _build_service(
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )

    with pytest.raises(SubscriptionDeviceOperationError) as exc_info:
        asyncio.run(
            service.revoke_device(
                subscription_id=106,
                user_telegram_id=9009,
                hwid="HWID-500",
            )
        )

    assert str(exc_info.value) == "Failed to revoke device: panel unavailable"


def test_apply_device_event_to_cached_list_adds_device() -> None:
    user_remna_id = uuid4()
    cached_snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(user_remna_id),
        devices=[],
        refreshed_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=cached_snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(redis_repository=redis_repository)

    updated_snapshot = asyncio.run(
        service.apply_device_event_to_cached_list(
            user_remna_id=user_remna_id,
            event="user_hwid_devices.added",
            hwid_device=SimpleNamespace(
                hwid="HWID-ADD",
                platform="Windows 11",
                created_at=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc),
            ),
        )
    )

    assert updated_snapshot is not None
    assert updated_snapshot.devices[0].hwid == "HWID-ADD"
    assert updated_snapshot.devices[0].device_type == "WINDOWS"
    redis_repository.set.assert_awaited_once()


def test_apply_device_event_to_cached_list_removes_device() -> None:
    user_remna_id = uuid4()
    cached_snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(user_remna_id),
        devices=[
            SubscriptionDeviceItem(
                hwid="HWID-DEL",
                device_type="WINDOWS",
                first_connected="2026-03-01T10:00:00+00:00",
                last_connected="2026-03-01T11:00:00+00:00",
            )
        ],
        refreshed_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=cached_snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_service(redis_repository=redis_repository)

    updated_snapshot = asyncio.run(
        service.apply_device_event_to_cached_list(
            user_remna_id=user_remna_id,
            event="user_hwid_devices.deleted",
            hwid_device=SimpleNamespace(hwid="HWID-DEL"),
        )
    )

    assert updated_snapshot is not None
    assert updated_snapshot.devices == []
    redis_repository.set.assert_awaited_once()
