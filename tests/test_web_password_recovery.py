from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.enums import Locale, UserRole
from src.core.security.password import hash_password
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import WebAccountDto
from src.services.auth_challenge import ChallengeErrorReason, ChallengeVerifyResult
from src.services.email_recovery import EmailRecoveryService
from src.services.user import UserService
from src.services.web_account import WebAccountService


class _DummyUoW:
    def __init__(self, repository: SimpleNamespace) -> None:
        self.repository = repository
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> "_DummyUoW":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        domain=SimpleNamespace(get_secret_value=lambda: "example.com"),
        web_app=SimpleNamespace(
            url_str="https://example.com/webapp",
            password_reset_ttl_seconds=600,
            auth_challenge_attempts=3,
            email_verify_ttl_seconds=600,
        ),
    )


def _build_user_model(*, telegram_id: int, username: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=None,
        telegram_id=telegram_id,
        username=username,
        referral_code=f"code{abs(telegram_id)}",
        name=name,
        role=UserRole.USER,
        language=Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
        max_subscriptions=None,
        created_at=None,
        updated_at=None,
        subscriptions=[],
        referral=None,
    )


def _build_web_account_model(
    *,
    account_id: int,
    username: str,
    user_telegram_id: int,
    password_hash_value: str,
    token_version: int = 0,
    requires_password_change: bool = False,
    temporary_password_expires_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=account_id,
        user_telegram_id=user_telegram_id,
        username=username,
        password_hash=password_hash_value,
        email=None,
        email_normalized=None,
        email_verified_at=None,
        token_version=token_version,
        requires_password_change=requires_password_change,
        temporary_password_expires_at=temporary_password_expires_at,
        link_prompt_snooze_until=None,
        created_at=None,
        updated_at=None,
    )


def _build_recovery_service(
    *,
    uow: _DummyUoW,
    challenge_service: SimpleNamespace | None = None,
    email_sender: SimpleNamespace | None = None,
    bot: SimpleNamespace | None = None,
) -> EmailRecoveryService:
    return EmailRecoveryService(
        uow=uow,
        config=_build_config(),
        challenge_service=challenge_service or SimpleNamespace(),
        email_sender=email_sender or SimpleNamespace(send=AsyncMock(return_value=True)),
        bot=bot or SimpleNamespace(send_message=AsyncMock()),
        settings_service=SimpleNamespace(),
    )


def test_request_telegram_password_reset_hides_missing_account() -> None:
    web_accounts = SimpleNamespace(get_by_username=AsyncMock(return_value=None))
    repository = SimpleNamespace(web_accounts=web_accounts, users=SimpleNamespace())
    uow = _DummyUoW(repository=repository)
    challenge_service = SimpleNamespace(create=AsyncMock())
    bot = SimpleNamespace(send_message=AsyncMock())
    service = _build_recovery_service(
        uow=uow,
        challenge_service=challenge_service,
        bot=bot,
    )

    asyncio.run(service.request_telegram_password_reset(username="ghost_user"))

    assert challenge_service.create.await_count == 0
    assert bot.send_message.await_count == 0


def test_reset_password_by_telegram_code_success() -> None:
    account = _build_web_account_model(
        account_id=7,
        username="alice",
        user_telegram_id=123456,
        password_hash_value=hash_password("oldpass"),
    )
    web_accounts = SimpleNamespace(get_by_username=AsyncMock(return_value=account))
    repository = SimpleNamespace(web_accounts=web_accounts, users=SimpleNamespace())
    uow = _DummyUoW(repository=repository)
    challenge_service = SimpleNamespace(
        verify_code=AsyncMock(return_value=ChallengeVerifyResult(ok=True)),
    )
    service = _build_recovery_service(
        uow=uow,
        challenge_service=challenge_service,
    )
    service._update_password = AsyncMock(  # type: ignore[method-assign]
        return_value=WebAccountDto(
            id=account.id,
            user_telegram_id=account.user_telegram_id,
            username=account.username,
            token_version=1,
        )
    )

    asyncio.run(
        service.reset_password_by_telegram_code(
            username="alice",
            code="123456",
            new_password="new-password",
        )
    )

    assert challenge_service.verify_code.await_count == 1
    assert service._update_password.await_count == 1  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("reason", "expected_message"),
    [
        (ChallengeErrorReason.INVALID_CODE, "Invalid or expired reset code"),
        (ChallengeErrorReason.INVALID_OR_EXPIRED, "Invalid or expired reset code"),
        (ChallengeErrorReason.TOO_MANY_ATTEMPTS, "Too many attempts. Request a new reset code."),
    ],
)
def test_reset_password_by_telegram_code_errors(reason: str, expected_message: str) -> None:
    account = _build_web_account_model(
        account_id=11,
        username="bob",
        user_telegram_id=555,
        password_hash_value=hash_password("oldpass"),
    )
    web_accounts = SimpleNamespace(get_by_username=AsyncMock(return_value=account))
    repository = SimpleNamespace(web_accounts=web_accounts, users=SimpleNamespace())
    uow = _DummyUoW(repository=repository)
    challenge_service = SimpleNamespace(
        verify_code=AsyncMock(return_value=ChallengeVerifyResult(ok=False, reason=reason)),
    )
    service = _build_recovery_service(
        uow=uow,
        challenge_service=challenge_service,
    )

    with pytest.raises(ValueError, match=expected_message):
        asyncio.run(
            service.reset_password_by_telegram_code(
                username="bob",
                code="111111",
                new_password="new-password",
            )
        )


def test_issue_temporary_password_for_dev_sets_flags_and_expiry() -> None:
    account = _build_web_account_model(
        account_id=19,
        username="web_only_user",
        user_telegram_id=-101,
        password_hash_value=hash_password("oldpass"),
        token_version=4,
    )

    async def update_account(_account_id: int, **data: object) -> SimpleNamespace:
        merged = dict(account.__dict__)
        merged.update(data)
        return SimpleNamespace(**merged)

    web_accounts = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(return_value=account),
        update=AsyncMock(side_effect=update_account),
    )
    users = SimpleNamespace(update=AsyncMock())
    repository = SimpleNamespace(web_accounts=web_accounts, users=users)
    uow = _DummyUoW(repository=repository)
    service = _build_recovery_service(uow=uow)

    username, temp_password, expires_at = asyncio.run(
        service.issue_temporary_password_for_dev(
            target_telegram_id=-101,
            ttl_seconds=24 * 60 * 60,
        )
    )

    assert username == "web_only_user"
    assert temp_password.startswith("Tmp")
    assert temp_password[3:].isdigit()
    assert expires_at > datetime_now()

    update_kwargs = web_accounts.update.await_args.kwargs
    assert update_kwargs["token_version"] == account.token_version + 1
    assert update_kwargs["requires_password_change"] is True
    assert isinstance(update_kwargs["temporary_password_expires_at"], datetime)
    assert update_kwargs["temporary_password_expires_at"] > datetime_now()
    assert users.update.await_count == 0


def test_change_password_clears_forced_flags_and_rotates_token_version() -> None:
    old_password = "old-password"
    account = _build_web_account_model(
        account_id=31,
        username="changed_user",
        user_telegram_id=777,
        password_hash_value=hash_password(old_password),
        token_version=9,
        requires_password_change=True,
        temporary_password_expires_at=datetime_now() + timedelta(hours=6),
    )

    async def update_account(_account_id: int, **data: object) -> SimpleNamespace:
        merged = dict(account.__dict__)
        merged.update(data)
        return SimpleNamespace(**merged)

    web_accounts = SimpleNamespace(
        get=AsyncMock(side_effect=[account, account]),
        update=AsyncMock(side_effect=update_account),
    )
    users = SimpleNamespace(update=AsyncMock())
    repository = SimpleNamespace(web_accounts=web_accounts, users=users)
    uow = _DummyUoW(repository=repository)
    service = _build_recovery_service(uow=uow)

    updated = asyncio.run(
        service.change_password(
            web_account_id=account.id,
            current_password=old_password,
            new_password="new-password",
        )
    )

    assert updated.token_version == account.token_version + 1
    assert updated.requires_password_change is False
    assert updated.temporary_password_expires_at is None

    update_kwargs = web_accounts.update.await_args.kwargs
    assert update_kwargs["token_version"] == account.token_version + 1
    assert update_kwargs["requires_password_change"] is False
    assert update_kwargs["temporary_password_expires_at"] is None
    assert users.update.await_count == 0


def test_login_rejects_expired_temporary_password() -> None:
    account_model = _build_web_account_model(
        account_id=77,
        username="temp_user",
        user_telegram_id=991,
        password_hash_value=hash_password("Tmp111111"),
        token_version=1,
        requires_password_change=True,
        temporary_password_expires_at=datetime_now() - timedelta(minutes=1),
    )
    web_accounts = SimpleNamespace(get_by_username=AsyncMock(return_value=account_model))
    users = SimpleNamespace(get=AsyncMock())
    repository = SimpleNamespace(web_accounts=web_accounts, users=users)
    uow = _DummyUoW(repository=repository)
    service = WebAccountService(uow=uow)

    with pytest.raises(ValueError, match="Temporary password expired. Contact support."):
        asyncio.run(service.login(username="temp_user", password="Tmp111111"))

    assert users.get.await_count == 0


def test_search_users_prioritizes_exact_web_login() -> None:
    found_user = _build_user_model(telegram_id=-505, username="legacy_user", name="Legacy User")
    web_account = _build_web_account_model(
        account_id=14,
        username="unique_login",
        user_telegram_id=found_user.telegram_id,
        password_hash_value=hash_password("unused"),
    )
    users_repo = SimpleNamespace(
        get=AsyncMock(return_value=found_user),
        get_by_partial_name=AsyncMock(return_value=[]),
    )
    repository = SimpleNamespace(
        web_accounts=SimpleNamespace(get_by_username=AsyncMock(return_value=web_account)),
        users=users_repo,
    )
    uow = _DummyUoW(repository=repository)
    service = UserService(
        config=SimpleNamespace(bot=SimpleNamespace(dev_id=[]), locales=["en"], default_locale="en"),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        uow=uow,
    )

    results = asyncio.run(
        service.search_users(message=SimpleNamespace(forward_from=None, text="unique_login"))
    )

    assert len(results) == 1
    assert results[0].telegram_id == found_user.telegram_id
    assert users_repo.get_by_partial_name.await_count == 0
