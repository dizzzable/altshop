from __future__ import annotations

from typing import Any, Literal, cast

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from loguru import logger
from redis.asyncio import Redis

from src.api.contracts.web_auth import (
    ChangePasswordRequest,
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
    VerifyEmailConfirmRequest,
    WebAccountBootstrapRequest,
)
from src.api.dependencies.web_auth import (
    get_current_user,
    get_current_web_account,
)
from src.api.presenters.web_auth import (
    AccessStatusResponse,
    AuthMeResponse,
    LogoutResponse,
    MessageResponse,
    RegistrationAccessRequirementsResponse,
    SessionResponse,
    TelegramLinkConfirmResponse,
    TelegramLinkRequestResponse,
    TelegramLinkStatusResponse,
    WebBrandingResponse,
    _build_access_status_response,
    _build_auth_me_response,
    _build_registration_access_requirements_response,
    _build_web_branding_response,
    _render_webapp_entry_html,
    _resolve_web_request_locale,
)
from src.api.services import web_auth_flows
from src.api.utils.web_auth_rate_limit import enforce_rate_limit, request_ip
from src.api.utils.web_auth_transport import (
    REFRESH_TOKEN_COOKIE_NAME,
    build_account_session_response,
    build_session_response,
    clear_auth_cookies,
    ensure_csrf_if_cookie_auth,
    parse_token_subject_and_version,
    set_account_session,
)
from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.enums import SystemNotificationType
from src.core.security.jwt_handler import verify_refresh_token
from src.core.utils.bot_menu import resolve_bot_menu_url
from src.core.utils.branding import normalize_text, resolve_project_name
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.email_recovery import EmailRecoveryService
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.telegram_link import TelegramLinkError, TelegramLinkService
from src.services.user import UserService
from src.services.user_profile import UserProfileService
from src.services.web_access_guard import WebAccessGuardService
from src.services.web_account import WebAccountService
from src.services.web_analytics_event import WebAnalyticsEventService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
_DISHKA_DEFAULT = cast(Any, None)
REGISTRATION_GENERIC_ERROR_DETAIL = web_auth_flows.REGISTRATION_GENERIC_ERROR_DETAIL


WEB_AUTH_MESSAGES: dict[str, dict[Literal["ru", "en"], str]] = {
    "email_verify_request_sent": {
        "ru": "Письмо с подтверждением отправлено",
        "en": "Verification email sent",
    },
    "email_verify_confirmed": {
        "ru": "Email подтвержден",
        "en": "Email verified",
    },
    "password_forgot_sent": {
        "ru": (
            "Если аккаунт существует и email подтвержден, "
            "инструкция по восстановлению отправлена"
        ),
        "en": "If the account exists and email is verified, recovery instructions were sent",
    },
    "password_updated": {
        "ru": "Пароль обновлен",
        "en": "Password updated",
    },
}

def _build_user_i18n_kwargs(user: UserDto) -> dict[str, object]:
    return {
        "user_id": str(user.telegram_id),
        "user_name": user.name or str(user.telegram_id),
        "username": user.username or False,
    }


async def _notify_web_account_linked(
    *,
    notification_service: NotificationService | None,
    linked_user: UserDto,
    web_username: str,
    old_user_id: int,
    linked_telegram_id: int,
) -> None:
    if notification_service is None:
        return

    await notification_service.system_notify(
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-event-web-account-linked",
            i18n_kwargs={
                **_build_user_i18n_kwargs(linked_user),
                "web_username": web_username,
                "old_user_id": str(old_user_id),
                "linked_telegram_id": str(linked_telegram_id),
            },
            reply_markup=get_user_keyboard(linked_telegram_id),
        ),
        ntf_type=SystemNotificationType.WEB_ACCOUNT_LINKED,
    )

def _resolve_web_auth_message(key: str, locale: Literal["ru", "en"]) -> str:
    values = WEB_AUTH_MESSAGES.get(key, {})
    return values.get(locale) or values.get("ru") or ""


@router.post("/register", response_model=SessionResponse)
@inject
async def register(
    register_data: RegisterRequest,
    request: Request,
    response: Response,
    web_account_service: FromDishka[WebAccountService],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    telegram_link_service: FromDishka[TelegramLinkService],
    config: FromDishka[AppConfig],
    redis_client: FromDishka[Redis],
) -> SessionResponse:
    result = await web_auth_flows.register_with_password(
        register_data=register_data,
        client_ip=request_ip(request),
        config=config,
        redis_client=redis_client,
        web_account_service=web_account_service,
        referral_service=referral_service,
        partner_service=partner_service,
        notification_service=notification_service,
        user_service=user_service,
        settings_service=settings_service,
        telegram_link_service=telegram_link_service,
    )

    return build_session_response(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        response=response,
        is_new_user=result.is_new_user,
        auth_source="WEB_PASSWORD",
    )


@router.get(
    "/registration/access-requirements", response_model=RegistrationAccessRequirementsResponse
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
    result = await web_auth_flows.login_with_password(
        login_data=login_data,
        client_ip=request_ip(request),
        config=config,
        redis_client=redis_client,
        web_account_service=web_account_service,
        settings_service=settings_service,
    )
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
    result = await web_auth_flows.bootstrap_web_account_credentials(
        payload=payload,
        current_user=current_user,
        web_account_service=web_account_service,
    )
    return build_session_response(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        response=response,
        is_new_user=result.is_new_user,
        auth_source="WEB_PASSWORD",
    )


@router.post("/telegram", response_model=SessionResponse)
@inject
async def telegram_auth(
    auth_request: TelegramAuthRequest,
    request: Request,
    response: Response,
    user_service: FromDishka[UserService],
    config: FromDishka[AppConfig],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
    web_account_service: FromDishka[WebAccountService],
    redis_client: FromDishka[Redis],
    web_analytics_event_service: FromDishka[WebAnalyticsEventService] = _DISHKA_DEFAULT,
) -> SessionResponse:
    telegram_auth_source = (
        "WEB_TELEGRAM_WEBAPP" if auth_request.initData else "WEB_TELEGRAM_WIDGET"
    )
    result = await web_auth_flows.authenticate_with_telegram(
        auth_request=auth_request,
        client_ip=request_ip(request),
        telegram_auth_source=telegram_auth_source,
        user_service=user_service,
        config=config,
        referral_service=referral_service,
        partner_service=partner_service,
        notification_service=notification_service,
        settings_service=settings_service,
        web_account_service=web_account_service,
        redis_client=redis_client,
        web_analytics_event_service=web_analytics_event_service,
    )
    return build_session_response(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        response=response,
        is_new_user=result.is_new_user,
        auth_source=telegram_auth_source,
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

    return build_account_session_response(
        web_account=web_account,
        response=response,
    )


@router.post("/logout", response_model=LogoutResponse)
@inject
async def logout(
    response: Response,
    current_user: UserDto = Depends(get_current_user),
    web_account_service: FromDishka[WebAccountService] = _DISHKA_DEFAULT,
) -> LogoutResponse:
    web_account = await web_account_service.get_by_user_telegram_id(current_user.telegram_id)
    if web_account and web_account.id is not None:
        await web_account_service.increment_token_version(web_account.id)
    clear_auth_cookies(response)
    logger.info(f"User {current_user.telegram_id} logged out")
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
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:tg_link:request:{web_account.id}:{request_ip(request)}",
    )
    locale = _resolve_web_request_locale(request, config=config, current_user=current_user)

    result = await telegram_link_service.request_code(
        web_account=web_account,
        telegram_id=payload.telegram_id,
        ttl_seconds=config.web_app.telegram_link_code_ttl_seconds,
        attempts=config.web_app.auth_challenge_attempts,
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
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:tg_link:confirm:{web_account.id}:{request_ip(request)}",
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
                status_code=409, detail={"code": exc.code, "message": str(exc)}
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

    set_account_session(response, result.web_account)

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
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:email_verify:request:{web_account.id}:{request_ip(request)}",
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
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:password_forgot:{identity}:{request_ip(request)}",
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
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:password_forgot_tg:{identity}:{request_ip(request)}",
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

    set_account_session(response, updated_web_account)

    return MessageResponse(message=_resolve_web_auth_message("password_updated", locale))
