from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import ValidationError
from remnawave.enums.users import TrafficLimitStrategy

import src.infrastructure.taskiq.tasks.notifications as notification_tasks
import src.infrastructure.taskiq.tasks.subscriptions as subscription_tasks
from src.core.constants import MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import (
    DeviceType,
    PlanType,
    RemnaNodeEvent,
    RemnaUserEvent,
    RemnaUserHwidDevicesEvent,
    SubscriptionStatus,
    SystemNotificationType,
)
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
)
from src.services.remnawave import RemnawaveService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_plan_snapshot(*, name: str = "Starter") -> PlanSnapshotDto:
    snapshot = PlanSnapshotDto.test()
    snapshot.id = 1
    snapshot.name = name
    snapshot.tag = "starter"
    snapshot.type = PlanType.BOTH
    snapshot.traffic_limit = 100
    snapshot.device_limit = 1
    snapshot.duration = 30
    snapshot.internal_squads = []
    snapshot.external_squad = None
    snapshot.traffic_limit_strategy = TrafficLimitStrategy.NO_RESET
    return snapshot


def build_plan(*, plan_id: int, tag: str, order_index: int = 0, name: str | None = None) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=name or f"Plan {plan_id}",
        tag=tag,
        is_active=True,
        order_index=order_index,
        type=PlanType.BOTH,
        traffic_limit=100,
        device_limit=1,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        internal_squads=[],
        external_squad=None,
    )


def _build_validation_error() -> ValidationError:
    return ValidationError.from_exception_data(
        "GetStatsResponseDto",
        [
            {
                "type": "missing",
                "loc": ("cpu", "physicalCores"),
                "input": {"cores": 1},
            }
        ],
    )


def test_try_connection_falls_back_to_raw_health_check_on_validation_error() -> None:
    remnawave = SimpleNamespace(
        system=SimpleNamespace(
            get_stats=AsyncMock(side_effect=_build_validation_error())
        )
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._try_connection_raw = AsyncMock()  # type: ignore[method-assign]

    run_async(service.try_connection())

    service._try_connection_raw.assert_awaited_once()


def test_get_external_squads_safe_falls_back_to_raw_http_on_validation_error() -> None:
    remnawave = SimpleNamespace(
        external_squads=SimpleNamespace(
            get_external_squads=AsyncMock(side_effect=_build_validation_error())
        )
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._get_external_squads_raw = AsyncMock(  # type: ignore[method-assign]
        return_value=[{"uuid": UUID("00000000-0000-0000-0000-000000000001"), "name": "Team"}]
    )

    result = run_async(service.get_external_squads_safe())

    assert result == [{"uuid": UUID("00000000-0000-0000-0000-000000000001"), "name": "Team"}]
    service._get_external_squads_raw.assert_awaited_once()


def test_try_connection_raw_uses_shared_request_helper() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._request_raw_api_response = AsyncMock()  # type: ignore[method-assign]

    run_async(service._try_connection_raw())

    service._request_raw_api_response.assert_awaited_once()
    assert service._request_raw_api_response.await_args.args[0] == "/system/stats"


def test_get_external_squads_raw_uses_shared_request_helper() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._request_raw_api_json = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "response": {
                "externalSquads": [
                    {"uuid": "00000000-0000-0000-0000-000000000001", "name": "Team"},
                ]
            }
        }
    )

    result = run_async(service._get_external_squads_raw())

    assert result == [{"uuid": UUID("00000000-0000-0000-0000-000000000001"), "name": "Team"}]
    service._request_raw_api_json.assert_awaited_once_with("/external-squads")


def test_parse_external_squads_payload_handles_invalid_and_valid_shapes() -> None:
    assert RemnawaveService._parse_external_squads_payload(None) == []
    assert RemnawaveService._parse_external_squads_payload({"response": []}) == []
    assert RemnawaveService._parse_external_squads_payload(
        {"response": {"externalSquads": "bad"}}
    ) == []
    assert RemnawaveService._parse_external_squads_payload(
        {
            "response": {
                "externalSquads": [
                    "bad",
                    {"uuid": "not-a-uuid", "name": "Skip"},
                    {"uuid": "00000000-0000-0000-0000-000000000001", "name": "Team"},
                ]
            }
        }
    ) == [{"uuid": UUID("00000000-0000-0000-0000-000000000001"), "name": "Team"}]
    assert RemnawaveService._parse_external_squads_payload(
        {
            "external_squads": [
                {"uuid": "00000000-0000-0000-0000-000000000002", "name": "Team 2"}
            ]
        }
    ) == [{"uuid": UUID("00000000-0000-0000-0000-000000000002"), "name": "Team 2"}]


def test_try_connection_falls_back_to_raw_health_check_on_unexpected_response_type() -> None:
    remnawave = SimpleNamespace(
        system=SimpleNamespace(get_stats=AsyncMock(return_value={"ok": True}))
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._try_connection_raw = AsyncMock()  # type: ignore[method-assign]

    run_async(service.try_connection())

    service._try_connection_raw.assert_awaited_once()


def test_pick_group_sync_current_subscription_id_prefers_active_latest_subscription() -> None:
    now = datetime.now(timezone.utc)
    plan = PlanSnapshotDto(
        id=1,
        name="Starter",
        tag="starter",
        type=PlanType.BOTH,
        traffic_limit=100,
        device_limit=1,
        duration=30,
        internal_squads=[],
        external_squad=None,
    )
    active_old = SubscriptionDto(
        id=1,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000001"),
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=now + timedelta(days=5),
        url="https://example.com/1",
        device_type=DeviceType.OTHER,
        plan=plan.model_copy(deep=True),
    )
    active_new = SubscriptionDto(
        id=2,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000002"),
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=now + timedelta(days=30),
        url="https://example.com/2",
        device_type=DeviceType.OTHER,
        plan=plan.model_copy(deep=True),
    )
    deleted = SubscriptionDto(
        id=3,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000003"),
        status=SubscriptionStatus.DELETED,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=now + timedelta(days=40),
        url="https://example.com/3",
        device_type=DeviceType.OTHER,
        plan=plan.model_copy(deep=True),
    )

    selected = RemnawaveService._pick_group_sync_current_subscription_id(
        [active_old, active_new, deleted]
    )

    assert selected == 2


def test_sync_user_rebinds_existing_subscription_owner_by_remna_id() -> None:
    remnawave = SimpleNamespace()
    user = SimpleNamespace(telegram_id=605)
    existing_subscription = SimpleNamespace(
        id=10,
        user_telegram_id=8,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000010"),
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=SimpleNamespace(
            get_by_remna_id=AsyncMock(return_value=existing_subscription),
            get_current=AsyncMock(return_value=None),
            rebind_user=AsyncMock(return_value=existing_subscription),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._resolve_matched_plan_for_sync = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._hydrate_panel_subscription_url = AsyncMock()  # type: ignore[method-assign]
    service._update_subscription_from_sync = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(
        uuid=UUID("00000000-0000-0000-0000-000000000010"),
        telegram_id=605,
        model_dump=lambda: {
            "uuid": UUID("00000000-0000-0000-0000-000000000010"),
            "status": SubscriptionStatus.ACTIVE,
            "expire_at": datetime.now(timezone.utc) + timedelta(days=30),
            "subscription_url": "https://example.com/sub",
            "traffic_limit_bytes": 100 * 1024 * 1024 * 1024,
            "hwid_device_limit": 1,
            "active_internal_squads": [],
            "external_squad_uuid": None,
            "traffic_limit_strategy": None,
            "tag": "starter",
        },
    )

    run_async(service.sync_user(remna_user, creating=True))

    service.subscription_service.rebind_user.assert_awaited_once_with(
        subscription_id=10,
        user_telegram_id=605,
        previous_user_telegram_id=8,
        auto_commit=False,
    )


def test_create_user_rejects_when_effective_subscription_limit_would_be_exceeded() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=SimpleNamespace(users=SimpleNamespace(create_user=AsyncMock())),
        user_service=MagicMock(),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(
                return_value=[SimpleNamespace(status=SubscriptionStatus.ACTIVE)]
            )
        ),
        plan_service=MagicMock(),
        settings_service=SimpleNamespace(get_max_subscriptions_for_user=AsyncMock(return_value=1)),
    )
    user = SimpleNamespace(
        telegram_id=701,
        remna_name="rm_701",
        remna_description="user 701",
    )

    try:
        run_async(service.create_user(user, build_plan_snapshot()))
    except ValueError as error:
        assert "would exceed maximum subscriptions limit" in str(error)
    else:
        raise AssertionError("Expected ValueError for effective subscription limit guardrail")

    service.remnawave.users.create_user.assert_not_awaited()


def test_create_user_rejects_when_hard_subscription_ceiling_would_be_exceeded() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=SimpleNamespace(users=SimpleNamespace(create_user=AsyncMock())),
        user_service=MagicMock(),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(
                return_value=[
                    SimpleNamespace(status=SubscriptionStatus.ACTIVE)
                    for _ in range(MAX_SUBSCRIPTIONS_PER_USER)
                ]
            )
        ),
        plan_service=MagicMock(),
        settings_service=SimpleNamespace(
            get_max_subscriptions_for_user=AsyncMock(
                return_value=MAX_SUBSCRIPTIONS_PER_USER + 10
            )
        ),
    )
    user = SimpleNamespace(
        telegram_id=702,
        remna_name="rm_702",
        remna_description="user 702",
    )

    try:
        run_async(service.create_user(user, build_plan_snapshot()))
    except ValueError as error:
        assert "would exceed hard ceiling" in str(error)
    else:
        raise AssertionError("Expected ValueError for hard subscription ceiling")

    service.remnawave.users.create_user.assert_not_awaited()


def test_resolve_plan_by_limits_prefers_tag_matching_candidate() -> None:
    matching_first = build_plan(plan_id=1, tag="other", order_index=0, name="First")
    matching_second = build_plan(plan_id=2, tag="starter", order_index=9, name="Tagged")
    remna_subscription = RemnaSubscriptionDto(
        uuid=UUID("00000000-0000-0000-0000-000000000010"),
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime.now(timezone.utc) + timedelta(days=30),
        url="",
        traffic_limit=100,
        device_limit=1,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        tag="starter",
        internal_squads=[],
        external_squad=None,
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=SimpleNamespace(
            get_all=AsyncMock(return_value=[matching_first, matching_second])
        ),
        settings_service=MagicMock(),
    )

    selected = run_async(
        service._resolve_plan_by_limits(remna_subscription=remna_subscription, telegram_id=703)
    )

    assert selected is not None
    assert selected.id == matching_second.id


def test_sync_profiles_by_telegram_id_restores_original_current_subscription_when_still_valid(
) -> None:
    user = SimpleNamespace(telegram_id=704)
    original_subscription = SimpleNamespace(
        id=55,
        user_telegram_id=704,
        status=SubscriptionStatus.ACTIVE,
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(
            get=AsyncMock(side_effect=[user, user]),
            set_current_subscription=AsyncMock(),
            delete_current_subscription=AsyncMock(),
        ),
        subscription_service=SimpleNamespace(
            get_current=AsyncMock(return_value=original_subscription),
            get=AsyncMock(return_value=original_subscription),
            get_all_by_user=AsyncMock(return_value=[original_subscription]),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._sync_group_profile = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(uuid=UUID("00000000-0000-0000-0000-000000000055"), telegram_id=704)

    stats = run_async(service.sync_profiles_by_telegram_id(704, [remna_user]))

    assert stats.user_created is False
    service.user_service.set_current_subscription.assert_awaited_once_with(
        telegram_id=704,
        subscription_id=55,
    )
    service.user_service.delete_current_subscription.assert_not_awaited()


def test_sync_profiles_by_telegram_id_falls_back_to_best_remaining_active_subscription() -> None:
    user = SimpleNamespace(telegram_id=705)
    original_subscription = SimpleNamespace(
        id=60,
        user_telegram_id=705,
        status=SubscriptionStatus.ACTIVE,
    )
    fallback_limited = SubscriptionDto(
        id=61,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000061"),
        status=SubscriptionStatus.LIMITED,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime.now(timezone.utc) + timedelta(days=5),
        url="https://example.test/61",
        device_type=DeviceType.OTHER,
        plan=build_plan_snapshot(name="Fallback").model_copy(deep=True),
    )
    fallback_active = SubscriptionDto(
        id=62,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000062"),
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime.now(timezone.utc) + timedelta(days=20),
        url="https://example.test/62",
        device_type=DeviceType.OTHER,
        plan=build_plan_snapshot(name="Best").model_copy(deep=True),
    )
    deleted = SubscriptionDto(
        id=63,
        user_remna_id=UUID("00000000-0000-0000-0000-000000000063"),
        status=SubscriptionStatus.DELETED,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime.now(timezone.utc) + timedelta(days=40),
        url="https://example.test/63",
        device_type=DeviceType.OTHER,
        plan=build_plan_snapshot(name="Deleted").model_copy(deep=True),
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(
            get=AsyncMock(side_effect=[user, user]),
            set_current_subscription=AsyncMock(),
            delete_current_subscription=AsyncMock(),
        ),
        subscription_service=SimpleNamespace(
            get_current=AsyncMock(return_value=original_subscription),
            get=AsyncMock(return_value=None),
            get_all_by_user=AsyncMock(return_value=[fallback_limited, fallback_active, deleted]),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._sync_group_profile = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(uuid=UUID("00000000-0000-0000-0000-000000000060"), telegram_id=705)

    run_async(service.sync_profiles_by_telegram_id(705, [remna_user]))

    service.user_service.set_current_subscription.assert_awaited_once_with(
        telegram_id=705,
        subscription_id=62,
    )


def test_hydrate_panel_subscription_url_falls_back_to_existing_local_subscription_url() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service.get_subscription_url = AsyncMock(return_value="")  # type: ignore[method-assign]
    remna_user = SimpleNamespace(uuid=UUID("00000000-0000-0000-0000-000000000070"))
    remna_subscription = RemnaSubscriptionDto(
        uuid=UUID("00000000-0000-0000-0000-000000000070"),
        status=SubscriptionStatus.ACTIVE,
        expire_at=datetime.now(timezone.utc) + timedelta(days=30),
        url="",
        traffic_limit=100,
        device_limit=1,
        traffic_limit_strategy=None,
        tag="starter",
        internal_squads=[],
        external_squad=None,
    )
    subscription = SimpleNamespace(url="https://local.example/sub")

    run_async(
        service._hydrate_panel_subscription_url(
            remna_user=remna_user,
            remna_subscription=remna_subscription,
            subscription=subscription,
            telegram_id=706,
        )
    )

    assert remna_subscription.url == "https://local.example/sub"


def test_sync_user_with_creating_false_and_missing_subscription_does_not_create_local_subscription(
) -> None:
    user = SimpleNamespace(telegram_id=707)
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=SimpleNamespace(
            get_by_remna_id=AsyncMock(return_value=None),
            get_current=AsyncMock(return_value=None),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._resolve_matched_plan_for_sync = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._hydrate_panel_subscription_url = AsyncMock()  # type: ignore[method-assign]
    service._create_subscription_from_sync = AsyncMock()  # type: ignore[method-assign]
    service._update_subscription_from_sync = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(
        uuid=UUID("00000000-0000-0000-0000-000000000071"),
        telegram_id=707,
        username="user707",
        model_dump=lambda: {
            "uuid": UUID("00000000-0000-0000-0000-000000000071"),
            "status": SubscriptionStatus.ACTIVE,
            "expire_at": datetime.now(timezone.utc) + timedelta(days=30),
            "subscription_url": "https://example.com/sub",
            "traffic_limit_bytes": 100 * 1024 * 1024 * 1024,
            "hwid_device_limit": 1,
            "active_internal_squads": [],
            "external_squad_uuid": None,
            "traffic_limit_strategy": None,
            "tag": "starter",
        },
    )

    run_async(service.sync_user(remna_user, creating=False))

    service._create_subscription_from_sync.assert_not_awaited()
    service._update_subscription_from_sync.assert_not_awaited()


def test_handle_user_event_created_with_imported_tag_triggers_sync() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service.sync_user = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(tag="IMPORTED", telegram_id=801)

    run_async(service.handle_user_event(RemnaUserEvent.CREATED, remna_user))

    service.sync_user.assert_awaited_once_with(remna_user)


def test_handle_user_event_created_without_imported_tag_skips_sync() -> None:
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service.sync_user = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(tag="MANUAL", telegram_id=802)

    run_async(service.handle_user_event(RemnaUserEvent.CREATED, remna_user))

    service.sync_user.assert_not_awaited()


def test_handle_user_event_modified_triggers_sync_without_create() -> None:
    existing_user = SimpleNamespace(telegram_id=803, name="User", username="u")
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(get=AsyncMock(return_value=existing_user)),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service.sync_user = AsyncMock()  # type: ignore[method-assign]
    remna_user = SimpleNamespace(
        telegram_id=803,
        username="u",
        uuid=UUID("00000000-0000-0000-0000-000000000803"),
        used_traffic_bytes=0,
        traffic_limit_bytes=0,
        hwid_device_limit=0,
        expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        status=SubscriptionStatus.ACTIVE,
    )

    run_async(service.handle_user_event(RemnaUserEvent.MODIFIED, remna_user))

    service.sync_user.assert_awaited_once_with(remna_user, creating=False)


def test_handle_user_event_deleted_enqueues_delete_task(monkeypatch) -> None:
    delete_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(subscription_tasks, "delete_current_subscription_task", delete_task)

    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(
            get=AsyncMock(return_value=SimpleNamespace(telegram_id=804, name="User", username="u"))
        ),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    remna_user = SimpleNamespace(
        telegram_id=804,
        username="u",
        uuid=UUID("00000000-0000-0000-0000-000000000804"),
        used_traffic_bytes=0,
        traffic_limit_bytes=0,
        hwid_device_limit=0,
        expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        status=SubscriptionStatus.ACTIVE,
    )

    run_async(service.handle_user_event(RemnaUserEvent.DELETED, remna_user))

    delete_task.kiq.assert_awaited_once_with(
        user_telegram_id=804,
        user_remna_id=remna_user.uuid,
    )


def test_handle_user_event_limited_routes_status_update_and_notification(monkeypatch) -> None:
    limited_task = SimpleNamespace(kiq=AsyncMock())
    expire_task = SimpleNamespace(kiq=AsyncMock())
    update_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(
        notification_tasks,
        "send_subscription_limited_notification_task",
        limited_task,
    )
    monkeypatch.setattr(
        notification_tasks,
        "send_subscription_expire_notification_task",
        expire_task,
    )
    monkeypatch.setattr(
        subscription_tasks,
        "update_status_current_subscription_task",
        update_task,
    )

    user = SimpleNamespace(telegram_id=805, name="User", username="u")
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    remna_user = SimpleNamespace(
        telegram_id=805,
        username="u",
        uuid=UUID("00000000-0000-0000-0000-000000000805"),
        used_traffic_bytes=0,
        traffic_limit_bytes=0,
        hwid_device_limit=0,
        expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        status=SubscriptionStatus.LIMITED,
    )

    run_async(service.handle_user_event(RemnaUserEvent.LIMITED, remna_user))

    update_task.kiq.assert_awaited_once_with(
        user_telegram_id=805,
        status=SubscriptionStatus.LIMITED,
        user_remna_id=remna_user.uuid,
    )
    limited_task.kiq.assert_awaited_once()
    expire_task.kiq.assert_not_awaited()


def test_handle_user_event_first_connected_emits_system_notification(monkeypatch) -> None:
    system_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(notification_tasks, "send_system_notification_task", system_task)

    user = SimpleNamespace(telegram_id=806, name="User", username="u")
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    remna_user = SimpleNamespace(
        telegram_id=806,
        username="u",
        uuid=UUID("00000000-0000-0000-0000-000000000806"),
        used_traffic_bytes=0,
        traffic_limit_bytes=0,
        hwid_device_limit=0,
        expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        status=SubscriptionStatus.ACTIVE,
    )

    run_async(service.handle_user_event(RemnaUserEvent.FIRST_CONNECTED, remna_user))

    system_task.kiq.assert_awaited_once()
    assert (
        system_task.kiq.await_args.kwargs["ntf_type"]
        == SystemNotificationType.USER_FIRST_CONNECTED
    )
    assert (
        system_task.kiq.await_args.kwargs["payload"].i18n_key
        == "ntf-event-user-first-connected"
    )


def test_handle_device_event_added_auto_assigns_only_for_none_or_other(monkeypatch) -> None:
    system_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(notification_tasks, "send_system_notification_task", system_task)

    user = SimpleNamespace(telegram_id=807, name="User", username="u")
    subscription = SimpleNamespace(id=91, device_type=None)
    updated_subscription = SimpleNamespace(id=91, device_type=DeviceType.ANDROID)
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=SimpleNamespace(
            get_by_remna_id=AsyncMock(return_value=subscription),
            update=AsyncMock(return_value=updated_subscription),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    remna_user = SimpleNamespace(
        telegram_id=807,
        username="u",
        uuid=UUID("00000000-0000-0000-0000-000000000807"),
    )
    device = SimpleNamespace(
        hwid="hwid-1",
        platform="android",
        device_model="Pixel",
        os_version="14",
        user_agent="agent",
    )

    run_async(service.handle_device_event(RemnaUserHwidDevicesEvent.ADDED, remna_user, device))

    service.subscription_service.update.assert_awaited_once()
    assert system_task.kiq.await_args.kwargs["ntf_type"] == SystemNotificationType.USER_HWID
    assert system_task.kiq.await_args.kwargs["payload"].i18n_key == "ntf-event-user-hwid-added"

    subscription.device_type = DeviceType.WINDOWS
    service.subscription_service.update.reset_mock()
    run_async(service.handle_device_event(RemnaUserHwidDevicesEvent.ADDED, remna_user, device))
    service.subscription_service.update.assert_not_awaited()


def test_handle_device_event_deleted_keeps_notification_routing(monkeypatch) -> None:
    system_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(notification_tasks, "send_system_notification_task", system_task)

    user = SimpleNamespace(telegram_id=808, name="User", username="u")
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
        subscription_service=SimpleNamespace(
            get_by_remna_id=AsyncMock(return_value=None),
            update=AsyncMock(),
        ),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    remna_user = SimpleNamespace(
        telegram_id=808,
        username="u",
        uuid=UUID("00000000-0000-0000-0000-000000000808"),
    )
    device = SimpleNamespace(
        hwid="hwid-2",
        platform="ios",
        device_model="iPhone",
        os_version="17",
        user_agent="agent",
    )

    run_async(service.handle_device_event(RemnaUserHwidDevicesEvent.DELETED, remna_user, device))

    assert system_task.kiq.await_args.kwargs["payload"].i18n_key == "ntf-event-user-hwid-deleted"


@pytest.mark.parametrize(
    ("event_name", "expected_key"),
    [
        (RemnaNodeEvent.CONNECTION_LOST, "ntf-event-node-connection-lost"),
        (RemnaNodeEvent.CONNECTION_RESTORED, "ntf-event-node-connection-restored"),
        (RemnaNodeEvent.TRAFFIC_NOTIFY, "ntf-event-node-traffic"),
    ],
)
def test_handle_node_event_maps_supported_events(monkeypatch, event_name, expected_key) -> None:
    system_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(notification_tasks, "send_system_notification_task", system_task)

    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=MagicMock(),
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    node = SimpleNamespace(
        country_code="RU",
        name="Node",
        address="1.1.1.1",
        port=443,
        traffic_used_bytes=100,
        traffic_limit_bytes=200,
        last_status_message="ok",
        last_status_change=datetime.now(timezone.utc),
    )

    run_async(service.handle_node_event(event_name, node))

    assert system_task.kiq.await_args.kwargs["ntf_type"] == SystemNotificationType.NODE_STATUS
    assert system_task.kiq.await_args.kwargs["payload"].i18n_key == expected_key
