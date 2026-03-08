from __future__ import annotations

import asyncio
import inspect
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import User as AiogramUser
from fastapi import HTTPException, Response
from pydantic import SecretStr
from starlette.requests import Request

from src.api.dependencies.web_access import (
    ACCESS_DENIED_INVITE_ONLY,
    ACCESS_DENIED_REGISTRATION_DISABLED,
    ACCESS_DENIED_SERVICE_RESTRICTED,
    ACCESS_DENIED_VALID_INVITE_REQUIRED,
)
from src.api.endpoints import web_auth as web_auth_module
from src.api.endpoints.web_auth import (
    LoginRequest,
    RegisterRequest,
    TelegramAuthRequest,
    login,
    register,
    telegram_auth,
)
from src.core.enums import AccessMode, Locale, UserRole
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.access import AccessService
from src.services.web_account import WebAuthResult

REGISTER_ENDPOINT = getattr(
    inspect.unwrap(register), "__dishka_orig_func__", inspect.unwrap(register)
)
LOGIN_ENDPOINT = getattr(inspect.unwrap(login), "__dishka_orig_func__", inspect.unwrap(login))
TELEGRAM_AUTH_ENDPOINT = getattr(
    inspect.unwrap(telegram_auth),
    "__dishka_orig_func__",
    inspect.unwrap(telegram_auth),
)


def _build_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {"type": "http", "headers": raw_headers}
    return Request(scope)


def _build_user(
    *,
    telegram_id: int,
    username: str,
    role: UserRole = UserRole.USER,
    is_blocked: bool = False,
) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=username,
        referral_code=f"code{abs(telegram_id)}",
        name=f"User {telegram_id}",
        role=role,
        language=Locale.EN,
        is_blocked=is_blocked,
    )


def _build_web_account(*, user_telegram_id: int, username: str) -> WebAccountDto:
    return WebAccountDto(
        id=1,
        user_telegram_id=user_telegram_id,
        username=username,
        password_hash="hashed",
        token_version=0,
    )


def _build_web_auth_result(
    *,
    user: UserDto,
    username: str,
    is_new_user: bool,
) -> WebAuthResult:
    return WebAuthResult(
        user=user,
        web_account=_build_web_account(user_telegram_id=user.telegram_id, username=username),
        access_token="access-token",
        refresh_token="refresh-token",
        is_new_user=is_new_user,
    )


def _assert_auth_cookies_set(response: Response) -> None:
    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any("altshop_access_token=" in header for header in set_cookie_headers)
    assert any("altshop_refresh_token=" in header for header in set_cookie_headers)


def _build_config(
    *,
    token: str = "bot-token",
    rate_limit_enabled: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        bot=SimpleNamespace(token=SecretStr(token)),
        web_app=SimpleNamespace(
            rate_limit_enabled=rate_limit_enabled,
            rate_limit_max_requests=10,
            rate_limit_window=60,
            telegram_link_code_ttl_seconds=300,
            auth_challenge_attempts=3,
        ),
    )


def _build_settings_service(
    *,
    access_mode: AccessMode,
    rules_required: bool = False,
    channel_required: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                access_mode=access_mode,
                rules_required=rules_required,
                channel_required=channel_required,
            )
        ),
        get_access_mode=AsyncMock(return_value=access_mode),
    )


def _build_notification_service() -> SimpleNamespace:
    return SimpleNamespace(system_notify=AsyncMock())


def _build_partner_service() -> SimpleNamespace:
    return SimpleNamespace(handle_new_user_referral=AsyncMock())


def _build_referral_service() -> SimpleNamespace:
    return SimpleNamespace(
        handle_referral=AsyncMock(),
        is_referral_event=AsyncMock(return_value=False),
    )


def _build_user_service(
    *,
    existing_user: UserDto | None,
    referrer: UserDto | None = None,
    created_user: UserDto | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        get=AsyncMock(return_value=existing_user),
        get_by_referral_code=AsyncMock(return_value=referrer),
        create=AsyncMock(return_value=created_user or existing_user),
        update=AsyncMock(side_effect=lambda user: user),
    )


def _build_web_account_service_for_register(result: WebAuthResult) -> SimpleNamespace:
    return SimpleNamespace(register=AsyncMock(return_value=result))


def _build_web_account_service_for_login(result: WebAuthResult) -> SimpleNamespace:
    return SimpleNamespace(login=AsyncMock(return_value=result))


def _build_web_account_service_for_telegram(result: WebAuthResult | None = None) -> SimpleNamespace:
    return SimpleNamespace(get_or_create_for_telegram_user=AsyncMock(return_value=result))


def test_invited_register_without_referral_code_returns_invite_only() -> None:
    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    existing_user = None
    user_service = _build_user_service(existing_user=existing_user, referrer=None)
    web_account_service = SimpleNamespace(register=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            REGISTER_ENDPOINT(
                register_data=RegisterRequest(username="new_user", password="secret123"),
                response=Response(),
                web_account_service=web_account_service,
                referral_service=_build_referral_service(),
                partner_service=_build_partner_service(),
                notification_service=_build_notification_service(),
                user_service=user_service,
                settings_service=settings_service,
                telegram_link_service=SimpleNamespace(request_code=AsyncMock()),
                config=_build_config(),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == ACCESS_DENIED_INVITE_ONLY
    assert web_account_service.register.await_count == 0


def test_invited_register_with_invalid_referral_code_returns_valid_invite_required() -> None:
    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    user_service = _build_user_service(existing_user=None, referrer=None)
    web_account_service = SimpleNamespace(register=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            REGISTER_ENDPOINT(
                register_data=RegisterRequest(
                    username="new_user",
                    password="secret123",
                    referral_code="invalidcode",
                ),
                response=Response(),
                web_account_service=web_account_service,
                referral_service=_build_referral_service(),
                partner_service=_build_partner_service(),
                notification_service=_build_notification_service(),
                user_service=user_service,
                settings_service=settings_service,
                telegram_link_service=SimpleNamespace(request_code=AsyncMock()),
                config=_build_config(),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == ACCESS_DENIED_VALID_INVITE_REQUIRED
    assert web_account_service.register.await_count == 0


def test_invited_register_with_valid_referral_code_succeeds_and_assigns_referral() -> None:
    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    referrer = _build_user(telegram_id=5000, username="referrer")
    created_user = _build_user(telegram_id=-1, username="new_user")
    user_service = _build_user_service(
        existing_user=None, referrer=referrer, created_user=created_user
    )

    web_result = _build_web_auth_result(user=created_user, username="new_user", is_new_user=True)
    web_account_service = _build_web_account_service_for_register(web_result)
    referral_service = _build_referral_service()
    partner_service = _build_partner_service()

    response_obj = Response()
    response = asyncio.run(
        REGISTER_ENDPOINT(
            register_data=RegisterRequest(
                username="new_user",
                password="secret123",
                referral_code="valid1234",
            ),
            response=response_obj,
            web_account_service=web_account_service,
            referral_service=referral_service,
            partner_service=partner_service,
            notification_service=_build_notification_service(),
            user_service=user_service,
            settings_service=settings_service,
            telegram_link_service=SimpleNamespace(request_code=AsyncMock()),
            config=_build_config(),
        )
    )

    assert response.auth_source == "WEB_PASSWORD"
    assert response.is_new_user is True
    _assert_auth_cookies_set(response_obj)
    assert web_account_service.register.await_count == 1
    assert referral_service.handle_referral.await_count == 1
    assert partner_service.handle_new_user_referral.await_count == 1


def test_invited_telegram_auth_new_user_without_referral_returns_invite_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_auth_module, "verify_telegram_hash", lambda *_args, **_kwargs: True)
    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    user_service = _build_user_service(existing_user=None, referrer=None)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            TELEGRAM_AUTH_ENDPOINT(
                auth_request=TelegramAuthRequest(
                    id=12345,
                    first_name="New",
                    auth_date=int(time.time()),
                    hash="sig",
                ),
                response=Response(),
                user_service=user_service,
                config=_build_config(),
                referral_service=_build_referral_service(),
                partner_service=_build_partner_service(),
                notification_service=_build_notification_service(),
                settings_service=settings_service,
                web_account_service=_build_web_account_service_for_telegram(),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == ACCESS_DENIED_INVITE_ONLY
    assert user_service.create.await_count == 0


def test_invited_telegram_auth_new_user_with_valid_referral_succeeds_and_assigns_referral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_auth_module, "verify_telegram_hash", lambda *_args, **_kwargs: True)

    created_user = _build_user(telegram_id=777001, username="tg_new")
    referrer = _build_user(telegram_id=7000, username="referrer")
    user_service = _build_user_service(
        existing_user=None, referrer=referrer, created_user=created_user
    )
    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    referral_service = _build_referral_service()
    partner_service = _build_partner_service()
    web_account_service = _build_web_account_service_for_telegram(
        _build_web_auth_result(user=created_user, username="tg_new", is_new_user=False)
    )

    response_obj = Response()
    response = asyncio.run(
        TELEGRAM_AUTH_ENDPOINT(
            auth_request=TelegramAuthRequest(
                id=created_user.telegram_id,
                first_name="New",
                auth_date=int(time.time()),
                hash="sig",
                referralCode="valid1234",
            ),
            response=response_obj,
            user_service=user_service,
            config=_build_config(),
            referral_service=referral_service,
            partner_service=partner_service,
            notification_service=_build_notification_service(),
            settings_service=settings_service,
            web_account_service=web_account_service,
        )
    )

    assert response.auth_source == "WEB_TELEGRAM_WIDGET"
    _assert_auth_cookies_set(response_obj)
    assert user_service.create.await_count == 1
    assert referral_service.handle_referral.await_count == 1
    assert partner_service.handle_new_user_referral.await_count == 1


def test_login_existing_user_allowed_in_invited_mode() -> None:
    existing_user = _build_user(telegram_id=8001, username="legacy_user")
    web_result = _build_web_auth_result(
        user=existing_user, username="legacy_user", is_new_user=False
    )

    response_obj = Response()
    response = asyncio.run(
        LOGIN_ENDPOINT(
            login_data=LoginRequest(username="legacy_user", password="secret123"),
            request=_build_request(),
            response=response_obj,
            web_account_service=_build_web_account_service_for_login(web_result),
            settings_service=_build_settings_service(access_mode=AccessMode.INVITED),
            config=_build_config(rate_limit_enabled=False),
            redis_client=SimpleNamespace(),
        )
    )

    assert response.auth_source == "WEB_PASSWORD"
    _assert_auth_cookies_set(response_obj)


def test_bot_access_existing_user_allowed_in_invited_mode() -> None:
    existing_user = _build_user(telegram_id=9100, username="legacy_bot_user")
    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    user_service = _build_user_service(existing_user=existing_user, referrer=None)

    service = AccessService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        settings_service=settings_service,
        user_service=user_service,
        referral_service=_build_referral_service(),
    )

    allowed = asyncio.run(
        service.is_access_allowed(
            AiogramUser(id=existing_user.telegram_id, is_bot=False, first_name="Legacy"),
            event=SimpleNamespace(),
        )
    )

    assert allowed is True


def test_switch_public_to_invited_keeps_existing_bot_user_allowed() -> None:
    existing_user = _build_user(telegram_id=9200, username="legacy_switch_user")
    settings_service = _build_settings_service(access_mode=AccessMode.PUBLIC)
    settings_service.get_access_mode = AsyncMock(
        side_effect=[AccessMode.PUBLIC, AccessMode.INVITED]
    )

    service = AccessService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        settings_service=settings_service,
        user_service=_build_user_service(existing_user=existing_user, referrer=None),
        referral_service=_build_referral_service(),
    )

    aiogram_user = AiogramUser(id=existing_user.telegram_id, is_bot=False, first_name="Legacy")
    event = SimpleNamespace()

    first_allowed = asyncio.run(service.is_access_allowed(aiogram_user, event))
    second_allowed = asyncio.run(service.is_access_allowed(aiogram_user, event))

    assert first_allowed is True
    assert second_allowed is True


def test_bot_new_user_without_invite_is_denied_in_invited_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    denied_notifications = AsyncMock()
    monkeypatch.setattr(
        "src.services.access.send_access_denied_notification_task",
        SimpleNamespace(kiq=denied_notifications),
    )

    settings_service = _build_settings_service(access_mode=AccessMode.INVITED)
    user_service = _build_user_service(existing_user=None, referrer=None)
    referral_service = _build_referral_service()
    referral_service.is_referral_event = AsyncMock(return_value=False)

    service = AccessService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        settings_service=settings_service,
        user_service=user_service,
        referral_service=referral_service,
    )

    allowed = asyncio.run(
        service.is_access_allowed(
            AiogramUser(id=3333, is_bot=False, first_name="New"),
            event=SimpleNamespace(),
        )
    )

    assert allowed is False
    assert denied_notifications.await_count == 1


def test_register_reg_blocked_keeps_legacy_mode_contract() -> None:
    settings_service = _build_settings_service(access_mode=AccessMode.REG_BLOCKED)
    user_service = _build_user_service(
        existing_user=None, referrer=_build_user(telegram_id=5001, username="ref")
    )
    web_account_service = SimpleNamespace(register=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            REGISTER_ENDPOINT(
                register_data=RegisterRequest(
                    username="new_user",
                    password="secret123",
                    referral_code="valid1234",
                ),
                response=Response(),
                web_account_service=web_account_service,
                referral_service=_build_referral_service(),
                partner_service=_build_partner_service(),
                notification_service=_build_notification_service(),
                user_service=user_service,
                settings_service=settings_service,
                telegram_link_service=SimpleNamespace(request_code=AsyncMock()),
                config=_build_config(),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == ACCESS_DENIED_REGISTRATION_DISABLED
    assert web_account_service.register.await_count == 0


def test_login_restricted_keeps_legacy_mode_contract() -> None:
    existing_user = _build_user(telegram_id=8301, username="legacy_user")
    web_result = _build_web_auth_result(
        user=existing_user, username="legacy_user", is_new_user=False
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            LOGIN_ENDPOINT(
                login_data=LoginRequest(username="legacy_user", password="secret123"),
                request=_build_request(),
                response=Response(),
                web_account_service=_build_web_account_service_for_login(web_result),
                settings_service=_build_settings_service(access_mode=AccessMode.RESTRICTED),
                config=_build_config(rate_limit_enabled=False),
                redis_client=SimpleNamespace(),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == ACCESS_DENIED_SERVICE_RESTRICTED
