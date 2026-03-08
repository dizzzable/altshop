from __future__ import annotations

import asyncio
import inspect
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from src.api.endpoints.user_subscription import get_subscription, list_subscriptions
from src.core.enums import RemnaUserHwidDevicesEvent
from src.core.utils.formatters import format_gb_to_bytes
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto
from src.services.subscription_runtime import (
    SubscriptionRuntimeService,
    SubscriptionRuntimeSnapshot,
)

LIST_SUBSCRIPTIONS_ENDPOINT = getattr(
    inspect.unwrap(list_subscriptions),
    "__dishka_orig_func__",
    inspect.unwrap(list_subscriptions),
)
GET_SUBSCRIPTION_ENDPOINT = getattr(
    inspect.unwrap(get_subscription),
    "__dishka_orig_func__",
    inspect.unwrap(get_subscription),
)


def _build_subscription(
    *,
    subscription_id: int,
    user_telegram_id: int,
    traffic_limit: int = 50,
    device_limit: int = 3,
    traffic_used: int = 0,
    devices_count: int = 0,
    url: str = "https://snapshot.local/sub",
) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=uuid4(),
        user_telegram_id=user_telegram_id,
        traffic_limit=traffic_limit,
        traffic_used=traffic_used,
        device_limit=device_limit,
        devices_count=devices_count,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime_now() + timedelta(days=30),
        url=url,
        plan=PlanSnapshotDto.test(),
    )


def _build_runtime_service(
    *,
    redis_repository: object | None = None,
    subscription_service: object | None = None,
    remnawave_service: object | None = None,
    redis_client: object | None = None,
) -> SubscriptionRuntimeService:
    return SubscriptionRuntimeService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=redis_client or SimpleNamespace(set=AsyncMock(return_value=True)),
        redis_repository=redis_repository or SimpleNamespace(get=AsyncMock(return_value=None)),
        translator_hub=SimpleNamespace(),
        subscription_service=subscription_service
        or SimpleNamespace(
            get=AsyncMock(return_value=None),
            get_by_ids=AsyncMock(return_value=[]),
            update=AsyncMock(),
        ),
        remnawave_service=remnawave_service
        or SimpleNamespace(
            get_users_by_telegram_id=AsyncMock(return_value=[]),
            get_user=AsyncMock(return_value=None),
            get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
        ),
    )


def test_prepare_for_list_uses_fresh_runtime_cache() -> None:
    subscription = _build_subscription(subscription_id=1, user_telegram_id=1001)
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=subscription.user_remna_id,
        traffic_used=777,
        traffic_limit=123,
        device_limit=9,
        devices_count=4,
        url="https://runtime.local/subscription",
        refreshed_at=datetime_now(),
    )
    redis_repository = SimpleNamespace(get=AsyncMock(return_value=snapshot))
    service = _build_runtime_service(redis_repository=redis_repository)

    prepared_subscription, should_refresh = asyncio.run(service.prepare_for_list(subscription))

    assert should_refresh is False
    assert prepared_subscription.traffic_used == snapshot.traffic_used
    assert prepared_subscription.traffic_limit == snapshot.traffic_limit
    assert prepared_subscription.device_limit == snapshot.device_limit
    assert prepared_subscription.devices_count == snapshot.devices_count
    assert prepared_subscription.url == snapshot.url


def test_apply_device_event_to_cached_runtime_increments_count() -> None:
    user_remna_id = uuid4()
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=user_remna_id,
        traffic_used=100,
        traffic_limit=50,
        device_limit=3,
        devices_count=1,
        url="https://runtime.local/subscription",
        refreshed_at=datetime_now() - timedelta(seconds=5),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_runtime_service(redis_repository=redis_repository)

    updated = asyncio.run(
        service.apply_device_event_to_cached_runtime(
            user_remna_id=user_remna_id,
            event=RemnaUserHwidDevicesEvent.ADDED,
        )
    )

    assert updated is True
    redis_repository.set.assert_awaited_once()
    cached_snapshot = redis_repository.set.await_args.args[1]
    assert isinstance(cached_snapshot, SubscriptionRuntimeSnapshot)
    assert cached_snapshot.devices_count == 2


def test_apply_device_event_to_cached_runtime_clamps_deleted_count_to_zero() -> None:
    user_remna_id = uuid4()
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=user_remna_id,
        traffic_used=100,
        traffic_limit=50,
        device_limit=3,
        devices_count=0,
        url="https://runtime.local/subscription",
        refreshed_at=datetime_now() - timedelta(seconds=5),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_runtime_service(redis_repository=redis_repository)

    updated = asyncio.run(
        service.apply_device_event_to_cached_runtime(
            user_remna_id=user_remna_id,
            event=RemnaUserHwidDevicesEvent.DELETED,
        )
    )

    assert updated is True
    redis_repository.set.assert_awaited_once()
    cached_snapshot = redis_repository.set.await_args.args[1]
    assert isinstance(cached_snapshot, SubscriptionRuntimeSnapshot)
    assert cached_snapshot.devices_count == 0


def test_apply_device_event_updates_devices_freshness_without_refreshing_core() -> None:
    user_remna_id = uuid4()
    stale_core_time = datetime_now() - timedelta(seconds=95)
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=user_remna_id,
        traffic_used=100,
        traffic_limit=50,
        device_limit=3,
        devices_count=1,
        url="https://runtime.local/subscription",
        refreshed_at=stale_core_time,
        core_refreshed_at=stale_core_time,
        devices_refreshed_at=stale_core_time,
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=snapshot),
        set=AsyncMock(return_value=None),
    )
    redis_client = SimpleNamespace(
        set=AsyncMock(return_value=True),
        ttl=AsyncMock(return_value=17),
    )
    service = _build_runtime_service(
        redis_repository=redis_repository,
        redis_client=redis_client,
    )

    updated = asyncio.run(
        service.apply_device_event_to_cached_runtime(
            user_remna_id=user_remna_id,
            event=RemnaUserHwidDevicesEvent.ADDED,
        )
    )

    assert updated is True
    cached_snapshot = redis_repository.set.await_args.args[1]
    assert isinstance(cached_snapshot, SubscriptionRuntimeSnapshot)
    assert cached_snapshot.refreshed_at == stale_core_time
    assert cached_snapshot.core_refreshed_at == stale_core_time
    assert cached_snapshot.devices_refreshed_at is not None
    assert cached_snapshot.devices_refreshed_at > stale_core_time
    assert redis_repository.set.await_args.kwargs["ex"] == 17


def test_apply_device_event_to_cached_runtime_returns_false_without_snapshot() -> None:
    user_remna_id = uuid4()
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    service = _build_runtime_service(redis_repository=redis_repository)

    updated = asyncio.run(
        service.apply_device_event_to_cached_runtime(
            user_remna_id=user_remna_id,
            event=RemnaUserHwidDevicesEvent.ADDED,
        )
    )

    assert updated is False
    redis_repository.set.assert_not_awaited()


def test_apply_observed_devices_count_to_cached_runtime_overwrites_count() -> None:
    user_remna_id = uuid4()
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=user_remna_id,
        traffic_used=100,
        traffic_limit=50,
        device_limit=3,
        devices_count=1,
        url="https://runtime.local/subscription",
        refreshed_at=datetime_now() - timedelta(seconds=5),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=snapshot),
        set=AsyncMock(return_value=None),
    )
    service = _build_runtime_service(redis_repository=redis_repository)

    updated = asyncio.run(
        service.apply_observed_devices_count_to_cached_runtime(
            user_remna_id=user_remna_id,
            devices_count=4,
        )
    )

    assert updated is True
    redis_repository.set.assert_awaited_once()
    cached_snapshot = redis_repository.set.await_args.args[1]
    assert isinstance(cached_snapshot, SubscriptionRuntimeSnapshot)
    assert cached_snapshot.devices_count == 4


def test_prepare_for_list_returns_local_snapshot_on_cache_miss() -> None:
    subscription = _build_subscription(
        subscription_id=2,
        user_telegram_id=2002,
        traffic_used=11,
        devices_count=2,
    )
    redis_repository = SimpleNamespace(get=AsyncMock(return_value=None))
    service = _build_runtime_service(redis_repository=redis_repository)

    prepared_subscription, should_refresh = asyncio.run(service.prepare_for_list(subscription))

    assert should_refresh is True
    assert prepared_subscription.traffic_used == 11
    assert prepared_subscription.devices_count == 2
    assert prepared_subscription.url == subscription.url


def test_prepare_for_list_uses_stale_runtime_cache_and_requests_refresh() -> None:
    subscription = _build_subscription(subscription_id=21, user_telegram_id=2100, traffic_used=5)
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=subscription.user_remna_id,
        traffic_used=512,
        traffic_limit=77,
        device_limit=4,
        devices_count=6,
        url="https://runtime.local/stale",
        refreshed_at=datetime_now() - timedelta(seconds=90),
    )
    redis_repository = SimpleNamespace(get=AsyncMock(return_value=snapshot))
    service = _build_runtime_service(redis_repository=redis_repository)

    prepared_subscription, should_refresh = asyncio.run(service.prepare_for_list(subscription))

    assert should_refresh is True
    assert prepared_subscription.traffic_used == 512
    assert prepared_subscription.traffic_limit == 77
    assert prepared_subscription.device_limit == 4
    assert prepared_subscription.devices_count == 6
    assert prepared_subscription.url == "https://runtime.local/stale"


def test_prepare_for_list_requests_refresh_when_only_devices_timestamp_is_fresh() -> None:
    subscription = _build_subscription(subscription_id=22, user_telegram_id=2200, traffic_used=5)
    stale_core_time = datetime_now() - timedelta(seconds=90)
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=subscription.user_remna_id,
        traffic_used=512,
        traffic_limit=77,
        device_limit=4,
        devices_count=9,
        url="https://runtime.local/stale-core",
        refreshed_at=stale_core_time,
        core_refreshed_at=stale_core_time,
        devices_refreshed_at=datetime_now(),
    )
    redis_repository = SimpleNamespace(get=AsyncMock(return_value=snapshot))
    service = _build_runtime_service(redis_repository=redis_repository)

    prepared_subscription, should_refresh = asyncio.run(service.prepare_for_list(subscription))

    assert should_refresh is True
    assert prepared_subscription.devices_count == 9
    assert prepared_subscription.url == "https://runtime.local/stale-core"


def test_refresh_subscription_runtime_snapshot_writes_cache_and_persists_url() -> None:
    subscription = _build_subscription(
        subscription_id=3,
        user_telegram_id=3003,
        url="",
    )
    remna_user = SimpleNamespace(
        user_traffic=SimpleNamespace(used_traffic_bytes=2048),
        traffic_limit_bytes=format_gb_to_bytes(64),
        hwid_device_limit=5,
        subscription_url="https://runtime.local/fresh",
    )
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=subscription),
        update=AsyncMock(return_value=subscription),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=remna_user),
        get_devices_by_subscription_uuid=AsyncMock(return_value=[object(), object(), object()]),
    )
    service = _build_runtime_service(
        redis_repository=redis_repository,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )

    asyncio.run(service.refresh_subscription_runtime_snapshot(subscription.id or 0))

    redis_repository.set.assert_awaited_once()
    subscription_service.update.assert_awaited_once()
    cached_snapshot = redis_repository.set.await_args.args[1]
    assert isinstance(cached_snapshot, SubscriptionRuntimeSnapshot)
    assert cached_snapshot.traffic_used == 2048
    assert cached_snapshot.traffic_limit == 64
    assert cached_snapshot.device_limit == 5
    assert cached_snapshot.devices_count == 3
    assert cached_snapshot.url == "https://runtime.local/fresh"


def test_prepare_for_detail_refreshes_live_runtime_once_on_cache_miss() -> None:
    subscription = _build_subscription(
        subscription_id=31,
        user_telegram_id=3100,
        traffic_used=1,
        devices_count=1,
        url="",
    )
    remna_user = SimpleNamespace(
        user_traffic=SimpleNamespace(used_traffic_bytes=4096),
        traffic_limit_bytes=format_gb_to_bytes(128),
        hwid_device_limit=8,
        subscription_url="https://runtime.local/detail",
    )
    subscription_service = SimpleNamespace(update=AsyncMock(return_value=subscription))
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=remna_user),
        get_devices_by_subscription_uuid=AsyncMock(return_value=[object(), object()]),
    )
    service = _build_runtime_service(
        redis_repository=redis_repository,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )

    prepared_subscription = asyncio.run(service.prepare_for_detail(subscription))

    assert prepared_subscription.traffic_used == 4096
    assert prepared_subscription.traffic_limit == 128
    assert prepared_subscription.device_limit == 8
    assert prepared_subscription.devices_count == 2
    assert prepared_subscription.url == "https://runtime.local/detail"
    remnawave_service.get_user.assert_awaited_once_with(subscription.user_remna_id)
    remnawave_service.get_devices_by_subscription_uuid.assert_awaited_once_with(
        subscription.user_remna_id
    )
    redis_repository.set.assert_awaited_once()
    subscription_service.update.assert_awaited_once()


def test_prepare_for_detail_uses_fresh_cache_without_remote_calls() -> None:
    subscription = _build_subscription(subscription_id=32, user_telegram_id=3200)
    snapshot = SubscriptionRuntimeSnapshot(
        user_remna_id=subscription.user_remna_id,
        traffic_used=1234,
        traffic_limit=60,
        device_limit=2,
        devices_count=1,
        url="https://runtime.local/cached",
        refreshed_at=datetime_now(),
    )
    redis_repository = SimpleNamespace(get=AsyncMock(return_value=snapshot))
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(),
        get_devices_by_subscription_uuid=AsyncMock(),
    )
    service = _build_runtime_service(
        redis_repository=redis_repository,
        remnawave_service=remnawave_service,
    )

    prepared_subscription = asyncio.run(service.prepare_for_detail(subscription))

    assert prepared_subscription.traffic_used == 1234
    assert prepared_subscription.url == "https://runtime.local/cached"
    remnawave_service.get_user.assert_not_awaited()
    remnawave_service.get_devices_by_subscription_uuid.assert_not_awaited()


def test_prepare_for_list_batch_enqueues_single_background_refresh() -> None:
    current_user = SimpleNamespace(telegram_id=4004)
    subscriptions = [
        _build_subscription(subscription_id=10, user_telegram_id=current_user.telegram_id),
        _build_subscription(subscription_id=11, user_telegram_id=current_user.telegram_id),
    ]
    service = _build_runtime_service()
    service.prepare_for_list = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            (subscriptions[0], True),
            (subscriptions[1], True),
        ]
    )
    service.acquire_refresh_lock = AsyncMock(return_value=True)  # type: ignore[method-assign]
    enqueue_runtime_refresh = AsyncMock(return_value=None)

    prepared_subscriptions = asyncio.run(
        service.prepare_for_list_batch(
            subscriptions,
            user_telegram_id=current_user.telegram_id,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )
    )

    assert [item.id for item in prepared_subscriptions] == [10, 11]
    enqueue_runtime_refresh.assert_awaited_once_with([10, 11])
    service.acquire_refresh_lock.assert_awaited_once_with(current_user.telegram_id)


def test_prepare_for_list_batch_skips_enqueue_on_cache_hit() -> None:
    current_user = SimpleNamespace(telegram_id=5005)
    subscription = _build_subscription(
        subscription_id=12,
        user_telegram_id=current_user.telegram_id,
        traffic_used=999,
    )
    service = _build_runtime_service()
    service.prepare_for_list = AsyncMock(return_value=(subscription, False))  # type: ignore[method-assign]
    service.acquire_refresh_lock = AsyncMock(return_value=True)  # type: ignore[method-assign]
    enqueue_runtime_refresh = AsyncMock(return_value=None)

    prepared_subscriptions = asyncio.run(
        service.prepare_for_list_batch(
            [subscription],
            user_telegram_id=current_user.telegram_id,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )
    )

    assert prepared_subscriptions[0].traffic_used == 999
    enqueue_runtime_refresh.assert_not_awaited()
    service.acquire_refresh_lock.assert_not_awaited()


def test_prepare_for_list_batch_skips_enqueue_when_lock_is_busy() -> None:
    current_user = SimpleNamespace(telegram_id=5105)
    subscription = _build_subscription(
        subscription_id=13,
        user_telegram_id=current_user.telegram_id,
    )
    service = _build_runtime_service()
    service.prepare_for_list = AsyncMock(return_value=(subscription, True))  # type: ignore[method-assign]
    service.acquire_refresh_lock = AsyncMock(return_value=False)  # type: ignore[method-assign]
    enqueue_runtime_refresh = AsyncMock(return_value=None)

    prepared_subscriptions = asyncio.run(
        service.prepare_for_list_batch(
            [subscription],
            user_telegram_id=current_user.telegram_id,
            enqueue_runtime_refresh=enqueue_runtime_refresh,
        )
    )

    assert prepared_subscriptions[0].id == 13
    enqueue_runtime_refresh.assert_not_awaited()
    service.acquire_refresh_lock.assert_awaited_once_with(current_user.telegram_id)


def test_list_subscriptions_delegates_to_batch_runtime_preparation() -> None:
    current_user = SimpleNamespace(telegram_id=5205)
    subscriptions = [
        _build_subscription(subscription_id=14, user_telegram_id=current_user.telegram_id),
    ]
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock(return_value=subscriptions))
    prepared_subscriptions = [
        _build_subscription(
            subscription_id=14,
            user_telegram_id=current_user.telegram_id,
            traffic_used=321,
        )
    ]
    subscription_runtime_service = SimpleNamespace(
        prepare_for_list_batch=AsyncMock(return_value=prepared_subscriptions)
    )

    response = asyncio.run(
        LIST_SUBSCRIPTIONS_ENDPOINT(
            current_user=current_user,
            subscription_service=subscription_service,
            subscription_runtime_service=subscription_runtime_service,
        )
    )

    assert response.subscriptions[0].traffic_used == 321
    subscription_runtime_service.prepare_for_list_batch.assert_awaited_once()
    await_args = subscription_runtime_service.prepare_for_list_batch.await_args
    assert await_args.kwargs["subscriptions"] == subscriptions
    assert await_args.kwargs["user_telegram_id"] == current_user.telegram_id
    assert callable(await_args.kwargs["enqueue_runtime_refresh"])


def test_get_subscription_delegates_detail_lookup_to_subscription_portal_service() -> None:
    current_user = SimpleNamespace(telegram_id=6006)
    subscription = _build_subscription(
        subscription_id=44,
        user_telegram_id=current_user.telegram_id,
        traffic_used=55,
    )
    subscription_portal_service = SimpleNamespace(
        get_detail=AsyncMock(return_value=subscription)
    )

    response = asyncio.run(
        GET_SUBSCRIPTION_ENDPOINT(
            subscription_id=subscription.id,
            current_user=current_user,
            subscription_portal_service=subscription_portal_service,
        )
    )

    assert response.id == 44
    subscription_portal_service.get_detail.assert_awaited_once_with(
        subscription_id=subscription.id,
        current_user=current_user,
    )


def test_refresh_user_subscriptions_runtime_batches_user_lookup_and_limits_concurrency() -> None:
    subscriptions = [
        _build_subscription(subscription_id=index, user_telegram_id=7007)
        for index in range(1, 8)
    ]
    panel_users = [
        SimpleNamespace(
            uuid=subscription.user_remna_id,
            user_traffic=SimpleNamespace(used_traffic_bytes=2048),
            traffic_limit_bytes=format_gb_to_bytes(64),
            hwid_device_limit=5,
            subscription_url=f"https://runtime.local/{subscription.id}",
        )
        for subscription in subscriptions
    ]
    subscription_service = SimpleNamespace(
        get_by_ids=AsyncMock(return_value=subscriptions),
        get=AsyncMock(return_value=None),
        update=AsyncMock(),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    remnawave_service = SimpleNamespace(
        get_users_by_telegram_id=AsyncMock(return_value=panel_users),
        get_user=AsyncMock(return_value=None),
        get_devices_by_subscription_uuid=AsyncMock(),
    )
    service = _build_runtime_service(
        subscription_service=subscription_service,
        redis_repository=redis_repository,
        remnawave_service=remnawave_service,
    )

    active = 0
    max_active = 0

    async def fake_get_devices(_user_remna_id: object) -> list[object]:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return [object()]

    remnawave_service.get_devices_by_subscription_uuid.side_effect = fake_get_devices

    asyncio.run(service.refresh_user_subscriptions_runtime([1, 2, 3, 4, 5, 6, 1, 2, 7]))

    subscription_service.get_by_ids.assert_awaited_once_with([1, 2, 3, 4, 5, 6, 7])
    remnawave_service.get_users_by_telegram_id.assert_awaited_once_with(7007)
    remnawave_service.get_user.assert_not_awaited()
    assert remnawave_service.get_devices_by_subscription_uuid.await_count == 7
    assert redis_repository.set.await_count == 7
    assert max_active <= 5


def test_refresh_user_subscriptions_runtime_falls_back_to_direct_lookup_for_missing_prefetch(
) -> None:
    subscription = _build_subscription(subscription_id=81, user_telegram_id=8008)
    panel_user = SimpleNamespace(
        uuid=subscription.user_remna_id,
        user_traffic=SimpleNamespace(used_traffic_bytes=1024),
        traffic_limit_bytes=format_gb_to_bytes(32),
        hwid_device_limit=3,
        subscription_url="https://runtime.local/fallback",
    )
    subscription_service = SimpleNamespace(
        get_by_ids=AsyncMock(return_value=[subscription]),
        get=AsyncMock(return_value=None),
        update=AsyncMock(),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=None),
    )
    remnawave_service = SimpleNamespace(
        get_users_by_telegram_id=AsyncMock(return_value=[]),
        get_user=AsyncMock(return_value=panel_user),
        get_devices_by_subscription_uuid=AsyncMock(return_value=[]),
    )
    service = _build_runtime_service(
        subscription_service=subscription_service,
        redis_repository=redis_repository,
        remnawave_service=remnawave_service,
    )

    asyncio.run(service.refresh_user_subscriptions_runtime([subscription.id or 0]))

    remnawave_service.get_users_by_telegram_id.assert_awaited_once_with(8008)
    remnawave_service.get_user.assert_awaited_once_with(subscription.user_remna_id)
    redis_repository.set.assert_awaited_once()
