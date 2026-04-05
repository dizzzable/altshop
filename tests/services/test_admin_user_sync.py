from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from src.bot.routers.dashboard.users.user.getters import _resolve_panel_profile_name
from src.bot.routers.dashboard.users.user.handlers import (
    _load_and_sync_admin_panel_profiles,
    _resolve_admin_panel_telegram_id,
)
from src.core.enums import UserRole
from src.infrastructure.database.models.dto import UserDto


def run_async(coroutine: Awaitable[object]) -> object:
    return asyncio.run(coroutine)


def test_resolve_admin_panel_telegram_id_prefers_dialog_value() -> None:
    dialog_manager = SimpleNamespace(dialog_data={"panel_telegram_id": "605"})
    target_user = UserDto(telegram_id=8, name="User", role=UserRole.USER)

    resolved = _resolve_admin_panel_telegram_id(dialog_manager, target_user)

    assert resolved == 605


def test_load_and_sync_admin_panel_profiles_uses_single_panel_telegram_id() -> None:
    remnawave_service = SimpleNamespace(
        get_users_by_telegram_id=AsyncMock(return_value=[SimpleNamespace(uuid=UUID(int=1))]),
        sync_profiles_by_telegram_id=AsyncMock(
            return_value=SimpleNamespace(
                subscriptions_created=1,
                subscriptions_updated=0,
                errors=0,
            )
        ),
    )

    profiles, stats = run_async(
        _load_and_sync_admin_panel_profiles(
            panel_telegram_id=605,
            remnawave_service=remnawave_service,
        )
    )

    remnawave_service.get_users_by_telegram_id.assert_awaited_once_with(605)
    remnawave_service.sync_profiles_by_telegram_id.assert_awaited_once()
    assert remnawave_service.sync_profiles_by_telegram_id.await_args.kwargs["telegram_id"] == 605
    assert len(profiles) == 1
    assert stats is not None


def test_resolve_panel_profile_name_returns_username() -> None:
    remna_user = SimpleNamespace(
        username="rs_8_sub",
    )

    result = _resolve_panel_profile_name(remna_user)

    assert result == "rs_8_sub"
