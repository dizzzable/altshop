from __future__ import annotations

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from src.api.utils.web_auth_transport import (
    ACCESS_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
    build_session_response,
    ensure_csrf_if_cookie_auth,
    parse_token_subject_and_version,
)


def _build_request(
    headers: dict[str, str] | None = None,
    *,
    method: str = "GET",
) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {"type": "http", "headers": raw_headers, "method": method}
    return Request(scope)


def test_build_session_response_sets_cookies_and_cache_control() -> None:
    response_obj = Response()

    response = build_session_response(
        access_token="access-token",
        refresh_token="refresh-token",
        response=response_obj,
        is_new_user=True,
        auth_source="WEB_PASSWORD",
    )

    set_cookie_headers = response_obj.headers.getlist("set-cookie")
    assert response.is_new_user is True
    assert response.auth_source == "WEB_PASSWORD"
    assert response_obj.headers["Cache-Control"] == "no-store"
    assert any(f"{ACCESS_TOKEN_COOKIE_NAME}=" in header for header in set_cookie_headers)
    assert any(f"{REFRESH_TOKEN_COOKIE_NAME}=" in header for header in set_cookie_headers)


def test_ensure_csrf_if_cookie_auth_rejects_invalid_token() -> None:
    request = _build_request(
        headers={
            "cookie": "altshop_refresh_token=valid-refresh-token; altshop_csrf_token=csrf123",
            "x-csrf-token": "mismatch",
        },
        method="POST",
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_csrf_if_cookie_auth(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Invalid CSRF token"


def test_ensure_csrf_if_cookie_auth_skips_safe_method() -> None:
    ensure_csrf_if_cookie_auth(
        _build_request(headers={"cookie": "altshop_access_token=token"}, method="GET"),
        cookie_name=ACCESS_TOKEN_COOKIE_NAME,
    )


def test_parse_token_subject_and_version_validates_payload() -> None:
    assert parse_token_subject_and_version({"sub": "101", "ver": "3"}) == (101, 3)

    with pytest.raises(ValueError, match="Invalid token subject"):
        parse_token_subject_and_version({"sub": None, "ver": 1})
