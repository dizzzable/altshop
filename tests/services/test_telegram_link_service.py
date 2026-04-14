from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.infrastructure.database.models.dto import WebAccountDto
from src.services.telegram_link import TelegramLinkError, TelegramLinkService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            web_accounts=SimpleNamespace(
                update=AsyncMock(),
                get=AsyncMock(return_value=None),
                get_by_user_telegram_id=AsyncMock(return_value=None),
                delete=AsyncMock(),
            ),
            users=SimpleNamespace(
                get=AsyncMock(return_value=None),
                create=AsyncMock(),
                update=AsyncMock(),
                delete=AsyncMock(),
                generate_unique_referral_code=AsyncMock(return_value="REFCODE"),
                has_material_data=AsyncMock(return_value=False),
                reassign_telegram_id_references=AsyncMock(),
            ),
            auth_challenges=SimpleNamespace(update=AsyncMock()),
        )
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def build_service() -> tuple[TelegramLinkService, DummyUow]:
    uow = DummyUow()
    service = TelegramLinkService(
        uow=uow,
        challenge_service=SimpleNamespace(),
        bot=SimpleNamespace(),
        settings_service=SimpleNamespace(),
    )
    return service, uow


def build_web_account_dto(*, account_id: int = 77, telegram_id: int = -555) -> WebAccountDto:
    return WebAccountDto(
        id=account_id,
        user_telegram_id=telegram_id,
        username="alice",
        password_hash="hash",
        token_version=4,
    )


def make_user_model(
    telegram_id: int,
    *,
    username: str | None = "alice",
    name: str = "Alice",
    role=None,
    language=None,
    points: int = 0,
    personal_discount: int = 0,
    purchase_discount: int = 0,
):
    return SimpleNamespace(
        telegram_id=telegram_id,
        username=username,
        name=name,
        role=role,
        language=language,
        points=points,
        personal_discount=personal_discount,
        purchase_discount=purchase_discount,
    )


def make_account_model(
    *,
    account_id: int = 77,
    user_telegram_id: int = -555,
    token_version: int = 4,
    username: str = "alice",
):
    return SimpleNamespace(
        id=account_id,
        user_telegram_id=user_telegram_id,
        token_version=token_version,
        username=username,
        password_hash="hash",
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


def test_request_code_returns_result_even_when_telegram_delivery_fails() -> None:
    service, uow = build_service()
    web_account = build_web_account_dto()
    service.challenge_service = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                challenge=SimpleNamespace(id=1, meta=None),
                code="123456",
                token="challenge-token",
            )
        )
    )
    service.bot = SimpleNamespace(
        send_message=AsyncMock(side_effect=RuntimeError("telegram down")),
        get_me=AsyncMock(return_value=SimpleNamespace(username="altshop_bot")),
    )
    service.settings_service = SimpleNamespace(
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
    uow.repository.users.get = AsyncMock(return_value=make_user_model(-555))

    result = run_async(
        service.request_code(
            web_account=web_account,
            telegram_id=412289221,
            ttl_seconds=600,
            attempts=5,
            return_to_miniapp=True,
        )
    )

    assert result.delivered is False
    assert result.expires_in_seconds == 600
    assert result.destination == 412289221
    assert result.bot_confirm_url == "https://t.me/altshop_bot?start=tglinkapp_challenge-token"
    assert (
        result.bot_confirm_deep_link
        == "tg://resolve?domain=altshop_bot&start=tglinkapp_challenge-token"
    )
    service.challenge_service.create.assert_awaited_once()
    assert service.challenge_service.create.await_args.kwargs["destination"] == "412289221"
    assert service.challenge_service.create.await_args.kwargs["meta"] == {
        "telegram_id": 412289221,
        "return_to_miniapp": True,
    }
    uow.repository.auth_challenges.update.assert_not_awaited()


def test_confirm_code_and_confirm_token_route_through_safe_auto_link() -> None:
    service, _uow = build_service()
    web_account = build_web_account_dto(account_id=77)
    linked_account = build_web_account_dto(account_id=77, telegram_id=412289221)
    service.challenge_service = SimpleNamespace(
        verify_code=AsyncMock(
            return_value=SimpleNamespace(
                ok=True,
                reason=None,
                challenge=SimpleNamespace(id=1, meta=None, web_account_id=77),
            )
        ),
        verify_token=AsyncMock(
            return_value=SimpleNamespace(
                ok=True,
                reason=None,
                challenge=SimpleNamespace(id=1, meta=None, web_account_id=77),
            )
        ),
    )
    service._safe_auto_link = AsyncMock(return_value=linked_account)  # type: ignore[method-assign]
    service._delete_verification_message = AsyncMock()  # type: ignore[method-assign]

    code_result = run_async(
        service.confirm_code(
            web_account=web_account,
            telegram_id=412289221,
            code="123456",
        )
    )
    token_result = run_async(
        service.confirm_token(
            telegram_id=412289221,
            token="challenge-token",
        )
    )

    assert code_result.linked_telegram_id == 412289221
    assert token_result.linked_telegram_id == 412289221
    assert service._safe_auto_link.await_count == 2
    service.challenge_service.verify_code.assert_awaited_once()
    service.challenge_service.verify_token.assert_awaited_once()


def test_handle_already_linked_account_refreshes_snooze_and_returns_current_dto() -> None:
    service, uow = build_service()
    current_account = make_account_model(account_id=77, user_telegram_id=412289221)
    updated_account = make_account_model(account_id=77, user_telegram_id=412289221)
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_account)

    result = run_async(
        service._handle_already_linked_account(
            current_account=current_account,
            telegram_id=412289221,
        )
    )

    assert result is not None
    assert result.user_telegram_id == 412289221
    uow.repository.web_accounts.update.assert_awaited_once_with(
        77,
        link_prompt_snooze_until=None,
    )
    uow.commit.assert_awaited_once()


def test_assert_telegram_not_linked_elsewhere_rejects_foreign_account() -> None:
    service, uow = build_service()
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(
        return_value=make_account_model(account_id=88, user_telegram_id=412289221)
    )

    with pytest.raises(TelegramLinkError) as error_info:
        run_async(
            service._assert_telegram_not_linked_elsewhere(
                current_account_id=77,
                telegram_id=412289221,
            )
        )

    assert error_info.value.code == "TELEGRAM_ALREADY_LINKED"


def test_assert_merge_allowed_preserves_manual_merge_rule() -> None:
    service, uow = build_service()
    source_user = make_user_model(555)
    target_user = make_user_model(412289221)
    uow.repository.users.has_material_data = AsyncMock(side_effect=[True, True, True])

    with pytest.raises(TelegramLinkError) as error_info:
        run_async(
            service._assert_merge_allowed(
                source_user=source_user,
                target_user=target_user,
            )
        )

    assert error_info.value.code == "MANUAL_MERGE_REQUIRED"


def test_safe_auto_link_preserves_reassignment_merge_and_shadow_cleanup() -> None:
    service, uow = build_service()
    current_account = make_account_model(account_id=77, user_telegram_id=-4, token_version=4)
    updated_account = make_account_model(account_id=77, user_telegram_id=412289221, token_version=5)
    source_user = make_user_model(-4, points=10, personal_discount=5, purchase_discount=7)
    target_user = make_user_model(412289221, username=None, name="412289221", points=1)

    service._get_web_account_or_error = AsyncMock(return_value=current_account)  # type: ignore[method-assign]
    service._handle_already_linked_account = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._assert_telegram_not_linked_elsewhere = AsyncMock()  # type: ignore[method-assign]
    service._get_source_user_or_error = AsyncMock(return_value=source_user)  # type: ignore[method-assign]
    service._get_or_create_target_user = AsyncMock(return_value=target_user)  # type: ignore[method-assign]
    service._assert_merge_allowed = AsyncMock(return_value=True)  # type: ignore[method-assign]
    service._merge_user_values = AsyncMock()  # type: ignore[method-assign]
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_account)

    result = run_async(service._safe_auto_link(web_account_id=77, telegram_id=412289221))

    assert result.user_telegram_id == 412289221
    uow.repository.users.reassign_telegram_id_references.assert_awaited_once_with(
        source_telegram_id=-4,
        target_telegram_id=412289221,
    )
    service._merge_user_values.assert_awaited_once_with(
        source_user_telegram_id=-4,
        target_user_telegram_id=412289221,
        source_has_data=True,
    )
    uow.repository.web_accounts.update.assert_awaited_once_with(
        77,
        user_telegram_id=412289221,
        token_version=5,
        link_prompt_snooze_until=None,
    )
    uow.repository.users.delete.assert_awaited_once_with(-4)
    uow.commit.assert_awaited_once()


def test_create_target_user_falls_back_to_existing_after_integrity_conflict() -> None:
    service, uow = build_service()
    source_user = make_user_model(-555, username="alice", name="Alice", role=None, language=None)
    existing_target = make_user_model(412289221, username="alice", name="Alice")
    uow.repository.users.create = AsyncMock(
        side_effect=IntegrityError("INSERT", {}, Exception("duplicate telegram_id"))
    )
    uow.repository.users.get = AsyncMock(return_value=existing_target)

    result = run_async(
        service._create_target_user(
            telegram_id=412289221,
            source_user=source_user,
        )
    )

    assert result.telegram_id == 412289221
    uow.repository.users.generate_unique_referral_code.assert_awaited_once()


def test_merge_user_values_preserves_fallback_profile_and_maxes_rewards() -> None:
    service, uow = build_service()
    source_user = make_user_model(
        -555,
        username="alice",
        name="Alice",
        points=15,
        personal_discount=10,
        purchase_discount=20,
    )
    target_user = make_user_model(
        412289221,
        username=None,
        name="412289221",
        points=5,
        personal_discount=2,
        purchase_discount=3,
    )
    uow.repository.users.get = AsyncMock(side_effect=[source_user, target_user])

    run_async(
        service._merge_user_values(
            source_user_telegram_id=-555,
            target_user_telegram_id=412289221,
            source_has_data=True,
        )
    )

    uow.repository.users.update.assert_awaited_once_with(
        412289221,
        username="alice",
        name="Alice",
        points=15,
        personal_discount=10,
        purchase_discount=20,
    )
