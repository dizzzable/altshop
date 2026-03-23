from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.presenters.user_account import _build_user_profile_response
from src.api.presenters.web_auth import _build_auth_me_response
from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.telegram_link import TelegramLinkService
from src.services.user_profile import UserProfileService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            web_accounts=SimpleNamespace(update=AsyncMock()),
            users=SimpleNamespace(
                reassign_telegram_id_references=AsyncMock(),
                delete=AsyncMock(),
            ),
        )
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def test_user_profile_snapshot_exposes_web_login_separately() -> None:
    web_account_service = SimpleNamespace(get_by_user_telegram_id=AsyncMock())
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock(return_value=[]))
    settings_service = SimpleNamespace(
        get_max_subscriptions_for_user=AsyncMock(return_value=1),
        get_default_currency=AsyncMock(return_value="RUB"),
        resolve_partner_balance_currency=AsyncMock(return_value="RUB"),
    )
    partner_service = SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None))
    service = UserProfileService(
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        settings_service=settings_service,
        partner_service=partner_service,
    )
    user = UserDto(
        telegram_id=412289221,
        username="tg_412289221",
        referral_code="ref",
        name="Alina",
        role=UserRole.USER,
        language=Locale.RU,
    )
    web_account = WebAccountDto(
        id=10,
        user_telegram_id=412289221,
        username="alice",
        password_hash="hash",
    )

    snapshot = run_async(service.build_snapshot(user=user, web_account=web_account))
    auth_response = _build_auth_me_response(snapshot)
    user_response = _build_user_profile_response(snapshot)

    assert snapshot.username == "tg_412289221"
    assert snapshot.web_login == "alice"
    assert auth_response.username == "tg_412289221"
    assert auth_response.web_login == "alice"
    assert user_response.username == "tg_412289221"
    assert user_response.web_login == "alice"


def test_telegram_link_keeps_existing_web_login() -> None:
    uow = DummyUow()
    service = TelegramLinkService(
        uow=uow,
        challenge_service=SimpleNamespace(),
        bot=SimpleNamespace(),
        settings_service=SimpleNamespace(),
    )
    current_account = SimpleNamespace(id=77, user_telegram_id=-555, token_version=4)
    source_user = SimpleNamespace(telegram_id=-555)
    target_user = SimpleNamespace(telegram_id=412289221)
    updated_account = SimpleNamespace(
        id=77,
        user_telegram_id=412289221,
        username="alice",
        password_hash="hash",
        token_version=5,
        email=None,
        email_normalized=None,
        email_verified_at=None,
        credentials_bootstrapped_at=None,
        requires_password_change=False,
        temporary_password_expires_at=None,
        link_prompt_snooze_until=None,
        created_at=None,
        updated_at=None,
    )
    service._get_web_account_or_error = AsyncMock(return_value=current_account)
    service._handle_already_linked_account = AsyncMock(return_value=None)
    service._assert_telegram_not_linked_elsewhere = AsyncMock()
    service._get_source_user_or_error = AsyncMock(return_value=source_user)
    service._get_or_create_target_user = AsyncMock(return_value=target_user)
    service._assert_merge_allowed = AsyncMock(return_value=False)
    service._merge_user_values = AsyncMock()
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_account)

    result = run_async(service._safe_auto_link(web_account_id=77, telegram_id=412289221))

    assert result.username == "alice"
    uow.repository.web_accounts.update.assert_awaited_once_with(
        77,
        user_telegram_id=412289221,
        token_version=5,
        link_prompt_snooze_until=None,
    )
    uow.commit.assert_awaited_once()
