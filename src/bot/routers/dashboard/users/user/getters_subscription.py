from __future__ import annotations

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from remnawave import RemnawaveSDK
from remnawave.models import GetAllInternalSquadsResponseDto

from src.core.constants import DATETIME_FORMAT
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    i18n_format_bytes_to_unit,
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .getters_identity import _resolve_subscription_owner
from .subscription_selection import (
    get_subscription_index,
    get_visible_subscriptions,
    resolve_selected_subscription,
)

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


def _resolve_panel_profile_name(remna_user: Any) -> str | bool:
    username = getattr(remna_user, "username", None)
    if not username:
        return False
    return str(username)


async def _load_owner_subscription_context(
    *,
    dialog_manager: DialogManager,
    target_user: UserDto,
    user_service: UserService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> tuple[
    UserDto,
    list[SubscriptionDto],
    list[SubscriptionDto],
    int | None,
    dict[Any, Any] | None,
]:
    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    current_subscription_id = (
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None
    )
    visible_subscriptions = get_visible_subscriptions(all_subscriptions)
    remna_users_by_uuid: dict[Any, Any] | None = None
    if hasattr(remnawave_service, "get_users_map_by_telegram_id"):
        try:
            remna_users_by_uuid = await remnawave_service.get_users_map_by_telegram_id(
                subscription_owner.telegram_id
            )
        except Exception:
            remna_users_by_uuid = None

    return (
        subscription_owner,
        all_subscriptions,
        visible_subscriptions,
        current_subscription_id,
        remna_users_by_uuid,
    )


async def _resolve_selected_subscription_with_panel_user(
    *,
    dialog_manager: DialogManager,
    target_telegram_id: int,
    all_subscriptions: list[SubscriptionDto],
    current_subscription_id: int | None,
    remna_users_by_uuid: dict[Any, Any] | None,
    remnawave_service: RemnawaveService,
) -> tuple[list[SubscriptionDto], SubscriptionDto, Any]:
    visible_subscriptions, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        current_subscription_id,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    remna_user = (
        remna_users_by_uuid.get(subscription.user_remna_id)
        if remna_users_by_uuid is not None
        else None
    )
    if remna_user is None:
        remna_user = await remnawave_service.get_user(subscription.user_remna_id)

    if not remna_user:
        raise ValueError(f"User Remnawave '{target_telegram_id}' not found")

    return visible_subscriptions, subscription, remna_user


@inject
async def subscriptions_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_subscriptions_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        subscription_service=subscription_service,
        i18n=i18n,
    )


async def _build_subscriptions_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    subscription_service: SubscriptionService,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    current_subscription_id = (
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None
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
    return await _build_subscription_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )


async def _build_subscription_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    (
        subscription_owner,
        all_subscriptions,
        _owner_visible_subscriptions,
        current_subscription_id,
        remna_users_by_uuid,
    ) = await _load_owner_subscription_context(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )

    visible_subscriptions, subscription, remna_user = (
        await _resolve_selected_subscription_with_panel_user(
            dialog_manager=dialog_manager,
            target_telegram_id=target_telegram_id,
            all_subscriptions=all_subscriptions,
            current_subscription_id=current_subscription_id,
            remna_users_by_uuid=remna_users_by_uuid,
            remnawave_service=remnawave_service,
        )
    )

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
        "profile_name": _resolve_panel_profile_name(remna_user),
        "is_trial": subscription.is_trial,
        "is_active": subscription.is_active,
        "has_devices_limit": subscription.has_devices_limit,
        "has_traffic_limit": subscription.has_traffic_limit,
        "url": remna_user.subscription_url,
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
        "squads": squads,
        "first_connected_at": (
            remna_user.first_connected.strftime(DATETIME_FORMAT)
            if remna_user.first_connected
            else False
        ),
        "last_connected_at": last_connected_at,
        "node_name": node_name,
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

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    visible_subscriptions, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None,
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


@inject
async def squads_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    internal_response = await remnawave.internal_squads.get_internal_squads()
    if not isinstance(internal_response, GetAllInternalSquadsResponseDto):
        raise ValueError("Wrong response from Remnawave internal squads")

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
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    response = await remnawave.internal_squads.get_internal_squads()
    if not isinstance(response, GetAllInternalSquadsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    squads = [
        {
            "uuid": squad.uuid,
            "name": squad.name,
            "selected": squad.uuid in subscription.internal_squads,
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

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None,
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
            "selected": squad["uuid"] == subscription.external_squad,
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

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    _, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None,
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

    return {
        "plans": [
            {
                "plan_name": plan.name,
                "plan_id": plan.id,
            }
            for plan in plans
        ]
    }


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

    subscription_owner = await _resolve_subscription_owner(
        dialog_manager=dialog_manager,
        target_user=target_user,
        user_service=user_service,
    )
    all_subscriptions = await subscription_service.get_all_by_user(subscription_owner.telegram_id)
    current_subscription_id = (
        subscription_owner.current_subscription.id
        if subscription_owner.current_subscription
        else None
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
