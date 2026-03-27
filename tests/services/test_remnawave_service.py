from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError
from remnawave.enums.users import TrafficLimitStrategy
from remnawave.models import (
    DeleteUserHwidDeviceResponseDto,
    DeleteUserResponseDto,
    GetAllInternalSquadsResponseDto,
    GetAllUsersResponseDto,
    GetUserHwidDevicesResponseDto,
    TelegramUserResponseDto,
    UserResponseDto,
)
from remnawave.models.hwid import HwidDeviceDto
from remnawave.models.internal_squads import InternalSquadDto
from remnawave.models.users import UserTrafficDto

from src.core.enums import DeviceType, RemnaUserHwidDevicesEvent, SubscriptionStatus
from src.core.observability import clear_metrics_registry, render_metrics_text
from src.services import remnawave as remnawave_module
from src.services.remnawave import RemnawaveService


def run_async(coroutine):
    return asyncio.run(coroutine)


def setup_function() -> None:
    clear_metrics_registry()


def teardown_function() -> None:
    clear_metrics_registry()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_user_response(
    *,
    user_uuid: UUID | None = None,
    telegram_id: int = 101,
) -> UserResponseDto:
    user_uuid = user_uuid or uuid4()
    timestamp = now_utc()
    return UserResponseDto.model_construct(
        uuid=user_uuid,
        short_uuid="short-123",
        username=f"user-{telegram_id}",
        status="ACTIVE",
        traffic_limit_bytes=1024,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        expire_at=timestamp,
        telegram_id=telegram_id,
        description="test user",
        tag="PLAN_A",
        hwid_device_limit=2,
        trojan_password="password123",
        vless_uuid=uuid4(),
        ss_password="password456",
        created_at=timestamp,
        updated_at=timestamp,
        subscription_url="https://example.com/subscription",
        active_internal_squads=[],
        user_traffic=UserTrafficDto.model_construct(
            used_traffic_bytes=0,
            lifetime_used_traffic_bytes=0,
        ),
    )


def build_device(*, user_uuid: UUID | None = None, hwid: str = "hwid-1") -> HwidDeviceDto:
    timestamp = now_utc()
    return HwidDeviceDto.model_construct(
        hwid=hwid,
        user_uuid=user_uuid or uuid4(),
        platform="Android 14",
        device_model="Pixel 8",
        user_agent="AltShopTest/1.0",
        created_at=timestamp,
        updated_at=timestamp,
    )


def build_service() -> tuple[RemnawaveService, SimpleNamespace]:
    remnawave = SimpleNamespace(
        system=SimpleNamespace(get_stats=AsyncMock()),
        internal_squads=SimpleNamespace(get_internal_squads=AsyncMock()),
        hosts=SimpleNamespace(get_all_hosts=AsyncMock()),
        nodes=SimpleNamespace(get_all_nodes=AsyncMock()),
        inbounds=SimpleNamespace(get_all_inbounds=AsyncMock()),
        external_squads=SimpleNamespace(get_external_squads=AsyncMock()),
        users=SimpleNamespace(
            create_user=AsyncMock(),
            update_user=AsyncMock(),
            reset_user_traffic=AsyncMock(),
            get_users_by_telegram_id=AsyncMock(),
            delete_user=AsyncMock(),
            get_user_by_uuid=AsyncMock(),
            enable_user=AsyncMock(),
            disable_user=AsyncMock(),
            get_all_users=AsyncMock(),
        ),
        hwid=SimpleNamespace(
            get_hwid_user=AsyncMock(),
            delete_hwid_to_user=AsyncMock(),
        ),
    )

    service = RemnawaveService(
        config=SimpleNamespace(remnawave=SimpleNamespace()),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=SimpleNamespace(
            get=AsyncMock(),
            create_from_panel=AsyncMock(),
        ),
        subscription_service=SimpleNamespace(
            get_all_by_user=AsyncMock(return_value=[]),
            create=AsyncMock(),
            update=AsyncMock(),
            get_by_remna_id=AsyncMock(),
        ),
        plan_service=SimpleNamespace(),
        settings_service=SimpleNamespace(
            get_max_subscriptions_for_user=AsyncMock(return_value=3),
        ),
    )
    return service, remnawave


def build_validation_error() -> ValidationError:
    try:
        GetAllInternalSquadsResponseDto.model_validate({"bad": "payload"})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected validation error")


def test_get_stats_safe_returns_none_on_http_error() -> None:
    service, remnawave = build_service()
    remnawave.system.get_stats.side_effect = httpx.ConnectError("boom")

    result = run_async(service.get_stats_safe())

    assert result is None
    assert (
        'remnawave_degraded_states_total{reason="http_error",stage="get_stats"} 1'
        in render_metrics_text()
    )


def test_get_external_squads_safe_uses_raw_fallback_on_validation_error() -> None:
    service, remnawave = build_service()
    fallback_result = [{"uuid": uuid4(), "name": "Europe"}]
    remnawave.external_squads.get_external_squads.side_effect = build_validation_error()
    service._get_external_squads_raw = AsyncMock(return_value=fallback_result)  # type: ignore[method-assign]

    result = run_async(service.get_external_squads_safe())

    assert result == fallback_result
    service._get_external_squads_raw.assert_awaited_once()  # type: ignore[attr-defined]
    assert (
        'remnawave_degraded_states_total{reason="sdk_validation",stage="external_squads"} 1'
        in render_metrics_text()
    )


def test_get_internal_squads_returns_validated_response() -> None:
    service, remnawave = build_service()
    timestamp = now_utc()
    response = GetAllInternalSquadsResponseDto.model_construct(
        total=1,
        internal_squads=[
            InternalSquadDto.model_construct(
                uuid=uuid4(),
                name="Default",
                created_at=timestamp,
                updated_at=timestamp,
            )
        ],
    )
    remnawave.internal_squads.get_internal_squads.return_value = response

    result = run_async(service.get_internal_squads())

    assert result.internal_squads[0].name == "Default"


def test_get_all_users_paginates_until_short_page() -> None:
    service, remnawave = build_service()
    first_page = GetAllUsersResponseDto.model_construct(
        users=[build_user_response(telegram_id=101), build_user_response(telegram_id=102)],
        total=3,
    )
    second_page = GetAllUsersResponseDto.model_construct(
        users=[build_user_response(telegram_id=103)],
        total=3,
    )
    remnawave.users.get_all_users.side_effect = [first_page, second_page]

    result = run_async(service.get_all_users(page_size=2))

    assert [user.telegram_id for user in result] == [101, 102, 103]


def test_import_user_sets_active_internal_squads_before_create() -> None:
    service, remnawave = build_service()
    remnawave.users.create_user.return_value = build_user_response()
    squad_uuid = uuid4()

    result = run_async(
        service.import_user(
            payload={
                "username": "imported-user",
                "expire_at": now_utc(),
                "tag": "IMPORTED",
            },
            active_internal_squads=[squad_uuid],
        )
    )

    request = remnawave.users.create_user.await_args.args[0]
    assert result.username == "user-101"
    assert request.active_internal_squads == [squad_uuid]


def test_create_user_builds_panel_request_from_snapshot() -> None:
    service, remnawave = build_service()
    panel_user = build_user_response(telegram_id=500)
    remnawave.users.create_user.return_value = panel_user
    user = SimpleNamespace(
        telegram_id=500,
        remna_name="alice",
        remna_description="AltShop user",
    )
    plan = SimpleNamespace(
        duration=30,
        traffic_limit=100,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        tag="PLAN_A",
        device_limit=2,
        internal_squads=[uuid4()],
        external_squad=uuid4(),
        name="Plan A",
    )

    result = run_async(service.create_user(user, plan))

    request = remnawave.users.create_user.await_args.args[0]
    assert result == panel_user
    assert request.username == "alice_sub"
    assert request.telegram_id == 500
    assert request.active_internal_squads == plan.internal_squads
    assert request.external_squad_uuid == plan.external_squad


def test_updated_user_resets_traffic_when_requested() -> None:
    service, remnawave = build_service()
    target_uuid = uuid4()
    remnawave.users.update_user.return_value = build_user_response(
        user_uuid=target_uuid,
        telegram_id=700,
    )
    subscription = SimpleNamespace(
        id=42,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=200,
        device_limit=3,
        internal_squads=[uuid4()],
        external_squad=uuid4(),
        expire_at=now_utc(),
        plan=SimpleNamespace(
            tag="PLAN_B",
            traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        ),
    )
    user = SimpleNamespace(telegram_id=700, remna_description="updated user")

    result = run_async(
        service.updated_user(
            user=user,
            uuid=target_uuid,
            subscription=subscription,
            reset_traffic=True,
        )
    )

    assert result.uuid == target_uuid
    remnawave.users.update_user.assert_awaited_once()
    remnawave.users.reset_user_traffic.assert_awaited_once_with(str(target_uuid))


def test_set_user_enabled_routes_to_expected_sdk_controller() -> None:
    service, remnawave = build_service()
    target_uuid = uuid4()

    run_async(service.set_user_enabled(target_uuid, enabled=True))
    run_async(service.set_user_enabled(target_uuid, enabled=False))

    remnawave.users.enable_user.assert_awaited_once_with(uuid=str(target_uuid))
    remnawave.users.disable_user.assert_awaited_once_with(uuid=str(target_uuid))


def test_get_users_by_telegram_id_returns_root_profiles() -> None:
    service, remnawave = build_service()
    panel_user = build_user_response(telegram_id=900)
    remnawave.users.get_users_by_telegram_id.return_value = TelegramUserResponseDto.model_construct(
        root=[panel_user]
    )

    result = run_async(service.get_users_by_telegram_id(900))

    assert result == [panel_user]


def test_delete_user_by_uuid_returns_deleted_flag() -> None:
    service, remnawave = build_service()
    target_uuid = uuid4()
    remnawave.users.delete_user.return_value = DeleteUserResponseDto.model_construct(
        is_deleted=True
    )

    result = run_async(service.delete_user_by_uuid(target_uuid))

    assert result is True
    remnawave.users.delete_user.assert_awaited_once_with(uuid=str(target_uuid))


def test_get_devices_by_subscription_uuid_returns_panel_devices() -> None:
    service, remnawave = build_service()
    target_uuid = uuid4()
    device = build_device(user_uuid=target_uuid)
    remnawave.hwid.get_hwid_user.return_value = GetUserHwidDevicesResponseDto.model_construct(
        total=1,
        devices=[device],
    )

    result = run_async(service.get_devices_by_subscription_uuid(target_uuid))

    assert result == [device]


def test_delete_device_by_subscription_uuid_returns_remaining_count() -> None:
    service, remnawave = build_service()
    target_uuid = uuid4()
    remnawave.hwid.delete_hwid_to_user.return_value = (
        DeleteUserHwidDeviceResponseDto.model_construct(
            total=0,
            devices=[],
        )
    )

    result = run_async(service.delete_device_by_subscription_uuid(target_uuid, "hwid-1"))

    assert result == 0


def test_handle_device_event_updates_unknown_device_type(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _remnawave = build_service()
    target_uuid = uuid4()
    local_user = SimpleNamespace(telegram_id=321, name="Alice", username="alice")
    subscription = SimpleNamespace(id=77, device_type=DeviceType.OTHER)
    service.user_service.get.return_value = local_user
    service.subscription_service.get_by_remna_id.return_value = subscription
    service.subscription_service.update = AsyncMock(return_value=subscription)
    notification_task = SimpleNamespace(kiq=AsyncMock())
    monkeypatch.setattr(remnawave_module, "send_system_notification_task", notification_task)

    remna_user = build_user_response(user_uuid=target_uuid, telegram_id=321)
    device = build_device(user_uuid=target_uuid)

    run_async(
        service.handle_device_event(
            RemnaUserHwidDevicesEvent.ADDED,
            remna_user,
            device,
        )
    )

    assert subscription.device_type == DeviceType.ANDROID
    service.subscription_service.update.assert_awaited_once_with(subscription)
    notification_task.kiq.assert_awaited_once()
