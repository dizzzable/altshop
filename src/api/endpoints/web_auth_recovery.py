from __future__ import annotations

from typing import Any, cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.asyncio import Redis

from src.api.contracts.web_auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordTelegramRequest,
    ResetPasswordByCodeRequest,
    ResetPasswordByLinkRequest,
    ResetPasswordByTelegramCodeRequest,
    VerifyEmailConfirmRequest,
)
from src.api.dependencies.web_auth import get_current_user, get_current_web_account
from src.api.presenters.web_auth import MessageResponse, _resolve_web_request_locale
from src.api.utils.web_auth_transport import set_auth_cookies
from src.core.config import AppConfig
from src.core.security.jwt_handler import create_access_token, create_refresh_token
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.email_recovery import EmailRecoveryService

from .web_auth_support import _enforce_rate_limit, _request_ip, _resolve_web_auth_message

router = APIRouter()
_DISHKA_DEFAULT = cast(Any, None)


@router.post("/email/verify/request", response_model=MessageResponse)
@inject
async def request_email_verification(
    request: Request,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
    redis_client: FromDishka[Redis] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:email_verify:request:{web_account.id}:{_request_ip(request)}",
    )
    try:
        await email_recovery_service.request_email_verification(web_account=web_account)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=_resolve_web_auth_message("email_verify_request_sent", locale))


@router.post("/email/verify/confirm", response_model=MessageResponse)
@inject
async def confirm_email_verification(
    payload: VerifyEmailConfirmRequest,
    request: Request,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)
    try:
        await email_recovery_service.confirm_email(
            web_account_id=web_account.id or 0,
            code=payload.code,
            token=payload.token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=_resolve_web_auth_message("email_verify_confirmed", locale))


@router.post("/password/forgot", response_model=MessageResponse)
@inject
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
    redis_client: FromDishka[Redis] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config)
    identity = (payload.username or payload.email or "unknown").strip().lower()
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:password_forgot:{identity}:{_request_ip(request)}",
    )
    await email_recovery_service.forgot_password(username=payload.username, email=payload.email)
    return MessageResponse(message=_resolve_web_auth_message("password_forgot_sent", locale))


@router.post("/password/forgot/telegram", response_model=MessageResponse)
@inject
async def forgot_password_telegram(
    payload: ForgotPasswordTelegramRequest,
    request: Request,
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
    redis_client: FromDishka[Redis] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config)
    identity = payload.username.strip().lower()
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:password_forgot_tg:{identity}:{_request_ip(request)}",
    )
    await email_recovery_service.request_telegram_password_reset(username=payload.username)
    return MessageResponse(message=_resolve_web_auth_message("password_forgot_sent", locale))


@router.post("/password/reset/by-link", response_model=MessageResponse)
@inject
async def reset_password_by_link(
    payload: ResetPasswordByLinkRequest,
    request: Request,
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config)
    try:
        await email_recovery_service.reset_password_by_link(
            token=payload.token,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=_resolve_web_auth_message("password_updated", locale))


@router.post("/password/reset/by-code", response_model=MessageResponse)
@inject
async def reset_password_by_code(
    payload: ResetPasswordByCodeRequest,
    request: Request,
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config)
    try:
        await email_recovery_service.reset_password_by_code(
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=_resolve_web_auth_message("password_updated", locale))


@router.post("/password/reset/by-telegram-code", response_model=MessageResponse)
@inject
async def reset_password_by_telegram_code(
    payload: ResetPasswordByTelegramCodeRequest,
    request: Request,
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config)
    try:
        await email_recovery_service.reset_password_by_telegram_code(
            username=payload.username,
            code=payload.code,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=_resolve_web_auth_message("password_updated", locale))


@router.post("/password/change", response_model=MessageResponse)
@inject
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    email_recovery_service: FromDishka[EmailRecoveryService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> MessageResponse:
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)
    try:
        updated_web_account = await email_recovery_service.change_password(
            web_account_id=web_account.id or 0,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    access_token = create_access_token(
        user_id=updated_web_account.user_telegram_id,
        username=updated_web_account.username,
        token_version=updated_web_account.token_version,
    )
    refresh_token = create_refresh_token(
        user_id=updated_web_account.user_telegram_id,
        username=updated_web_account.username,
        token_version=updated_web_account.token_version,
    )
    set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    return MessageResponse(message=_resolve_web_auth_message("password_updated", locale))
