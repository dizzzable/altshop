from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.core.enums import Locale
from src.core.security.password import hash_password
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import WebAccountDto
from src.services.auth_challenge import (
    ChallengeChannel,
    ChallengeErrorReason,
    ChallengePurpose,
)
from src.services.email_recovery import EmailRecoveryService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self) -> None:
        self.repository = SimpleNamespace(
            web_accounts=SimpleNamespace(
                update=AsyncMock(),
                get=AsyncMock(return_value=None),
                get_by_email=AsyncMock(return_value=None),
                get_by_username=AsyncMock(return_value=None),
                get_by_user_telegram_id=AsyncMock(return_value=None),
            ),
            users=SimpleNamespace(get=AsyncMock(return_value=None)),
        )
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def build_service() -> tuple[EmailRecoveryService, DummyUow]:
    uow = DummyUow()
    service = EmailRecoveryService(
        uow=uow,
        config=SimpleNamespace(
            web_app=SimpleNamespace(
                url_str="https://panel.example.com",
                email_verify_ttl_seconds=600,
                auth_challenge_attempts=5,
                password_reset_ttl_seconds=900,
            ),
            domain=SimpleNamespace(get_secret_value=lambda: "example.com"),
        ),
        challenge_service=SimpleNamespace(),
        email_sender=SimpleNamespace(send=AsyncMock(return_value=True)),
        bot=SimpleNamespace(send_message=AsyncMock()),
        settings_service=SimpleNamespace(get_branding_settings=AsyncMock()),
    )
    return service, uow


def make_account_model(
    *,
    account_id: int = 77,
    username: str = "alice",
    user_telegram_id: int = 412289221,
    token_version: int = 4,
    email: str | None = "Alice@Example.com",
    email_normalized: str | None = "alice@example.com",
    email_verified_at: datetime | None = None,
    password_hash: str | None = None,
    requires_password_change: bool = False,
    temporary_password_expires_at: datetime | None = None,
):
    return SimpleNamespace(
        id=account_id,
        username=username,
        user_telegram_id=user_telegram_id,
        token_version=token_version,
        password_hash=password_hash or hash_password("current-password"),
        email=email,
        email_normalized=email_normalized,
        email_verified_at=email_verified_at,
        credentials_bootstrapped_at=None,
        requires_password_change=requires_password_change,
        temporary_password_expires_at=temporary_password_expires_at,
        created_at=None,
        updated_at=None,
    )


def build_web_account_dto(
    *,
    account_id: int = 77,
    email: str | None = "Alice@Example.com",
    email_normalized: str | None = "alice@example.com",
    email_verified_at: datetime | None = None,
) -> WebAccountDto:
    return WebAccountDto(
        id=account_id,
        user_telegram_id=412289221,
        username="alice",
        password_hash="hash",
        token_version=4,
        email=email,
        email_normalized=email_normalized,
        email_verified_at=email_verified_at,
    )


def test_set_email_normalizes_and_clears_verification() -> None:
    service, uow = build_service()
    updated_model = make_account_model(
        email="Alice@Example.com",
        email_normalized="alice@example.com",
        email_verified_at=None,
    )
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_model)

    result = run_async(service.set_email(web_account_id=77, email=" Alice@Example.com "))

    assert result.email == "Alice@Example.com"
    assert result.email_normalized == "alice@example.com"
    uow.repository.web_accounts.update.assert_awaited_once_with(
        77,
        email="Alice@Example.com",
        email_normalized="alice@example.com",
        email_verified_at=None,
    )
    uow.commit.assert_awaited_once()


def test_set_email_maps_duplicate_integrity_error() -> None:
    service, uow = build_service()
    uow.repository.web_accounts.update = AsyncMock(
        side_effect=IntegrityError("UPDATE", {}, Exception("duplicate email"))
    )

    with pytest.raises(ValueError, match="Email is already used"):
        run_async(service.set_email(web_account_id=77, email="alice@example.com"))

    uow.rollback.assert_awaited_once()


def test_request_email_verification_creates_challenge_and_sends_branded_email() -> None:
    service, _uow = build_service()
    web_account = build_web_account_dto()
    service.challenge_service = SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(code="123456", token="email-token"))
    )
    service.settings_service = SimpleNamespace(
        get_branding_settings=AsyncMock(
            return_value=SimpleNamespace(project_name="My Shop")
        )
    )

    delivered = run_async(service.request_email_verification(web_account=web_account))

    assert delivered is True
    service.challenge_service.create.assert_awaited_once()
    assert service.challenge_service.create.await_args.kwargs == {
        "web_account_id": 77,
        "purpose": ChallengePurpose.EMAIL_VERIFY,
        "channel": service.challenge_service.create.await_args.kwargs["channel"],
        "destination": "alice@example.com",
        "ttl_seconds": 600,
        "attempts": 5,
        "include_code": True,
        "include_token": True,
        "meta": {"email": "alice@example.com"},
    }
    assert service.challenge_service.create.await_args.kwargs["channel"] == ChallengeChannel.EMAIL
    service.email_sender.send.assert_awaited_once()
    assert service.email_sender.send.await_args.kwargs["subject"] == "My Shop email verification"
    assert "/webapp/dashboard/settings?email_verify_token=email-token" in (
        service.email_sender.send.await_args.kwargs["text_body"]
    )


def test_confirm_email_verifies_by_code_and_marks_account() -> None:
    service, uow = build_service()
    account = make_account_model(email_verified_at=None)
    updated_model = make_account_model(email_verified_at=datetime_now())
    uow.repository.web_accounts.get = AsyncMock(return_value=account)
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_model)
    service.challenge_service = SimpleNamespace(
        verify_code=AsyncMock(
            return_value=SimpleNamespace(ok=True, reason=None, challenge=SimpleNamespace())
        )
    )

    result = run_async(service.confirm_email(web_account_id=77, code="123456", token=None))

    assert result.email_verified_at is not None
    service.challenge_service.verify_code.assert_awaited_once_with(
        web_account_id=77,
        purpose=ChallengePurpose.EMAIL_VERIFY,
        destination="alice@example.com",
        code="123456",
    )
    uow.repository.web_accounts.update.assert_awaited_once()


def test_confirm_email_maps_too_many_attempts() -> None:
    service, uow = build_service()
    uow.repository.web_accounts.get = AsyncMock(return_value=make_account_model())
    service.challenge_service = SimpleNamespace(
        verify_token=AsyncMock(
            return_value=SimpleNamespace(
                ok=False,
                reason=ChallengeErrorReason.TOO_MANY_ATTEMPTS,
                challenge=None,
            )
        )
    )

    with pytest.raises(ValueError, match="Too many attempts. Request a new verification code."):
        run_async(service.confirm_email(web_account_id=77, code=None, token="email-token"))


def test_forgot_password_is_silent_for_missing_or_unverified_accounts() -> None:
    service, uow = build_service()
    unverified_account = make_account_model(email_verified_at=None)
    uow.repository.web_accounts.get_by_email = AsyncMock(side_effect=[None, unverified_account])
    service._send_password_reset = AsyncMock()  # type: ignore[method-assign]

    run_async(service.forgot_password(username=None, email="missing@example.com"))
    run_async(service.forgot_password(username=None, email="alice@example.com"))

    service._send_password_reset.assert_not_awaited()


def test_forgot_password_sends_reset_for_verified_account() -> None:
    service, uow = build_service()
    verified_account = make_account_model(email_verified_at=datetime_now())
    uow.repository.web_accounts.get_by_email = AsyncMock(return_value=verified_account)
    service._send_password_reset = AsyncMock()  # type: ignore[method-assign]

    run_async(service.forgot_password(username=None, email="Alice@Example.com"))

    service._send_password_reset.assert_awaited_once()
    sent_account = service._send_password_reset.await_args.kwargs["account"]
    assert sent_account.email_normalized == "alice@example.com"


def test_request_telegram_password_reset_creates_challenge_for_linked_user() -> None:
    service, uow = build_service()
    account = make_account_model()
    uow.repository.web_accounts.get_by_username = AsyncMock(return_value=account)
    uow.repository.users.get = AsyncMock(return_value=SimpleNamespace(language=Locale.RU))
    service.challenge_service = SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(code="654321"))
    )
    service._send_password_reset_telegram_code = AsyncMock()  # type: ignore[method-assign]

    run_async(service.request_telegram_password_reset(username="Alice"))

    service.challenge_service.create.assert_awaited_once_with(
        web_account_id=77,
        purpose=ChallengePurpose.PASSWORD_RESET,
        channel=ChallengeChannel.TELEGRAM,
        destination="412289221",
        ttl_seconds=900,
        attempts=5,
        include_code=True,
        include_token=False,
        meta={
            "telegram_id": 412289221,
            "username": "alice",
        },
    )
    service._send_password_reset_telegram_code.assert_awaited_once_with(
        telegram_id=412289221,
        code="654321",
        language=Locale.RU,
    )


def test_request_telegram_password_reset_is_silent_for_unknown_or_shadow_accounts() -> None:
    service, uow = build_service()
    shadow_account = make_account_model(user_telegram_id=-5)
    uow.repository.web_accounts.get_by_username = AsyncMock(side_effect=[None, shadow_account])
    service.challenge_service = SimpleNamespace(create=AsyncMock())

    run_async(service.request_telegram_password_reset(username="missing"))
    run_async(service.request_telegram_password_reset(username="shadow"))

    service.challenge_service.create.assert_not_awaited()


def test_send_password_reset_telegram_code_tolerates_branding_and_delivery_failures() -> None:
    service, _uow = build_service()
    service.settings_service = SimpleNamespace(
        get_branding_settings=AsyncMock(side_effect=RuntimeError("branding failed"))
    )
    service.bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("blocked")))

    run_async(
        service._send_password_reset_telegram_code(
            telegram_id=412289221,
            code="654321",
            language=Locale.RU,
        )
    )

    service.bot.send_message.assert_awaited_once()


def test_reset_password_by_link_updates_password_from_valid_token() -> None:
    service, _uow = build_service()
    service.challenge_service = SimpleNamespace(
        verify_token=AsyncMock(
            return_value=SimpleNamespace(
                ok=True,
                challenge=SimpleNamespace(web_account_id=77),
            )
        )
    )
    service._update_password = AsyncMock()  # type: ignore[method-assign]

    run_async(service.reset_password_by_link(token="reset-token", new_password="new-pass"))

    service._update_password.assert_awaited_once_with(
        web_account_id=77,
        new_password="new-pass",
    )


def test_reset_password_by_code_maps_too_many_attempts() -> None:
    service, uow = build_service()
    verified_account = make_account_model(email_verified_at=datetime_now())
    uow.repository.web_accounts.get_by_email = AsyncMock(return_value=verified_account)
    service.challenge_service = SimpleNamespace(
        verify_code=AsyncMock(
            return_value=SimpleNamespace(
                ok=False,
                reason=ChallengeErrorReason.TOO_MANY_ATTEMPTS,
            )
        )
    )

    with pytest.raises(ValueError, match="Too many attempts. Request a new reset code."):
        run_async(
            service.reset_password_by_code(
                email="alice@example.com",
                code="123456",
                new_password="new-pass",
            )
        )


def test_reset_password_by_telegram_code_updates_password_for_linked_account() -> None:
    service, uow = build_service()
    linked_account = make_account_model(user_telegram_id=412289221)
    uow.repository.web_accounts.get_by_username = AsyncMock(return_value=linked_account)
    service.challenge_service = SimpleNamespace(
        verify_code=AsyncMock(return_value=SimpleNamespace(ok=True, reason=None))
    )
    service._update_password = AsyncMock()  # type: ignore[method-assign]

    run_async(
        service.reset_password_by_telegram_code(
            username="Alice",
            code="654321",
            new_password="new-pass",
        )
    )

    service._update_password.assert_awaited_once_with(
        web_account_id=77,
        new_password="new-pass",
    )


def test_change_password_rejects_invalid_current_password() -> None:
    service, uow = build_service()
    uow.repository.web_accounts.get = AsyncMock(return_value=make_account_model())

    with pytest.raises(ValueError, match="Invalid current password"):
        run_async(
            service.change_password(
                web_account_id=77,
                current_password="wrong-password",
                new_password="new-pass",
            )
        )


def test_change_password_returns_updated_dto() -> None:
    service, uow = build_service()
    updated_model = make_account_model(token_version=5)
    uow.repository.web_accounts.get = AsyncMock(return_value=make_account_model())
    service._update_password = AsyncMock(
        return_value=WebAccountDto.from_model(updated_model)
    )  # type: ignore[method-assign]

    result = run_async(
        service.change_password(
            web_account_id=77,
            current_password="current-password",
            new_password="new-pass",
        )
    )

    assert result.token_version == 5
    service._update_password.assert_awaited_once_with(
        web_account_id=77,
        new_password="new-pass",
    )


def test_issue_temporary_password_for_dev_preserves_flags_and_expiry() -> None:
    service, uow = build_service()
    account = make_account_model()
    updated_account = make_account_model(
        token_version=5,
        requires_password_change=True,
        temporary_password_expires_at=datetime_now(),
    )
    uow.repository.web_accounts.get_by_user_telegram_id = AsyncMock(return_value=account)
    uow.repository.web_accounts.update = AsyncMock(return_value=updated_account)

    username, temp_password, expires_at = run_async(
        service.issue_temporary_password_for_dev(
            target_telegram_id=412289221,
            ttl_seconds=300,
        )
    )

    assert username == "alice"
    assert temp_password.startswith("Tmp")
    assert len(temp_password) == 9
    assert expires_at == uow.repository.web_accounts.update.await_args.kwargs[
        "temporary_password_expires_at"
    ]
    assert uow.repository.web_accounts.update.await_args.kwargs["requires_password_change"] is True
    assert uow.repository.web_accounts.update.await_args.kwargs["token_version"] == 5


def test_issue_temporary_password_for_dev_rejects_non_positive_ttl() -> None:
    service, _uow = build_service()

    with pytest.raises(ValueError, match="Invalid temporary password TTL"):
        run_async(
            service.issue_temporary_password_for_dev(
                target_telegram_id=412289221,
                ttl_seconds=0,
            )
        )


def test_build_front_url_preserves_webapp_suffix_rules() -> None:
    service, _uow = build_service()
    service.config.web_app.url_str = "https://panel.example.com"
    assert service._build_front_url("/auth/reset-password") == (
        "https://panel.example.com/webapp/auth/reset-password"
    )

    service.config.web_app.url_str = "https://panel.example.com/webapp"
    assert service._build_front_url("dashboard/settings") == (
        "https://panel.example.com/webapp/dashboard/settings"
    )

    service.config.web_app.url_str = ""
    assert service._build_front_url("/auth/reset-password") == (
        "https://example.com/webapp/auth/reset-password"
    )
