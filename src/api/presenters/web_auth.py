from __future__ import annotations

from typing import Literal

from fastapi import Request
from pydantic import BaseModel

from src.core.config import AppConfig
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.settings import BrandingSettingsDto, SettingsDto
from src.services.user_profile import UserProfileSnapshot
from src.services.web_access_guard import WebAccessStatus


class SessionResponse(BaseModel):
    expires_in: int = 604800
    is_new_user: bool = False
    auth_source: str | None = None


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class AuthMeResponse(BaseModel):
    telegram_id: int
    username: str | None
    web_login: str | None = None
    name: str | None
    role: str
    points: int
    language: str
    default_currency: str
    personal_discount: int
    purchase_discount: int
    partner_balance_currency_override: str | None = None
    effective_partner_balance_currency: str = "RUB"
    is_blocked: bool
    is_bot_blocked: bool
    created_at: str
    updated_at: str
    email: str | None = None
    email_verified: bool = False
    telegram_linked: bool = False
    linked_telegram_id: int | None = None
    show_link_prompt: bool = False
    requires_password_change: bool = False
    effective_max_subscriptions: int = 1
    active_subscriptions_count: int = 0
    is_partner: bool = False
    is_partner_active: bool = False
    has_web_account: bool = False
    needs_web_credentials_bootstrap: bool = False


class TelegramLinkStatusResponse(BaseModel):
    telegram_linked: bool
    linked_telegram_id: int | None
    show_link_prompt: bool


class MessageResponse(BaseModel):
    message: str


class TelegramLinkRequestResponse(BaseModel):
    message: str
    delivered: bool
    expires_in_seconds: int


class TelegramLinkConfirmResponse(BaseModel):
    message: str
    linked_telegram_id: int


class WebBrandingResponse(BaseModel):
    project_name: str
    web_title: str
    default_locale: Literal["ru", "en"]
    supported_locales: list[Literal["ru", "en"]]
    support_url: str | None = None


class RegistrationAccessRequirementsResponse(BaseModel):
    access_mode: str
    rules_required: bool
    channel_required: bool
    rules_link: str | None = None
    channel_link: str | None = None
    requires_telegram_id: bool
    tg_id_helper_bot_link: str = "https://t.me/userinfobot"
    verification_bot_link: str | None = None


class AccessStatusResponse(BaseModel):
    access_mode: str
    rules_required: bool
    channel_required: bool
    requires_telegram_id: bool
    access_level: Literal["full", "read_only", "blocked"]
    channel_check_status: Literal["not_required", "verified", "required_unverified", "unavailable"]
    rules_accepted: bool
    telegram_linked: bool
    channel_verified: bool
    linked_telegram_id: int | None = None
    rules_link: str | None = None
    channel_link: str | None = None
    tg_id_helper_bot_link: str
    verification_bot_link: str | None = None
    unmet_requirements: list[str]
    can_use_product_features: bool


def _build_auth_me_response(profile: UserProfileSnapshot) -> AuthMeResponse:
    return AuthMeResponse(
        telegram_id=profile.telegram_id,
        username=profile.username,
        web_login=profile.web_login,
        name=profile.name,
        role=profile.role,
        points=profile.points,
        language=profile.language,
        default_currency=profile.default_currency,
        personal_discount=profile.personal_discount,
        purchase_discount=profile.purchase_discount,
        partner_balance_currency_override=profile.partner_balance_currency_override,
        effective_partner_balance_currency=profile.effective_partner_balance_currency,
        is_blocked=profile.is_blocked,
        is_bot_blocked=profile.is_bot_blocked,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        email=profile.email,
        email_verified=profile.email_verified,
        telegram_linked=profile.telegram_linked,
        linked_telegram_id=profile.linked_telegram_id,
        show_link_prompt=profile.show_link_prompt,
        requires_password_change=profile.requires_password_change,
        effective_max_subscriptions=profile.effective_max_subscriptions,
        active_subscriptions_count=profile.active_subscriptions_count,
        is_partner=profile.is_partner,
        is_partner_active=profile.is_partner_active,
        has_web_account=profile.has_web_account,
        needs_web_credentials_bootstrap=profile.needs_web_credentials_bootstrap,
    )


def _normalize_web_locale(raw_locale: object) -> Literal["ru", "en"] | None:
    raw_value = str(getattr(raw_locale, "value", raw_locale) or "").strip().lower()
    if raw_value.startswith("en"):
        return "en"
    if raw_value.startswith("ru"):
        return "ru"
    return None


def _resolve_supported_web_locales(config: AppConfig) -> list[Literal["ru", "en"]]:
    supported: list[Literal["ru", "en"]] = []
    for locale in config.locales:
        normalized = _normalize_web_locale(locale)
        if normalized and normalized not in supported:
            supported.append(normalized)

    if not supported:
        default_locale = _normalize_web_locale(config.default_locale)
        if default_locale:
            supported.append(default_locale)

    if not supported:
        supported.append("ru")

    return supported


def _resolve_support_url(config: AppConfig) -> str | None:
    bot_config = getattr(config, "bot", None)
    if bot_config is None:
        return None

    support_secret = getattr(bot_config, "support_username", None)
    if support_secret is None:
        return None

    raw_username = (
        support_secret.get_secret_value()
        if hasattr(support_secret, "get_secret_value")
        else str(support_secret)
    )
    support_username = str(raw_username or "").strip().lstrip("@")
    if not support_username:
        return None

    return f"https://t.me/{support_username}"


def _resolve_default_web_locale(config: AppConfig) -> Literal["ru", "en"]:
    supported = _resolve_supported_web_locales(config)
    default_locale = _normalize_web_locale(config.default_locale)
    if default_locale in supported:
        return default_locale
    return supported[0]


def _resolve_web_request_locale(
    request: Request,
    *,
    config: AppConfig,
    current_user: UserDto | None = None,
) -> Literal["ru", "en"]:
    supported_locales = _resolve_supported_web_locales(config)

    header_locale = _normalize_web_locale(request.headers.get("X-Web-Locale"))
    if header_locale and header_locale in supported_locales:
        return header_locale

    user_locale = _normalize_web_locale(current_user.language) if current_user else None
    if user_locale and user_locale in supported_locales:
        return user_locale

    return _resolve_default_web_locale(config)


def _build_access_status_response(access_status: WebAccessStatus) -> AccessStatusResponse:
    return AccessStatusResponse(
        access_mode=access_status.access_mode,
        rules_required=access_status.rules_required,
        channel_required=access_status.channel_required,
        requires_telegram_id=access_status.requires_telegram_id,
        access_level=access_status.access_level,
        channel_check_status=access_status.channel_check_status,
        rules_accepted=access_status.rules_accepted,
        telegram_linked=access_status.telegram_linked,
        channel_verified=access_status.channel_verified,
        linked_telegram_id=access_status.linked_telegram_id,
        rules_link=access_status.rules_link,
        channel_link=access_status.channel_link,
        tg_id_helper_bot_link=access_status.tg_id_helper_bot_link,
        verification_bot_link=access_status.verification_bot_link,
        unmet_requirements=access_status.unmet_requirements,
        can_use_product_features=access_status.can_use_product_features,
    )


def _build_registration_access_requirements_response(
    settings: SettingsDto,
    *,
    verification_bot_link: str | None,
) -> RegistrationAccessRequirementsResponse:
    rules_required = bool(settings.rules_required)
    channel_required = bool(settings.channel_required)
    requires_telegram_id = rules_required or channel_required

    return RegistrationAccessRequirementsResponse(
        access_mode=settings.access_mode.value,
        rules_required=rules_required,
        channel_required=channel_required,
        rules_link=settings.rules_link.get_secret_value() if rules_required else None,
        channel_link=settings.get_url_channel_link if channel_required else None,
        requires_telegram_id=requires_telegram_id,
        verification_bot_link=verification_bot_link,
    )


def _build_web_branding_response(
    branding: BrandingSettingsDto,
    *,
    config: AppConfig,
) -> WebBrandingResponse:
    return WebBrandingResponse(
        project_name=branding.project_name,
        web_title=branding.web_title,
        default_locale=_resolve_default_web_locale(config),
        supported_locales=_resolve_supported_web_locales(config),
        support_url=_resolve_support_url(config),
    )


__all__ = [
    "AccessStatusResponse",
    "AuthMeResponse",
    "LogoutResponse",
    "MessageResponse",
    "RegistrationAccessRequirementsResponse",
    "SessionResponse",
    "TelegramLinkConfirmResponse",
    "TelegramLinkRequestResponse",
    "TelegramLinkStatusResponse",
    "WebBrandingResponse",
    "_build_access_status_response",
    "_build_auth_me_response",
    "_build_registration_access_requirements_response",
    "_build_web_branding_response",
    "_normalize_web_locale",
    "_resolve_default_web_locale",
    "_resolve_support_url",
    "_resolve_supported_web_locales",
    "_resolve_web_request_locale",
]
