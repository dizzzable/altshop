from __future__ import annotations

from typing import Any, cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from loguru import logger
from redis.asyncio import Redis

from src.api.contracts.web_auth import LoginRequest, RegisterRequest, WebAccountBootstrapRequest
from src.api.dependencies.web_access import (
    assert_web_general_access,
    assert_web_registration_access,
    normalize_web_referral_code,
    validate_web_invite_code,
)
from src.api.dependencies.web_auth import get_current_user, get_current_web_account
from src.api.presenters.web_auth import (
    AccessStatusResponse,
    AuthMeResponse,
    AuthSessionStatusResponse,
    LogoutResponse,
    RegistrationAccessRequirementsResponse,
    SessionResponse,
    WebBrandingResponse,
    _build_access_status_response,
    _build_auth_me_response,
    _build_registration_access_requirements_response,
    _build_web_branding_response,
    _render_webapp_entry_html,
)
from src.api.utils.web_auth_transport import (
    ACCESS_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
    build_session_response,
    clear_auth_cookies,
    ensure_csrf_if_cookie_auth,
    parse_token_subject_and_version,
)
from src.core.config import AppConfig
from src.core.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from src.core.utils.bot_menu import resolve_bot_menu_url
from src.core.utils.branding import normalize_text, resolve_project_name
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.telegram_link import TelegramLinkService
from src.services.user import UserService
from src.services.user_profile import UserProfileService
from src.services.web_access_guard import WebAccessGuardService
from src.services.web_account import WebAccountService

from .web_auth_support import (
    _apply_referral_for_new_user,
    _enforce_rate_limit,
    _has_valid_cookie_session,
    _notify_web_user_registered,
    _request_ip,
)

router = APIRouter()
_DISHKA_DEFAULT = cast(Any, None)


@router.post("/register", response_model=SessionResponse)
@inject
async def register(
    register_data: RegisterRequest,
    response: Response,
    web_account_service: FromDishka[WebAccountService],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    telegram_link_service: FromDishka[TelegramLinkService],
    config: FromDishka[AppConfig],
) -> SessionResponse:
    settings = await settings_service.get()
    mode = settings.access_mode
    requires_telegram_id = bool(settings.rules_required or settings.channel_required)

    if settings.rules_required and not register_data.accept_rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the rules to register",
        )

    if settings.channel_required and not register_data.accept_channel_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must confirm channel subscription to register",
        )

    if requires_telegram_id and register_data.telegram_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram ID is required when access conditions are enabled",
        )

    is_valid_invite = await validate_web_invite_code(
        raw_code=register_data.referral_code,
        referral_service=referral_service,
        new_user_telegram_id=register_data.telegram_id or -1,
    )
    assert_web_registration_access(mode=mode, existing_user=None, is_valid_invite=is_valid_invite)

    try:
        result = await web_account_service.register(
            username=register_data.username,
            password=register_data.password,
            telegram_id=None,
            name=register_data.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rules_accepted = bool((not settings.rules_required) or register_data.accept_rules)
    if result.user.is_rules_accepted != rules_accepted:
        result.user.is_rules_accepted = rules_accepted
        updated_user = await user_service.update(result.user)
        if updated_user:
            result.user = updated_user

    if result.is_new_user:
        await _apply_referral_for_new_user(
            user=result.user,
            referral_code=normalize_web_referral_code(register_data.referral_code),
            referral_service=referral_service,
            partner_service=partner_service,
        )
    await _notify_web_user_registered(
        notification_service=notification_service,
        user=result.user,
        web_username=result.web_account.username,
        auth_source="WEB_PASSWORD",
    )

    if requires_telegram_id and register_data.telegram_id is not None:
        try:
            await telegram_link_service.request_code(
                web_account=result.web_account,
                telegram_id=register_data.telegram_id,
                ttl_seconds=config.web_app.telegram_link_code_ttl_seconds,
                attempts=config.web_app.auth_challenge_attempts,
            )
        except Exception as exc:
            logger.warning(
                "Failed to auto-request Telegram link code after registration for tg_id='{}': {}",
                register_data.telegram_id,
                exc,
            )

    return build_session_response(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        response=response,
        is_new_user=result.is_new_user,
        auth_source="WEB_PASSWORD",
    )


@router.get(
    "/registration/access-requirements",
    response_model=RegistrationAccessRequirementsResponse,
)
@inject
async def get_registration_access_requirements(
    settings_service: FromDishka[SettingsService],
    web_access_guard_service: FromDishka[WebAccessGuardService],
) -> RegistrationAccessRequirementsResponse:
    settings = await settings_service.get()
    return _build_registration_access_requirements_response(
        settings,
        verification_bot_link=await web_access_guard_service.get_verification_bot_link(),
    )


@router.get("/access-status", response_model=AccessStatusResponse)
@inject
async def get_access_status(
    force_channel_recheck: bool = False,
    current_user: UserDto = Depends(get_current_user),
    web_access_guard_service: FromDishka[WebAccessGuardService] = _DISHKA_DEFAULT,
) -> AccessStatusResponse:
    access_status = await web_access_guard_service.evaluate_user_access(
        user=current_user,
        force_channel_recheck=force_channel_recheck,
    )
    return _build_access_status_response(access_status)


@router.post("/access/rules/accept", response_model=AccessStatusResponse)
@inject
async def accept_rules_for_access(
    current_user: UserDto = Depends(get_current_user),
    user_service: FromDishka[UserService] = _DISHKA_DEFAULT,
    web_access_guard_service: FromDishka[WebAccessGuardService] = _DISHKA_DEFAULT,
) -> AccessStatusResponse:
    if not current_user.is_rules_accepted:
        current_user.is_rules_accepted = True
        updated_user = await user_service.update(current_user)
        if updated_user:
            current_user = updated_user

    access_status = await web_access_guard_service.evaluate_user_access(
        user=current_user,
        force_channel_recheck=True,
    )
    return _build_access_status_response(access_status)


@router.post("/login", response_model=SessionResponse)
@inject
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    web_account_service: FromDishka[WebAccountService],
    settings_service: FromDishka[SettingsService],
    config: FromDishka[AppConfig],
    redis_client: FromDishka[Redis],
) -> SessionResponse:
    await _enforce_rate_limit(
        config,
        redis_client,
        f"auth:login:{login_data.username.lower()}:{_request_ip(request)}",
    )

    try:
        result = await web_account_service.login(
            username=login_data.username,
            password=login_data.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    mode = await settings_service.get_access_mode()
    assert_web_general_access(result.user, mode)
    return build_session_response(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        response=response,
        is_new_user=result.is_new_user,
        auth_source="WEB_PASSWORD",
    )


@router.post("/web-account/bootstrap", response_model=SessionResponse)
@inject
async def bootstrap_web_account(
    payload: WebAccountBootstrapRequest,
    response: Response,
    current_user: UserDto = Depends(get_current_user),
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
) -> SessionResponse:
    if current_user.telegram_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram account is required for web bootstrap",
        )

    try:
        result = await web_account_service.bootstrap_credentials_for_telegram_user(
            telegram_id=current_user.telegram_id,
            username=payload.username,
            password=payload.password,
            name=current_user.name or current_user.username,
        )
    except ValueError as exc:
        error_message = str(exc)
        error_status = (
            status.HTTP_409_CONFLICT
            if error_message == "Web credentials already configured"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=error_message) from exc

    return build_session_response(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        response=response,
        is_new_user=result.is_new_user,
        auth_source="WEB_PASSWORD",
    )


@router.post("/refresh", response_model=SessionResponse)
@inject
async def refresh_token(
    response: Response,
    request: Request,
    web_account_service: FromDishka[WebAccountService],
) -> SessionResponse:
    ensure_csrf_if_cookie_auth(request, cookie_name=REFRESH_TOKEN_COOKIE_NAME)

    refresh_token_value = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh token is required")

    web_payload = verify_refresh_token(refresh_token_value)
    if not web_payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    try:
        user_id, token_version = parse_token_subject_and_version(web_payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token payload") from exc

    web_account = await web_account_service.get_by_user_telegram_id(user_id)
    if not web_account or web_account.token_version != token_version:
        raise HTTPException(status_code=401, detail="Refresh token is outdated")

    return build_session_response(
        access_token=create_access_token(
            user_id=web_account.user_telegram_id,
            username=web_account.username,
            token_version=web_account.token_version,
        ),
        refresh_token=create_refresh_token(
            user_id=web_account.user_telegram_id,
            username=web_account.username,
            token_version=web_account.token_version,
        ),
        response=response,
    )


@router.get("/session-status", response_model=AuthSessionStatusResponse)
@inject
async def get_session_status(
    request: Request,
    web_account_service: FromDishka[WebAccountService],
) -> AuthSessionStatusResponse:
    if await _has_valid_cookie_session(
        request=request,
        cookie_name=ACCESS_TOKEN_COOKIE_NAME,
        token_verifier=verify_access_token,
        web_account_service=web_account_service,
    ):
        return AuthSessionStatusResponse(authenticated=True, refresh_required=False)

    if await _has_valid_cookie_session(
        request=request,
        cookie_name=REFRESH_TOKEN_COOKIE_NAME,
        token_verifier=verify_refresh_token,
        web_account_service=web_account_service,
    ):
        return AuthSessionStatusResponse(authenticated=True, refresh_required=True)

    return AuthSessionStatusResponse(authenticated=False, refresh_required=False)


@router.post("/logout", response_model=LogoutResponse)
@inject
async def logout(
    response: Response,
    current_user: UserDto = Depends(get_current_user),
    web_account: WebAccountDto = Depends(get_current_web_account),
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
) -> LogoutResponse:
    cleaned_up_provisional = False
    if web_account.id is not None:
        cleaned_up_provisional = await web_account_service.cleanup_provisional_account_on_logout(
            web_account_id=web_account.id,
            expected_user_telegram_id=current_user.telegram_id,
        )
        if not cleaned_up_provisional:
            await web_account_service.increment_token_version(web_account.id)
    clear_auth_cookies(response)
    logger.info(
        "User {} logged out (provisional_cleanup={})",
        current_user.telegram_id,
        cleaned_up_provisional,
    )
    return LogoutResponse()


@router.get("/me", response_model=AuthMeResponse)
@inject
async def get_current_user_info(
    current_user: UserDto = Depends(get_current_user),
    user_profile_service: FromDishka[UserProfileService] = _DISHKA_DEFAULT,
) -> AuthMeResponse:
    profile = await user_profile_service.build_snapshot(user=current_user)
    return _build_auth_me_response(profile)


@router.get("/branding", response_model=WebBrandingResponse)
@inject
async def get_web_branding(
    settings_service: FromDishka[SettingsService] = _DISHKA_DEFAULT,
    config: FromDishka[AppConfig] = _DISHKA_DEFAULT,
) -> WebBrandingResponse:
    settings = await settings_service.get()
    mini_app_url, _ = resolve_bot_menu_url(bot_menu=settings.bot_menu, config=config)
    return _build_web_branding_response(
        settings.branding,
        config=config,
        mini_app_url=mini_app_url,
    )


@router.get("/webapp-shell", response_class=HTMLResponse, include_in_schema=False)
@inject
async def get_webapp_shell(
    request: Request,
    settings_service: FromDishka[SettingsService] = _DISHKA_DEFAULT,
) -> HTMLResponse:
    settings = await settings_service.get()
    branding = settings.branding
    project_name = resolve_project_name(branding.project_name)
    web_title = normalize_text(branding.web_title) or project_name
    entry_url = "entry"
    if request.url.query:
        entry_url = f"{entry_url}?{request.url.query}"

    return HTMLResponse(
        _render_webapp_entry_html(
            project_name=project_name,
            web_title=web_title,
            entry_url=entry_url,
        ),
        headers={"Cache-Control": "no-store"},
    )
