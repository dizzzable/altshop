from __future__ import annotations

import time
from typing import Any, cast
from uuid import uuid4

from aiogram.types import User as AiogramUser
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from redis.asyncio import Redis

from src.api.contracts.web_auth import (
    TelegramAuthRequest,
    TelegramLinkAutoRequestPayload,
    TelegramLinkConfirmPayload,
    TelegramLinkRequestPayload,
)
from src.api.dependencies.web_access import (
    assert_web_general_access,
    assert_web_registration_access,
    validate_web_invite_code,
)
from src.api.dependencies.web_auth import get_current_user, get_current_web_account
from src.api.presenters.web_auth import (
    SessionResponse,
    TelegramLinkConfirmResponse,
    TelegramLinkRequestResponse,
    TelegramLinkStatusResponse,
    _resolve_web_request_locale,
)
from src.api.utils.web_auth_transport import build_session_response, set_auth_cookies
from src.core.config import AppConfig
from src.core.security.jwt_handler import create_access_token, create_refresh_token
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.telegram_link import TelegramLinkError, TelegramLinkService
from src.services.user import UserService
from src.services.web_account import WebAccountService
from src.services.web_analytics_event import WebAnalyticsEventService

from .web_auth_support import (
    TelegramAuthData,
    _apply_referral_for_new_user,
    _enforce_rate_limit,
    _extract_referral_code_from_telegram_request,
    _extract_telegram_launch_context,
    _notify_web_account_linked,
    _notify_web_user_registered,
    _parse_telegram_auth_request,
    _request_ip,
    _resolve_trusted_telegram_id_for_auto_link,
    _track_web_analytics_event,
    verify_telegram_hash,
    verify_telegram_webapp_init_data,
)

router = APIRouter()
_DISHKA_DEFAULT = cast(Any, None)


@router.post("/telegram", response_model=SessionResponse)
@inject
async def telegram_auth(
    auth_request: TelegramAuthRequest,
    response: Response,
    user_service: FromDishka[UserService],
    config: FromDishka[AppConfig],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
    web_account_service: FromDishka[WebAccountService],
    web_analytics_event_service: FromDishka[WebAnalyticsEventService] = _DISHKA_DEFAULT,
) -> SessionResponse:
    auth_data: TelegramAuthData | None = None
    launch_context = {
        "source": "widget",
        "start_param": None,
        "has_query_id": False,
        "chat_type": None,
    }
    analytics_session_id = str(uuid4())
    analytics_device_mode = "telegram-mobile" if auth_request.initData else "web"
    launch_source = "widget"
    launch_start_param: str | None = None
    launch_has_query_id = False
    launch_chat_type: str | None = None

    try:
        auth_data = _parse_telegram_auth_request(auth_request)
        launch_context = _extract_telegram_launch_context(auth_request)

        raw_source = launch_context["source"]
        if isinstance(raw_source, str) and raw_source:
            launch_source = raw_source

        raw_start_param = launch_context["start_param"]
        launch_start_param = (
            raw_start_param if isinstance(raw_start_param, str) and raw_start_param else None
        )

        launch_has_query_id = bool(launch_context["has_query_id"])

        raw_chat_type = launch_context["chat_type"]
        launch_chat_type = (
            raw_chat_type if isinstance(raw_chat_type, str) and raw_chat_type else None
        )

        telegram_auth_source = (
            "WEB_TELEGRAM_WEBAPP" if auth_request.initData else "WEB_TELEGRAM_WIDGET"
        )

        await _track_web_analytics_event(
            web_analytics_event_service=web_analytics_event_service,
            event_name="telegram_auth_attempt",
            source_path="/api/v1/auth/telegram",
            session_id=analytics_session_id,
            user_telegram_id=auth_data.id,
            device_mode=analytics_device_mode,
            is_in_telegram=bool(auth_request.initData),
            has_init_data=bool(auth_request.initData),
            start_param=launch_start_param,
            has_query_id=launch_has_query_id,
            chat_type=launch_chat_type,
            meta={"source": launch_source},
        )

        logger.info(
            "Telegram auth attempt: user_id={}, source={}, has_query_id={}, "
            "start_param={}, chat_type={}",
            auth_data.id,
            launch_source,
            launch_has_query_id,
            launch_start_param or "-",
            launch_chat_type or "-",
        )

        bot_secret = config.bot.token.get_secret_value()
        is_valid_signature = (
            verify_telegram_webapp_init_data(auth_request.initData, bot_secret)
            if auth_request.initData
            else verify_telegram_hash(auth_data.model_dump(), bot_secret)
        )
        if not is_valid_signature:
            raise HTTPException(status_code=401, detail="Invalid Telegram signature")

        if int(time.time()) - auth_data.auth_date > 86400:
            raise HTTPException(status_code=401, detail="Authorization data expired")

        user = await user_service.get(telegram_id=auth_data.id)
        mode = await settings_service.get_access_mode()
        referral_code = _extract_referral_code_from_telegram_request(auth_request)
        is_new_user = False

        if not user:
            is_valid_invite = await validate_web_invite_code(
                raw_code=referral_code,
                referral_service=referral_service,
                new_user_telegram_id=auth_data.id,
            )
            assert_web_registration_access(
                mode=mode,
                existing_user=None,
                is_valid_invite=is_valid_invite,
            )

            aiogram_user = AiogramUser(
                id=auth_data.id,
                is_bot=False,
                first_name=auth_data.first_name,
                last_name=auth_data.last_name,
                username=auth_data.username,
                language_code="en",
            )
            user = await user_service.create(aiogram_user)
            is_new_user = True
        else:
            assert_web_general_access(user, mode)

        if is_new_user:
            await _apply_referral_for_new_user(
                user=user,
                referral_code=referral_code,
                referral_service=referral_service,
                partner_service=partner_service,
            )

        await _track_web_analytics_event(
            web_analytics_event_service=web_analytics_event_service,
            event_name="telegram_auth_success",
            source_path="/api/v1/auth/telegram",
            session_id=analytics_session_id,
            user_telegram_id=user.telegram_id,
            device_mode=analytics_device_mode,
            is_in_telegram=bool(auth_request.initData),
            has_init_data=bool(auth_request.initData),
            start_param=launch_start_param,
            has_query_id=launch_has_query_id,
            chat_type=launch_chat_type,
            meta={
                "source": launch_source,
                "auth_source": telegram_auth_source,
                "is_new_user": is_new_user,
            },
        )

        web_auth_result = await web_account_service.get_or_create_for_telegram_user(
            user=user,
            preferred_username=auth_data.username or user.username,
        )

        if is_new_user:
            await _notify_web_user_registered(
                notification_service=notification_service,
                user=user,
                web_username=web_auth_result.web_account.username,
                auth_source="WEB_TELEGRAM",
            )

        return build_session_response(
            access_token=web_auth_result.access_token,
            refresh_token=web_auth_result.refresh_token,
            response=response,
            is_new_user=is_new_user,
            auth_source=telegram_auth_source,
        )
    except HTTPException as exc:
        await _track_web_analytics_event(
            web_analytics_event_service=web_analytics_event_service,
            event_name="telegram_auth_failed",
            source_path="/api/v1/auth/telegram",
            session_id=analytics_session_id,
            user_telegram_id=auth_data.id if auth_data else None,
            device_mode=analytics_device_mode,
            is_in_telegram=bool(auth_request.initData),
            has_init_data=bool(auth_request.initData),
            start_param=launch_start_param,
            has_query_id=launch_has_query_id,
            chat_type=launch_chat_type,
            meta={
                "source": launch_source,
                "status_code": exc.status_code,
                "reason": str(exc.detail),
            },
        )
        raise
    except Exception as exc:
        await _track_web_analytics_event(
            web_analytics_event_service=web_analytics_event_service,
            event_name="telegram_auth_failed",
            source_path="/api/v1/auth/telegram",
            session_id=analytics_session_id,
            user_telegram_id=auth_data.id if auth_data else None,
            device_mode=analytics_device_mode,
            is_in_telegram=bool(auth_request.initData),
            has_init_data=bool(auth_request.initData),
            start_param=launch_start_param,
            has_query_id=launch_has_query_id,
            chat_type=launch_chat_type,
            meta={
                "source": launch_source,
                "reason": str(exc),
                "exception_type": type(exc).__name__,
            },
        )
        raise


@router.post("/telegram-link/request", response_model=TelegramLinkRequestResponse)
@inject
async def request_telegram_link_code(
    payload: TelegramLinkRequestPayload,
    request: Request,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    telegram_link_service: FromDishka[TelegramLinkService] = _DISHKA_DEFAULT,
    settings_service: FromDishka[SettingsService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
    redis_client: FromDishka[Redis] = _DISHKA_DEFAULT,
) -> TelegramLinkRequestResponse:
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:tg_link:request:{web_account.id}:{_request_ip(request)}",
    )
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)

    result = await telegram_link_service.request_code(
        web_account=web_account,
        telegram_id=payload.telegram_id,
        ttl_seconds=config.web_app.telegram_link_code_ttl_seconds,
        attempts=config.web_app.auth_challenge_attempts,
        return_to_miniapp=False,
    )
    branding = await settings_service.get_branding_settings()
    message_template = (
        settings_service.resolve_localized_branding_text(
            branding.verification.web_request_delivered,
            language=locale,
        )
        if result.delivered
        else settings_service.resolve_localized_branding_text(
            branding.verification.web_request_open_bot,
            language=locale,
        )
    )
    message = settings_service.render_branding_text(
        message_template,
        placeholders={"project_name": branding.project_name},
    )
    return TelegramLinkRequestResponse(
        message=message,
        delivered=result.delivered,
        expires_in_seconds=result.expires_in_seconds,
        bot_confirm_url=result.bot_confirm_url,
        bot_confirm_deep_link=result.bot_confirm_deep_link,
    )


@router.post("/telegram-link/request-auto", response_model=TelegramLinkRequestResponse)
@inject
async def request_telegram_link_auto_confirm(
    payload: TelegramLinkAutoRequestPayload,
    request: Request,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    telegram_link_service: FromDishka[TelegramLinkService] = _DISHKA_DEFAULT,
    settings_service: FromDishka[SettingsService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
    redis_client: FromDishka[Redis] = _DISHKA_DEFAULT,
) -> TelegramLinkRequestResponse:
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:tg_link:request_auto:{web_account.id}:{_request_ip(request)}",
    )
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)

    trusted_telegram_id = _resolve_trusted_telegram_id_for_auto_link(current_user)
    if trusted_telegram_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TRUSTED_TELEGRAM_ID_REQUIRED",
                "message": "Automatic Telegram confirmation is unavailable for this session.",
            },
        )

    result = await telegram_link_service.request_code(
        web_account=web_account,
        telegram_id=trusted_telegram_id,
        ttl_seconds=config.web_app.telegram_link_code_ttl_seconds,
        attempts=config.web_app.auth_challenge_attempts,
        return_to_miniapp=payload.return_to_miniapp,
    )
    branding = await settings_service.get_branding_settings()
    message_template = (
        settings_service.resolve_localized_branding_text(
            branding.verification.web_request_delivered,
            language=locale,
        )
        if result.delivered
        else settings_service.resolve_localized_branding_text(
            branding.verification.web_request_open_bot,
            language=locale,
        )
    )
    message = settings_service.render_branding_text(
        message_template,
        placeholders={"project_name": branding.project_name},
    )
    return TelegramLinkRequestResponse(
        message=message,
        delivered=result.delivered,
        expires_in_seconds=result.expires_in_seconds,
        bot_confirm_url=result.bot_confirm_url,
        bot_confirm_deep_link=result.bot_confirm_deep_link,
    )


@router.post("/telegram-link/confirm", response_model=TelegramLinkConfirmResponse)
@inject
async def confirm_telegram_link_code(
    payload: TelegramLinkConfirmPayload,
    request: Request,
    response: Response,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    telegram_link_service: FromDishka[TelegramLinkService] = _DISHKA_DEFAULT,
    user_service: FromDishka[UserService] = _DISHKA_DEFAULT,
    notification_service: FromDishka[NotificationService] = _DISHKA_DEFAULT,
    settings_service: FromDishka[SettingsService] = _DISHKA_DEFAULT,
    redis_client: FromDishka[Redis] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> TelegramLinkConfirmResponse:
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:tg_link:confirm:{web_account.id}:{_request_ip(request)}",
    )
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)

    try:
        result = await telegram_link_service.confirm_code(
            web_account=web_account,
            telegram_id=payload.telegram_id,
            code=payload.code,
        )
    except TelegramLinkError as exc:
        if exc.code in {"TELEGRAM_ALREADY_LINKED", "MANUAL_MERGE_REQUIRED"}:
            raise HTTPException(
                status_code=409,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    linked_user = await user_service.get(result.linked_telegram_id) if user_service else None
    if linked_user:
        await _notify_web_account_linked(
            notification_service=notification_service,
            linked_user=linked_user,
            web_username=result.web_account.username,
            old_user_id=web_account.user_telegram_id,
            linked_telegram_id=result.linked_telegram_id,
            link_source="WEB_CONFIRM",
        )

    branding = await settings_service.get_branding_settings()
    message_template = settings_service.resolve_localized_branding_text(
        branding.verification.web_confirm_success,
        language=locale,
    )
    message = settings_service.render_branding_text(
        message_template,
        placeholders={"project_name": branding.project_name},
    )

    access_token = create_access_token(
        user_id=result.web_account.user_telegram_id,
        username=result.web_account.username,
        token_version=result.web_account.token_version,
    )
    refresh_token = create_refresh_token(
        user_id=result.web_account.user_telegram_id,
        username=result.web_account.username,
        token_version=result.web_account.token_version,
    )
    set_auth_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    return TelegramLinkConfirmResponse(
        message=message,
        linked_telegram_id=result.linked_telegram_id,
    )


@router.post("/telegram-link/remind-later", response_model=TelegramLinkStatusResponse)
@inject
async def telegram_link_remind_later(
    web_account: WebAccountDto = Depends(get_current_web_account),
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> TelegramLinkStatusResponse:
    updated = await web_account_service.set_link_prompt_snooze(
        web_account.id or 0,
        config.web_app.link_prompt_snooze_days,
    )
    if not updated:
        raise HTTPException(status_code=400, detail="Failed to update reminder state")
    linked_telegram_id = updated.user_telegram_id if updated.user_telegram_id > 0 else None
    return TelegramLinkStatusResponse(
        telegram_linked=linked_telegram_id is not None,
        linked_telegram_id=linked_telegram_id,
        show_link_prompt=linked_telegram_id is None,
    )
