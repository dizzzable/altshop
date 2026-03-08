from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import UserDto
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


def _build_user_model(
    *,
    telegram_id: int,
    username: str | None,
    name: str,
) -> SimpleNamespace:
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
    password_hash: str,
    credentials_bootstrapped_at: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=account_id,
        user_telegram_id=user_telegram_id,
        username=username,
        password_hash=password_hash,
        email=None,
        email_normalized=None,
        email_verified_at=None,
        credentials_bootstrapped_at=credentials_bootstrapped_at,
        token_version=0,
        requires_password_change=False,
        temporary_password_expires_at=None,
        link_prompt_snooze_until=None,
        created_at=None,
        updated_at=None,
    )


def test_register_stops_legacy_auth_field_mirroring() -> None:
    existing_user = _build_user_model(
        telegram_id=7001,
        username="telegram_user",
        name="Telegram User",
    )
    refreshed_user = _build_user_model(
        telegram_id=7001,
        username="telegram_user",
        name="Telegram User",
    )
    created_account = _build_web_account_model(
        account_id=1,
        username="web_login",
        user_telegram_id=7001,
        password_hash="hashed-password",
    )
    users = SimpleNamespace(
        get=AsyncMock(side_effect=[existing_user, refreshed_user]),
        update=AsyncMock(return_value=refreshed_user),
    )
    web_accounts = SimpleNamespace(
        get_by_username=AsyncMock(return_value=None),
        get_by_user_telegram_id=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created_account),
    )
    uow = _DummyUoW(repository=SimpleNamespace(users=users, web_accounts=web_accounts))
    service = WebAccountService(uow=uow)
    service._generate_tokens = lambda **kwargs: ("access", "refresh")  # type: ignore[method-assign]

    result = asyncio.run(
        service.register(
            username="web_login",
            password="secret123",
            telegram_id=7001,
            name="Telegram User",
        )
    )

    update_kwargs = users.update.await_args.kwargs
    assert set(update_kwargs) == {"telegram_id", "username", "name"}
    assert result.web_account.username == "web_login"
    assert set(vars(users)) == {"get", "update"}


def test_get_or_create_for_telegram_user_stops_legacy_auth_field_mirroring() -> None:
    user = UserDto(
        telegram_id=7002,
        username="telegram_user",
        referral_code="code7002",
        name="Telegram User",
        role=UserRole.USER,
        language=Locale.EN,
    )
    refreshed_user = _build_user_model(
        telegram_id=user.telegram_id,
        username=user.username,
        name=user.name,
    )
    created_account = _build_web_account_model(
        account_id=2,
        username="tg_7002",
        user_telegram_id=user.telegram_id,
        password_hash="hashed-password",
    )
    users = SimpleNamespace(
        get=AsyncMock(return_value=refreshed_user),
        update=AsyncMock(return_value=refreshed_user),
    )
    web_accounts = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created_account),
    )
    uow = _DummyUoW(repository=SimpleNamespace(users=users, web_accounts=web_accounts))
    service = WebAccountService(uow=uow)
    service._allocate_telegram_username = AsyncMock(  # type: ignore[method-assign]
        return_value="tg_7002"
    )
    service._generate_tokens = lambda **kwargs: ("access", "refresh")  # type: ignore[method-assign]

    result = asyncio.run(service.get_or_create_for_telegram_user(user=user))

    update_kwargs = users.update.await_args.kwargs
    assert set(update_kwargs) == {"telegram_id", "username", "name"}
    assert result.web_account.username == "tg_7002"


def test_register_uses_only_web_accounts_for_username_uniqueness() -> None:
    existing_user = _build_user_model(
        telegram_id=7003,
        username="telegram_user",
        name="Telegram User",
    )
    users = SimpleNamespace(
        get=AsyncMock(return_value=existing_user),
        update=AsyncMock(),
    )
    web_accounts = SimpleNamespace(
        get_by_username=AsyncMock(
            return_value=_build_web_account_model(
                account_id=3,
                username="busy_login",
                user_telegram_id=9000,
                password_hash="hashed-password",
            )
        ),
        get_by_user_telegram_id=AsyncMock(return_value=None),
        create=AsyncMock(),
    )
    uow = _DummyUoW(repository=SimpleNamespace(users=users, web_accounts=web_accounts))
    service = WebAccountService(uow=uow)

    try:
        asyncio.run(
            service.register(
                username="busy_login",
                password="secret123",
                telegram_id=7003,
                name="Telegram User",
            )
        )
    except ValueError as exc:
        assert str(exc) == "Username already taken"
    else:
        raise AssertionError("register() should reject duplicate web_account usernames")

    assert web_accounts.get_by_username.await_count == 1
    assert set(vars(users)) == {"get", "update"}


def test_allocate_telegram_username_uses_web_accounts_only() -> None:
    users = SimpleNamespace()
    web_accounts = SimpleNamespace(
        get_by_username=AsyncMock(side_effect=[object(), None]),
    )
    uow = _DummyUoW(repository=SimpleNamespace(users=users, web_accounts=web_accounts))
    service = WebAccountService(uow=uow)

    username = asyncio.run(
        service._allocate_telegram_username(
            preferred_username="Busy_Login",
            telegram_id=7004,
        )
    )

    assert username == "busy_login_1"
    assert web_accounts.get_by_username.await_count == 2
    assert vars(users) == {}


def test_bootstrap_credentials_updates_existing_shell_web_account() -> None:
    user_model = _build_user_model(
        telegram_id=7005,
        username="tg_7005",
        name="Telegram User",
    )
    refreshed_user = _build_user_model(
        telegram_id=7005,
        username="final_login",
        name="Telegram User",
    )
    shell_account = _build_web_account_model(
        account_id=5,
        username="tg_7005",
        user_telegram_id=7005,
        password_hash="temp-hash",
        credentials_bootstrapped_at=None,
    )
    bootstrapped_account = _build_web_account_model(
        account_id=5,
        username="final_login",
        user_telegram_id=7005,
        password_hash="final-hash",
        credentials_bootstrapped_at=datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
    )
    users = SimpleNamespace(
        get=AsyncMock(side_effect=[user_model, refreshed_user]),
        update=AsyncMock(return_value=refreshed_user),
    )
    web_accounts = SimpleNamespace(
        get_by_username=AsyncMock(return_value=None),
        get_by_user_telegram_id=AsyncMock(return_value=shell_account),
        update=AsyncMock(return_value=bootstrapped_account),
    )
    uow = _DummyUoW(repository=SimpleNamespace(users=users, web_accounts=web_accounts))
    service = WebAccountService(uow=uow)
    service._generate_tokens = lambda **kwargs: ("access", "refresh")  # type: ignore[method-assign]

    result = asyncio.run(
        service.bootstrap_credentials_for_telegram_user(
            telegram_id=7005,
            username="final_login",
            password="secret123",
            name="Telegram User",
        )
    )

    update_call = web_accounts.update.await_args
    assert update_call.args[0] == shell_account.id
    assert update_call.kwargs["username"] == "final_login"
    assert update_call.kwargs["requires_password_change"] is False
    assert update_call.kwargs["temporary_password_expires_at"] is None
    assert "credentials_bootstrapped_at" in update_call.kwargs
    assert result.web_account.username == "final_login"
