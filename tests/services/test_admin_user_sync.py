from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from src.bot.routers.dashboard.users.user.getters import _resolve_effective_panel_telegram_id
from src.bot.routers.dashboard.users.user.handlers import (
    _get_target_user_subscription_context,
    _resolve_admin_panel_telegram_id,
    _resolve_effective_subscription_owner,
)
from src.core.enums import DeviceType, PlanType, SubscriptionStatus, UserRole
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
    WebAccountDto,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def _build_subscription(subscription_id: int) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=UUID(f"00000000-0000-0000-0000-00000000000{subscription_id}"),
        user_telegram_id=605,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime.now(timezone.utc) + timedelta(days=30),
        url=f"https://example.com/{subscription_id}",
        device_type=DeviceType.OTHER,
        plan=PlanSnapshotDto(
            id=1,
            name="StarterPack",
            tag="starter",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=1,
            duration=30,
            internal_squads=[],
            external_squad=None,
        ),
    )


def test_resolve_effective_subscription_owner_prefers_panel_identity() -> None:
    target_user = UserDto(telegram_id=8, name="Shadow", role=UserRole.USER)
    owner_user = UserDto(telegram_id=605, name="Linked", role=UserRole.USER)
    dialog_manager = SimpleNamespace(dialog_data={"panel_telegram_id": "605"})

    async def get_user(telegram_id: int):
        if telegram_id == 605:
            return owner_user
        return target_user

    user_service = SimpleNamespace(get=get_user)

    resolved = run_async(
        _resolve_effective_subscription_owner(
            dialog_manager,
            user_service,
            target_user,
        )
    )

    assert resolved.telegram_id == 605


def test_target_user_subscription_context_uses_effective_owner_subscriptions() -> None:
    target_user = UserDto(telegram_id=8, name="Shadow", role=UserRole.USER)
    owner_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=_build_subscription(2),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={"target_telegram_id": 8, "panel_telegram_id": 605},
    )

    async def get_user(telegram_id: int):
        if telegram_id == 8:
            return target_user
        if telegram_id == 605:
            return owner_user
        return None

    async def get_subscriptions(telegram_id: int):
        assert telegram_id == 605
        return [_build_subscription(1), _build_subscription(2)]

    user_service = SimpleNamespace(get=get_user)
    subscription_service = SimpleNamespace(get_all_by_user=get_subscriptions)

    resolved_user, visible_subscriptions, selected_subscription = run_async(
        _get_target_user_subscription_context(
            dialog_manager,
            user_service,
            subscription_service,
        )
    )

    assert resolved_user.telegram_id == 605
    assert len(visible_subscriptions) == 2
    assert selected_subscription.id == 2


def test_effective_panel_telegram_id_prefers_negative_session_override() -> None:
    target_user = UserDto(telegram_id=-12, name="Web only", role=UserRole.USER)
    dialog_manager = SimpleNamespace(dialog_data={"panel_sync_override_telegram_id": "-605"})
    web_account_service = SimpleNamespace(get_by_user_telegram_id=AsyncMock())
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock())
    remnawave_service = SimpleNamespace(get_user=AsyncMock())

    result = run_async(
        _resolve_effective_panel_telegram_id(
            dialog_manager=dialog_manager,
            target_user=target_user,
            web_account_service=web_account_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result == -605
    web_account_service.get_by_user_telegram_id.assert_not_called()
    subscription_service.get_all_by_user.assert_not_called()


def test_effective_panel_telegram_id_infers_from_remnawave_profile() -> None:
    target_user = UserDto(
        telegram_id=-12,
        name="Web only",
        role=UserRole.USER,
        current_subscription=_build_subscription(1),
    )
    dialog_manager = SimpleNamespace(dialog_data={})
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(
            return_value=WebAccountDto(
                id=7,
                user_telegram_id=-12,
                username="alice",
                password_hash="hash",
            )
        )
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=[_build_subscription(1)])
    )
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=SimpleNamespace(telegram_id="605"))
    )

    result = run_async(
        _resolve_effective_panel_telegram_id(
            dialog_manager=dialog_manager,
            target_user=target_user,
            web_account_service=web_account_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result == 605
    subscription_service.get_all_by_user.assert_awaited_once_with(-12)


def test_resolve_admin_panel_telegram_id_prefers_effective_dialog_value() -> None:
    target_user = UserDto(telegram_id=-12, name="Web only", role=UserRole.USER)
    dialog_manager = SimpleNamespace(
        dialog_data={
            "panel_sync_override_telegram_id": -605,
            "effective_panel_telegram_id": 605,
            "panel_telegram_id": -12,
        }
    )

    result = _resolve_admin_panel_telegram_id(dialog_manager, target_user)

    assert result == 605
