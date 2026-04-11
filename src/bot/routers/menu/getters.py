from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.enums import DeviceType, PointsExchangeType, PurchaseChannel, SubscriptionStatus
from src.core.utils.bot_menu import (
    BOT_MENU_URL_KIND_WEB_APP,
    resolve_bot_menu_launch_target,
    resolve_bot_menu_state,
)
from src.core.utils.formatters import (
    format_username_to_url,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.access import AccessService
from src.services.partner import PartnerService
from src.services.purchase_access import PurchaseAccessError
from src.services.referral import ReferralService
from src.services.referral_exchange import ReferralExchangeService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_trial import SubscriptionTrialService

DEVICE_TYPE_EMOJIS = {
    DeviceType.ANDROID: "📱",
    DeviceType.IPHONE: "🍏",
    DeviceType.WINDOWS: "🖥",
    DeviceType.MAC: "💻",
    DeviceType.OTHER: "🛩️",
}

DEVICE_TYPE_NAMES = {
    DeviceType.ANDROID: "Android",
    DeviceType.IPHONE: "iPhone",
    DeviceType.WINDOWS: "Windows",
    DeviceType.MAC: "Mac",
    DeviceType.OTHER: "Other",
}


def _resolve_device_visual(device_type: DeviceType | None) -> tuple[str, str]:
    if device_type is None:
        return DEVICE_TYPE_EMOJIS[DeviceType.OTHER], DEVICE_TYPE_NAMES[DeviceType.OTHER]

    return (
        DEVICE_TYPE_EMOJIS.get(device_type, DEVICE_TYPE_EMOJIS[DeviceType.OTHER]),
        DEVICE_TYPE_NAMES.get(device_type, DEVICE_TYPE_NAMES[DeviceType.OTHER]),
    )


def _exchange_option_map(options: Any) -> dict[PointsExchangeType, Any]:
    return {option.type: option for option in options.types}


def _gift_plan_name(options: Any, plan_id: int | None) -> str | None:
    if plan_id is None:
        return None
    for plan in options.gift_plans:
        if plan.plan_id == plan_id:
            return plan.plan_name
    return None


def _plan_name_or_fallback(plan_name: str | None, i18n: TranslatorRunner) -> str:
    return plan_name or i18n.get("msg-common-plan-fallback")


def _empty_value(i18n: TranslatorRunner) -> str:
    return i18n.get("msg-common-empty-value")


def _resolve_main_menu_view_state(
    invite_locked: bool,
    miniapp_only_active: bool = False,
) -> tuple[str, bool]:
    if invite_locked:
        return "msg-main-menu-invite-locked", False
    if miniapp_only_active:
        return "msg-main-menu-miniapp-only", True
    return "msg-main-menu-public", True


@inject
async def menu_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    subscription_trial_service: FromDishka[SubscriptionTrialService],
    settings_service: FromDishka[SettingsService],
    access_service: FromDishka[AccessService],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        trial_eligibility = await subscription_trial_service.get_eligibility(
            user,
            channel=PurchaseChannel.TELEGRAM,
        )
    except PurchaseAccessError:
        trial_eligibility = None
    settings = await settings_service.get()
    bot_menu_state = resolve_bot_menu_state(
        bot_menu=settings.bot_menu,
        branding=settings.branding,
        config=config,
    )
    mini_app_url = bot_menu_state.mini_app_url
    is_app_enabled = bool(mini_app_url)
    support_username = config.bot.support_username.get_secret_value()
    support_link = format_username_to_url(support_username, i18n.get("contact-support-help"))
    access_mode = settings.access_mode
    invite_locked = await access_service.is_invite_locked(user, mode=access_mode)
    menu_message_key, product_sections_enabled = _resolve_main_menu_view_state(
        invite_locked,
        bot_menu_state.miniapp_only_active,
    )
    miniapp_only_active = product_sections_enabled and bot_menu_state.miniapp_only_active
    invite_state = await referral_service.get_invite_state(user, create_if_missing=True)
    has_active_invite = (
        invite_state.invite is not None
        and invite_state.invite_block_reason is None
    )
    ref_link = (
        await referral_service.get_ref_link(invite_state.invite.token)
        if has_active_invite and invite_state.invite
        else ""
    )

    # Get subscriptions count
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s
        for s in all_subscriptions
        if s.status
        in (SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMITED, SubscriptionStatus.EXPIRED)
    ]
    subscriptions_count = len(active_subscriptions)

    # Count subscriptions with device_type for btn-menu-devices
    # Показываем кнопку "Мои устройства" если есть подписки с указанным типом устройства
    subscriptions_with_device_type = [
        s
        for s in all_subscriptions
        if s.status != SubscriptionStatus.DELETED and s.device_type is not None
    ]
    devices_count = len(subscriptions_with_device_type)

    # Показываем кнопку если есть хотя бы одна подписка (даже без device_type)
    has_any_subscription = (
        len([s for s in all_subscriptions if s.status != SubscriptionStatus.DELETED]) > 0
    )

    # Получаем настройки реферальной системы для проверки типа награды
    referral_settings = settings.referral
    is_points_reward = referral_settings.reward.is_points

    # Проверяем, является ли пользователь партнером
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    is_partner_active = partner is not None and partner.is_active
    is_referral_enabled = await settings_service.is_referral_enable()
    can_show_referral_controls = is_referral_enabled and not is_partner_active
    can_show_referral_invite = is_referral_enabled and not is_partner_active
    can_show_referral_inline_send = (not is_referral_enabled) and not is_partner_active

    base_data = {
        "user_id": str(user.telegram_id),
        "user_name": user.name,
        "is_privileged_user": user.is_privileged,
        "personal_discount": user.personal_discount,
        "support": support_link,
        "invite": i18n.get("referral-invite-message", url=ref_link) if ref_link else "",
        "has_subscription": user.has_subscription,
        "is_app": is_app_enabled,
        "is_referral_enable": is_referral_enabled,
        "can_show_referral_exchange": can_show_referral_controls,
        "can_show_referral_invite": can_show_referral_invite,
        "can_show_referral_send_inline": can_show_referral_inline_send and bool(ref_link),
        "is_points_reward": is_points_reward,
        "subscriptions_count": subscriptions_count,
        "count": devices_count,  # For btn-menu-devices
        "is_partner": is_partner_active,
        "is_partner_active": is_partner_active,
        "invite_locked": invite_locked,
        "menu_message_key": menu_message_key,
        "product_sections_enabled": product_sections_enabled,
        "miniapp_only_active": miniapp_only_active,
        "mini_app_button_text": bot_menu_state.primary_button_text,
        "menu_mini_app_url": mini_app_url or "",
        "menu_mini_app_is_web_app": bot_menu_state.mini_app_url_kind == BOT_MENU_URL_KIND_WEB_APP,
        "menu_mini_app_is_url": bot_menu_state.mini_app_url_kind != BOT_MENU_URL_KIND_WEB_APP,
        "custom_menu_buttons": [
            {
                "id": button.id,
                "label": button.label,
                "url": button.url,
                "kind": button.kind.value,
                "is_url": button.is_url,
                "is_web_app": button.is_web_app,
            }
            for button in bot_menu_state.custom_buttons
        ]
        if miniapp_only_active
        else [],
        "has_custom_menu_buttons": miniapp_only_active and bool(bot_menu_state.custom_buttons),
    }

    subscription = user.current_subscription

    if not subscription:
        base_data.update(
            {
                "status": None,
                "is_trial": False,
                "trial_available": bool(trial_eligibility and trial_eligibility.eligible),
                "has_device_limit": has_any_subscription,  # Показываем кнопку если есть подписки
                "connectable": False,
            }
        )
        return base_data

    base_data.update(
        {
            "status": subscription.status,
            "type": subscription.get_subscription_type,
            "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
            "device_limit": i18n_format_device_limit(subscription.device_limit),
            "expire_time": i18n_format_expire_time(subscription.expire_at),
            "is_trial": subscription.is_trial,
            "has_device_limit": has_any_subscription,  # Показываем кнопку если есть подписки
            "connectable": subscription.is_active,
            "url": mini_app_url or subscription.url,
        }
    )

    return base_data


@inject
async def connect_device_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Get connectable subscriptions with normalized device labels."""
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    connectable_subscriptions = [
        s
        for s in all_subscriptions
        if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMITED)
    ]

    formatted_subscriptions = []
    for sub in connectable_subscriptions:
        device_type = sub.device_type
        emoji, device_name = _resolve_device_visual(device_type)
        status_emoji = "🟢" if sub.status == SubscriptionStatus.ACTIVE else "🟡"
        plan_name = _plan_name_or_fallback(sub.plan.name if sub.plan else None, i18n)

        formatted_subscriptions.append(
            {
                "id": sub.id,
                "display_name": f"{status_emoji} {emoji} {device_name} - {plan_name}",
                "url": sub.url,
                "device_type": device_type.value if device_type else None,
                "plan_name": plan_name,
            }
        )

    return {
        "subscriptions": formatted_subscriptions,
        "subscriptions_empty": len(formatted_subscriptions) == 0,
    }


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Return purchased subscriptions as device entries with normalized labels."""
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [s for s in all_subscriptions if s.status != SubscriptionStatus.DELETED]

    formatted_devices = []
    for sub in active_subscriptions:
        device_type = sub.device_type
        emoji, device_name = _resolve_device_visual(device_type)

        formatted_devices.append(
            {
                "id": sub.id,
                "device_type": device_type.value if device_type else None,
                "device_name": f"{emoji} {device_name}",
                "plan_name": _plan_name_or_fallback(sub.plan.name if sub.plan else None, i18n),
                "subscription_url": sub.url,
                "status": sub.status.value,
                "is_active": sub.is_active,
            }
        )

    return {
        "devices": formatted_devices,
        "devices_empty": len(formatted_devices) == 0,
        "subscriptions_count": len(active_subscriptions),
    }


@inject
async def invite_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    referrals = await referral_service.get_referral_count(user.telegram_id)
    payments = await referral_service.get_reward_count(user.telegram_id)
    invite_state = await referral_service.get_invite_state(user, create_if_missing=True)
    has_active_invite = (
        invite_state.invite is not None
        and invite_state.invite_block_reason is None
    )
    ref_link = (
        await referral_service.get_ref_link(invite_state.invite.token)
        if has_active_invite and invite_state.invite
        else ""
    )
    support_username = config.bot.support_username.get_secret_value()
    support_link = format_username_to_url(
        support_username, i18n.get("contact-support-withdraw-points")
    )
    invite_status_key = {
        None: "msg-menu-invite-status-active",
        "EXPIRED": "msg-menu-invite-status-expired",
        "SLOTS_EXHAUSTED": "msg-menu-invite-status-exhausted",
    }.get(invite_state.invite_block_reason, "msg-menu-invite-status-missing")
    expires_at = (
        invite_state.invite_expires_at.strftime("%d.%m.%Y %H:%M")
        if invite_state.invite_expires_at
        else i18n.get("msg-menu-invite-status-never")
    )
    slots_value = (
        i18n.get(
            "msg-menu-invite-status-slots-unlimited",
        )
        if invite_state.total_capacity is None
        else i18n.get(
            "msg-menu-invite-status-slots",
            remaining=invite_state.remaining_slots or 0,
            total=invite_state.total_capacity or 0,
        )
    )
    progress_value = (
        i18n.get("msg-menu-invite-status-progress-disabled")
        if invite_state.refill_step_target is None
        else i18n.get(
            "msg-menu-invite-status-progress",
            current=invite_state.refill_step_progress or 0,
            target=invite_state.refill_step_target,
        )
    )
    invite_status_block = "\n".join(
        [
            i18n.get("msg-menu-invite-status-title"),
            i18n.get(invite_status_key),
            i18n.get("msg-menu-invite-status-expires-at", expires_at=expires_at),
            slots_value,
            progress_value,
        ]
    )

    return {
        "reward_type": settings.reward.type,
        "referrals": referrals,
        "payments": payments,
        "points": user.points,
        "is_points_reward": settings.reward.is_points,
        "has_points": True if user.points > 0 else False,
        "referral_link": ref_link,
        "invite": i18n.get("referral-invite-message", url=ref_link) if ref_link else "",
        "withdraw": support_link,
        "has_active_referral_link": has_active_invite,
        "can_regenerate_invite": invite_state.requires_regeneration
        and invite_state.invite_block_reason != "SLOTS_EXHAUSTED",
        "invite_status_block": invite_status_block,
    }


@inject
async def invite_referrals_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    referrals, total = await referral_service.get_referrals_page_by_referrer(
        user.telegram_id,
        page=1,
        limit=25,
    )

    rows: list[dict[str, Any]] = []
    for referral in referrals:
        referred = referral.referred
        display_name = referred.name or referred.username or str(referred.telegram_id)
        invited_at = (
            referral.created_at.strftime("%d.%m.%Y %H:%M")
            if referral.created_at
            else _empty_value(i18n)
        )
        source = getattr(referral.invite_source, "value", str(referral.invite_source))
        qualified = referral.qualified_at is not None
        purchase_channel = (
            getattr(referral.qualified_purchase_channel, "value", "UNKNOWN")
            if qualified
            else _empty_value(i18n)
        )
        status = i18n.get(
            "msg-menu-invite-referral-status-qualified"
            if qualified
            else "msg-menu-invite-referral-status-pending"
        )
        rows.append(
            {
                "id": referral.id,
                "display": i18n.get(
                    "msg-menu-invite-referral-row",
                    name=display_name,
                    source=source,
                    status=status,
                    purchase_channel=purchase_channel,
                    invited_at=invited_at,
                ),
            }
        )

    return {
        "has_referrals": bool(rows),
        "referral_rows": rows,
        "count": total,
        "referrals_total": total,
    }


@inject
async def invite_about_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    reward_config = settings.reward.config

    max_level = settings.level.value
    identical_reward = settings.reward.is_identical

    reward_levels: dict[str, str] = {}
    for lvl, val in reward_config.items():
        if lvl.value <= max_level:
            reward_levels[f"reward_level_{lvl.value}"] = i18n.get(
                "msg-invite-reward",
                value=val,
                reward_strategy_type=settings.reward.strategy,
                reward_type=settings.reward.type,
            )

    return {
        **reward_levels,
        "reward_type": settings.reward.type,
        "reward_strategy_type": settings.reward.strategy,
        "accrual_strategy": settings.accrual_strategy,
        "identical_reward": identical_reward,
        "max_level": max_level,
    }


@inject
async def connect_device_url_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для окна с URL выбранного устройства.
    """
    subscription_url = dialog_manager.dialog_data.get("selected_subscription_url", "")
    settings = await settings_service.get()
    mini_app_url, _source, mini_app_url_kind = resolve_bot_menu_launch_target(
        bot_menu=settings.bot_menu,
        config=config,
    )
    is_app_enabled = mini_app_url_kind == BOT_MENU_URL_KIND_WEB_APP
    plan_name = dialog_manager.dialog_data.get(
        "selected_subscription_plan_name",
        i18n.get("msg-common-plan-fallback"),
    )

    return {
        "url": mini_app_url or subscription_url,
        "plan_name": plan_name,
        "is_app": is_app_enabled,
        "connectable": True,
    }


@inject
async def exchange_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    subscription_service: FromDishka[SubscriptionService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get_referral_settings()
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    options_map = _exchange_option_map(options)

    subscription_days_option = options_map.get(PointsExchangeType.SUBSCRIPTION_DAYS)
    gift_subscription_option = options_map.get(PointsExchangeType.GIFT_SUBSCRIPTION)
    discount_option = options_map.get(PointsExchangeType.DISCOUNT)
    traffic_option = options_map.get(PointsExchangeType.TRAFFIC)

    referrals = await referral_service.get_referral_count(user.telegram_id)
    payments = await referral_service.get_reward_count(user.telegram_id)

    # Keep checks aligned with exchange service eligibility.
    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s
        for s in all_subscriptions
        if s.status
        in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]
    has_subscriptions = len(active_subscriptions) > 0
    enabled_types = [option for option in options.types if option.enabled]
    has_multiple_types = len(enabled_types) > 1

    points = options.points_balance
    days_available = subscription_days_option.computed_value if subscription_days_option else 0
    extra_days = points
    gift_plan_name = _gift_plan_name(
        options,
        gift_subscription_option.gift_plan_id if gift_subscription_option else None,
    )

    return {
        "points": points,
        "days_available": days_available,
        "extra_days": extra_days,
        "points_per_day": subscription_days_option.points_cost if subscription_days_option else 0,
        "exchange_enabled": options.exchange_enabled,
        "referrals": referrals,
        "payments": payments,
        "has_points": any(option.available for option in options.types),
        "has_subscriptions": has_subscriptions,
        "reward_type": settings.reward.type,
        "has_multiple_types": has_multiple_types,
        "enabled_types_count": len(enabled_types),
        "subscription_days_available": (
            subscription_days_option.available if subscription_days_option else False
        ),
        "gift_subscription_available": (
            gift_subscription_option.available if gift_subscription_option else False
        ),
        "discount_available": discount_option.available if discount_option else False,
        "traffic_available": traffic_option.available if traffic_option else False,
        "discount_percent": discount_option.computed_value if discount_option else 0,
        "traffic_gb": traffic_option.computed_value if traffic_option else 0,
        "gift_plan_name": gift_plan_name,
        "gift_duration_days": (
            gift_subscription_option.gift_duration_days if gift_subscription_option else 0
        ),
        "subscription_days_cost": (
            subscription_days_option.points_cost if subscription_days_option else 0
        ),
        "gift_subscription_cost": (
            gift_subscription_option.points_cost if gift_subscription_option else 0
        ),
        "discount_cost": discount_option.points_cost if discount_option else 0,
        "traffic_cost": traffic_option.points_cost if traffic_option else 0,
    }


@inject
async def exchange_select_type_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    exchange_types: list[dict[str, Any]] = []

    for option in options.types:
        if not option.enabled:
            continue

        if option.type == PointsExchangeType.SUBSCRIPTION_DAYS:
            description = i18n.get("exchange-type-days-value", days=option.computed_value)
        elif option.type == PointsExchangeType.GIFT_SUBSCRIPTION:
            description = i18n.get(
                "exchange-type-gift-value",
                plan_name=_gift_plan_name(options, option.gift_plan_id) or _empty_value(i18n),
                days=option.gift_duration_days or 0,
            )
        elif option.type == PointsExchangeType.DISCOUNT:
            description = i18n.get("exchange-type-discount-value", percent=option.computed_value)
        else:
            description = i18n.get("exchange-type-traffic-value", gb=option.computed_value)

        exchange_types.append(
            {
                "type": option.type,
                "available": option.available,
                "value": option.computed_value,
                "cost": option.points_cost,
                "description": description,
            }
        )

    return {
        "points": options.points_balance,
        "exchange_types": exchange_types,
        "has_available_types": any(t["available"] for t in exchange_types),
    }


@inject
async def exchange_gift_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    gift_option = _exchange_option_map(options).get(PointsExchangeType.GIFT_SUBSCRIPTION)

    return {
        "points": options.points_balance,
        "cost": gift_option.points_cost if gift_option else 0,
        "plan_name": _gift_plan_name(options, gift_option.gift_plan_id if gift_option else None)
        or _empty_value(i18n),
        "duration_days": gift_option.gift_duration_days if gift_option else 0,
        "can_exchange": gift_option.available if gift_option else False,
    }


@inject
async def exchange_gift_select_plan_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    gift_option = _exchange_option_map(options).get(PointsExchangeType.GIFT_SUBSCRIPTION)

    formatted_plans = [
        {
            "id": plan.plan_id,
            "name": plan.plan_name,
            "display_name": f"📦 {plan.plan_name}",
            "durations": i18n.get(
                "msg-common-duration-days-short",
                days=gift_option.gift_duration_days if gift_option else 0,
            ),
        }
        for plan in options.gift_plans
    ]

    return {
        "points": options.points_balance,
        "cost": gift_option.points_cost if gift_option else 0,
        "plans": formatted_plans,
        "has_plans": len(formatted_plans) > 0,
        "can_exchange": gift_option.available if gift_option else False,
    }


@inject
async def exchange_gift_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    gift_option = _exchange_option_map(options).get(PointsExchangeType.GIFT_SUBSCRIPTION)

    selected_plan_id = dialog_manager.dialog_data.get("gift_selected_plan_id")
    selected_duration = dialog_manager.dialog_data.get(
        "gift_selected_duration",
        gift_option.gift_duration_days if gift_option else 0,
    )
    plan_name = _gift_plan_name(options, selected_plan_id) or _gift_plan_name(
        options,
        gift_option.gift_plan_id if gift_option else None,
    )

    return {
        "points": options.points_balance,
        "cost": gift_option.points_cost if gift_option else 0,
        "plan_name": plan_name or _empty_value(i18n),
        "duration_days": selected_duration,
        "can_exchange": bool(
            gift_option and gift_option.available and selected_plan_id is not None
        ),
    }


@inject
async def exchange_gift_success_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Getter для успешного обмена на подарочную подписку - показывает промокод.
    """
    promocode = dialog_manager.dialog_data.get("gift_promocode", "")
    plan_name = dialog_manager.dialog_data.get("gift_plan_name", "")
    duration_days = dialog_manager.dialog_data.get("gift_duration_days", 0)

    return {
        "promocode": promocode,
        "plan_name": plan_name,
        "duration_days": duration_days,
    }


@inject
async def exchange_discount_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    discount_option = _exchange_option_map(options).get(PointsExchangeType.DISCOUNT)
    discount_percent = discount_option.computed_value if discount_option else 0
    points_to_spend = discount_percent * (discount_option.points_cost if discount_option else 0)

    return {
        "points": options.points_balance,
        "cost_per_percent": discount_option.points_cost if discount_option else 0,
        "discount_percent": discount_percent,
        "points_to_spend": points_to_spend,
        "max_discount": discount_option.max_discount_percent if discount_option else 0,
        "can_exchange": discount_option.available if discount_option else False,
    }


@inject
async def exchange_traffic_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    traffic_option = _exchange_option_map(options).get(PointsExchangeType.TRAFFIC)
    traffic_gb = traffic_option.computed_value if traffic_option else 0

    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s
        for s in all_subscriptions
        if s.status
        in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]

    formatted_subscriptions = []
    for sub in active_subscriptions:
        device_type = sub.device_type
        emoji, _ = _resolve_device_visual(device_type)

        formatted_subscriptions.append(
            {
                "id": sub.id,
                "display_name": (
                    f"{emoji} {_plan_name_or_fallback(sub.plan.name if sub.plan else None, i18n)}"
                ),
                "traffic_limit": sub.traffic_limit,
                "status": sub.status.value,
            }
        )

    return {
        "points": options.points_balance,
        "cost_per_gb": traffic_option.points_cost if traffic_option else 0,
        "traffic_gb": traffic_gb,
        "max_traffic": traffic_option.max_traffic_gb if traffic_option else 0,
        "subscriptions": formatted_subscriptions,
        "has_subscriptions": len(formatted_subscriptions) > 0,
        "can_exchange": traffic_option.available if traffic_option else False,
    }


@inject
async def exchange_traffic_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    traffic_option = _exchange_option_map(options).get(PointsExchangeType.TRAFFIC)

    if not traffic_option:
        return {"error": True}

    subscription_id = dialog_manager.dialog_data.get("traffic_subscription_id")

    if not subscription_id:
        return {"error": True}

    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        return {"error": True}

    traffic_gb = traffic_option.computed_value
    points_to_spend = traffic_gb * traffic_option.points_cost

    device_type = subscription.device_type
    emoji, _ = _resolve_device_visual(device_type)

    return {
        "points": options.points_balance,
        "points_to_spend": points_to_spend,
        "traffic_gb": traffic_gb,
        "subscription_name": (
            f"{emoji} "
            f"{_plan_name_or_fallback(subscription.plan.name if subscription.plan else None, i18n)}"
        ),
        "current_traffic_limit": subscription.traffic_limit,
    }


@inject
async def exchange_points_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    days_option = _exchange_option_map(options).get(PointsExchangeType.SUBSCRIPTION_DAYS)

    all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions = [
        s
        for s in all_subscriptions
        if s.status
        in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
        and not s.is_unlimited
    ]

    formatted_subscriptions = []
    for sub in active_subscriptions:
        expire_parts = i18n_format_expire_time(sub.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)

        device_type = sub.device_type
        emoji, _ = _resolve_device_visual(device_type)

        formatted_subscriptions.append(
            {
                "id": sub.id,
                "display_name": (
                    f"{emoji} {_plan_name_or_fallback(sub.plan.name if sub.plan else None, i18n)}"
                ),
                "expire_time": expire_time_str,
                "status": sub.status.value,
            }
        )

    return {
        "points": options.points_balance,
        "days_available": days_option.computed_value if days_option else 0,
        "points_per_day": days_option.points_cost if days_option else 0,
        "subscriptions": formatted_subscriptions,
        "has_subscriptions": len(formatted_subscriptions) > 0,
    }


@inject
async def exchange_points_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    subscription_service: FromDishka[SubscriptionService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
    **kwargs: Any,
) -> dict[str, Any]:
    options = await referral_exchange_service.get_options(user_telegram_id=user.telegram_id)
    days_option = _exchange_option_map(options).get(PointsExchangeType.SUBSCRIPTION_DAYS)
    points_per_day = days_option.points_cost if days_option else 0

    subscription_id = dialog_manager.dialog_data.get("exchange_subscription_id")

    if not subscription_id:
        return {
            "points": 0,
            "days_to_add": 0,
            "points_per_day": points_per_day,
            "subscription_name": _empty_value(i18n),
            "expire_time": _empty_value(i18n),
        }

    subscription = await subscription_service.get(subscription_id)

    if not subscription:
        return {
            "points": 0,
            "days_to_add": 0,
            "points_per_day": points_per_day,
            "subscription_name": _empty_value(i18n),
            "expire_time": _empty_value(i18n),
        }

    device_type = subscription.device_type
    emoji, _ = _resolve_device_visual(device_type)

    expire_parts = i18n_format_expire_time(subscription.expire_at)
    expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)

    days_to_add = days_option.computed_value if days_option else 0
    points_to_exchange = days_to_add * points_per_day

    return {
        "points": points_to_exchange,
        "days_to_add": days_to_add,
        "points_per_day": points_per_day,
        "subscription_name": (
            f"{emoji} "
            f"{_plan_name_or_fallback(subscription.plan.name if subscription.plan else None, i18n)}"
        ),
        "expire_time": expire_time_str,
    }
