from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.core.enums import AccessMode, Locale
from src.infrastructure.database.models.dto import SettingsDto, UserDto
from src.services.access_policy import AccessModePolicyService
from src.services.web_access_guard import WebAccessGuardService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int, created_at: datetime | None = None) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Guest",
        language=Locale.RU,
        created_at=created_at,
    )


def build_guard(settings: SettingsDto) -> WebAccessGuardService:
    return WebAccessGuardService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        settings_service=SimpleNamespace(get=AsyncMock(return_value=settings)),
        web_account_service=SimpleNamespace(get_by_user_telegram_id=AsyncMock(return_value=None)),
        access_mode_policy_service=AccessModePolicyService(),
    )


def test_purchase_blocked_mode_keeps_web_access_but_disables_purchase() -> None:
    guard = build_guard(SettingsDto(access_mode=AccessMode.PURCHASE_BLOCKED))
    status = run_async(guard.evaluate_user_access(user=build_user(telegram_id=1)))

    assert status.access_level == "full"
    assert status.can_view_product_screens is True
    assert status.can_mutate_product is True
    assert status.can_purchase is False
    assert status.should_redirect_to_access_screen is False


def test_invited_mode_grandfathers_existing_web_user() -> None:
    started_at = datetime.now(timezone.utc)
    guard = build_guard(
        SettingsDto(
            access_mode=AccessMode.INVITED,
            invite_mode_started_at=started_at,
        )
    )
    status = run_async(
        guard.evaluate_user_access(
            user=build_user(
                telegram_id=2,
                created_at=started_at - timedelta(minutes=5),
            )
        )
    )

    assert status.access_level == "full"
    assert status.invite_locked is False
    assert status.should_redirect_to_access_screen is False


def test_invited_mode_blocks_new_non_invited_web_user() -> None:
    started_at = datetime.now(timezone.utc)
    guard = build_guard(
        SettingsDto(
            access_mode=AccessMode.INVITED,
            invite_mode_started_at=started_at,
        )
    )
    status = run_async(
        guard.evaluate_user_access(
            user=build_user(
                telegram_id=3,
                created_at=started_at + timedelta(minutes=5),
            )
        )
    )

    assert status.access_level == "blocked"
    assert status.invite_locked is True
    assert status.can_view_product_screens is False
    assert status.can_purchase is False
    assert status.should_redirect_to_access_screen is True


def test_restricted_mode_redirects_web_user_to_access_screen() -> None:
    guard = build_guard(SettingsDto(access_mode=AccessMode.RESTRICTED))
    status = run_async(guard.evaluate_user_access(user=build_user(telegram_id=4)))

    assert status.access_level == "blocked"
    assert status.can_view_product_screens is False
    assert status.can_mutate_product is False
    assert status.can_purchase is False
    assert status.should_redirect_to_access_screen is True
