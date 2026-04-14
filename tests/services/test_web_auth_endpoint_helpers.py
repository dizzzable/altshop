from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.endpoints.web_auth import (
    _enforce_rate_limit,
    _has_valid_cookie_session,
    _resolve_web_auth_message,
)
from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import UserDto, WebAccountDto


def run_async(coroutine):
    return asyncio.run(coroutine)


def make_request(
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    raw_headers = list(headers or [])
    if cookies:
        cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        raw_headers.append((b"cookie", cookie_header.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "app": SimpleNamespace(state=SimpleNamespace(config=None)),
    }
    return Request(scope)


def build_config() -> SimpleNamespace:
    return SimpleNamespace(
        locales=["ru", "en"],
        default_locale="ru",
        web_app=SimpleNamespace(
            rate_limit_enabled=True,
            rate_limit_max_requests=2,
            rate_limit_window=60,
        ),
    )


def build_user(*, telegram_id: int = 412289221, language: Locale = Locale.RU) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username="alice",
        referral_code="REFCODE",
        name="Alice",
        role=UserRole.USER,
        language=language,
    )


def build_web_account() -> WebAccountDto:
    return WebAccountDto(
        id=77,
        user_telegram_id=412289221,
        username="alice",
        password_hash="hash",
        token_version=4,
        email="alice@example.com",
        email_normalized="alice@example.com",
    )


def test_resolve_web_auth_message_returns_readable_strings_and_preserves_fallbacks() -> None:
    assert _resolve_web_auth_message("email_verify_request_sent", "ru") == (
        "Письмо с подтверждением отправлено"
    )
    assert _resolve_web_auth_message("password_updated", "en") == "Password updated"
    assert _resolve_web_auth_message("password_updated", "de") == "Пароль обновлен"  # type: ignore[arg-type]
    assert _resolve_web_auth_message("missing_key", "ru") == ""


def test_enforce_rate_limit_sets_expiry_and_raises_after_limit() -> None:
    config = build_config()
    redis_client = SimpleNamespace(
        incr=AsyncMock(side_effect=[1, 2, 3]),
        expire=AsyncMock(),
    )

    run_async(_enforce_rate_limit(config, redis_client, "auth:key"))
    run_async(_enforce_rate_limit(config, redis_client, "auth:key"))

    with pytest.raises(HTTPException) as error_info:
        run_async(_enforce_rate_limit(config, redis_client, "auth:key"))

    assert error_info.value.status_code == 429
    redis_client.expire.assert_awaited_once_with("auth:key", 60)


def test_enforce_rate_limit_degrades_open_when_redis_errors() -> None:
    config = build_config()
    redis_client = SimpleNamespace(
        incr=AsyncMock(side_effect=RuntimeError("redis down")),
        expire=AsyncMock(),
    )

    run_async(_enforce_rate_limit(config, redis_client, "auth:key"))

    redis_client.expire.assert_not_awaited()


def test_has_valid_cookie_session_truth_table() -> None:
    web_account_service = SimpleNamespace(get_by_user_telegram_id=AsyncMock())

    missing_cookie_request = make_request()
    assert (
        run_async(
            _has_valid_cookie_session(
                request=missing_cookie_request,
                cookie_name="access",
                token_verifier=lambda token: {"sub": token},
                web_account_service=web_account_service,
            )
        )
        is False
    )

    invalid_token_request = make_request(cookies={"access": "bad-token"})
    assert (
        run_async(
            _has_valid_cookie_session(
                request=invalid_token_request,
                cookie_name="access",
                token_verifier=lambda token: None,
                web_account_service=web_account_service,
            )
        )
        is False
    )

    original_parser = _has_valid_cookie_session.__globals__["parse_token_subject_and_version"]
    try:
        _has_valid_cookie_session.__globals__["parse_token_subject_and_version"] = (
            lambda payload: (_ for _ in ()).throw(ValueError("bad payload"))
        )
        assert (
            run_async(
                _has_valid_cookie_session(
                    request=invalid_token_request,
                    cookie_name="access",
                    token_verifier=lambda token: {"sub": token},
                    web_account_service=web_account_service,
                )
            )
            is False
        )

        _has_valid_cookie_session.__globals__["parse_token_subject_and_version"] = (
            lambda payload: (412289221, 7)
        )
        web_account_service.get_by_user_telegram_id = AsyncMock(
            return_value=SimpleNamespace(token_version=6)
        )
        assert (
            run_async(
                _has_valid_cookie_session(
                    request=invalid_token_request,
                    cookie_name="access",
                    token_verifier=lambda token: {"sub": token},
                    web_account_service=web_account_service,
                )
            )
            is False
        )

        web_account_service.get_by_user_telegram_id = AsyncMock(
            return_value=SimpleNamespace(token_version=7)
        )
        assert (
            run_async(
                _has_valid_cookie_session(
                    request=invalid_token_request,
                    cookie_name="access",
                    token_verifier=lambda token: {"sub": token},
                    web_account_service=web_account_service,
                )
            )
            is True
        )
    finally:
        _has_valid_cookie_session.__globals__["parse_token_subject_and_version"] = original_parser


def test_resolve_web_auth_message_covers_recovery_messages_in_russian() -> None:
    assert _resolve_web_auth_message("email_verify_request_sent", "ru") == (
        "Письмо с подтверждением отправлено"
    )
    assert _resolve_web_auth_message("email_verify_confirmed", "ru") == "Email подтвержден"
    assert _resolve_web_auth_message("password_forgot_sent", "ru") == (
        "Если аккаунт существует и email подтвержден, инструкция по восстановлению отправлена"
    )
    assert _resolve_web_auth_message("password_updated", "ru") == "Пароль обновлен"
