from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from src.api.contracts.web_auth import RegisterRequest, WebAccountBootstrapRequest
from src.api.endpoints.web_auth import _resolve_trusted_telegram_id_for_auto_link
from src.api.presenters.user_account import _build_user_profile_response
from src.api.presenters.web_auth import _build_auth_me_response
from src.bot.routers.dashboard.users.user.getters import _resolve_identity_kind
from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.telegram_link import TelegramLinkService
from src.services.user import UserService
from src.services.user_profile import UserProfileService
from src.services.web_account import WebAccountService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            web_accounts=SimpleNamespace(update=AsyncMock()),
            users=SimpleNamespace(
                get=AsyncMock(return_value=None),
                reassign_telegram_id_references=AsyncMock(),
                delete=AsyncMock(),
            ),
            auth_challenges=SimpleNamespace(update=AsyncMock()),
        )
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def make_user_model(telegram_id: int, *, username: str | None, name: str):
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
        is_blocked=False,
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


def make_user_dto(telegram_id: int, *, username: str | None, name: str) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=username,
        referral_code="REFCODE",
        name=name,
        role=UserRole.USER,
        language=Locale.EN,
    )


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


def test_telegram_link_request_returns_bot_confirm_url() -> None:
    uow = DummyUow()
    challenge_service = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                challenge=SimpleNamespace(id=1, meta=None),
                code="123456",
                token="challenge-token",
            )
        )
    )
    settings_service = SimpleNamespace(
        get_branding_settings=AsyncMock(
            return_value=SimpleNamespace(
                project_name="AltShop",
                verification=SimpleNamespace(telegram_template=SimpleNamespace()),
            )
        ),
        resolve_localized_branding_text=(
            lambda localized_text, language=None: "{project_name} {code}"
        ),
        render_branding_text=lambda template, placeholders: "AltShop 123456",
    )
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=777)),
        get_me=AsyncMock(return_value=SimpleNamespace(username="altshop_bot")),
    )
    service = TelegramLinkService(
        uow=uow,
        challenge_service=challenge_service,
        bot=bot,
        settings_service=settings_service,
    )
    web_account = WebAccountDto(
        id=77,
        user_telegram_id=-555,
        username="alice",
        password_hash="hash",
    )

    result = run_async(
        service.request_code(
            web_account=web_account,
            telegram_id=412289221,
            ttl_seconds=600,
            attempts=5,
        )
    )

    assert result.bot_confirm_url == "https://t.me/altshop_bot?start=tglink_challenge-token"
    assert (
        result.bot_confirm_deep_link
        == "tg://resolve?domain=altshop_bot&start=tglink_challenge-token"
    )
    challenge_service.create.assert_awaited_once()
    assert challenge_service.create.await_args.kwargs["include_token"] is True
    bot.send_message.assert_awaited_once()


def test_telegram_link_confirm_token_consumes_challenge_for_matching_destination() -> None:
    uow = DummyUow()
    challenge = SimpleNamespace(
        web_account_id=77,
        meta=None,
        destination="412289221",
        id=1,
        purpose="TG_LINK",
        channel="TELEGRAM",
        expires_at=datetime.now(timezone.utc),
        attempts_left=5,
    )
    challenge_service = SimpleNamespace(
        verify_token=AsyncMock(return_value=SimpleNamespace(ok=True, challenge=challenge))
    )
    service = TelegramLinkService(
        uow=uow,
        challenge_service=challenge_service,
        bot=SimpleNamespace(),
        settings_service=SimpleNamespace(),
    )
    updated_account = WebAccountDto(
        id=77,
        user_telegram_id=412289221,
        username="alice",
        password_hash="hash",
        token_version=5,
    )
    service._safe_auto_link = AsyncMock(return_value=updated_account)
    service._delete_verification_message = AsyncMock()

    result = run_async(
        service.confirm_token(
            telegram_id=412289221,
            token="challenge-token",
        )
    )

    assert result.linked_telegram_id == 412289221
    service._safe_auto_link.assert_awaited_once_with(
        web_account_id=77,
        telegram_id=412289221,
    )
    challenge_service.verify_token.assert_awaited_once_with(
        purpose="TG_LINK",
        token="challenge-token",
        destination="412289221",
    )


def test_telegram_link_wraps_integrity_error_during_reference_merge() -> None:
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
    service._get_web_account_or_error = AsyncMock(return_value=current_account)
    service._handle_already_linked_account = AsyncMock(return_value=None)
    service._assert_telegram_not_linked_elsewhere = AsyncMock()
    service._get_source_user_or_error = AsyncMock(return_value=source_user)
    service._get_or_create_target_user = AsyncMock(return_value=target_user)
    service._assert_merge_allowed = AsyncMock(return_value=True)
    service._merge_user_values = AsyncMock()
    uow.repository.users.reassign_telegram_id_references = AsyncMock(
        side_effect=IntegrityError("UPDATE", {}, Exception("duplicate referral"))
    )

    with pytest.raises(ValueError) as exception_info:
        run_async(service._safe_auto_link(web_account_id=77, telegram_id=412289221))

    error = exception_info.value
    assert getattr(error, "code", None) == "MANUAL_MERGE_REQUIRED"


def test_web_login_contract_normalizes_supported_values() -> None:
    register = RegisterRequest(username=" Alice.User_1 ", password="secret123")
    bootstrap = WebAccountBootstrapRequest(username=" USER_01.TEST ", password="secret123")

    assert register.username == "alice.user_1"
    assert bootstrap.username == "user_01.test"


def test_auto_link_uses_trusted_positive_telegram_id_only() -> None:
    assert (
        _resolve_trusted_telegram_id_for_auto_link(UserDto(telegram_id=412289221, name="TG User"))
        == 412289221
    )
    assert (
        _resolve_trusted_telegram_id_for_auto_link(UserDto(telegram_id=-555, name="Shadow User"))
        is None
    )


@pytest.mark.parametrize(
    ("username",),
    [
        ("абв",),
        ("alice smith",),
        ("alice-",),
        ("_alice",),
        ("alice_",),
        ("alice.",),
        (".alice",),
    ],
)
def test_web_login_contract_rejects_invalid_format(username: str) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(username=username, password="secret123")


def test_web_account_service_register_rejects_invalid_login_format_directly() -> None:
    service = WebAccountService(uow=SimpleNamespace())

    with pytest.raises(ValueError, match="Invalid username format"):
        run_async(service.register(username="alice.", password="secret123"))


def test_user_service_search_query_accepts_negative_shadow_id() -> None:
    service = UserService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        uow=SimpleNamespace(),
    )
    expected_user = make_user_dto(-555, username="alice", name="Alice")
    service._search_users_by_telegram_id = AsyncMock(return_value=[expected_user])
    service._search_users_by_login_or_name = AsyncMock(return_value=[])

    result = run_async(service._search_users_by_query("-555"))

    assert result == [expected_user]
    service._search_users_by_telegram_id.assert_awaited_once_with(-555)
    service._search_users_by_login_or_name.assert_not_called()


def test_user_service_search_supports_exact_web_login() -> None:
    exact_user_model = make_user_model(-555, username="alice", name="Alice")
    uow = DummyUow()
    uow.repository.web_accounts.get_by_username = AsyncMock(
        return_value=SimpleNamespace(user_telegram_id=-555)
    )
    uow.repository.users.get = AsyncMock(return_value=exact_user_model)
    service = UserService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        uow=uow,
    )

    result = run_async(service._search_users_by_login_or_name("ALICE"))

    assert [user.telegram_id for user in result] == [-555]


def test_user_service_search_merges_partial_name_and_web_login_matches() -> None:
    partial_name_user = make_user_dto(412289221, username="tg_412289221", name="Alina")
    partial_login_user_model = make_user_model(-555, username="alice", name="Alice")
    uow = DummyUow()
    uow.repository.web_accounts.get_by_username = AsyncMock(return_value=None)
    uow.repository.web_accounts.get_by_partial_username = AsyncMock(
        return_value=[SimpleNamespace(user_telegram_id=-555)]
    )
    uow.repository.users.get_by_ids = AsyncMock(return_value=[partial_login_user_model])
    service = UserService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        uow=uow,
    )
    service.get_by_partial_name = AsyncMock(return_value=[partial_name_user])

    result = run_async(service._search_users_by_login_or_name("ali"))

    assert {user.telegram_id for user in result} == {412289221, -555}


def test_identity_kind_marks_web_only_and_linked_profiles() -> None:
    web_only_user = make_user_dto(-555, username="alice", name="Alice")
    linked_user = make_user_dto(412289221, username="tg_412289221", name="Alina")

    assert (
        _resolve_identity_kind(
            web_only_user,
            web_login="alice",
            linked_telegram_id=None,
        )
        == "WEB_ONLY"
    )
    assert (
        _resolve_identity_kind(
            linked_user,
            web_login="alice",
            linked_telegram_id=412289221,
        )
        == "TELEGRAM_LINKED"
    )


def test_create_placeholder_user_does_not_touch_recent_registered() -> None:
    created_user_model = make_user_model(777, username=None, name="777")
    uow = DummyUow()
    uow.repository.users.generate_unique_referral_code = AsyncMock(return_value="PLACEHOLDER")
    uow.repository.users.create = AsyncMock(return_value=created_user_model)
    service = UserService(
        config=SimpleNamespace(
            default_locale=Locale.EN,
            crypt_key=SimpleNamespace(get_secret_value=lambda: "secret"),
            bot=SimpleNamespace(dev_id=[]),
        ),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        uow=uow,
    )
    service.get = AsyncMock(return_value=None)
    service.add_to_recent_registered = AsyncMock()
    service.clear_user_cache = AsyncMock()

    result = run_async(service.create_placeholder_user(telegram_id=777))

    assert result.telegram_id == 777
    service.add_to_recent_registered.assert_not_awaited()
    service.clear_user_cache.assert_awaited_once_with(777)
