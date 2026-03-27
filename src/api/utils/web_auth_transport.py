from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request, Response

from src.api.presenters.web_auth import SessionResponse
from src.core.observability import emit_counter
from src.core.security.jwt_handler import create_access_token, create_refresh_token
from src.infrastructure.database.models.dto import WebAccountDto

ACCESS_TOKEN_COOKIE_NAME = "altshop_access_token"
REFRESH_TOKEN_COOKIE_NAME = "altshop_refresh_token"
CSRF_TOKEN_COOKIE_NAME = "altshop_csrf_token"
SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    response: Response | None,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str | None = None,
) -> str:
    csrf_value = csrf_token or _generate_csrf_token()
    if response is None:
        return csrf_value

    response.set_cookie(
        ACCESS_TOKEN_COOKIE_NAME,
        access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/v1/auth",
        max_age=30 * 24 * 60 * 60,
    )
    response.set_cookie(
        CSRF_TOKEN_COOKIE_NAME,
        csrf_value,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
        max_age=30 * 24 * 60 * 60,
    )
    response.headers["Cache-Control"] = "no-store"
    emit_counter("auth_cookie_issued_total")
    return csrf_value


def clear_auth_cookies(response: Response | None) -> None:
    if response is None:
        return

    response.delete_cookie(ACCESS_TOKEN_COOKIE_NAME, path="/", secure=True, samesite="lax")
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE_NAME,
        path="/api/v1/auth",
        secure=True,
        samesite="lax",
    )
    response.delete_cookie(CSRF_TOKEN_COOKIE_NAME, path="/", secure=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"


def ensure_csrf_if_cookie_auth(request: Request | None, *, cookie_name: str) -> None:
    if request is None:
        return
    if request.method.upper() in SAFE_HTTP_METHODS:
        return

    cookie_token = request.cookies.get(CSRF_TOKEN_COOKIE_NAME)
    auth_cookie = request.cookies.get(cookie_name)
    if not auth_cookie:
        return

    header_token = request.headers.get("X-CSRF-Token", "").strip()
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def build_session_response(
    *,
    access_token: str,
    refresh_token: str,
    response: Response | None = None,
    expires_in: int = 604800,
    is_new_user: bool = False,
    auth_source: str | None = None,
) -> SessionResponse:
    set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return SessionResponse(
        expires_in=expires_in,
        is_new_user=is_new_user,
        auth_source=auth_source,
    )


def create_account_session_tokens(web_account: WebAccountDto) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=web_account.user_telegram_id,
        username=web_account.username,
        token_version=web_account.token_version,
    )
    refresh_token = create_refresh_token(
        user_id=web_account.user_telegram_id,
        username=web_account.username,
        token_version=web_account.token_version,
    )
    return access_token, refresh_token


def set_account_session(response: Response | None, web_account: WebAccountDto) -> str:
    access_token, refresh_token = create_account_session_tokens(web_account)
    return set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
    )


def build_account_session_response(
    *,
    web_account: WebAccountDto,
    response: Response | None = None,
    expires_in: int = 604800,
    is_new_user: bool = False,
    auth_source: str | None = None,
) -> SessionResponse:
    access_token, refresh_token = create_account_session_tokens(web_account)
    return build_session_response(
        access_token=access_token,
        refresh_token=refresh_token,
        response=response,
        expires_in=expires_in,
        is_new_user=is_new_user,
        auth_source=auth_source,
    )


def parse_token_subject_and_version(payload: dict[str, Any]) -> tuple[int, int]:
    raw_subject = payload.get("sub")
    raw_version = payload.get("ver", 0)
    if not isinstance(raw_subject, (str, int)):
        raise ValueError("Invalid token subject")
    if not isinstance(raw_version, (str, int)):
        raise ValueError("Invalid token version")
    return int(raw_subject), int(raw_version)


__all__ = [
    "ACCESS_TOKEN_COOKIE_NAME",
    "CSRF_TOKEN_COOKIE_NAME",
    "REFRESH_TOKEN_COOKIE_NAME",
    "SAFE_HTTP_METHODS",
    "build_account_session_response",
    "build_session_response",
    "clear_auth_cookies",
    "create_account_session_tokens",
    "ensure_csrf_if_cookie_auth",
    "parse_token_subject_and_version",
    "set_account_session",
    "set_auth_cookies",
]
