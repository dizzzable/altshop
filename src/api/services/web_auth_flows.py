from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import parse_qsl
from uuid import uuid4

from aiogram.types import User as AiogramUser
from fastapi import HTTPException, status
from loguru import logger
from pydantic import BaseModel
from redis.asyncio import Redis

from src.api.contracts.web_auth import (
    LoginRequest,
    RegisterRequest,
    TelegramAuthRequest,
    TelegramLinkConfirmPayload,
    WebAccountBootstrapRequest,
)
from src.api.dependencies.web_access import (
    assert_web_general_access,
    assert_web_registration_access,
    normalize_web_referral_code,
    validate_web_invite_code,
)
from src.api.utils.web_auth_rate_limit import enforce_public_auth_rate_limit, enforce_rate_limit
from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.constants import REFERRAL_PREFIX
from src.core.enums import ReferralInviteSource, SystemNotificationType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import SettingsDto, UserDto, WebAccountDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.telegram_link import TelegramLinkError, TelegramLinkService
from src.services.user import UserService
from src.services.web_account import WebAccountService, WebAuthResult
from src.services.web_analytics_event import WebAnalyticsEventService

REGISTRATION_GENERIC_ERROR_DETAIL = "Registration could not be completed with the provided data."


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


@dataclass(slots=True)
class TelegramLinkConfirmFlowResult:
    web_account: WebAccountDto
    linked_telegram_id: int
    message: str


def verify_telegram_hash(data: dict, bot_token: str) -> bool:
    check_data = {key: value for key, value in data.items() if key != "hash"}
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
            "Failed to apply referral for new web user '{}' with code '{}'",
            user.telegram_id,
            referral_code,
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


async def _enforce_register_rate_limits(
    *,
    config: AppConfig,
    redis_client: Redis,
    register_data: RegisterRequest,
    client_ip: str,
) -> None:
    await enforce_public_auth_rate_limit(
        config=config,
        redis_client=redis_client,
        endpoint="register",
        scope="ip",
        subject=client_ip,
        limit=config.web_app.register_rate_limit_ip_max_requests,
        client_ip=client_ip,
    )
    await enforce_public_auth_rate_limit(
        config=config,
        redis_client=redis_client,
        endpoint="register",
        scope="username",
        subject=register_data.username,
        limit=config.web_app.register_rate_limit_identity_max_requests,
        client_ip=client_ip,
    )
    if register_data.telegram_id is None:
        return

    await enforce_public_auth_rate_limit(
        config=config,
        redis_client=redis_client,
        endpoint="register",
        scope="telegram_id",
        subject=register_data.telegram_id,
        limit=config.web_app.register_rate_limit_identity_max_requests,
        client_ip=client_ip,
    )


def _validate_registration_requirements(
    settings: SettingsDto,
    register_data: RegisterRequest,
) -> bool:
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

    return requires_telegram_id


async def register_with_password(
    *,
    register_data: RegisterRequest,
    client_ip: str,
    config: AppConfig,
    redis_client: Redis,
    web_account_service: WebAccountService,
    referral_service: ReferralService,
    partner_service: PartnerService,
    notification_service: NotificationService,
    user_service: UserService,
    settings_service: SettingsService,
    telegram_link_service: TelegramLinkService,
) -> WebAuthResult:
    await _enforce_register_rate_limits(
        config=config,
        redis_client=redis_client,
        register_data=register_data,
        client_ip=client_ip,
    )

    settings = await settings_service.get()
    mode = settings.access_mode
    requires_telegram_id = _validate_registration_requirements(settings, register_data)

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
        logger.warning(
            "Public registration rejected. username='{}' telegram_id='{}' reason='{}'",
            register_data.username,
            register_data.telegram_id or "-",
            exc,
        )
        raise HTTPException(status_code=400, detail=REGISTRATION_GENERIC_ERROR_DETAIL) from exc

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

    return result


async def login_with_password(
    *,
    login_data: LoginRequest,
    client_ip: str,
    config: AppConfig,
    redis_client: Redis,
    web_account_service: WebAccountService,
    settings_service: SettingsService,
) -> WebAuthResult:
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:login:{login_data.username.lower()}:{client_ip}",
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
    return result


async def bootstrap_web_account_credentials(
    *,
    payload: WebAccountBootstrapRequest,
    current_user: UserDto,
    web_account_service: WebAccountService,
) -> WebAuthResult:
    if current_user.telegram_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram account is required for web bootstrap",
        )

    try:
        return await web_account_service.bootstrap_credentials_for_telegram_user(
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


async def confirm_telegram_link(
    *,
    payload: TelegramLinkConfirmPayload,
    web_account: WebAccountDto,
    locale: Literal["ru", "en"],
    telegram_link_service: TelegramLinkService,
    user_service: UserService | None,
    notification_service: NotificationService | None,
    settings_service: SettingsService,
) -> TelegramLinkConfirmFlowResult:
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
    return TelegramLinkConfirmFlowResult(
        web_account=result.web_account,
        linked_telegram_id=result.linked_telegram_id,
        message=message,
    )


async def authenticate_with_telegram(
    *,
    auth_request: TelegramAuthRequest,
    client_ip: str,
    telegram_auth_source: str,
    user_service: UserService,
    config: AppConfig,
    referral_service: ReferralService,
    partner_service: PartnerService,
    notification_service: NotificationService,
    settings_service: SettingsService,
    web_account_service: WebAccountService,
    redis_client: Redis,
    web_analytics_event_service: WebAnalyticsEventService | None = None,
) -> WebAuthResult:
    await enforce_public_auth_rate_limit(
        config=config,
        redis_client=redis_client,
        endpoint="telegram",
        scope="ip",
        subject=client_ip,
        limit=config.web_app.telegram_auth_rate_limit_ip_max_requests,
        client_ip=client_ip,
    )

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
        await enforce_public_auth_rate_limit(
            config=config,
            redis_client=redis_client,
            endpoint="telegram",
            scope="telegram_id",
            subject=auth_data.id,
            limit=config.web_app.telegram_auth_rate_limit_identity_max_requests,
            client_ip=client_ip,
        )
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
            (
                "Telegram auth attempt: user_id={}, source={}, "
                "has_query_id={}, start_param={}, chat_type={}"
            ),
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

        web_auth_result.is_new_user = is_new_user
        return web_auth_result
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


__all__ = [
    "REGISTRATION_GENERIC_ERROR_DETAIL",
    "authenticate_with_telegram",
    "bootstrap_web_account_credentials",
    "login_with_password",
    "register_with_password",
]
