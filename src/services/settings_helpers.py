from __future__ import annotations

from loguru import logger

from src.core.constants import MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import Currency
from src.infrastructure.database.models.dto import (
    BotMenuSettingsDto,
    BrandingSettingsDto,
    SettingsDto,
    UserDto,
)


def normalize_settings_for_update(settings: SettingsDto) -> SettingsDto:
    if settings.user_notifications.changed_data:
        settings.user_notifications = settings.user_notifications

    if settings.system_notifications.changed_data:
        settings.system_notifications = settings.system_notifications

    if settings.referral.changed_data or settings.referral.reward:
        settings.referral = settings.referral

    if settings.partner.changed_data:
        settings.partner = settings.partner

    if settings.multi_subscription.changed_data:
        settings.multi_subscription = settings.multi_subscription

    settings.branding = BrandingSettingsDto.model_validate(settings.branding.model_dump())
    if settings.branding.changed_data or settings.branding.verification:
        settings.branding = settings.branding

    settings.bot_menu = BotMenuSettingsDto.model_validate(settings.bot_menu.model_dump())
    return settings


def resolve_partner_balance_currency(default_currency: Currency, user: UserDto) -> Currency:
    resolved = user.partner_balance_currency_override or default_currency or Currency.RUB
    if resolved == Currency.XTR:
        return Currency.RUB
    return resolved


def normalize_and_clamp_max_subscriptions(
    raw_limit: int,
    *,
    source: str,
    hard_ceiling: int = MAX_SUBSCRIPTIONS_PER_USER,
) -> int:
    normalized = raw_limit
    if normalized < 1:
        logger.warning(
            f"Invalid max subscriptions value '{raw_limit}' from {source}. "
            "Falling back to 1."
        )
        normalized = 1

    effective_limit = min(normalized, hard_ceiling)
    if effective_limit != normalized:
        logger.warning(
            f"Max subscriptions from {source} is '{normalized}', "
            f"clamped to hard ceiling '{hard_ceiling}'"
        )

    return effective_limit


def resolve_effective_max_subscriptions(
    *,
    user: UserDto,
    multi_subscription_enabled: bool,
    default_max_subscriptions: int,
    hard_ceiling: int = MAX_SUBSCRIPTIONS_PER_USER,
) -> int:
    if user.max_subscriptions is not None:
        if user.max_subscriptions == -1:
            logger.warning(
                f"User '{user.telegram_id}' has unlimited individual subscriptions, "
                f"clamped to hard ceiling '{hard_ceiling}'"
            )
            return hard_ceiling

        return normalize_and_clamp_max_subscriptions(
            raw_limit=user.max_subscriptions,
            source=f"user:{user.telegram_id}",
            hard_ceiling=hard_ceiling,
        )

    if not multi_subscription_enabled:
        logger.debug(f"Multi-subscription disabled, user '{user.telegram_id}' limited to 1")
        return 1

    return normalize_and_clamp_max_subscriptions(
        raw_limit=default_max_subscriptions,
        source="settings.multi_subscription.default_max_subscriptions",
        hard_ceiling=hard_ceiling,
    )
