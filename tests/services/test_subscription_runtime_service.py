from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from remnawave.enums.users import TrafficLimitStrategy

from src.core.enums import DeviceType
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, SubscriptionDto
from src.services.subscription_device import (
    SubscriptionDeviceAccessDeniedError,
    SubscriptionDeviceItem,
    SubscriptionDeviceLimitReachedError,
    SubscriptionDeviceListSnapshot,
    SubscriptionDeviceNotFoundError,
    SubscriptionDeviceOperationError,
    SubscriptionDeviceService,
)
from src.services.subscription_runtime import (
    SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS,
    SubscriptionRuntimeService,
    SubscriptionRuntimeSnapshot,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_plan(*, plan_id: int = 1) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name="Plan",
        is_active=True,
        traffic_limit=100,
        device_limit=2,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        internal_squads=[],
        external_squad=None,
        durations=[],
        allowed_user_ids=[],
    )


def build_subscription(
    *,
    subscription_id: int = 10,
    user_telegram_id: int = 100,
    url: str = "https://example.test/subscription",
    device_limit: int = 2,
    devices_count: int = 0,
) -> SubscriptionDto:
    plan = build_plan()
    subscription = SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        traffic_limit=plan.traffic_limit,
        traffic_used=0,
        device_limit=device_limit,
        devices_count=devices_count,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url=url,
        plan=PlanSnapshotDto.from_plan(plan, 30),
    )
    return subscription


def build_runtime_snapshot(
    subscription: SubscriptionDto,
    *,
    refreshed_delta_seconds: int = 0,
    devices_count: int = 0,
    traffic_used: int = 0,
    url: str | None = None,
) -> SubscriptionRuntimeSnapshot:
    refreshed_at = datetime_now() - timedelta(seconds=refreshed_delta_seconds)
    return SubscriptionRuntimeSnapshot(
        user_remna_id=subscription.user_remna_id,
        traffic_used=traffic_used,
        traffic_limit=subscription.traffic_limit + 50,
        device_limit=subscription.device_limit + 1,
        devices_count=devices_count,
        url=url or subscription.url,
        refreshed_at=refreshed_at,
        core_refreshed_at=refreshed_at,
        devices_refreshed_at=refreshed_at,
    )


def build_runtime_service() -> SubscriptionRuntimeService:
    return SubscriptionRuntimeService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(set=AsyncMock(), ttl=AsyncMock(return_value=12)),
        redis_repository=SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock()),
        translator_hub=SimpleNamespace(),
        subscription_service=SimpleNamespace(
            get=AsyncMock(return_value=None),
            get_by_ids=AsyncMock(return_value=[]),
            update=AsyncMock(),
        ),
        remnawave_service=SimpleNamespace(
            get_user=AsyncMock(),
            get_users_by_telegram_id=AsyncMock(return_value=[]),
            get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
        ),
    )


def build_device_service(
    *,
    runtime_service=None,
    subscription_service=None,
    remnawave_service=None,
    redis_repository=None,
) -> SubscriptionDeviceService:
    return SubscriptionDeviceService(
        subscription_service=subscription_service
        or SimpleNamespace(get=AsyncMock(return_value=None), update=AsyncMock()),
        subscription_runtime_service=runtime_service
        or SimpleNamespace(
            get_cached_runtime=AsyncMock(return_value=None),
            prepare_for_detail=AsyncMock(),
            apply_observed_devices_count_to_cached_runtime=AsyncMock(),
        ),
        remnawave_service=remnawave_service
        or SimpleNamespace(
            get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
            get_subscription_url=AsyncMock(return_value=""),
            delete_device_by_subscription_uuid=AsyncMock(return_value=1),
        ),
        redis_repository=redis_repository
        or SimpleNamespace(get=AsyncMock(return_value=None), set=AsyncMock()),
    )


def test_prepare_for_list_returns_cached_runtime_when_core_fresh() -> None:
    service = build_runtime_service()
    subscription = build_subscription()
    snapshot = build_runtime_snapshot(subscription, refreshed_delta_seconds=0, devices_count=3)
    service.get_cached_runtime = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]

    prepared, should_refresh = run_async(service.prepare_for_list(subscription))

    assert should_refresh is False
    assert prepared.traffic_limit == snapshot.traffic_limit
    assert prepared.device_limit == snapshot.device_limit
    assert prepared.devices_count == 3


def test_prepare_for_list_returns_stale_snapshot_with_refresh_flag() -> None:
    service = build_runtime_service()
    subscription = build_subscription()
    snapshot = build_runtime_snapshot(
        subscription,
        refreshed_delta_seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS + 5,
        devices_count=2,
    )
    service.get_cached_runtime = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]

    prepared, should_refresh = run_async(service.prepare_for_list(subscription))

    assert should_refresh is True
    assert prepared.traffic_limit == snapshot.traffic_limit
    assert prepared.devices_count == 2


def test_prepare_for_list_returns_original_subscription_on_cache_miss() -> None:
    service = build_runtime_service()
    subscription = build_subscription()
    service.get_cached_runtime = AsyncMock(return_value=None)  # type: ignore[method-assign]

    prepared, should_refresh = run_async(service.prepare_for_list(subscription))

    assert should_refresh is True
    assert prepared is subscription


def test_prepare_for_list_batch_deduplicates_refresh_ids() -> None:
    service = build_runtime_service()
    subscriptions = [
        build_subscription(subscription_id=1, user_telegram_id=100),
        build_subscription(subscription_id=1, user_telegram_id=100),
        build_subscription(subscription_id=2, user_telegram_id=100),
    ]
    service.prepare_for_list = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            (subscriptions[0], True),
            (subscriptions[1], True),
            (subscriptions[2], False),
        ]
    )
    enqueue_runtime_refresh = AsyncMock()
    service._enqueue_runtime_refresh_if_needed = AsyncMock()  # type: ignore[method-assign]

    prepared = run_async(
        service.prepare_for_list_batch(
            subscriptions,
            user_telegram_id=100,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )
    )

    assert prepared == subscriptions
    service._enqueue_runtime_refresh_if_needed.assert_awaited_once_with(
        user_telegram_id=100,
        subscription_ids=[1, 1],
        enqueue_runtime_refresh=enqueue_runtime_refresh,
    )


def test_prepare_for_detail_falls_back_to_stale_snapshot_when_refresh_fails() -> None:
    service = build_runtime_service()
    subscription = build_subscription()
    snapshot = build_runtime_snapshot(
        subscription,
        refreshed_delta_seconds=SUBSCRIPTION_RUNTIME_CACHE_TTL_SECONDS + 5,
        devices_count=4,
    )
    service.get_cached_runtime = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]
    service._refresh_runtime_snapshot_for_subscription = AsyncMock(return_value=None)  # type: ignore[method-assign]

    prepared = run_async(service.prepare_for_detail(subscription))

    assert prepared.devices_count == 4
    service._refresh_runtime_snapshot_for_subscription.assert_awaited_once_with(subscription)


def test_apply_observed_devices_count_to_cached_runtime_updates_snapshot() -> None:
    service = build_runtime_service()
    subscription = build_subscription()
    snapshot = build_runtime_snapshot(subscription, devices_count=1)
    service.get_cached_runtime = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]
    service._store_runtime_snapshot = AsyncMock()  # type: ignore[method-assign]

    result = run_async(
        service.apply_observed_devices_count_to_cached_runtime(
            user_remna_id=subscription.user_remna_id,
            devices_count=5,
        )
    )

    assert result is True
    assert snapshot.devices_count == 5
    service._store_runtime_snapshot.assert_awaited_once()


def test_apply_device_event_to_cached_runtime_updates_device_count() -> None:
    service = build_runtime_service()
    subscription = build_subscription()
    snapshot = build_runtime_snapshot(subscription, devices_count=2)
    service.get_cached_runtime = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]
    service._store_runtime_snapshot = AsyncMock()  # type: ignore[method-assign]

    added = run_async(
        service.apply_device_event_to_cached_runtime(
            user_remna_id=subscription.user_remna_id,
            event="user_hwid_devices.added",
        )
    )
    assert added is True
    assert snapshot.devices_count == 3

    deleted = run_async(
        service.apply_device_event_to_cached_runtime(
            user_remna_id=subscription.user_remna_id,
            event="user_hwid_devices.deleted",
        )
    )
    assert deleted is True
    assert snapshot.devices_count == 2


def test_resolve_devices_count_after_event_handles_invalid_events() -> None:
    assert (
        SubscriptionRuntimeService._resolve_devices_count_after_event(
            0,
            "user_hwid_devices.added",
        )
        == 1
    )
    assert (
        SubscriptionRuntimeService._resolve_devices_count_after_event(
            1,
            "user_hwid_devices.deleted",
        )
        == 0
    )
    assert SubscriptionRuntimeService._resolve_devices_count_after_event(1, "UNKNOWN") is None


def test_refresh_user_subscriptions_runtime_groups_by_user() -> None:
    service = build_runtime_service()
    subscriptions = [
        build_subscription(subscription_id=1, user_telegram_id=100),
        build_subscription(subscription_id=2, user_telegram_id=100),
        build_subscription(subscription_id=3, user_telegram_id=200),
    ]
    service.subscription_service.get_by_ids = AsyncMock(return_value=subscriptions)
    service._refresh_runtime_snapshots_for_user = AsyncMock()  # type: ignore[method-assign]

    run_async(service.refresh_user_subscriptions_runtime([1, 2, 2, 3]))

    assert service._refresh_runtime_snapshots_for_user.await_count == 2
    grouped = [
        recorded_call.args[0]
        for recorded_call in service._refresh_runtime_snapshots_for_user.await_args_list
    ]
    assert [sub.id for sub in grouped[0]] == [1, 2]
    assert [sub.id for sub in grouped[1]] == [3]


def test_refresh_runtime_snapshot_for_subscription_persists_url_change_and_returns_snapshot(
) -> None:
    service = build_runtime_service()
    subscription = build_subscription(url="https://old.example")
    remna_user = SimpleNamespace(
        subscription_url=" https://new.example ",
        traffic_limit_bytes=200 * 1024 * 1024 * 1024,
        hwid_device_limit=5,
        user_traffic=SimpleNamespace(used_traffic_bytes=123),
    )
    service.remnawave_service.get_devices_by_subscription_uuid = AsyncMock(
        return_value=[SimpleNamespace(), SimpleNamespace()]
    )
    service._store_runtime_snapshot = AsyncMock()  # type: ignore[method-assign]
    service._persist_url_if_changed = AsyncMock()  # type: ignore[method-assign]

    snapshot = run_async(
        service._refresh_runtime_snapshot_for_subscription(
            subscription,
            remna_user=remna_user,
        )
    )

    assert snapshot is not None
    assert snapshot.traffic_limit == 200
    assert snapshot.device_limit == 5
    assert snapshot.devices_count == 2
    assert snapshot.url == "https://new.example"
    service._persist_url_if_changed.assert_awaited_once_with(subscription, "https://new.example")


def test_persist_url_if_changed_updates_only_when_normalized_url_changed() -> None:
    service = build_runtime_service()
    subscription = build_subscription(url="https://same.example")

    run_async(service._persist_url_if_changed(subscription, " https://same.example "))
    service.subscription_service.update.assert_not_awaited()

    run_async(service._persist_url_if_changed(subscription, " https://new.example "))
    service.subscription_service.update.assert_awaited_once_with(subscription)


def test_device_list_uses_fresh_cached_devices_when_available() -> None:
    subscription = build_subscription()
    snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(subscription.user_remna_id),
        devices=[
            SubscriptionDeviceItem(
                hwid="hwid-1",
                device_type="ANDROID",
                first_connected=None,
                last_connected=None,
            )
        ],
        refreshed_at=datetime_now(),
    )
    device_service = build_device_service()
    device_service._get_owned_subscription = AsyncMock(return_value=subscription)  # type: ignore[method-assign]
    device_service.get_cached_device_list = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]

    result = run_async(
        device_service.list_devices(
            subscription_id=subscription.id or 0,
            user_telegram_id=subscription.user_telegram_id,
        )
    )

    assert result.devices_count == 1
    assert result.devices[0].hwid == "hwid-1"
    device_service.remnawave_service.get_devices_by_subscription_uuid.assert_not_awaited()


def test_device_list_falls_back_to_cached_devices_on_panel_failure() -> None:
    subscription = build_subscription()
    stale_snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id=str(subscription.user_remna_id),
        devices=[
            SubscriptionDeviceItem(
                hwid="hwid-1",
                device_type="ANDROID",
                first_connected=None,
                last_connected=None,
            )
        ],
        refreshed_at=datetime_now() - timedelta(seconds=60),
    )
    runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=SimpleNamespace(devices_count=5)),
        prepare_for_detail=AsyncMock(),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(),
    )
    remnawave_service = SimpleNamespace(
        get_devices_by_subscription_uuid=AsyncMock(side_effect=RuntimeError("panel down")),
        get_subscription_url=AsyncMock(return_value=""),
        delete_device_by_subscription_uuid=AsyncMock(return_value=1),
    )
    device_service = build_device_service(
        runtime_service=runtime_service,
        remnawave_service=remnawave_service,
    )
    device_service._get_owned_subscription = AsyncMock(return_value=subscription)  # type: ignore[method-assign]
    device_service.get_cached_device_list = AsyncMock(return_value=stale_snapshot)  # type: ignore[method-assign]
    device_service._resolve_cached_devices_count = AsyncMock(return_value=5)  # type: ignore[method-assign]

    result = run_async(
        device_service.list_devices(
            subscription_id=subscription.id or 0,
            user_telegram_id=subscription.user_telegram_id,
        )
    )

    assert result.devices_count == 5
    assert [device.hwid for device in result.devices] == ["hwid-1"]


def test_get_owned_subscription_raises_for_missing_and_foreign_subscription() -> None:
    device_service = build_device_service()
    subscription = build_subscription(user_telegram_id=200)
    device_service.subscription_service.get = AsyncMock(side_effect=[None, subscription])

    with pytest.raises(SubscriptionDeviceNotFoundError):
        run_async(
            device_service._get_owned_subscription(
                subscription_id=10,
                user_telegram_id=100,
            )
        )

    with pytest.raises(SubscriptionDeviceAccessDeniedError):
        run_async(
            device_service._get_owned_subscription(
                subscription_id=10,
                user_telegram_id=100,
            )
        )


def test_apply_device_event_to_cached_list_preserves_add_delete_invalid_and_empty_hwid_behavior(
) -> None:
    device_service = build_device_service()
    snapshot = SubscriptionDeviceListSnapshot(
        user_remna_id="user-1",
        devices=[
            SubscriptionDeviceItem(
                hwid="old-hwid",
                device_type="ANDROID",
                first_connected=None,
                last_connected=None,
            )
        ],
        refreshed_at=datetime_now(),
    )
    device_service.get_cached_device_list = AsyncMock(return_value=snapshot)  # type: ignore[method-assign]
    device_service._store_cached_device_list = AsyncMock()  # type: ignore[method-assign]

    added = run_async(
        device_service.apply_device_event_to_cached_list(
            user_remna_id="user-1",
            event="user_hwid_devices.added",
            hwid_device=SimpleNamespace(
                hwid="new-hwid",
                platform="ios",
                created_at=datetime_now(),
                updated_at=datetime_now(),
            ),
        )
    )
    assert added is not None
    assert {device.hwid for device in added.devices} == {"old-hwid", "new-hwid"}

    deleted = run_async(
        device_service.apply_device_event_to_cached_list(
            user_remna_id="user-1",
            event="user_hwid_devices.deleted",
            hwid_device=SimpleNamespace(hwid="old-hwid"),
        )
    )
    assert deleted is not None
    assert {device.hwid for device in deleted.devices} == {"new-hwid"}

    invalid = run_async(
        device_service.apply_device_event_to_cached_list(
            user_remna_id="user-1",
            event="invalid-event",
            hwid_device=SimpleNamespace(hwid="ignored"),
        )
    )
    assert invalid is None

    empty_hwid = run_async(
        device_service.apply_device_event_to_cached_list(
            user_remna_id="user-1",
            event="user_hwid_devices.added",
            hwid_device=SimpleNamespace(hwid="", platform="android"),
        )
    )
    assert empty_hwid is None


def test_resolve_cached_devices_count_prefers_runtime_cache_and_falls_back_to_subscription(
) -> None:
    subscription = build_subscription(devices_count=2)
    runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(
            side_effect=[SimpleNamespace(devices_count=5), None]
        ),
        prepare_for_detail=AsyncMock(return_value=subscription),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(),
    )
    device_service = build_device_service(runtime_service=runtime_service)

    cached_count = run_async(device_service._resolve_cached_devices_count(subscription))
    fallback_count = run_async(device_service._resolve_cached_devices_count(subscription))

    assert cached_count == 5
    assert fallback_count == 2


def test_persist_subscription_url_if_changed_only_updates_when_url_changes() -> None:
    subscription = build_subscription(url="https://same.example")
    device_service = build_device_service()

    run_async(
        device_service._persist_subscription_url_if_changed(
            subscription=subscription,
            normalized_subscription_url="https://same.example",
        )
    )
    device_service.subscription_service.update.assert_not_awaited()

    run_async(
        device_service._persist_subscription_url_if_changed(
            subscription=subscription,
            normalized_subscription_url="https://new.example",
        )
    )
    device_service.subscription_service.update.assert_awaited_once_with(subscription)


def test_resolve_requested_device_type_and_map_panel_device_item_preserve_current_behavior(
) -> None:
    device_service = build_device_service()

    assert device_service._resolve_requested_device_type(None) == "UNKNOWN"
    assert device_service._resolve_requested_device_type(DeviceType.ANDROID) == "ANDROID"
    assert (
        device_service._resolve_requested_device_type(SimpleNamespace(value="WINDOWS"))  # type: ignore[arg-type]
        == "WINDOWS"
    )

    created_at = datetime_now()
    updated_at = datetime_now()
    item = device_service._map_panel_device_to_device_item(
        SimpleNamespace(
            hwid="hwid-1",
            platform="macos",
            created_at=created_at,
            updated_at=updated_at,
        )
    )
    assert item.hwid == "hwid-1"
    assert item.device_type == DeviceType.MAC.value
    assert item.first_connected == created_at.isoformat()
    assert item.last_connected == updated_at.isoformat()


def test_generate_device_link_enforces_limit_and_persists_url_behavior() -> None:
    limited_subscription = build_subscription(device_limit=2, devices_count=2)
    runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=None),
        prepare_for_detail=AsyncMock(return_value=limited_subscription),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(),
    )
    device_service = build_device_service(runtime_service=runtime_service)
    device_service._get_owned_subscription = AsyncMock(return_value=limited_subscription)  # type: ignore[method-assign]

    with pytest.raises(SubscriptionDeviceLimitReachedError):
        run_async(
            device_service.generate_device_link(
                subscription_id=limited_subscription.id or 0,
                user_telegram_id=limited_subscription.user_telegram_id,
                device_type=DeviceType.ANDROID,
            )
        )

    open_subscription = build_subscription(url="", device_limit=3, devices_count=1)
    runtime_service.prepare_for_detail = AsyncMock(return_value=open_subscription)
    device_service._get_owned_subscription = AsyncMock(return_value=open_subscription)  # type: ignore[method-assign]
    device_service.remnawave_service.get_subscription_url = AsyncMock(
        return_value=" https://new.example/sub "
    )
    device_service._persist_subscription_url_if_changed = AsyncMock()  # type: ignore[method-assign]

    result = run_async(
        device_service.generate_device_link(
            subscription_id=open_subscription.id or 0,
            user_telegram_id=open_subscription.user_telegram_id,
            device_type=DeviceType.ANDROID,
        )
    )

    assert result.connection_url == "https://new.example/sub"
    assert result.device_type == DeviceType.ANDROID.value
    device_service._persist_subscription_url_if_changed.assert_awaited_once_with(
        subscription=open_subscription,
        normalized_subscription_url="https://new.example/sub",
    )


def test_revoke_device_updates_cached_list_and_runtime_count() -> None:
    subscription = build_subscription()
    runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=None),
        prepare_for_detail=AsyncMock(return_value=subscription),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(),
    )
    remnawave_service = SimpleNamespace(
        get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
        get_subscription_url=AsyncMock(return_value=""),
        delete_device_by_subscription_uuid=AsyncMock(return_value=1),
    )
    device_service = build_device_service(
        runtime_service=runtime_service,
        remnawave_service=remnawave_service,
    )
    device_service._get_owned_subscription = AsyncMock(return_value=subscription)  # type: ignore[method-assign]
    device_service.apply_device_event_to_cached_list = AsyncMock(  # type: ignore[method-assign]
        return_value=SubscriptionDeviceListSnapshot(
            user_remna_id=str(subscription.user_remna_id),
            devices=[],
            refreshed_at=datetime_now(),
        )
    )

    result = run_async(
        device_service.revoke_device(
            subscription_id=subscription.id or 0,
            user_telegram_id=subscription.user_telegram_id,
            hwid="hwid-1",
        )
    )

    assert result.success is True
    runtime_service.apply_observed_devices_count_to_cached_runtime.assert_awaited_once_with(
        user_remna_id=subscription.user_remna_id,
        devices_count=0,
    )


def test_generate_device_link_wraps_unexpected_errors() -> None:
    subscription = build_subscription(url="", device_limit=3, devices_count=0)
    runtime_service = SimpleNamespace(
        get_cached_runtime=AsyncMock(return_value=None),
        prepare_for_detail=AsyncMock(return_value=subscription),
        apply_observed_devices_count_to_cached_runtime=AsyncMock(),
    )
    remnawave_service = SimpleNamespace(
        get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
        get_subscription_url=AsyncMock(side_effect=RuntimeError("panel down")),
        delete_device_by_subscription_uuid=AsyncMock(return_value=1),
    )
    device_service = build_device_service(
        runtime_service=runtime_service,
        remnawave_service=remnawave_service,
    )
    device_service._get_owned_subscription = AsyncMock(return_value=subscription)  # type: ignore[method-assign]

    with pytest.raises(SubscriptionDeviceOperationError):
        run_async(
            device_service.generate_device_link(
                subscription_id=subscription.id or 0,
                user_telegram_id=subscription.user_telegram_id,
                device_type=DeviceType.ANDROID,
            )
        )
