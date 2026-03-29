from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Callable, Literal, Optional, cast
from urllib.parse import parse_qsl
from uuid import uuid4

from aiogram.types import User as AiogramUser
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel
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
from src.api.dependencies.web_access import (
    assert_web_general_access,
    assert_web_registration_access,
    normalize_web_referral_code,
    validate_web_invite_code,
)
from src.api.dependencies.web_auth import (
    get_current_user,
    get_current_web_account,
)
from src.api.presenters.web_auth import (
    AccessStatusResponse,
    AuthMeResponse,
    AuthSessionStatusResponse,
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
from src.api.utils.request_ip import resolve_client_ip
from src.api.utils.web_auth_transport import (
    ACCESS_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_NAME,
    build_session_response,
    clear_auth_cookies,
    ensure_csrf_if_cookie_auth,
    parse_token_subject_and_version,
    set_auth_cookies,
)
from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.constants import REFERRAL_PREFIX
from src.core.enums import ReferralInviteSource, SystemNotificationType
from src.core.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
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


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


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


def verify_telegram_hash(data: dict, bot_token: str) -> bool:
    check_data = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(check_data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, data["hash"])


def verify_telegram_webapp_init_data(init_data: str, bot_token: str) -> bool:
    parsed_pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    provided_hash = parsed_pairs.pop("hash", "")
    if not provided_hash:
        return False
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed_pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, provided_hash)


def _parse_telegram_auth_request(auth_request: TelegramAuthRequest) -> TelegramAuthData:
    if auth_request.initData:
        init_data_pairs = dict(parse_qsl(auth_request.initData, keep_blank_values=True))
        user_raw = init_data_pairs.get("user")
        auth_date_raw = init_data_pairs.get("auth_date")
        hash_raw = init_data_pairs.get("hash")
        if not user_raw or not auth_date_raw or not hash_raw:
            raise HTTPException(status_code=400, detail="Invalid initData payload")
        try:
            user_obj = json.loads(user_raw)
            return TelegramAuthData(
                id=int(user_obj["id"]),
                first_name=str(user_obj.get("first_name") or ""),
                last_name=user_obj.get("last_name"),
                username=user_obj.get("username"),
                photo_url=user_obj.get("photo_url"),
                auth_date=int(auth_date_raw),
                hash=str(hash_raw),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Malformed initData payload") from exc

    if (
        auth_request.id is None
        or auth_request.first_name is None
        or auth_request.auth_date is None
        or auth_request.hash is None
    ):
        raise HTTPException(status_code=400, detail="Missing Telegram auth fields")

    return TelegramAuthData(
        id=auth_request.id,
        first_name=auth_request.first_name,
        last_name=auth_request.last_name,
        username=auth_request.username,
        photo_url=auth_request.photo_url,
        auth_date=auth_request.auth_date,
        hash=auth_request.hash,
    )


def _extract_referral_code_from_telegram_request(
    auth_request: TelegramAuthRequest,
) -> Optional[str]:
    if auth_request.initData:
        init_data_pairs = dict(parse_qsl(auth_request.initData, keep_blank_values=True))
        if referral_from_start_param := normalize_web_referral_code(
            init_data_pairs.get("start_param"),
            require_prefix=True,
        ):
            return referral_from_start_param
    return normalize_web_referral_code(auth_request.referralCode)


def _extract_telegram_launch_context(
    auth_request: TelegramAuthRequest,
) -> dict[str, str | bool | None]:
    if not auth_request.initData:
        return {
            "source": "widget",
            "start_param": None,
            "has_query_id": False,
            "chat_type": None,
        }

    init_data_pairs = dict(parse_qsl(auth_request.initData, keep_blank_values=True))
    return {
        "source": "webapp",
        "start_param": init_data_pairs.get("start_param"),
        "has_query_id": bool(init_data_pairs.get("query_id")),
        "chat_type": init_data_pairs.get("chat_type"),
    }


async def _track_web_analytics_event(
    *,
    web_analytics_event_service: Optional[WebAnalyticsEventService],
    event_name: str,
    source_path: str,
    session_id: str,
    device_mode: str,
    is_in_telegram: bool,
    has_init_data: bool,
    has_query_id: bool,
    user_telegram_id: Optional[int] = None,
    start_param: Optional[str] = None,
    chat_type: Optional[str] = None,
    meta: Optional[dict[str, object]] = None,
) -> None:
    if web_analytics_event_service is None:
        return

    try:
        await web_analytics_event_service.create_event(
            event_name=event_name,
            source_path=source_path,
            session_id=session_id,
            user_telegram_id=user_telegram_id,
            device_mode=device_mode,
            is_in_telegram=is_in_telegram,
            has_init_data=has_init_data,
            start_param=start_param,
            has_query_id=has_query_id,
            chat_type=chat_type,
            meta=meta or {},
        )
    except Exception as exc:
        logger.warning("Failed to persist auth analytics event '{}': {}", event_name, exc)


async def _apply_referral_for_new_user(
    *,
    user: UserDto,
    referral_code: Optional[str],
    referral_service: ReferralService,
    partner_service: PartnerService,
) -> None:
    if not referral_code:
        return
    try:
        normalized_code = (
            referral_code
            if referral_code.startswith(REFERRAL_PREFIX)
            else f"{REFERRAL_PREFIX}{referral_code}"
        )
        partner_referrer = await referral_service.get_partner_referrer_by_code(
            normalized_code,
            user_telegram_id=user.telegram_id,
        )
        await referral_service.handle_referral(
            user=user,
            code=normalized_code,
            source=ReferralInviteSource.WEB,
        )
        if partner_referrer:
            await partner_service.handle_new_user_referral(
                user=user,
                referrer_code=partner_referrer.referral_code,
            )
    except Exception:
        logger.exception(
            f"Failed to apply referral for new web user '{user.telegram_id}' "
            f"with code '{referral_code}'"
        )


def _build_user_i18n_kwargs(user: UserDto) -> dict[str, object]:
    return {
        "user_id": str(user.telegram_id),
        "user_name": user.name or str(user.telegram_id),
        "username": user.username or False,
    }


async def _notify_web_user_registered(
    *,
    notification_service: Optional[NotificationService],
    user: UserDto,
    web_username: str,
    auth_source: str,
) -> None:
    if notification_service is None:
        return

    await notification_service.system_notify(
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-event-web-user-registered",
            i18n_kwargs={
                **_build_user_i18n_kwargs(user),
                "web_username": web_username,
                "auth_source": auth_source,
            },
            reply_markup=get_user_keyboard(user.telegram_id),
        ),
        ntf_type=SystemNotificationType.WEB_USER_REGISTERED,
    )


async def _notify_web_account_linked(
    *,
    notification_service: Optional[NotificationService],
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

async def _enforce_rate_limit(config: AppConfig, redis_client: Redis, key: str) -> None:
    if not config.web_app.rate_limit_enabled:
        return
    limit = max(config.web_app.rate_limit_max_requests, 1)
    window = config.web_app.rate_limit_window
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window)
    except Exception as exc:
        logger.warning(f"Rate-limit fallback disabled for key '{key}': {exc}")
        return
    if current > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")


def _request_ip(request: Request) -> str:
    app = request.scope.get("app")
    app_state = getattr(app, "state", None)
    config = getattr(app_state, "config", None)
    if config is None:
        client_host = request.client.host if request.client else ""
        return client_host or "unknown"
    return resolve_client_ip(request, config)

def _resolve_web_auth_message(key: str, locale: Literal["ru", "en"]) -> str:
    values = WEB_AUTH_MESSAGES.get(key, {})
    return values.get(locale) or values.get("ru") or ""


async def _has_valid_cookie_session(
    *,
    request: Request,
    cookie_name: str,
    token_verifier: Callable[[str], dict[str, Any] | None],
    web_account_service: WebAccountService,
) -> bool:
    token_value = request.cookies.get(cookie_name)
    if not token_value:
        return False

    token_payload = token_verifier(token_value)
    if not token_payload:
        return False

    try:
        user_id, token_version = parse_token_subject_and_version(token_payload)
    except (TypeError, ValueError):
        return False

    if not user_id:
        return False

    web_account = await web_account_service.get_by_user_telegram_id(user_id)
    return bool(web_account and web_account.token_version == token_version)


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
    await _enforce_rate_limit(
        config, redis_client, f"auth:login:{login_data.username.lower()}:{_request_ip(request)}"
    )

    try:
        result = await web_account_service.login(
            username=login_data.username, password=login_data.password
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
    auth_data: Optional[TelegramAuthData] = None
    launch_context = {
        "source": "widget",
        "start_param": None,
        "has_query_id": False,
        "chat_type": None,
    }
    analytics_session_id = str(uuid4())
    analytics_device_mode = "telegram-mobile" if auth_request.initData else "web"
    launch_source = "widget"
    launch_start_param: Optional[str] = None
    launch_has_query_id = False
    launch_chat_type: Optional[str] = None

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
                mode=mode, existing_user=None, is_valid_invite=is_valid_invite
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
    await _enforce_rate_limit(
        config, redis_client, f"auth:tg_link:request:{web_account.id}:{_request_ip(request)}"
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
        bot_confirm_url=result.bot_confirm_url,
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
        config, redis_client, f"auth:tg_link:confirm:{web_account.id}:{_request_ip(request)}"
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
        config, redis_client, f"auth:email_verify:request:{web_account.id}:{_request_ip(request)}"
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
        config, redis_client, f"auth:password_forgot:{identity}:{_request_ip(request)}"
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
        config, redis_client, f"auth:password_forgot_tg:{identity}:{_request_ip(request)}"
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
