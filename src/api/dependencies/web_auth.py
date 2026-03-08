"""Authentication dependencies for web API endpoints."""

from __future__ import annotations

from typing import Any, cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.dependencies.web_access import assert_web_general_access
from src.api.utils.web_auth_transport import (
    ACCESS_TOKEN_COOKIE_NAME,
    SAFE_HTTP_METHODS,
    ensure_csrf_if_cookie_auth,
    parse_token_subject_and_version,
)
from src.core.security.jwt_handler import verify_access_token
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.settings import SettingsService
from src.services.user import UserService
from src.services.web_access_guard import WebAccessGuardService
from src.services.web_account import WebAccountService

security = HTTPBearer(auto_error=False)
_DISHKA_DEFAULT = cast(Any, None)


@inject
async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    user_service: FromDishka[UserService] = _DISHKA_DEFAULT,
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
) -> UserDto:
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME) if request else None
    header_token = credentials.credentials if credentials else None
    token = cookie_token or header_token

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    ensure_csrf_if_cookie_auth(request, cookie_name=ACCESS_TOKEN_COOKIE_NAME)
    user_id: int | None = None

    web_payload = verify_access_token(token)
    if web_payload:
        try:
            subject_user_id, token_version = parse_token_subject_and_version(web_payload)
        except (TypeError, ValueError):
            subject_user_id = 0
            token_version = -1

        if subject_user_id:
            web_account = await web_account_service.get_by_user_telegram_id(subject_user_id)
            if web_account and web_account.token_version == token_version:
                user_id = web_account.user_telegram_id

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_service.get(telegram_id=user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@inject
async def get_current_web_account(
    current_user: UserDto = Depends(get_current_user),
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
) -> WebAccountDto:
    web_account = await web_account_service.get_by_user_telegram_id(current_user.telegram_id)
    if not web_account:
        raise HTTPException(status_code=400, detail="Web account is required for this action")
    return web_account


@inject
async def require_web_product_access(
    request: Request,
    current_user: UserDto = Depends(get_current_user),
    web_access_guard_service: FromDishka[WebAccessGuardService] = _DISHKA_DEFAULT,
    settings_service: FromDishka[SettingsService] = _DISHKA_DEFAULT,
) -> UserDto:
    mode = await settings_service.get_access_mode()
    assert_web_general_access(current_user, mode)
    access_status = await web_access_guard_service.evaluate_user_access(user=current_user)
    web_access_guard_service.assert_can_use_product_features(
        access_status,
        allow_read_only=request.method.upper() in SAFE_HTTP_METHODS,
    )
    return current_user


__all__ = [
    "get_current_user",
    "get_current_web_account",
    "require_web_product_access",
]
