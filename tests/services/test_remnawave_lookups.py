from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from remnawave.models import (
    GetAllUsersResponseDto,
    GetUserHwidDevicesResponseDto,
    TelegramUserResponseDto,
    UserResponseDto,
)
from remnawave.models.hwid import HwidDeviceDto
from remnawave.models.users import UserTrafficDto

from src.services.remnawave_lookups import RemnawaveUserDeviceLookup


def run_async(coroutine):
    return asyncio.run(coroutine)


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
        traffic_limit_strategy="NO_RESET",
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


def build_lookup() -> tuple[RemnawaveUserDeviceLookup, SimpleNamespace]:
    remnawave = SimpleNamespace(
        users=SimpleNamespace(
            get_user_by_uuid=AsyncMock(),
            get_users_by_telegram_id=AsyncMock(),
            get_all_users=AsyncMock(),
        ),
        hwid=SimpleNamespace(get_hwid_user=AsyncMock()),
    )
    return RemnawaveUserDeviceLookup(remnawave=remnawave), remnawave


def test_get_users_by_telegram_id_returns_root_profiles() -> None:
    lookup, remnawave = build_lookup()
    panel_user = build_user_response(telegram_id=900)
    remnawave.users.get_users_by_telegram_id.return_value = TelegramUserResponseDto.model_construct(
        root=[panel_user]
    )

    result = run_async(lookup.get_users_by_telegram_id(900))

    assert result == [panel_user]


def test_get_all_users_paginates_until_short_page() -> None:
    lookup, remnawave = build_lookup()
    first_page = GetAllUsersResponseDto.model_construct(
        users=[build_user_response(telegram_id=101), build_user_response(telegram_id=102)],
        total=3,
    )
    second_page = GetAllUsersResponseDto.model_construct(
        users=[build_user_response(telegram_id=103)],
        total=3,
    )
    remnawave.users.get_all_users.side_effect = [first_page, second_page]

    result = run_async(lookup.get_all_users(page_size=2))

    assert [user.telegram_id for user in result] == [101, 102, 103]


def test_get_devices_by_subscription_uuid_returns_panel_devices() -> None:
    lookup, remnawave = build_lookup()
    target_uuid = uuid4()
    device = build_device(user_uuid=target_uuid)
    remnawave.hwid.get_hwid_user.return_value = GetUserHwidDevicesResponseDto.model_construct(
        total=1,
        devices=[device],
    )

    result = run_async(lookup.get_devices_by_subscription_uuid(target_uuid))

    assert result == [device]
