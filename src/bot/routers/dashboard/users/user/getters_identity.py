from __future__ import annotations

from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.config import AppConfig
from src.core.enums import SubscriptionStatus, UserRole
from src.core.utils.formatters import (
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.user import UserService
from src.services.web_account import WebAccountService

from .subscription_selection import resolve_selected_subscription


def _extract_numeric_panel_telegram_id(remna_user: Any) -> int | None:
    raw_telegram_id = getattr(remna_user, "telegram_id", None)
    if raw_telegram_id is None:
        return None

    normalized_telegram_id = str(raw_telegram_id).strip()
    if not normalized_telegram_id.lstrip("-").isdigit():
        return None

    return int(normalized_telegram_id)


def _resolve_panel_telegram_id_from_dialog(
    dialog_manager: DialogManager,
    target_user: UserDto,
) -> int:
    raw_value = (
        dialog_manager.dialog_data.get("effective_panel_telegram_id")
        or dialog_manager.dialog_data.get("panel_sync_override_telegram_id")
        or dialog_manager.dialog_data.get("panel_telegram_id")
    )
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, str) and raw_value.lstrip("-").isdigit():
        return int(raw_value)
    return target_user.telegram_id


async def _infer_panel_telegram_id_from_local_subscriptions(
    *,
    target_user: UserDto,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> int | None:
    all_subscriptions = await subscription_service.get_all_by_user(target_user.telegram_id)
    subscriptions = [
        subscription
        for subscription in all_subscriptions
        if subscription.status != SubscriptionStatus.DELETED and subscription.user_remna_id
    ]
    if not subscriptions:
        return None

    current_subscription_id = (
        target_user.current_subscription.id if target_user.current_subscription else None
    )
    subscriptions.sort(
        key=lambda subscription: (
            0 if subscription.id == current_subscription_id else 1,
            subscription.id or 0,
        )
    )

    first_subscription = subscriptions[0]
    inferred_ids: set[int] = set()
    try:
        first_remna_user = await remnawave_service.get_user(first_subscription.user_remna_id)
    except Exception:
        return None

    candidate_telegram_id = _extract_numeric_panel_telegram_id(first_remna_user)
    if candidate_telegram_id is None:
        return await _infer_panel_telegram_id_from_direct_probes(
            target_user=target_user,
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        )

    inferred_ids.add(candidate_telegram_id)
    if not hasattr(remnawave_service, "get_users_map_by_telegram_id"):
        return await _infer_panel_telegram_id_from_direct_probes(
            target_user=target_user,
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        )

    try:
        remna_users_by_uuid = await remnawave_service.get_users_map_by_telegram_id(
            candidate_telegram_id
        )
    except Exception:
        return await _infer_panel_telegram_id_from_direct_probes(
            target_user=target_user,
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        )

    return await _infer_panel_telegram_id_from_batched_map(
        target_user=target_user,
        subscriptions=subscriptions,
        remna_users_by_uuid=remna_users_by_uuid,
        inferred_ids=inferred_ids,
        remnawave_service=remnawave_service,
    )


async def _infer_panel_telegram_id_from_direct_probes(
    *,
    target_user: UserDto,
    subscriptions: list[SubscriptionDto],
    remnawave_service: RemnawaveService,
) -> int | None:
    inferred_ids: set[int] = set()
    for subscription in subscriptions:
        try:
            remna_user = await remnawave_service.get_user(subscription.user_remna_id)
        except Exception:
            return None

        inferred_telegram_id = _extract_numeric_panel_telegram_id(remna_user)
        if inferred_telegram_id is None:
            continue

        inferred_ids.add(inferred_telegram_id)
        if len(inferred_ids) > 1:
            return None

    return next(iter(inferred_ids), None)


async def _infer_panel_telegram_id_from_batched_map(
    *,
    target_user: UserDto,
    subscriptions: list[SubscriptionDto],
    remna_users_by_uuid: dict[Any, Any],
    inferred_ids: set[int],
    remnawave_service: RemnawaveService,
) -> int | None:
    for subscription in subscriptions:
        remna_user = remna_users_by_uuid.get(subscription.user_remna_id)
        if remna_user is None:
            return await _infer_panel_telegram_id_from_direct_probes(
                target_user=target_user,
                subscriptions=subscriptions,
                remnawave_service=remnawave_service,
            )

        inferred_telegram_id = _extract_numeric_panel_telegram_id(remna_user)
        if inferred_telegram_id is None:
            continue

        inferred_ids.add(inferred_telegram_id)
        if len(inferred_ids) > 1:
            return None

    return next(iter(inferred_ids), None)


async def _resolve_effective_panel_telegram_id(
    *,
    dialog_manager: DialogManager,
    target_user: UserDto,
    web_account_service: WebAccountService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> int:
    override_value = dialog_manager.dialog_data.get("panel_sync_override_telegram_id")
    if isinstance(override_value, int):
        return override_value
    if isinstance(override_value, str) and override_value.lstrip("-").isdigit():
        return int(override_value)

    web_account = await web_account_service.get_by_user_telegram_id(target_user.telegram_id)
    linked_telegram_id = (
        target_user.telegram_id
        if target_user.telegram_id > 0
        else (
            web_account.user_telegram_id
            if web_account and web_account.user_telegram_id > 0
            else None
        )
    )
    if linked_telegram_id is not None:
        return linked_telegram_id

    inferred_telegram_id = await _infer_panel_telegram_id_from_local_subscriptions(
        target_user=target_user,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )
    if inferred_telegram_id is not None:
        return inferred_telegram_id

    return target_user.telegram_id


async def _resolve_subscription_owner(
    *,
    dialog_manager: DialogManager,
    target_user: UserDto,
    user_service: UserService,
) -> UserDto:
    panel_telegram_id = _resolve_panel_telegram_id_from_dialog(dialog_manager, target_user)
    if panel_telegram_id == target_user.telegram_id:
        return target_user

    subscription_owner = await user_service.get(telegram_id=panel_telegram_id)
    return subscription_owner or target_user


def _resolve_identity_kind(
    target_user: UserDto,
    *,
    web_login: str | None,
    linked_telegram_id: int | None,
    web_credentials_bootstrapped: bool,
) -> str:
    if linked_telegram_id is not None and web_login and not web_credentials_bootstrapped:
        return "TELEGRAM_PROVISIONAL"
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
    remnawave_service: FromDishka[RemnawaveService],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_user_getter_payload(
        dialog_manager=dialog_manager,
        config=config,
        user=user,
        user_service=user_service,
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
        settings_service=settings_service,
        referral_service=referral_service,
        partner_service=partner_service,
    )


async def _build_user_getter_payload(
    *,
    dialog_manager: DialogManager,
    config: AppConfig,
    user: UserDto,
    user_service: UserService,
    web_account_service: WebAccountService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
    settings_service: SettingsService,
    referral_service: ReferralService,
    partner_service: PartnerService,
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
    web_credentials_bootstrapped = bool(
        web_account and web_account.credentials_bootstrapped_at is not None
    )
    public_username = target_user.username or None
    panel_telegram_id = await _resolve_effective_panel_telegram_id(
        dialog_manager=dialog_manager,
        target_user=target_user,
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )
    dialog_manager.dialog_data["panel_telegram_id"] = panel_telegram_id
    dialog_manager.dialog_data["effective_panel_telegram_id"] = panel_telegram_id
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
    visible_subscriptions, selected_subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        current_subscription_id,
    )
    subscription = subscription_owner.current_subscription or selected_subscription
    subscriptions_count = len(visible_subscriptions)

    partner = await partner_service.get_partner_by_user(target_telegram_id)
    is_partner = partner is not None and partner.is_active
    has_referral_attribution = await referral_service.has_referral_attribution(target_telegram_id)
    has_partner_attribution = await partner_service.has_partner_attribution(target_telegram_id)
    can_edit = user.role > target_user.role or user.telegram_id in config.bot.dev_id
    attach_referrer_reason: str | None = None
    if not can_edit:
        attach_referrer_reason = "NO_PERMISSION"
    elif target_user.telegram_id == user.telegram_id:
        attach_referrer_reason = "SELF"
    elif has_referral_attribution:
        attach_referrer_reason = "REFERRAL_EXISTS"
    elif has_partner_attribution:
        attach_referrer_reason = "PARTNER_EXISTS"
    dialog_manager.dialog_data["attach_referrer_reason"] = attach_referrer_reason

    data: dict[str, Any] = {
        "user_id": str(target_user.telegram_id),
        "username": target_user.username or False,
        "public_username": public_username or False,
        "has_public_username": bool(public_username),
        "web_login": web_login or False,
        "has_web_login": bool(web_login),
        "linked_telegram_id": str(linked_telegram_id) if linked_telegram_id is not None else False,
        "has_linked_telegram_id": linked_telegram_id is not None,
        "effective_panel_telegram_id": str(panel_telegram_id),
        "has_panel_sync_override": bool(
            dialog_manager.dialog_data.get("panel_sync_override_telegram_id") is not None
        ),
        "panel_sync_override_telegram_id": (
            str(dialog_manager.dialog_data["panel_sync_override_telegram_id"])
            if dialog_manager.dialog_data.get("panel_sync_override_telegram_id") is not None
            else False
        ),
        "identity_kind": _resolve_identity_kind(
            target_user,
            web_login=web_login,
            linked_telegram_id=linked_telegram_id,
            web_credentials_bootstrapped=web_credentials_bootstrapped,
        ),
        "is_provisional_web_account": bool(web_account) and not web_credentials_bootstrapped,
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
        "can_edit": can_edit,
        "has_referral_attribution": has_referral_attribution,
        "has_partner_attribution": has_partner_attribution,
        "show_attach_referrer": can_edit,
        "can_attach_referrer": attach_referrer_reason is None,
        "attach_referrer_reason": attach_referrer_reason or False,
        "status": None,
        "is_trial": False,
        "has_subscription": bool(visible_subscriptions),
        "subscriptions_count": subscriptions_count,
        "has_multiple_subscriptions": subscriptions_count > 1,
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
async def web_cabinet_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_web_cabinet_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )


async def _build_web_cabinet_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    web_account_service: WebAccountService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)
    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    web_account = await web_account_service.get_by_user_telegram_id(target_telegram_id)
    effective_panel_telegram_id = await _resolve_effective_panel_telegram_id(
        dialog_manager=dialog_manager,
        target_user=target_user,
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )
    dialog_manager.dialog_data["panel_telegram_id"] = effective_panel_telegram_id
    dialog_manager.dialog_data["effective_panel_telegram_id"] = effective_panel_telegram_id
    return {
        "target_name": target_user.name,
        "target_telegram_id": str(target_user.telegram_id),
        "has_web_account": bool(web_account),
        "web_login": web_account.username if web_account else False,
        "web_credentials_bootstrapped": bool(
            web_account and web_account.credentials_bootstrapped_at is not None
        ),
        "web_account_provisional": bool(
            web_account and web_account.credentials_bootstrapped_at is None
        ),
        "linked_telegram_id": (
            str(web_account.user_telegram_id)
            if web_account and web_account.user_telegram_id > 0
            else False
        ),
        "effective_panel_telegram_id": str(effective_panel_telegram_id),
        "has_panel_sync_override": bool(
            dialog_manager.dialog_data.get("panel_sync_override_telegram_id") is not None
        ),
        "panel_sync_override_telegram_id": (
            str(dialog_manager.dialog_data["panel_sync_override_telegram_id"])
            if dialog_manager.dialog_data.get("panel_sync_override_telegram_id") is not None
            else False
        ),
    }


@inject
async def web_login_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_web_login_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        web_account_service=web_account_service,
    )


async def _build_web_login_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    web_account_service: WebAccountService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)
    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    web_account = await web_account_service.get_by_user_telegram_id(target_telegram_id)
    return {
        "target_name": target_user.name,
        "target_telegram_id": str(target_user.telegram_id),
        "web_login": web_account.username if web_account else False,
        "has_web_account": bool(web_account),
        "web_account_provisional": bool(
            web_account and web_account.credentials_bootstrapped_at is None
        ),
    }


@inject
async def panel_sync_id_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_panel_sync_id_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )


async def _build_panel_sync_id_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    web_account_service: WebAccountService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)
    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    effective_panel_telegram_id = await _resolve_effective_panel_telegram_id(
        dialog_manager=dialog_manager,
        target_user=target_user,
        web_account_service=web_account_service,
        subscription_service=subscription_service,
        remnawave_service=remnawave_service,
    )
    dialog_manager.dialog_data["panel_telegram_id"] = effective_panel_telegram_id
    dialog_manager.dialog_data["effective_panel_telegram_id"] = effective_panel_telegram_id

    return {
        "target_name": target_user.name,
        "target_telegram_id": str(target_user.telegram_id),
        "effective_panel_telegram_id": str(effective_panel_telegram_id),
        "has_panel_sync_override": bool(
            dialog_manager.dialog_data.get("panel_sync_override_telegram_id") is not None
        ),
        "panel_sync_override_telegram_id": (
            str(dialog_manager.dialog_data["panel_sync_override_telegram_id"])
            if dialog_manager.dialog_data.get("panel_sync_override_telegram_id") is not None
            else False
        ),
    }
