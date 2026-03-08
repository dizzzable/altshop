from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

from src.api.dependencies import web_auth as web_auth_dependency_module
from src.api.dependencies.web_auth import (
    get_current_user,
    get_current_web_account,
    require_web_product_access,
)
from src.api.endpoints import web_auth as web_auth_endpoint_module
from src.api.endpoints.web_auth import refresh_token
from src.core.enums import AccessMode, Locale
from src.infrastructure.database.models.dto import UserDto, WebAccountDto

GET_CURRENT_USER = getattr(
    inspect.unwrap(get_current_user),
    "__dishka_orig_func__",
    inspect.unwrap(get_current_user),
)
GET_CURRENT_WEB_ACCOUNT = getattr(
    inspect.unwrap(get_current_web_account),
    "__dishka_orig_func__",
    inspect.unwrap(get_current_web_account),
)
REQUIRE_WEB_PRODUCT_ACCESS = getattr(
    inspect.unwrap(require_web_product_access),
    "__dishka_orig_func__",
    inspect.unwrap(require_web_product_access),
)
REFRESH_TOKEN_ENDPOINT = getattr(
    inspect.unwrap(refresh_token),
    "__dishka_orig_func__",
    inspect.unwrap(refresh_token),
)


def _build_request(
    headers: dict[str, str] | None = None,
    *,
    method: str = "GET",
) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {"type": "http", "headers": raw_headers, "method": method}
    return Request(scope)


def _build_user(telegram_id: int) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=f"user_{telegram_id}",
        referral_code=f"code{telegram_id}",
        name=f"User {telegram_id}",
        language=Locale.EN,
    )


def _build_web_account(*, user_telegram_id: int, token_version: int = 3) -> WebAccountDto:
    return WebAccountDto(
        id=7,
        user_telegram_id=user_telegram_id,
        username=f"user_{user_telegram_id}",
        password_hash="hashed",
        token_version=token_version,
    )


def _assert_auth_cookies_set(response: Response) -> None:
    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any("altshop_access_token=" in header for header in set_cookie_headers)
    assert any("altshop_refresh_token=" in header for header in set_cookie_headers)


def test_get_current_user_accepts_web_account_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _build_user(telegram_id=101)
    web_account = _build_web_account(user_telegram_id=user.telegram_id, token_version=5)
    monkeypatch.setattr(
        web_auth_dependency_module,
        "verify_access_token",
        lambda _token: {"sub": str(user.telegram_id), "ver": web_account.token_version},
    )

    resolved_user = asyncio.run(
        GET_CURRENT_USER(
            request=_build_request(),
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="web-token"),
            user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
            web_account_service=SimpleNamespace(
                get_by_user_telegram_id=AsyncMock(return_value=web_account)
            ),
        )
    )

    assert resolved_user.telegram_id == user.telegram_id


def test_get_current_user_rejects_legacy_access_token_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_auth_dependency_module, "verify_access_token", lambda _token: None)
    user_service = SimpleNamespace(get=AsyncMock())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            GET_CURRENT_USER(
                request=_build_request(),
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="legacy-bot-token",
                ),
                user_service=user_service,
                web_account_service=SimpleNamespace(
                    get_by_user_telegram_id=AsyncMock(return_value=None)
                ),
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
    user_service.get.assert_not_awaited()


def test_get_current_web_account_requires_existing_account() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            GET_CURRENT_WEB_ACCOUNT(
                current_user=_build_user(telegram_id=150),
                web_account_service=SimpleNamespace(
                    get_by_user_telegram_id=AsyncMock(return_value=None)
                ),
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Web account is required for this action"


def test_require_web_product_access_marks_get_as_read_only() -> None:
    user = _build_user(telegram_id=303)
    access_status = SimpleNamespace()
    guard_service = SimpleNamespace(
        evaluate_user_access=AsyncMock(return_value=access_status),
        assert_can_use_product_features=Mock(),
    )

    resolved_user = asyncio.run(
        REQUIRE_WEB_PRODUCT_ACCESS(
            request=_build_request(method="GET"),
            current_user=user,
            web_access_guard_service=guard_service,
            settings_service=SimpleNamespace(get_access_mode=AsyncMock(return_value=AccessMode.PUBLIC)),
        )
    )

    assert resolved_user.telegram_id == user.telegram_id
    guard_service.evaluate_user_access.assert_awaited_once_with(user=user)
    guard_service.assert_can_use_product_features.assert_called_once_with(
        access_status,
        allow_read_only=True,
    )


def test_refresh_token_requires_cookie_session() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            REFRESH_TOKEN_ENDPOINT(
                response=Response(),
                request=_build_request(method="POST"),
                web_account_service=SimpleNamespace(
                    get_by_user_telegram_id=AsyncMock(return_value=None)
                ),
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Refresh token is required"


def test_refresh_token_rotates_web_account_session(monkeypatch: pytest.MonkeyPatch) -> None:
    web_account = _build_web_account(user_telegram_id=202, token_version=4)
    monkeypatch.setattr(
        web_auth_endpoint_module,
        "verify_refresh_token",
        lambda _token: {"sub": str(web_account.user_telegram_id), "ver": web_account.token_version},
    )
    monkeypatch.setattr(
        web_auth_endpoint_module,
        "create_access_token",
        lambda **_kwargs: "new-access",
    )
    monkeypatch.setattr(
        web_auth_endpoint_module,
        "create_refresh_token",
        lambda **_kwargs: "new-refresh",
    )

    response_obj = Response()
    response = asyncio.run(
        REFRESH_TOKEN_ENDPOINT(
            response=response_obj,
            request=_build_request(
                headers={
                    "cookie": (
                        "altshop_refresh_token=valid-refresh-token; "
                        "altshop_csrf_token=csrf123"
                    ),
                    "x-csrf-token": "csrf123",
                },
                method="POST",
            ),
            web_account_service=SimpleNamespace(
                get_by_user_telegram_id=AsyncMock(return_value=web_account)
            ),
        )
    )

    assert response.expires_in == 604800
    _assert_auth_cookies_set(response_obj)
