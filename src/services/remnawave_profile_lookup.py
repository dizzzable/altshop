from __future__ import annotations

from typing import Any

from src.infrastructure.database.models.dto import SubscriptionDto

from .remnawave import RemnawaveService


async def load_owner_remna_users_by_uuid(
    *,
    owner_telegram_id: int | None,
    remnawave_service: RemnawaveService,
) -> dict[Any, Any] | None:
    if owner_telegram_id is None or not hasattr(remnawave_service, "get_users_map_by_telegram_id"):
        return None

    try:
        return await remnawave_service.get_users_map_by_telegram_id(owner_telegram_id)
    except Exception:
        return None


async def resolve_subscription_remna_user(
    *,
    subscription: SubscriptionDto,
    remna_users_by_uuid: dict[Any, Any] | None,
    remnawave_service: RemnawaveService,
) -> Any | None:
    remna_user = (
        remna_users_by_uuid.get(subscription.user_remna_id)
        if remna_users_by_uuid is not None
        else None
    )
    if remna_user is not None:
        return remna_user

    if not hasattr(remnawave_service, "get_user"):
        return None

    try:
        return await remnawave_service.get_user(subscription.user_remna_id)
    except Exception:
        return None


async def resolve_subscription_profile_name(
    *,
    subscription: SubscriptionDto,
    remna_users_by_uuid: dict[Any, Any] | None,
    remnawave_service: RemnawaveService,
) -> str | None:
    remna_user = await resolve_subscription_remna_user(
        subscription=subscription,
        remna_users_by_uuid=remna_users_by_uuid,
        remnawave_service=remnawave_service,
    )
    raw_username = getattr(remna_user, "username", None)
    if not raw_username:
        return None
    return str(raw_username)
