from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Callable, Literal
from urllib.parse import parse_qsl

from fastapi import HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from redis.asyncio import Redis

from src.api.contracts.web_auth import TelegramAuthRequest
from src.api.dependencies.web_access import normalize_web_referral_code
from src.api.utils.request_ip import resolve_client_ip
from src.api.utils.web_auth_transport import parse_token_subject_and_version
from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.constants import REFERRAL_PREFIX
from src.core.enums import ReferralInviteSource, SystemNotificationType
from src.core.utils.system_events import build_system_event_payload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.web_account import WebAccountService
from src.services.web_analytics_event import WebAnalyticsEventService


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
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
) -> str | None:
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
    web_analytics_event_service: WebAnalyticsEventService | None,
    event_name: str,
    source_path: str,
    session_id: str,
    device_mode: str,
    is_in_telegram: bool,
    has_init_data: bool,
    has_query_id: bool,
    user_telegram_id: int | None = None,
    start_param: str | None = None,
    chat_type: str | None = None,
    meta: dict[str, object] | None = None,
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
    referral_code: str | None,
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
    notification_service: NotificationService | None,
    user: UserDto,
    web_username: str,
    auth_source: str,
) -> None:
    if notification_service is None:
        return

    await notification_service.system_notify(
        payload=build_system_event_payload(
            i18n_key="ntf-event-web-user-registered",
            i18n_kwargs={
                **_build_user_i18n_kwargs(user),
                "web_username": web_username,
                "auth_source": auth_source,
            },
            severity="INFO",
            event_source="api.web_auth",
            operation="user_registration",
            auth_source=auth_source,
            impact="A new user account was created through the web authentication surface.",
            operator_hint=(
                "Check whether the source and linked profile state "
                "match the expected registration path."
            ),
            reply_markup=get_user_keyboard(user.telegram_id),
        ),
        ntf_type=SystemNotificationType.WEB_USER_REGISTERED,
    )


async def _notify_web_account_linked(
    *,
    notification_service: NotificationService | None,
    linked_user: UserDto,
    web_username: str,
    old_user_id: int,
    linked_telegram_id: int,
    link_source: str,
) -> None:
    if notification_service is None:
        return

    await notification_service.system_notify(
        payload=build_system_event_payload(
            i18n_key="ntf-event-web-account-linked",
            i18n_kwargs={
                **_build_user_i18n_kwargs(linked_user),
                "web_username": web_username,
                "old_user_id": str(old_user_id),
                "linked_telegram_id": str(linked_telegram_id),
            },
            severity="INFO",
            event_source="api.web_auth",
            operation="account_link",
            link_source=link_source,
            impact=(
                "A web login is now bound to a Telegram profile "
                "and will use that identity going forward."
            ),
            operator_hint=(
                "Verify that the previous profile ID and the linked "
                "Telegram ID match the intended merge target."
            ),
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
        logger.warning("Rate-limit fallback disabled for key '{}': {}", key, exc)
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


def _resolve_trusted_telegram_id_for_auto_link(current_user: UserDto) -> int | None:
    return current_user.telegram_id if current_user.telegram_id > 0 else None


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


__all__ = [
    "TelegramAuthData",
    "WEB_AUTH_MESSAGES",
    "_apply_referral_for_new_user",
    "_build_user_i18n_kwargs",
    "_enforce_rate_limit",
    "_extract_referral_code_from_telegram_request",
    "_extract_telegram_launch_context",
    "_has_valid_cookie_session",
    "_notify_web_account_linked",
    "_notify_web_user_registered",
    "_parse_telegram_auth_request",
    "_request_ip",
    "_resolve_trusted_telegram_id_for_auto_link",
    "_resolve_web_auth_message",
    "_track_web_analytics_event",
    "verify_telegram_hash",
    "verify_telegram_webapp_init_data",
]
