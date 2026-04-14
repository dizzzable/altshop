from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.enums import Locale, UserRole
from src.core.security.password import hash_password
from src.core.utils.time import datetime_now
from src.services.web_account import WebAccountService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            web_accounts=SimpleNamespace(
                create=AsyncMock(),
                update=AsyncMock(),
                delete=AsyncMock(return_value=False),
                get=AsyncMock(return_value=None),
                get_by_id=AsyncMock(return_value=None),
                get_by_username=AsyncMock(return_value=None),
                get_by_email=AsyncMock(return_value=None),
                get_by_user_telegram_id=AsyncMock(return_value=None),
            ),
            users=SimpleNamespace(
                get=AsyncMock(return_value=None),
                update=AsyncMock(),
                create=AsyncMock(),
                delete=AsyncMock(),
                get_min_telegram_id=AsyncMock(return_value=None),
                generate_unique_referral_code=AsyncMock(return_value="REFCODE"),
                has_material_data=AsyncMock(return_value=False),
            ),
        )
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def make_user_model(
    telegram_id: int,
    *,
    username: str | None,
    name: str,
    is_blocked: bool = False,
):
    return SimpleNamespace(
        id=None,
        telegram_id=telegram_id,
        username=username,
        referral_code="REFCODE",
        name=name,
        role=UserRole.USER,
        language=Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=is_blocked,
        is_bot_blocked=False,
        is_rules_accepted=True,
        partner_balance_currency_override=None,
        referral_invite_settings=None,
        max_subscriptions=None,
        created_at=None,
        updated_at=None,
        subscriptions=[],
        referral=None,
    )


def make_web_account_model(
    *,
    account_id: int = 77,
    user_telegram_id: int = 100,
    username: str = "alice",
    password_hash: str | None = None,
    credentials_bootstrapped_at=None,
    token_version: int = 0,
    requires_password_change: bool = False,
    temporary_password_expires_at=None,
):
    return SimpleNamespace(
        id=account_id,
        user_telegram_id=user_telegram_id,
        username=username,
        password_hash=password_hash or hash_password("secret123"),
        email=None,
        email_normalized=None,
        email_verified_at=None,
        credentials_bootstrapped_at=credentials_bootstrapped_at,
        token_version=token_version,
        requires_password_change=requires_password_change,
        temporary_password_expires_at=temporary_password_expires_at,
        link_prompt_snooze_until=None,
        created_at=None,
        updated_at=None,
    )


def build_service() -> tuple[WebAccountService, DummyUow]:
    uow = DummyUow()
    service = WebAccountService(uow=uow)
    service._generate_tokens = MagicMock(return_value=("access", "refresh"))  # type: ignore[method-assign]
    return service, uow


def test_register_creates_shadow_user_without_telegram_id() -> None:
    service, uow = build_service()
    user_model = make_user_model(-1, username="alice", name="Alice")
    account_model = make_web_account_model(user_telegram_id=-1, username="alice")
    service._create_shadow_user = AsyncMock(return_value=user_model)  # type: ignore[method-assign]
    uow.repository.web_accounts.create = AsyncMock(return_value=account_model)
    uow.repository.users.get = AsyncMock(return_value=user_model)

    result = run_async(service.register(username="alice", password="secret123"))

    assert result.is_new_user is True
    assert result.user.telegram_id == -1
    assert result.web_account.username == "alice"
    service._create_shadow_user.assert_awaited_once_with(username="alice", name=None)
    uow.repository.users.update.assert_awaited_once()
    uow.commit.assert_awaited_once()


def test_register_creates_real_user_and_links_positive_telegram_id() -> None:
    service, uow = build_service()
    user_model = make_user_model(100, username="alice", name="Alice")
    account_model = make_web_account_model(user_telegram_id=100, username="alice")
    service._create_real_user = AsyncMock(return_value=user_model)  # type: ignore[method-assign]
    uow.repository.users.get = AsyncMock(side_effect=[None, user_model])
    uow.repository.web_accounts.create = AsyncMock(return_value=account_model)

    result = run_async(
        service.register(username="alice", password="secret123", telegram_id=100, name="Alice")
    )

    assert result.is_new_user is True
    assert result.user.telegram_id == 100
    service._create_real_user.assert_awaited_once_with(
        telegram_id=100,
        username="alice",
        name="Alice",
    )
    uow.repository.web_accounts.get_by_user_telegram_id.assert_awaited_once_with(100)


@pytest.mark.parametrize(
    ("user_model", "existing_account", "expected_message"),
    [
        (
            make_user_model(100, username="alice", name="Alice", is_blocked=True),
            None,
            "User is blocked",
        ),
        (
            make_user_model(100, username="alice", name="Alice"),
            object(),
            "Telegram ID already linked. Please login.",
        ),
    ],
)
def test_register_rejects_blocked_or_already_linked_users(
    user_model,
    existing_account,
    expected_message: str,
) -> None:
    service, uow = build_service()
    uow.repository.users.get = AsyncMock(return_value=user_model)
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(return_value=existing_account)

    with pytest.raises(ValueError, match=expected_message):
        run_async(service.register(username="alice", password="secret123", telegram_id=100))


def test_register_rejects_duplicate_username_before_creating_user() -> None:
    service, uow = build_service()
    uow.repository.web_accounts.get_by_username = AsyncMock(return_value=object())

    with pytest.raises(ValueError, match="Username already taken"):
        run_async(service.register(username="alice", password="secret123"))

    uow.repository.web_accounts.create.assert_not_called()


@pytest.mark.parametrize(
    ("account_model", "user_model", "expected_message"),
    [
        (
            None,
            None,
            "Invalid username or password",
        ),
        (
            make_web_account_model(
                requires_password_change=True,
                temporary_password_expires_at=datetime_now() - timedelta(minutes=1),
            ),
            make_user_model(100, username="alice", name="Alice"),
            "Temporary password expired. Contact support.",
        ),
        (
            make_web_account_model(),
            make_user_model(100, username="alice", name="Alice", is_blocked=True),
            "User is blocked",
        ),
    ],
)
def test_login_rejects_invalid_credentials_blocked_users_and_expired_temp_password(
    account_model,
    user_model,
    expected_message: str,
) -> None:
    service, uow = build_service()
    uow.repository.web_accounts.get_by_username = AsyncMock(return_value=account_model)
    uow.repository.users.get = AsyncMock(return_value=user_model)

    with pytest.raises(ValueError, match=expected_message):
        run_async(service.login(username="alice", password="secret123"))


def test_get_or_create_for_telegram_user_returns_existing_linked_account() -> None:
    service, uow = build_service()
    user = SimpleNamespace(telegram_id=100, username="alice", name="Alice")
    account_model = make_web_account_model(user_telegram_id=100, username="alice")
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(return_value=account_model)

    result = run_async(service.get_or_create_for_telegram_user(user=user))

    assert result.is_new_user is False
    assert result.web_account.username == "alice"
    uow.repository.web_accounts.create.assert_not_called()


def test_get_or_create_for_telegram_user_creates_provisional_account_when_missing() -> None:
    service, uow = build_service()
    user = SimpleNamespace(telegram_id=100, username="tg_100", name="Alice")
    account_model = make_web_account_model(user_telegram_id=100, username="tg_100")
    refreshed_user = make_user_model(100, username="tg_100", name="Alice")
    service._allocate_telegram_username = AsyncMock(return_value="tg_100")  # type: ignore[method-assign]
    uow.repository.web_accounts.create = AsyncMock(return_value=account_model)
    uow.repository.users.get = AsyncMock(return_value=refreshed_user)

    result = run_async(service.get_or_create_for_telegram_user(user=user))

    assert result.web_account.username == "tg_100"
    assert result.is_new_user is False
    service._allocate_telegram_username.assert_awaited_once()
    uow.repository.users.update.assert_awaited_once()
    uow.commit.assert_awaited_once()


def test_bootstrap_credentials_creates_first_account_when_missing() -> None:
    service, uow = build_service()
    user_model = make_user_model(100, username="tg_100", name="Alice")
    account_model = make_web_account_model(
        user_telegram_id=100,
        username="alice",
        credentials_bootstrapped_at=datetime_now(),
    )
    uow.repository.users.get = AsyncMock(side_effect=[user_model, user_model])
    uow.repository.web_accounts.create = AsyncMock(return_value=account_model)

    result = run_async(
        service.bootstrap_credentials_for_telegram_user(
            telegram_id=100,
            username="alice",
            password="secret123",
            name="Alice",
        )
    )

    assert result.web_account.username == "alice"
    uow.repository.web_accounts.create.assert_awaited_once()
    uow.commit.assert_awaited_once()


def test_bootstrap_credentials_updates_provisional_account() -> None:
    service, uow = build_service()
    user_model = make_user_model(100, username="tg_100", name="Alice")
    provisional_account = make_web_account_model(
        user_telegram_id=100,
        username="tg_100",
        credentials_bootstrapped_at=None,
    )
    updated_account = make_web_account_model(
        user_telegram_id=100,
        username="alice",
        credentials_bootstrapped_at=datetime_now(),
    )
    uow.repository.users.get = AsyncMock(side_effect=[user_model, user_model])
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(
        return_value=provisional_account
    )
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_account)

    result = run_async(
        service.bootstrap_credentials_for_telegram_user(
            telegram_id=100,
            username="alice",
            password="secret123",
        )
    )

    assert result.web_account.username == "alice"
    uow.repository.web_accounts.update.assert_awaited_once()


@pytest.mark.parametrize(
    ("existing_username", "account_model", "expected_message"),
    [
        (make_web_account_model(account_id=88, username="taken"), None, "Username already taken"),
        (
            None,
            make_web_account_model(credentials_bootstrapped_at=datetime_now()),
            "Web credentials already configured",
        ),
    ],
)
def test_bootstrap_credentials_rejects_collisions_and_already_configured_accounts(
    existing_username,
    account_model,
    expected_message: str,
) -> None:
    service, uow = build_service()
    user_model = make_user_model(100, username="tg_100", name="Alice")
    uow.repository.users.get = AsyncMock(return_value=user_model)
    uow.repository.web_accounts.get_by_username = AsyncMock(return_value=existing_username)
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(return_value=account_model)

    with pytest.raises(ValueError, match=expected_message):
        run_async(
            service.bootstrap_credentials_for_telegram_user(
                telegram_id=100,
                username="alice",
                password="secret123",
            )
        )


def test_rename_login_syncs_only_mirrored_profile_fields() -> None:
    service, uow = build_service()
    account_model = make_web_account_model(account_id=77, user_telegram_id=100, username="old")
    updated_account = make_web_account_model(account_id=77, user_telegram_id=100, username="new")
    mirrored_user = make_user_model(100, username="old", name="old")
    external_user = make_user_model(100, username="custom", name="Custom Name")

    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(return_value=account_model)
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_account)
    uow.repository.users.get = AsyncMock(return_value=mirrored_user)

    result = run_async(service.rename_login(user_telegram_id=100, username="new"))

    assert result.username == "new"
    uow.repository.users.update.assert_awaited_once_with(
        telegram_id=100,
        username="new",
        name="new",
    )

    uow.repository.users.update.reset_mock()
    uow.repository.users.get = AsyncMock(return_value=external_user)

    run_async(service.rename_login(user_telegram_id=100, username="fresh"))

    uow.repository.users.update.assert_not_awaited()


def test_inspect_telegram_account_occupancy_marks_only_empty_provisional_accounts_reclaimable(
) -> None:
    service, uow = build_service()
    provisional_account = make_web_account_model(
        user_telegram_id=100,
        username="tg_100",
        credentials_bootstrapped_at=None,
    )
    user_model = make_user_model(100, username="tg_100", name="Ghost")
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(
        return_value=provisional_account
    )
    uow.repository.users.get = AsyncMock(return_value=user_model)
    uow.repository.users.has_material_data = AsyncMock(return_value=False)

    snapshot = run_async(service.inspect_telegram_account_occupancy(telegram_id=100))

    assert snapshot.is_reclaimable_provisional is True
    assert snapshot.has_material_data is False

    uow.repository.users.has_material_data = AsyncMock(return_value=True)
    snapshot = run_async(service.inspect_telegram_account_occupancy(telegram_id=100))

    assert snapshot.is_reclaimable_provisional is False


def test_cleanup_provisional_account_on_logout_deletes_only_empty_provisional_pairs() -> None:
    service, uow = build_service()
    provisional_account = make_web_account_model(
        account_id=77,
        user_telegram_id=100,
        username="tg_100",
        credentials_bootstrapped_at=None,
    )
    user_model = make_user_model(100, username="tg_100", name="Ghost")
    uow.repository.web_accounts.get = AsyncMock(return_value=provisional_account)
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(
        return_value=provisional_account
    )
    uow.repository.users.get = AsyncMock(return_value=user_model)
    uow.repository.users.has_material_data = AsyncMock(return_value=False)

    deleted = run_async(
        service.cleanup_provisional_account_on_logout(
            web_account_id=77,
            expected_user_telegram_id=100,
        )
    )

    assert deleted is True
    uow.repository.web_accounts.delete.assert_awaited_once_with(77)
    uow.repository.users.delete.assert_awaited_once_with(100)

    uow.repository.web_accounts.delete.reset_mock()
    uow.repository.users.delete.reset_mock()
    uow.repository.users.has_material_data = AsyncMock(return_value=True)

    deleted = run_async(
        service.cleanup_provisional_account_on_logout(
            web_account_id=77,
            expected_user_telegram_id=100,
        )
    )

    assert deleted is False
    uow.repository.web_accounts.delete.assert_not_awaited()
    uow.repository.users.delete.assert_not_awaited()


def test_shadow_helpers_preserve_negative_id_and_username_suffix_fallback() -> None:
    service, uow = build_service()
    uow.repository.users.get_min_telegram_id = AsyncMock(return_value=None)
    assert run_async(service._next_shadow_telegram_id()) == -1

    uow.repository.users.get_min_telegram_id = AsyncMock(return_value=-5)
    assert run_async(service._next_shadow_telegram_id()) == -6

    uow.repository.web_accounts.get_by_username = AsyncMock(
        side_effect=[object(), None]
    )
    username = run_async(
        service._allocate_telegram_username(
            preferred_username="Alice",
            telegram_id=100,
        )
    )

    assert username == "alice_1"
