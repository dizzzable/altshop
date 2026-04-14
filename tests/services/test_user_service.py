from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.exc import IntegrityError

from src.core.enums import Currency, Locale, UserRole
from src.infrastructure.database.models.dto import UserDto
from src.services.user import UserService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            users=SimpleNamespace(
                create=AsyncMock(),
                get=AsyncMock(return_value=None),
                update=AsyncMock(),
                delete=AsyncMock(return_value=True),
                get_by_partial_name=AsyncMock(return_value=[]),
                get_by_referral_code=AsyncMock(return_value=None),
                count=AsyncMock(return_value=0),
                filter_by_role=AsyncMock(return_value=[]),
                filter_by_blocked=AsyncMock(return_value=[]),
                get_all=AsyncMock(return_value=[]),
                get_by_ids=AsyncMock(return_value=[]),
                generate_unique_referral_code=AsyncMock(return_value="PLACEHOLDER"),
                set_rules_accepted_for_non_privileged=AsyncMock(return_value=3),
            ),
            web_accounts=SimpleNamespace(
                get_by_username=AsyncMock(return_value=None),
                get_by_partial_username=AsyncMock(return_value=[]),
            ),
        )
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def build_service() -> tuple[UserService, DummyUow]:
    uow = DummyUow()
    service = UserService(
        config=SimpleNamespace(
            default_locale=Locale.EN,
            locales=[Locale.EN, Locale.RU],
            crypt_key=SimpleNamespace(get_secret_value=lambda: "secret"),
            bot=SimpleNamespace(dev_id=[1]),
        ),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(delete=AsyncMock()),
        redis_repository=SimpleNamespace(
            list_remove=AsyncMock(),
            list_push=AsyncMock(),
            list_trim=AsyncMock(),
            list_range=AsyncMock(return_value=[]),
            delete_pattern=AsyncMock(),
        ),
        translator_hub=SimpleNamespace(),
        uow=uow,
    )
    return service, uow


def make_user_model(
    telegram_id: int,
    *,
    username: str | None = "alice",
    name: str = "Alice",
    role: UserRole = UserRole.USER,
    language: Locale = Locale.EN,
    points: int = 0,
    purchase_discount: int = 0,
    personal_discount: int = 0,
    partner_balance_currency_override: Currency | None = None,
):
    return SimpleNamespace(
        id=None,
        telegram_id=telegram_id,
        username=username,
        referral_code="REFCODE",
        name=name,
        role=role,
        language=language,
        personal_discount=personal_discount,
        purchase_discount=purchase_discount,
        points=points,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
        partner_balance_currency_override=partner_balance_currency_override,
        referral_invite_settings=None,
        max_subscriptions=None,
        created_at=None,
        updated_at=None,
        current_subscription=None,
        subscriptions=[],
        referral=None,
    )


def make_user_dto(
    telegram_id: int,
    *,
    username: str | None = "alice",
    name: str = "Alice",
) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=username,
        referral_code="REFCODE",
        name=name,
        role=UserRole.USER,
        language=Locale.EN,
    )


def test_create_reuses_existing_user_after_integrity_error() -> None:
    service, uow = build_service()
    existing_user = make_user_model(412289221, username="alice")
    uow.repository.users.create = AsyncMock(
        side_effect=IntegrityError("INSERT", {}, Exception("duplicate telegram_id"))
    )
    uow.repository.users.get = AsyncMock(return_value=existing_user)
    service.add_to_recent_registered = AsyncMock()  # type: ignore[method-assign]
    service.clear_user_cache = AsyncMock()  # type: ignore[method-assign]
    aiogram_user = SimpleNamespace(
        id=412289221,
        username="alice",
        full_name="Alice",
        language_code=Locale.EN,
    )

    result = run_async(service.create(aiogram_user))

    assert result.telegram_id == 412289221
    uow.rollback.assert_awaited_once()
    service.add_to_recent_registered.assert_awaited_once_with(412289221)
    service.clear_user_cache.assert_awaited_once_with(412289221)


def test_search_query_accepts_negative_shadow_id() -> None:
    service, _uow = build_service()
    expected_user = make_user_dto(-555)
    service._search_users_by_telegram_id = AsyncMock(return_value=[expected_user])  # type: ignore[method-assign]
    service._search_users_by_login_or_name = AsyncMock(return_value=[])  # type: ignore[method-assign]

    result = run_async(service._search_users_by_query("-555"))

    assert result == [expected_user]
    service._search_users_by_telegram_id.assert_awaited_once_with(-555)
    service._search_users_by_login_or_name.assert_not_called()


def test_search_supports_exact_web_login() -> None:
    service, uow = build_service()
    exact_user_model = make_user_model(-555, username="alice")
    uow.repository.web_accounts.get_by_username = AsyncMock(
        return_value=SimpleNamespace(user_telegram_id=-555)
    )
    uow.repository.users.get = AsyncMock(return_value=exact_user_model)

    result = run_async(service._search_users_by_login_or_name("ALICE"))

    assert [user.telegram_id for user in result] == [-555]


def test_search_merges_partial_name_and_web_login_matches() -> None:
    service, uow = build_service()
    partial_name_user = make_user_dto(412289221, username="tg_412289221", name="Alina")
    partial_login_user_model = make_user_model(-555, username="alice", name="Alice")
    uow.repository.web_accounts.get_by_partial_username = AsyncMock(
        return_value=[SimpleNamespace(user_telegram_id=-555)]
    )
    uow.repository.users.get_by_ids = AsyncMock(return_value=[partial_login_user_model])
    service.get_by_partial_name = AsyncMock(return_value=[partial_name_user])  # type: ignore[method-assign]

    result = run_async(service._search_users_by_login_or_name("ali"))

    assert {user.telegram_id for user in result} == {412289221, -555}


def test_create_placeholder_user_does_not_touch_recent_registered() -> None:
    service, uow = build_service()
    created_user_model = make_user_model(777, username=None, name="777")
    uow.repository.users.create = AsyncMock(return_value=created_user_model)
    service.get = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service.add_to_recent_registered = AsyncMock()  # type: ignore[method-assign]
    service.clear_user_cache = AsyncMock()  # type: ignore[method-assign]

    result = run_async(service.create_placeholder_user(telegram_id=777))

    assert result.telegram_id == 777
    service.add_to_recent_registered.assert_not_awaited()
    service.clear_user_cache.assert_awaited_once_with(777)


def test_get_recent_registered_users_prunes_missing_cached_users() -> None:
    service, uow = build_service()
    service._get_recent_registered = AsyncMock(return_value=[1, 2])  # type: ignore[method-assign]
    uow.repository.users.get_by_ids = AsyncMock(return_value=[make_user_model(1)])
    service._remove_from_recent_registered = AsyncMock()  # type: ignore[method-assign]

    result = run_async(service.get_recent_registered_users())

    assert [user.telegram_id for user in result] == [1]
    service._remove_from_recent_registered.assert_awaited_once_with(2)


def test_clear_user_cache_invalidates_user_and_list_caches() -> None:
    service, _uow = build_service()
    service._clear_list_caches = AsyncMock()  # type: ignore[method-assign]

    run_async(service.clear_user_cache(412289221))

    service.redis_client.delete.assert_awaited_once()
    service._clear_list_caches.assert_awaited_once()


def test_set_current_subscription_updates_repo_and_clears_cache() -> None:
    service, uow = build_service()
    service.clear_user_cache = AsyncMock()  # type: ignore[method-assign]

    run_async(service.set_current_subscription(412289221, 9))

    uow.repository.users.update.assert_awaited_once_with(
        telegram_id=412289221,
        current_subscription_id=9,
    )
    service.clear_user_cache.assert_awaited_once_with(412289221)


def test_set_partner_balance_currency_override_updates_repo_and_clears_cache() -> None:
    service, uow = build_service()
    service.clear_user_cache = AsyncMock()  # type: ignore[method-assign]
    user = make_user_dto(412289221)

    run_async(service.set_partner_balance_currency_override(user, Currency.USD))

    uow.repository.users.update.assert_awaited_once_with(
        412289221,
        partner_balance_currency_override=Currency.USD,
    )
    service.clear_user_cache.assert_awaited_once_with(412289221)


def test_compare_and_update_falls_back_to_default_locale_for_unsupported_language() -> None:
    service, _uow = build_service()
    user = make_user_dto(412289221, username="alice", name="Alice")
    service.update = AsyncMock(return_value=user)  # type: ignore[method-assign]
    aiogram_user = SimpleNamespace(
        username="alice_new",
        full_name="Alice New",
        language_code="de",
    )

    run_async(service.compare_and_update(user, aiogram_user))

    assert user.username == "alice_new"
    assert user.name == "Alice New"
    assert user.language == Locale.EN
    service.update.assert_awaited_once()
