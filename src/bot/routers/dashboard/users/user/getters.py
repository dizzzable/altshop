from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT
from src.core.enums import PartnerAccrualStrategy, PartnerRewardType, UserRole
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    i18n_format_bytes_to_unit,
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import UserDto
from src.services.partner import PartnerService
from src.services.plan import PlanService
from src.services.referral import ReferralService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService
from src.services.web_account import WebAccountService

from .subscription_selection import get_subscription_index, resolve_selected_subscription

DEVICE_TYPE_EMOJIS = {
    "ANDROID": "📱",
    "IPHONE": "🍏",
    "WINDOWS": "🖥",
    "MAC": "💻",
    "OTHER": "🛩️",
}

DEVICE_TYPE_NAMES = {
    "ANDROID": "Android",
    "IPHONE": "iPhone",
    "WINDOWS": "Windows",
    "MAC": "Mac",
    "OTHER": "Other",
}


def _resolve_device_type_meta(device_type: Any) -> tuple[str, str]:
    if device_type is None:
        return DEVICE_TYPE_EMOJIS["OTHER"], DEVICE_TYPE_NAMES["OTHER"]

    device_type_key = getattr(device_type, "value", str(device_type)).upper()
    return (
        DEVICE_TYPE_EMOJIS.get(device_type_key, DEVICE_TYPE_EMOJIS["OTHER"]),
        DEVICE_TYPE_NAMES.get(device_type_key, DEVICE_TYPE_NAMES["OTHER"]),
    )


def _format_subscription_title(plan_name: str, device_type: Any) -> str:
    emoji, device_name = _resolve_device_type_meta(device_type)
    return f"{emoji} {device_name} - {plan_name}"


def _resolve_identity_kind(
    target_user: UserDto,
    *,
    web_login: str | None,
    linked_telegram_id: int | None,
) -> str:
    if linked_telegram_id is not None and web_login:
        return "TELEGRAM_LINKED"
    if linked_telegram_id is not None:
        return "TELEGRAM_ONLY"
    if target_user.telegram_id < 0 or web_login:
        return "WEB_ONLY"
    return "TELEGRAM_ONLY"


@inject
async def user_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    await settings_service.get_referral_settings()
    dialog_manager.dialog_data.pop("payload", None)
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    target_telegram_id = start_data["target_telegram_id"]
    dialog_manager.dialog_data["target_telegram_id"] = target_telegram_id
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    web_account = await web_account_service.get_by_user_telegram_id(target_telegram_id)
    linked_telegram_id = (
        target_user.telegram_id
        if target_user.telegram_id > 0
        else (
            web_account.user_telegram_id
            if web_account and web_account.user_telegram_id > 0
            else None
        )
    )
    web_login = web_account.username if web_account else None
    public_username = target_user.username or None

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    current_subscription_id = (
        target_user.current_subscription.id if target_user.current_subscription else None
    )
    visible_subscriptions, selected_subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        current_subscription_id,
    )
    subscription = target_user.current_subscription or selected_subscription
    subscriptions_count = len(visible_subscriptions)

    # Проверяем партнерский статус
    partner = await partner_service.get_partner_by_user(target_telegram_id)
    is_partner = partner is not None and partner.is_active

    data: dict[str, Any] = {
        "user_id": str(target_user.telegram_id),
        "username": target_user.username or False,
        "public_username": public_username or False,
        "has_public_username": bool(public_username),
        "web_login": web_login or False,
        "has_web_login": bool(web_login),
        "linked_telegram_id": str(linked_telegram_id) if linked_telegram_id is not None else False,
        "has_linked_telegram_id": linked_telegram_id is not None,
        "identity_kind": _resolve_identity_kind(
            target_user,
            web_login=web_login,
            linked_telegram_id=linked_telegram_id,
        ),
        "user_name": target_user.name,
        "role": target_user.role,
        "language": target_user.language,
        "is_dev": user.role == UserRole.DEV or user.telegram_id in config.bot.dev_id,
        "show_points": True,
        "points": target_user.points,
        "personal_discount": target_user.personal_discount,
        "purchase_discount": target_user.purchase_discount,
        "is_blocked": target_user.is_blocked,
        "is_not_self": target_user.telegram_id != user.telegram_id,
        "can_edit": user.role > target_user.role or user.telegram_id in config.bot.dev_id,
        "status": None,
        "is_trial": False,
        "has_subscription": bool(visible_subscriptions),
        "subscriptions_count": subscriptions_count,
        "has_multiple_subscriptions": subscriptions_count > 1,
        # Партнерская программа
        "is_partner": is_partner,
        "partner_balance": partner.balance_rub if partner else 0,
    }

    if subscription:
        data.update(
            {
                "status": subscription.status,
                "is_trial": subscription.is_trial,
                "traffic_limit": i18n_format_traffic_limit(subscription.traffic_limit),
                "device_limit": i18n_format_device_limit(subscription.device_limit),
                "expire_time": i18n_format_expire_time(subscription.expire_at),
            }
        )

    return data


@inject
async def subscriptions_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    current_subscription_id = (
        target_user.current_subscription.id if target_user.current_subscription else None
    )
    visible_subscriptions, _ = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        current_subscription_id,
    )

    formatted_subscriptions = []
    for subscription in visible_subscriptions:
        expire_parts = i18n_format_expire_time(subscription.expire_at)
        expire_time_str = " ".join(i18n.get(key, **kw) for key, kw in expire_parts)
        plan_name = subscription.plan.name if subscription.plan else "—"

        formatted_subscriptions.append(
            {
                "id": subscription.id,
                "status": subscription.status.value,
                "device_name": _format_subscription_title(plan_name, subscription.device_type),
                "expire_time": expire_time_str,
                "is_current": current_subscription_id == subscription.id,
            }
        )

    return {
        "count": len(formatted_subscriptions),
        "subscriptions": formatted_subscriptions,
        "has_multiple_subscriptions": len(formatted_subscriptions) > 1,
    }


@inject
async def subscription_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    current_subscription_id = (
        target_user.current_subscription.id if target_user.current_subscription else None
    )
    visible_subscriptions, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        current_subscription_id,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    remna_user = await remnawave_service.get_user(subscription.user_remna_id)

    if not remna_user:
        raise ValueError(f"User Remnawave '{target_telegram_id}' not found")

    squads = (
        ", ".join(squad.name for squad in remna_user.active_internal_squads)
        if remna_user.active_internal_squads
        else False
    )
    last_connected_node = getattr(remna_user, "last_connected_node", None)
    last_connected_node_uuid = getattr(remna_user, "last_connected_node_uuid", None)
    last_connected_at = (
        last_connected_node.connected_at.strftime(DATETIME_FORMAT)
        if last_connected_node and getattr(last_connected_node, "connected_at", None)
        else False
    )
    node_name = getattr(last_connected_node, "node_name", None) or (
        str(last_connected_node_uuid) if last_connected_node_uuid else False
    )

    return {
        "subscriptions_count": len(visible_subscriptions),
        "subscription_index": get_subscription_index(subscription.id, visible_subscriptions),
        "is_current_subscription": current_subscription_id == subscription.id,
        "is_trial": subscription.is_trial,
        "is_active": subscription.is_active,
        "has_devices_limit": subscription.has_devices_limit,
        "has_traffic_limit": subscription.has_traffic_limit,
        "url": remna_user.subscription_url,
        #
        "subscription_id": str(subscription.user_remna_id),
        "subscription_status": subscription.status,
        "traffic_used": i18n_format_bytes_to_unit(
            remna_user.used_traffic_bytes,
            min_unit=ByteUnitKey.MEGABYTE,
        ),
        "traffic_limit": (
            i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes)
            if remna_user.traffic_limit_bytes and remna_user.traffic_limit_bytes > 0
            else i18n_format_traffic_limit(-1)
        ),
        "device_limit": i18n_format_device_limit(subscription.device_limit),
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        #
        "squads": squads,
        "first_connected_at": (
            remna_user.first_connected.strftime(DATETIME_FORMAT)
            if remna_user.first_connected
            else False
        ),
        "last_connected_at": last_connected_at,
        "node_name": node_name,
        #
        "plan_name": subscription.plan.name,
        "plan_type": subscription.plan.type,
        "plan_traffic_limit": i18n_format_traffic_limit(subscription.plan.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(subscription.plan.device_limit),
        "plan_duration": i18n_format_days(subscription.plan.duration),
    }


@inject
async def devices_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    visible_subscriptions, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    devices = await remnawave_service.get_devices_by_subscription_uuid(subscription.user_remna_id)

    if not devices:
        raise ValueError(f"Devices not found for user '{target_telegram_id}'")

    formatted_devices = [
        {
            "hwid": device.hwid,
            "platform": device.platform,
            "device_model": device.device_model,
            "user_agent": device.user_agent,
        }
        for device in devices
    ]

    return {
        "current_count": len(devices),
        "max_count": i18n_format_device_limit(subscription.device_limit),
        "devices": formatted_devices,
        "subscriptions_count": len(visible_subscriptions),
    }


async def discount_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"percentages": [0, 5, 10, 25, 40, 50, 70, 80, 100]}


async def purchase_discount_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"percentages": [0, 5, 10, 25, 40, 50, 70, 80, 100]}


@inject
async def points_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    formatted_points = [
        {
            "operation": "+" if value > 0 else "",
            "points": value,
        }
        for value in [5, -5, 25, -25, 50, -50, 100, -100]
    ]

    return {
        "current_points": target_user.points,
        "points": formatted_points,
    }


async def traffic_limit_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    formatted_traffic = [
        {
            "traffic_limit": i18n_format_traffic_limit(value),
            "traffic": value,
        }
        for value in [100, 200, 300, 500, 1024, 2048, -1]
    ]

    return {"traffic_count": formatted_traffic}


async def device_limit_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"devices_count": [1, 2, 3, 4, 5, 10, -1]}


@inject
async def squads_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    internal_response = await remnawave_service.get_internal_squads()
    internal_dict = {s.uuid: s.name for s in internal_response.internal_squads}
    internal_squads_names = ", ".join(
        internal_dict.get(squad, str(squad)) for squad in subscription.internal_squads
    )

    external_squads = await remnawave_service.get_external_squads_safe()
    external_dict = {s["uuid"]: s["name"] for s in external_squads}
    external_squad_name = (
        external_dict.get(subscription.external_squad) if subscription.external_squad else False
    )

    return {
        "internal_squads": internal_squads_names or False,
        "external_squad": external_squad_name or False,
    }


@inject
async def internal_squads_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    response = await remnawave_service.get_internal_squads()
    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": True if squad.uuid in subscription.internal_squads else False,
        }
        for squad in response.internal_squads
    ]

    return {"squads": squads}


@inject
async def external_squads_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    external_squads = await remnawave_service.get_external_squads_safe()
    existing_squad_uuids = {squad["uuid"] for squad in external_squads}

    if subscription.external_squad and subscription.external_squad not in existing_squad_uuids:
        subscription.external_squad = None

    squads = [
        {
            "uuid": squad["uuid"],
            "name": squad["name"],
            "selected": True if squad["uuid"] == subscription.external_squad else False,
        }
        for squad in external_squads
    ]

    return {"squads": squads}


@inject
async def expire_time_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    formatted_durations = []
    for value in [1, -1, 3, -3, 7, -7, 14, -14, 30, -30]:
        key, kw = i18n_format_days(value)
        key2, kw2 = i18n_format_days(-value)
        formatted_durations.append(
            {
                "operation": "+" if value > 0 else "-",
                "duration": i18n.get(key, **kw) if value > 0 else i18n.get(key2, **kw2),
                "days": value,
            }
        )

    return {
        "expire_time": i18n_format_expire_time(subscription.expire_at),
        "durations": formatted_durations,
    }


@inject
async def transactions_getter(
    dialog_manager: DialogManager,
    transaction_service: FromDishka[TransactionService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    transactions = await transaction_service.get_by_user(target_telegram_id)

    if not transactions:
        raise ValueError(f"Transactions not found for user '{target_telegram_id}'")

    formatted_transactions = [
        {
            "payment_id": transaction.payment_id,
            "status": transaction.status,
            "created_at": transaction.created_at.strftime(DATETIME_FORMAT),
        }
        for transaction in transactions
    ]

    return {"transactions": list(reversed(formatted_transactions))}


@inject
async def transaction_getter(
    dialog_manager: DialogManager,
    transaction_service: FromDishka[TransactionService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    selected_transaction = dialog_manager.dialog_data["selected_transaction"]
    transaction = await transaction_service.get(selected_transaction)

    if not transaction:
        raise ValueError(
            f"Transaction '{selected_transaction}' not found for user '{target_telegram_id}'"
        )

    return {
        "is_test": transaction.is_test,
        "payment_id": str(transaction.payment_id),
        "purchase_type": transaction.purchase_type,
        "transaction_status": transaction.status,
        "gateway_type": transaction.gateway_type,
        "final_amount": transaction.pricing.final_amount,
        "currency": transaction.currency.symbol,
        "discount_percent": transaction.pricing.discount_percent,
        "original_amount": transaction.pricing.original_amount,
        "created_at": transaction.created_at.strftime(DATETIME_FORMAT),
        "plan_name": transaction.plan.name,
        "plan_type": transaction.plan.type,
        "plan_traffic_limit": i18n_format_traffic_limit(transaction.plan.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(transaction.plan.device_limit),
        "plan_duration": i18n_format_days(transaction.plan.duration),
    }


@inject
async def referrals_getter(
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    referrals, total = await referral_service.get_referrals_page_by_referrer(
        target_telegram_id,
        page=1,
        limit=50,
    )

    rows: list[dict[str, Any]] = []
    for referral in referrals:
        referred = referral.referred
        source = getattr(referral.invite_source, "value", str(referral.invite_source))
        qualified_channel = (
            getattr(referral.qualified_purchase_channel, "value", "UNKNOWN")
            if referral.qualified_at
            else "—"
        )
        invited_at = referral.created_at.strftime("%d.%m.%Y %H:%M") if referral.created_at else "—"
        rows.append(
            {
                "id": referred.telegram_id,
                "display": (
                    f"{referred.telegram_id} ({referred.name}) | src:{source} "
                    f"| buy:{qualified_channel} | {invited_at}"
                ),
            }
        )

    return {
        "has_referrals": bool(rows),
        "referrals": rows,
        "count": total,
    }


@inject
async def referrer_assignment_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    referral = await referral_service.get_referral_by_referred(target_telegram_id)
    referrer = referral.referrer if referral else None

    return {
        "target_user_name": target_user.name or str(target_user.telegram_id),
        "target_user_id": target_user.telegram_id,
        "has_referrer": referrer is not None,
        "referrer_user_id": referrer.telegram_id if referrer else 0,
        "referrer_user_name": referrer.name if referrer else "",
        "has_referrer_username": bool(referrer and referrer.username),
        "referrer_username": referrer.username if referrer and referrer.username else "",
    }


@inject
async def give_access_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await plan_service.get_allowed_plans()

    if not plans:
        raise ValueError("Allowed plans not found")

    formatted_plans = [
        {
            "plan_name": plan.name,
            "plan_id": plan.id,
            "selected": True if target_telegram_id in plan.allowed_user_ids else False,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def give_subscription_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await plan_service.get_assignable_active_plans()

    if not plans:
        raise ValueError("Available plans not found")

    formatted_plans = [
        {
            "plan_name": plan.name,
            "plan_id": plan.id,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def subscription_duration_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    selected_plan_id = dialog_manager.dialog_data["selected_plan_id"]
    plan = await plan_service.get(selected_plan_id)

    if not plan:
        raise ValueError(f"Plan '{selected_plan_id}' not found")

    durations = [duration.model_dump() for duration in plan.durations]
    return {"durations": durations}


@inject
async def assign_plan_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    current_subscription_id = (
        target_user.current_subscription.id if target_user.current_subscription else None
    )
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        current_subscription_id,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    plans = [
        plan for plan in await plan_service.get_all() if plan.is_active and plan.id is not None
    ]
    formatted_plans = [
        {
            "plan_name": plan.name,
            "plan_id": plan.id,
            "selected": plan.id == subscription.plan.id,
        }
        for plan in plans
    ]

    return {
        "plans": formatted_plans,
        "current_plan_name": subscription.plan.name if subscription.plan else "—",
    }


@inject
async def role_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    roles = [role for role in UserRole if role != target_user.role]
    return {"roles": roles}


@inject
async def partner_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для управления партнеркой пользователя."""
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    partner = await partner_service.get_partner_by_user(target_telegram_id)
    settings = await settings_service.get()
    partner_settings = settings.partner

    if partner and partner.id:
        statistics = await partner_service.get_partner_statistics(partner)
        await partner_service.get_partner_referrals(partner.id)

        return {
            "is_partner": True,
            "is_active": partner.is_active,
            "balance": partner.balance_rub,
            "total_earned": partner.total_earned_rub,
            "total_withdrawn_rubles": partner.total_withdrawn_rub,
            "referrals_count": partner.referrals_count,
            # Переменные для шаблона msg-user-partner
            "level1_count": partner.referrals_count,
            "level2_count": partner.level2_referrals_count,
            "level3_count": partner.level3_referrals_count,
            "total_referrals": partner.total_referrals,
            "level1_earned": statistics.get("level1_earnings", 0) / 100,
            "level2_earned": statistics.get("level2_earnings", 0) / 100,
            "level3_earned": statistics.get("level3_earnings", 0) / 100,
            "level_1_percent": partner_settings.level1_percent,
            "level_2_percent": partner_settings.level2_percent,
            "level_3_percent": partner_settings.level3_percent,
            "created_at": partner.created_at.strftime("%d.%m.%Y %H:%M")
            if partner.created_at
            else "",
        }
    else:
        return {
            "is_partner": False,
            "is_active": False,
            "balance": 0,
            "total_earned": 0,
            "total_withdrawn_rubles": 0,
            "referrals_count": 0,
            "level1_count": 0,
            "level2_count": 0,
            "level3_count": 0,
            "total_referrals": 0,
            "level1_earned": 0,
            "level2_earned": 0,
            "level3_earned": 0,
            "level_1_percent": partner_settings.level1_percent,
            "level_2_percent": partner_settings.level2_percent,
            "level_3_percent": partner_settings.level3_percent,
            "created_at": "",
        }


@inject
async def partner_source_assignment_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    source_user = await partner_service.get_partner_attribution_source(target_telegram_id)

    return {
        "target_user_name": target_user.name or str(target_user.telegram_id),
        "target_user_id": target_user.telegram_id,
        "has_partner_source": source_user is not None,
        "partner_source_user_id": source_user.telegram_id if source_user else 0,
        "partner_source_user_name": source_user.name if source_user else "",
        "has_partner_source_username": bool(source_user and source_user.username),
        "partner_source_username": source_user.username
        if source_user and source_user.username
        else "",
    }


@inject
async def partner_balance_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для управления балансом партнера."""
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    # Форматируем варианты изменения баланса (в рублях)
    formatted_amounts = [
        {
            "operation": "+" if value > 0 else "",
            "amount": value,
        }
        for value in [100, -100, 500, -500, 1000, -1000, 5000, -5000]
    ]

    return {
        "current_balance": partner.balance_rub,
        "total_earned": partner.total_earned_rub,
        "total_withdrawn": partner.total_withdrawn_rub,
        "amounts": formatted_amounts,
    }


@inject
async def partner_settings_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для индивидуальных настроек партнера."""
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    # Получаем глобальные настройки для отображения
    settings = await settings_service.get()
    partner_settings = settings.partner

    # Индивидуальные настройки
    ind = partner.individual_settings

    # Определяем текущие значения
    if ind.use_global_settings:
        current_l1_percent = partner_settings.level1_percent
        current_l2_percent = partner_settings.level2_percent
        current_l3_percent = partner_settings.level3_percent
        current_strategy = "global"
        current_reward_type = "global"
    else:
        current_l1_percent = (
            ind.level1_percent
            if ind.level1_percent is not None
            else partner_settings.level1_percent
        )
        current_l2_percent = (
            ind.level2_percent
            if ind.level2_percent is not None
            else partner_settings.level2_percent
        )
        current_l3_percent = (
            ind.level3_percent
            if ind.level3_percent is not None
            else partner_settings.level3_percent
        )
        current_strategy = ind.accrual_strategy.value
        current_reward_type = ind.reward_type.value

    return {
        "use_global_settings": ind.use_global_settings,
        "use_global": ind.use_global_settings,  # для FTL шаблона
        "accrual_strategy": current_strategy,
        "reward_type": current_reward_type,
        # Текущие проценты
        "level1_percent": current_l1_percent,
        "level2_percent": current_l2_percent,
        "level3_percent": current_l3_percent,
        # Индивидуальные значения (None если используются глобальные)
        "ind_level1_percent": ind.level1_percent,
        "ind_level2_percent": ind.level2_percent,
        "ind_level3_percent": ind.level3_percent,
        # Фиксированные суммы
        "level1_fixed": ind.level1_fixed_amount / 100 if ind.level1_fixed_amount else 0,
        "level2_fixed": ind.level2_fixed_amount / 100 if ind.level2_fixed_amount else 0,
        "level3_fixed": ind.level3_fixed_amount / 100 if ind.level3_fixed_amount else 0,
        # Глобальные проценты для справки
        "global_level1_percent": partner_settings.level1_percent,
        "global_level2_percent": partner_settings.level2_percent,
        "global_level3_percent": partner_settings.level3_percent,
        # Флаги для UI
        "is_first_payment_only": not ind.use_global_settings
        and ind.accrual_strategy == PartnerAccrualStrategy.ON_FIRST_PAYMENT,
        "is_fixed_amount": not ind.use_global_settings
        and ind.reward_type == PartnerRewardType.FIXED_AMOUNT,
    }


async def partner_accrual_strategy_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для выбора стратегии начисления."""
    strategies = [
        {
            "value": PartnerAccrualStrategy.ON_EACH_PAYMENT.value,
            "name": "С каждой оплаты реферала",
        },
        {
            "value": PartnerAccrualStrategy.ON_FIRST_PAYMENT.value,
            "name": "Только при первой оплате реферала",
        },
    ]

    return {"strategies": strategies}


async def partner_reward_type_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для выбора типа вознаграждения."""
    reward_types = [
        {
            "value": PartnerRewardType.PERCENT.value,
            "name": "Процент от суммы оплаты",
        },
        {
            "value": PartnerRewardType.FIXED_AMOUNT.value,
            "name": "Фиксированная сумма",
        },
    ]

    return {"reward_types": reward_types}


@inject
async def partner_percent_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настройки индивидуальных процентов."""
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    settings = await settings_service.get()
    partner_settings = settings.partner

    ind = partner.individual_settings

    # Варианты процентов
    percentages = [{"value": p, "label": f"{p}%"} for p in [1, 2, 3, 5, 7, 10, 15, 20, 25, 30]]

    return {
        "percentages": percentages,
        "current_level1": ind.level1_percent
        if ind.level1_percent is not None
        else partner_settings.level1_percent,
        "current_level2": ind.level2_percent
        if ind.level2_percent is not None
        else partner_settings.level2_percent,
        "current_level3": ind.level3_percent
        if ind.level3_percent is not None
        else partner_settings.level3_percent,
        "global_level1": partner_settings.level1_percent,
        "global_level2": partner_settings.level2_percent,
        "global_level3": partner_settings.level3_percent,
    }


@inject
async def partner_fixed_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настройки фиксированных сумм."""
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    ind = partner.individual_settings

    # Варианты фиксированных сумм (в рублях)
    amounts = [{"value": a, "label": f"{a} ₽"} for a in [10, 25, 50, 100, 150, 200, 300, 500]]

    return {
        "amounts": amounts,
        "current_level1": ind.level1_fixed_amount / 100 if ind.level1_fixed_amount else 0,
        "current_level2": ind.level2_fixed_amount / 100 if ind.level2_fixed_amount else 0,
        "current_level3": ind.level3_fixed_amount / 100 if ind.level3_fixed_amount else 0,
    }


@inject
async def max_subscriptions_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настройки индивидуального лимита подписок пользователя."""
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    # Получаем глобальные настройки
    settings = await settings_service.get()
    multi_sub = settings.multi_subscription

    # Определяем текущее значение
    if target_user.max_subscriptions is not None:
        current_max = target_user.max_subscriptions
        use_global = False
    else:
        current_max = multi_sub.default_max_subscriptions
        use_global = True

    # Варианты лимитов
    limits = [
        {"value": 1, "label": "1"},
        {"value": 2, "label": "2"},
        {"value": 3, "label": "3"},
        {"value": 5, "label": "5"},
        {"value": 10, "label": "10"},
        {"value": -1, "label": "∞"},
    ]

    return {
        "use_global": use_global,
        "current_max": current_max,
        "global_max": multi_sub.default_max_subscriptions,
        "multi_subscription_enabled": multi_sub.enabled,
        "limits": limits,
        "is_unlimited": current_max == -1,
    }


@inject
async def referral_invite_settings_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    global_settings = await settings_service.get_referral_settings()
    effective = await referral_service.get_effective_invite_limits(target_user)
    individual = target_user.referral_invite_settings

    def _display(value: int | None) -> str:
        return str(value) if value is not None else i18n.get("msg-referral-invite-unset")

    return {
        "use_global_settings": individual.use_global_settings,
        "use_global": individual.use_global_settings,
        "ttl_enabled": individual.link_ttl_enabled,
        "slots_enabled": individual.slots_enabled,
        "ttl_value": _display(individual.link_ttl_seconds),
        "initial_slots": _display(individual.initial_slots),
        "refill_threshold": _display(individual.refill_threshold_qualified),
        "refill_amount": _display(individual.refill_amount),
        "effective_ttl_enabled": effective.link_ttl_enabled,
        "effective_slots_enabled": effective.slots_enabled,
        "effective_ttl_status": i18n.get(
            "msg-referral-invite-enabled-status",
            enabled=effective.link_ttl_enabled,
        ),
        "effective_slots_status": i18n.get(
            "msg-referral-invite-enabled-status",
            enabled=effective.slots_enabled,
        ),
        "effective_ttl_value": _display(effective.link_ttl_seconds),
        "effective_initial_slots": _display(effective.initial_slots),
        "effective_refill_threshold": _display(effective.refill_threshold_qualified),
        "effective_refill_amount": _display(effective.refill_amount),
        "global_ttl_enabled": global_settings.invite_limits.link_ttl_enabled,
        "global_slots_enabled": global_settings.invite_limits.slots_enabled,
    }
