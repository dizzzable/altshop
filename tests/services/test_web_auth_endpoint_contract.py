from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response

import src.api.endpoints.web_auth as web_auth_module
from src.api.contracts.web_auth import (
    ForgotPasswordRequest,
    ForgotPasswordTelegramRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordByCodeRequest,
    ResetPasswordByLinkRequest,
    ResetPasswordByTelegramCodeRequest,
    TelegramAuthRequest,
    TelegramLinkConfirmPayload,
    TelegramLinkRequestPayload,
    WebAccountBootstrapRequest,
)
from src.api.utils.web_auth_transport import (
    ACCESS_TOKEN_COOKIE_NAME,
    CSRF_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
)
from src.core.config import AppConfig
from src.core.enums import AccessMode, Locale, UserRole
from src.core.security.jwt_handler import create_refresh_token
from src.infrastructure.database.models.dto import SettingsDto, UserDto, WebAccountDto
from src.services.telegram_link import TelegramLinkError
from src.services.web_access_guard import WebAccessStatus
from src.services.web_account import WebAuthResult


def run_async(coroutine):
    return asyncio.run(coroutine)


def call_endpoint(route_fn, /, **kwargs):
    endpoint = getattr(route_fn, "__dishka_orig_func__", route_fn)
    return run_async(endpoint(**kwargs))


def make_config() -> AppConfig:
    return AppConfig()


def make_request(
    *,
    config: AppConfig,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    client_host: str = "203.0.113.10",
):
    app = SimpleNamespace(state=SimpleNamespace(config=config))
    return SimpleNamespace(
        method=method,
        headers=headers or {},
        cookies=cookies or {},
        client=SimpleNamespace(host=client_host),
        app=app,
        scope={"app": app},
        state=SimpleNamespace(dishka_container=None),
    )


def make_redis():
    return SimpleNamespace(incr=AsyncMock(return_value=1), expire=AsyncMock())


def make_user(
    *,
    telegram_id: int = 101,
    username: str | None = "tg_101",
    name: str = "Alice",
    language: Locale = Locale.EN,
    is_rules_accepted: bool = True,
) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=username,
        referral_code="ref_ABC123",
        name=name,
        role=UserRole.USER,
        language=language,
        is_rules_accepted=is_rules_accepted,
    )


def make_web_account(
    *,
    account_id: int = 7,
    user_telegram_id: int = 101,
    username: str = "alice",
    token_version: int = 0,
) -> WebAccountDto:
    return WebAccountDto(
        id=account_id,
        user_telegram_id=user_telegram_id,
        username=username,
        password_hash="hash",
        token_version=token_version,
    )


def make_auth_result(
    *,
    user: UserDto | None = None,
    web_account: WebAccountDto | None = None,
    is_new_user: bool = False,
) -> WebAuthResult:
    resolved_user = user or make_user()
    resolved_account = web_account or make_web_account(user_telegram_id=resolved_user.telegram_id)
    return WebAuthResult(
        user=resolved_user,
        web_account=resolved_account,
        access_token="access-token",
        refresh_token="refresh-token",
        is_new_user=is_new_user,
    )


def make_settings_service(*, access_mode: AccessMode = AccessMode.PUBLIC):
    settings = SettingsDto(access_mode=access_mode)

    def resolve_localized_branding_text(localized_text, *, language):
        language_value = str(getattr(language, "value", language) or "").lower()
        if language_value.startswith("ru") and getattr(localized_text, "ru", ""):
            return localized_text.ru
        return getattr(localized_text, "en", "") or getattr(localized_text, "ru", "")

    def render_branding_text(template: str, *, placeholders: dict[str, object]) -> str:
        return template.format(**placeholders)

    return SimpleNamespace(
        get=AsyncMock(return_value=settings),
        get_access_mode=AsyncMock(return_value=access_mode),
        get_branding_settings=AsyncMock(return_value=settings.branding),
        resolve_localized_branding_text=resolve_localized_branding_text,
        render_branding_text=render_branding_text,
    )


def assert_session_cookies(response: Response) -> None:
    set_cookie_headers = "\n".join(
        value.decode("latin-1")
        for name, value in response.raw_headers
        if name == b"set-cookie"
    )
    assert f"{ACCESS_TOKEN_COOKIE_NAME}=" in set_cookie_headers
    assert f"{REFRESH_TOKEN_COOKIE_NAME}=" in set_cookie_headers
    assert f"{CSRF_TOKEN_COOKIE_NAME}=" in set_cookie_headers
    assert response.headers["cache-control"] == "no-store"


def test_register_endpoint_returns_cookie_session_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_config()
    request = make_request(config=config)
    response = Response()
    user = make_user()
    auth_result = make_auth_result(user=user, is_new_user=True)
    web_account_service = SimpleNamespace(register=AsyncMock(return_value=auth_result))
    notification_service = SimpleNamespace(system_notify=AsyncMock())
    user_service = SimpleNamespace(update=AsyncMock(return_value=None))
    settings_service = make_settings_service()
    telegram_link_service = SimpleNamespace(request_code=AsyncMock())

    monkeypatch.setattr(web_auth_module.web_auth_flows, "get_user_keyboard", lambda _id: None)

    result = call_endpoint(
        web_auth_module.register,
        register_data=RegisterRequest(username="alice", password="secret123"),
        request=request,
        response=response,
        web_account_service=web_account_service,
        referral_service=SimpleNamespace(),
        partner_service=SimpleNamespace(),
        notification_service=notification_service,
        user_service=user_service,
        settings_service=settings_service,
        telegram_link_service=telegram_link_service,
        config=config,
        redis_client=make_redis(),
    )

    assert result.is_new_user is True
    assert result.auth_source == "WEB_PASSWORD"
    assert_session_cookies(response)
    web_account_service.register.assert_awaited_once()
    notification_service.system_notify.assert_awaited_once()


def test_login_endpoint_returns_cookie_session_contract() -> None:
    config = make_config()
    request = make_request(config=config)
    response = Response()
    auth_result = make_auth_result()
    web_account_service = SimpleNamespace(login=AsyncMock(return_value=auth_result))
    settings_service = make_settings_service()

    result = call_endpoint(
        web_auth_module.login,
        login_data=LoginRequest(username="alice", password="secret123"),
        request=request,
        response=response,
        web_account_service=web_account_service,
        settings_service=settings_service,
        config=config,
        redis_client=make_redis(),
    )

    assert result.auth_source == "WEB_PASSWORD"
    assert_session_cookies(response)
    web_account_service.login.assert_awaited_once_with(
        username="alice",
        password="secret123",
    )


def test_refresh_endpoint_uses_cookie_first_contract() -> None:
    config = make_config()
    web_account = make_web_account(token_version=3)
    refresh_token = create_refresh_token(
        user_id=web_account.user_telegram_id,
        username=web_account.username,
        token_version=web_account.token_version,
    )
    request = make_request(
        config=config,
        headers={"X-CSRF-Token": "csrf-token"},
        cookies={
            REFRESH_TOKEN_COOKIE_NAME: refresh_token,
            CSRF_TOKEN_COOKIE_NAME: "csrf-token",
        },
    )
    response = Response()
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(return_value=web_account)
    )

    result = call_endpoint(
        web_auth_module.refresh_token,
        response=response,
        request=request,
        web_account_service=web_account_service,
    )

    assert result.expires_in == 604800
    assert_session_cookies(response)
    web_account_service.get_by_user_telegram_id.assert_awaited_once_with(
        web_account.user_telegram_id
    )


def test_access_status_endpoint_returns_presented_guard_snapshot() -> None:
    current_user = make_user()
    access_status = WebAccessStatus(
        access_mode="PUBLIC",
        rules_required=True,
        channel_required=True,
        requires_telegram_id=True,
        access_level="read_only",
        channel_check_status="required_unverified",
        rules_accepted=False,
        telegram_linked=False,
        channel_verified=False,
        linked_telegram_id=None,
        rules_link="https://example.com/rules",
        channel_link="https://t.me/example",
        tg_id_helper_bot_link="https://t.me/userinfobot",
        verification_bot_link="https://t.me/example_bot",
        unmet_requirements=["RULES_ACCEPTANCE_REQUIRED", "TELEGRAM_LINK_REQUIRED"],
        can_use_product_features=False,
        can_view_product_screens=True,
        can_mutate_product=False,
        can_purchase=False,
        should_redirect_to_access_screen=True,
        invite_locked=False,
    )
    web_access_guard_service = SimpleNamespace(
        evaluate_user_access=AsyncMock(return_value=access_status)
    )

    response = call_endpoint(
        web_auth_module.get_access_status,
        force_channel_recheck=True,
        current_user=current_user,
        web_access_guard_service=web_access_guard_service,
    )

    assert response.access_level == "read_only"
    assert response.unmet_requirements == [
        "RULES_ACCEPTANCE_REQUIRED",
        "TELEGRAM_LINK_REQUIRED",
    ]
    web_access_guard_service.evaluate_user_access.assert_awaited_once_with(
        user=current_user,
        force_channel_recheck=True,
    )


def test_bootstrap_endpoint_returns_cookie_session_contract() -> None:
    response = Response()
    current_user = make_user(telegram_id=412289221, username="tg_412289221")
    auth_result = make_auth_result(
        user=current_user,
        web_account=make_web_account(user_telegram_id=current_user.telegram_id, username="alice"),
    )
    web_account_service = SimpleNamespace(
        bootstrap_credentials_for_telegram_user=AsyncMock(return_value=auth_result)
    )

    result = call_endpoint(
        web_auth_module.bootstrap_web_account,
        payload=WebAccountBootstrapRequest(username="alice", password="secret123"),
        response=response,
        current_user=current_user,
        web_account_service=web_account_service,
    )

    assert result.auth_source == "WEB_PASSWORD"
    assert_session_cookies(response)
    web_account_service.bootstrap_credentials_for_telegram_user.assert_awaited_once_with(
        telegram_id=current_user.telegram_id,
        username="alice",
        password="secret123",
        name=current_user.name or current_user.username,
    )


def test_telegram_link_request_endpoint_returns_localized_contract() -> None:
    config = make_config()
    request = make_request(config=config, headers={"X-Web-Locale": "en"})
    current_user = make_user(language=Locale.EN)
    web_account = make_web_account(user_telegram_id=current_user.telegram_id)
    telegram_link_service = SimpleNamespace(
        request_code=AsyncMock(
            return_value=SimpleNamespace(delivered=True, expires_in_seconds=600)
        )
    )
    settings_service = make_settings_service()

    result = call_endpoint(
        web_auth_module.request_telegram_link_code,
        payload=TelegramLinkRequestPayload(telegram_id=555001),
        request=request,
        current_user=current_user,
        web_account=web_account,
        telegram_link_service=telegram_link_service,
        settings_service=settings_service,
        config=config,
        redis_client=make_redis(),
    )

    assert result.delivered is True
    assert result.expires_in_seconds == 600
    assert result.message == "Verification code sent to Telegram"


def test_telegram_link_confirm_endpoint_sets_session_cookies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_config()
    request = make_request(config=config, headers={"X-Web-Locale": "en"})
    response = Response()
    current_user = make_user(language=Locale.EN)
    old_web_account = make_web_account(user_telegram_id=-55, username="alice")
    updated_web_account = make_web_account(
        user_telegram_id=555001,
        username="alice",
        token_version=2,
    )
    linked_user = make_user(telegram_id=555001, username="tg_555001", name="Linked")
    telegram_link_service = SimpleNamespace(
        confirm_code=AsyncMock(
            return_value=SimpleNamespace(
                web_account=updated_web_account,
                linked_telegram_id=555001,
            )
        )
    )
    user_service = SimpleNamespace(get=AsyncMock(return_value=linked_user))
    notification_service = SimpleNamespace(system_notify=AsyncMock())
    settings_service = make_settings_service()

    monkeypatch.setattr(web_auth_module, "get_user_keyboard", lambda _id: None)

    result = call_endpoint(
        web_auth_module.confirm_telegram_link_code,
        payload=TelegramLinkConfirmPayload(telegram_id=555001, code="1234"),
        request=request,
        response=response,
        current_user=current_user,
        web_account=old_web_account,
        telegram_link_service=telegram_link_service,
        user_service=user_service,
        notification_service=notification_service,
        settings_service=settings_service,
        redis_client=make_redis(),
        config=config,
    )

    assert result.linked_telegram_id == 555001
    assert result.message == "Telegram account linked successfully"
    assert_session_cookies(response)
    notification_service.system_notify.assert_awaited_once()


@pytest.mark.parametrize(
    ("route_fn", "payload", "service_method"),
    [
        (
            web_auth_module.forgot_password,
            ForgotPasswordRequest(username="alice"),
            "forgot_password",
        ),
        (
            web_auth_module.forgot_password_telegram,
            ForgotPasswordTelegramRequest(username="alice"),
            "request_telegram_password_reset",
        ),
    ],
)
def test_password_forgot_contracts_return_generic_message(
    route_fn,
    payload,
    service_method: str,
) -> None:
    config = make_config()
    request = make_request(config=config, headers={"X-Web-Locale": "en"})
    email_recovery_service = SimpleNamespace(
        forgot_password=AsyncMock(),
        request_telegram_password_reset=AsyncMock(),
    )

    result = call_endpoint(
        route_fn,
        payload=payload,
        request=request,
        email_recovery_service=email_recovery_service,
        config=config,
        redis_client=make_redis(),
    )

    assert (
        result.message
        == "If the account exists and email is verified, recovery instructions were sent"
    )
    getattr(email_recovery_service, service_method).assert_awaited_once()


@pytest.mark.parametrize(
    ("route_fn", "payload", "expected_call"),
    [
        (
            web_auth_module.reset_password_by_link,
            ResetPasswordByLinkRequest(token="token-12345", new_password="secret123"),
            ("reset_password_by_link", {"token": "token-12345", "new_password": "secret123"}),
        ),
        (
            web_auth_module.reset_password_by_code,
            ResetPasswordByCodeRequest(
                email="alice@example.com",
                code="1234",
                new_password="secret123",
            ),
            (
                "reset_password_by_code",
                {
                    "email": "alice@example.com",
                    "code": "1234",
                    "new_password": "secret123",
                },
            ),
        ),
        (
            web_auth_module.reset_password_by_telegram_code,
            ResetPasswordByTelegramCodeRequest(
                username="alice",
                code="1234",
                new_password="secret123",
            ),
            (
                "reset_password_by_telegram_code",
                {
                    "username": "alice",
                    "code": "1234",
                    "new_password": "secret123",
                },
            ),
        ),
    ],
)
def test_password_reset_contracts_return_updated_message(
    route_fn,
    payload,
    expected_call: tuple[str, dict[str, object]],
) -> None:
    config = make_config()
    request = make_request(config=config, headers={"X-Web-Locale": "en"})
    email_recovery_service = SimpleNamespace(
        reset_password_by_link=AsyncMock(),
        reset_password_by_code=AsyncMock(),
        reset_password_by_telegram_code=AsyncMock(),
    )

    result = call_endpoint(
        route_fn,
        payload=payload,
        request=request,
        email_recovery_service=email_recovery_service,
        config=config,
    )

    method_name, kwargs = expected_call
    assert result.message == "Password updated"
    getattr(email_recovery_service, method_name).assert_awaited_once_with(**kwargs)


def test_telegram_auth_endpoint_returns_cookie_session_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_config()
    request = make_request(config=config)
    response = Response()
    created_user = make_user(telegram_id=777001, username="tg_777001", name="Alice")
    auth_result = make_auth_result(
        user=created_user,
        web_account=make_web_account(user_telegram_id=created_user.telegram_id, username="alice"),
    )
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created_user),
    )
    notification_service = SimpleNamespace(system_notify=AsyncMock())
    settings_service = make_settings_service()
    web_account_service = SimpleNamespace(
        get_or_create_for_telegram_user=AsyncMock(return_value=auth_result)
    )

    monkeypatch.setattr(web_auth_module.web_auth_flows, "get_user_keyboard", lambda _id: None)
    monkeypatch.setattr(web_auth_module.web_auth_flows, "verify_telegram_hash", lambda *_: True)

    result = call_endpoint(
        web_auth_module.telegram_auth,
        auth_request=TelegramAuthRequest(
            id=created_user.telegram_id,
            first_name="Alice",
            username="alice",
            auth_date=int(time.time()),
            hash="telegram-hash",
        ),
        request=request,
        response=response,
        user_service=user_service,
        config=config,
        referral_service=SimpleNamespace(),
        partner_service=SimpleNamespace(),
        notification_service=notification_service,
        settings_service=settings_service,
        web_account_service=web_account_service,
        redis_client=make_redis(),
        web_analytics_event_service=None,
    )

    assert result.is_new_user is True
    assert result.auth_source == "WEB_TELEGRAM_WIDGET"
    assert_session_cookies(response)
    user_service.create.assert_awaited_once()
    notification_service.system_notify.assert_awaited_once()


def test_telegram_link_confirm_maps_conflict_errors() -> None:
    config = make_config()
    request = make_request(config=config)
    response = Response()
    current_user = make_user()
    web_account = make_web_account()
    telegram_link_service = SimpleNamespace(
        confirm_code=AsyncMock(
            side_effect=TelegramLinkError(
                code="TELEGRAM_ALREADY_LINKED",
                message="Telegram ID is already linked to another account.",
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        call_endpoint(
            web_auth_module.confirm_telegram_link_code,
            payload=TelegramLinkConfirmPayload(telegram_id=555001, code="1234"),
            request=request,
            response=response,
            current_user=current_user,
            web_account=web_account,
            telegram_link_service=telegram_link_service,
            user_service=SimpleNamespace(get=AsyncMock(return_value=None)),
            notification_service=SimpleNamespace(system_notify=AsyncMock()),
            settings_service=make_settings_service(),
            redis_client=make_redis(),
            config=config,
        )

    assert exc_info.value.status_code == 409
