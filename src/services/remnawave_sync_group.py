from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Sequence, cast

from loguru import logger
from remnawave.enums.users import TrafficLimitStrategy

from src.core.constants import IMPORTED_TAG
from src.core.enums import DeviceType, SubscriptionStatus
from src.core.utils.formatters import format_limits_to_plan_type
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)

if TYPE_CHECKING:
    from .remnawave import PanelSyncStats


async def _get_original_current_subscription_id(
    service: Any,
    *,
    telegram_id: int,
    preserve_current: bool,
    user_before: Optional[UserDto],
) -> Optional[int]:
    if not preserve_current or not user_before:
        return None

    current_subscription = cast(
        Optional[SubscriptionDto],
        await service.subscription_service.get_current(telegram_id),
    )
    if (
        current_subscription
        and current_subscription.id
        and current_subscription.status != SubscriptionStatus.DELETED
    ):
        return current_subscription.id

    return None


def _validate_group_sync_profile_telegram_id(
    *,
    remna_user: Any,
    telegram_id: int,
) -> bool:
    if not remna_user.telegram_id:
        logger.warning(
            f"Skipping profile '{remna_user.uuid}' during grouped sync: missing telegram_id"
        )
        return False

    try:
        profile_tg_id = int(remna_user.telegram_id)
    except (TypeError, ValueError):
        logger.warning(
            f"Skipping profile '{remna_user.uuid}' during grouped sync: "
            f"invalid telegram_id '{remna_user.telegram_id}'"
        )
        return False

    if profile_tg_id != telegram_id:
        logger.warning(
            f"Skipping profile '{remna_user.uuid}' during grouped sync: "
            f"telegram_id mismatch ({profile_tg_id} != {telegram_id})"
        )
        return False

    return True


async def _sync_group_profile(
    service: Any,
    *,
    remna_user: Any,
    telegram_id: int,
    stats: PanelSyncStats,
) -> None:
    try:
        existing_subscription = cast(
            Optional[SubscriptionDto],
            await service.subscription_service.get_by_remna_id(remna_user.uuid),
        )
        await service.sync_user(remna_user, creating=True)

        if existing_subscription:
            stats.subscriptions_updated += 1
        else:
            stats.subscriptions_created += 1
    except Exception as exception:
        logger.exception(
            f"Failed to sync profile '{remna_user.uuid}' for telegram_id='{telegram_id}': "
            f"{exception}"
        )
        stats.errors += 1


async def _restore_group_sync_current_subscription(
    service: Any,
    *,
    telegram_id: int,
    original_current_subscription_id: Optional[int],
    preserve_current: bool,
) -> None:
    if not preserve_current:
        return

    if not original_current_subscription_id:
        await service._set_group_sync_fallback_current_subscription(telegram_id)
        return

    original_subscription = cast(
        Optional[SubscriptionDto],
        await service.subscription_service.get(original_current_subscription_id),
    )
    if (
        original_subscription
        and original_subscription.status != SubscriptionStatus.DELETED
        and original_subscription.user_telegram_id == telegram_id
    ):
        await service.user_service.set_current_subscription(
            telegram_id=telegram_id,
            subscription_id=original_current_subscription_id,
        )
        logger.info(
            f"Restored current subscription '{original_current_subscription_id}' "
            f"for user '{telegram_id}' after grouped sync"
        )
        return

    logger.debug(
        f"Original current subscription '{original_current_subscription_id}' for "
        f"user '{telegram_id}' is no longer valid, skip restore"
    )
    await service._set_group_sync_fallback_current_subscription(telegram_id)


def _pick_group_sync_current_subscription_id(
    subscriptions: Sequence[SubscriptionDto],
) -> Optional[int]:
    candidates = [
        subscription
        for subscription in subscriptions
        if subscription.id is not None and subscription.status != SubscriptionStatus.DELETED
    ]
    if not candidates:
        return None

    status_priority = {
        SubscriptionStatus.ACTIVE: 0,
        SubscriptionStatus.LIMITED: 1,
        SubscriptionStatus.EXPIRED: 2,
        SubscriptionStatus.DISABLED: 3,
    }
    candidates.sort(
        key=lambda subscription: (
            status_priority.get(subscription.status, 99),
            -subscription.expire_at.timestamp(),
            subscription.id or 0,
        )
    )
    return candidates[0].id


async def _set_group_sync_fallback_current_subscription(
    service: Any,
    telegram_id: int,
) -> None:
    subscriptions = cast(
        list[SubscriptionDto],
        await service.subscription_service.get_all_by_user(telegram_id),
    )
    fallback_subscription_id = service._pick_group_sync_current_subscription_id(subscriptions)
    if fallback_subscription_id is None:
        await service.user_service.delete_current_subscription(telegram_id)
        logger.debug(
            f"No fallback current subscription remains for user '{telegram_id}' "
            "after grouped sync"
        )
        return

    await service.user_service.set_current_subscription(
        telegram_id=telegram_id,
        subscription_id=fallback_subscription_id,
    )
    logger.info(
        f"Selected fallback current subscription '{fallback_subscription_id}' "
        f"for user '{telegram_id}' after grouped sync"
    )


async def sync_profiles_by_telegram_id(
    service: Any,
    telegram_id: int,
    remna_users: Sequence[Any],
    preserve_current: bool = True,
) -> PanelSyncStats:
    from .remnawave import PanelSyncStats  # noqa: PLC0415

    stats = PanelSyncStats()
    if not remna_users:
        return stats

    user_before = await service.user_service.get(telegram_id=telegram_id)
    original_current_subscription_id = await service._get_original_current_subscription_id(
        telegram_id=telegram_id,
        preserve_current=preserve_current,
        user_before=user_before,
    )

    logger.info(
        f"Starting grouped sync for telegram_id='{telegram_id}' "
        f"with '{len(remna_users)}' profile(s)"
    )

    for remna_user in remna_users:
        if not service._validate_group_sync_profile_telegram_id(
            remna_user=remna_user,
            telegram_id=telegram_id,
        ):
            continue

        await service._sync_group_profile(
            remna_user=remna_user,
            telegram_id=telegram_id,
            stats=stats,
        )

    await service._restore_group_sync_current_subscription(
        telegram_id=telegram_id,
        original_current_subscription_id=original_current_subscription_id,
        preserve_current=preserve_current,
    )

    user_after = await service.user_service.get(telegram_id=telegram_id)
    stats.user_created = user_before is None and user_after is not None

    logger.info(
        f"Grouped sync summary for user '{telegram_id}': "
        f"user_created={stats.user_created}, "
        f"created={stats.subscriptions_created}, "
        f"updated={stats.subscriptions_updated}, "
        f"errors={stats.errors}"
    )
    return stats


async def _hydrate_panel_subscription_url(
    service: Any,
    *,
    remna_user: Any,
    remna_subscription: RemnaSubscriptionDto,
    subscription: Optional[SubscriptionDto],
    telegram_id: int,
) -> None:
    panel_subscription_url = remna_subscription.url.strip() if remna_subscription.url else ""
    if panel_subscription_url:
        return

    refreshed_subscription_url = await service.get_subscription_url(remna_user.uuid)
    if refreshed_subscription_url:
        remna_subscription.url = refreshed_subscription_url
        return

    if subscription and subscription.url:
        remna_subscription.url = subscription.url

    if not remna_subscription.url:
        logger.warning(
            f"Subscription URL is empty for RemnaUser '{remna_user.uuid}' "
            f"(telegram_id='{telegram_id}')"
        )


async def _create_subscription_from_sync(
    service: Any,
    *,
    user: UserDto,
    remna_user: Any,
    remna_subscription: RemnaSubscriptionDto,
    matched_plan: Optional[PlanDto],
) -> None:
    plan_tag = remna_subscription.tag
    plan_name = IMPORTED_TAG
    plan_id = -1

    if matched_plan and matched_plan.id is not None:
        plan_name = matched_plan.name
        plan_id = matched_plan.id
        plan_tag = matched_plan.tag

    internal_squads = remna_subscription.internal_squads
    if not isinstance(internal_squads, list):
        logger.warning(
            f"internal_squads is not a list for user '{user.telegram_id}', using empty list"
        )
        internal_squads = []

    traffic_limit_strategy = remna_subscription.traffic_limit_strategy
    if traffic_limit_strategy is None:
        traffic_limit_strategy = TrafficLimitStrategy.NO_RESET

    temp_plan = PlanSnapshotDto(
        id=plan_id,
        name=plan_name,
        tag=plan_tag,
        type=format_limits_to_plan_type(
            remna_subscription.traffic_limit,
            remna_subscription.device_limit,
        ),
        traffic_limit=remna_subscription.traffic_limit,
        device_limit=remna_subscription.device_limit,
        duration=-1,
        traffic_limit_strategy=traffic_limit_strategy,
        internal_squads=internal_squads,
        external_squad=remna_subscription.external_squad,
    )

    expired = remna_user.expire_at and remna_user.expire_at < datetime_now()
    status = SubscriptionStatus.EXPIRED if expired else remna_user.status
    subscription = SubscriptionDto(
        user_remna_id=remna_user.uuid,
        status=status,
        traffic_limit=temp_plan.traffic_limit,
        device_limit=temp_plan.device_limit,
        internal_squads=internal_squads,
        external_squad=remna_subscription.external_squad,
        expire_at=remna_user.expire_at,
        url=remna_subscription.url,
        plan=temp_plan,
        device_type=DeviceType.OTHER,
    )
    await service.subscription_service.create(user, subscription)
    logger.info(f"Subscription created for '{user.telegram_id}'")


async def _update_subscription_from_sync(
    service: Any,
    *,
    user: UserDto,
    subscription: SubscriptionDto,
    remna_subscription: RemnaSubscriptionDto,
    matched_plan: Optional[PlanDto],
) -> None:
    logger.info(f"Synchronizing subscription '{subscription.id}' for '{user.telegram_id}'")
    subscription = subscription.apply_sync(remna_subscription)

    auto_plan_assignment = service._is_imported_or_unassigned_snapshot(subscription)
    if auto_plan_assignment:
        service._apply_plan_identity(
            subscription=subscription,
            matched_plan=matched_plan,
            telegram_id=user.telegram_id,
        )
    else:
        logger.debug(
            f"Preserving manually assigned plan snapshot for subscription "
            f"'{subscription.id}' (user '{user.telegram_id}')"
        )

    if subscription.device_type is None and auto_plan_assignment:
        subscription.device_type = DeviceType.OTHER

    await service.subscription_service.update(subscription)
    logger.info(f"Subscription '{subscription.id}' updated for '{user.telegram_id}'")


async def _rebind_subscription_owner_if_needed(
    service: Any,
    *,
    user: UserDto,
    subscription: SubscriptionDto,
) -> SubscriptionDto:
    if subscription.user_telegram_id == user.telegram_id:
        return subscription

    if subscription.id is None:
        raise ValueError("Subscription ID is required for ownership rebind")

    logger.info(
        "Rebinding subscription '{}' from user '{}' to '{}'",
        subscription.id,
        subscription.user_telegram_id,
        user.telegram_id,
    )
    rebound_subscription = cast(
        Optional[SubscriptionDto],
        await service.subscription_service.rebind_user(
            subscription_id=subscription.id,
            user_telegram_id=user.telegram_id,
            previous_user_telegram_id=subscription.user_telegram_id,
            auto_commit=False,
        ),
    )
    if rebound_subscription is None:
        raise ValueError(
            f"Failed to rebind subscription '{subscription.id}' "
            f"to user '{user.telegram_id}'"
        )
    return rebound_subscription


async def sync_user(
    service: Any,
    remna_user: Any,
    creating: bool = True,
    *,
    use_current_subscription_fallback: bool = False,
) -> None:
    if not remna_user.telegram_id:
        logger.warning(f"Skipping sync for '{remna_user.username}', missing 'telegram_id'")
        return

    user = await service.user_service.get(telegram_id=remna_user.telegram_id)
    if not user and creating:
        logger.debug(f"User '{remna_user.telegram_id}' not found in bot, creating new user")
        user = await service.user_service.create_from_panel(remna_user)

    if not user:
        logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
        return

    user = cast(UserDto, user)
    subscription = cast(
        Optional[SubscriptionDto],
        await service.subscription_service.get_by_remna_id(remna_user.uuid),
    )
    if subscription:
        subscription = await service._rebind_subscription_owner_if_needed(
            user=user,
            subscription=subscription,
        )
    if not subscription and creating and use_current_subscription_fallback:
        subscription = cast(
            Optional[SubscriptionDto],
            await service.subscription_service.get_current(telegram_id=user.telegram_id),
        )
        if subscription:
            logger.debug(
                f"Subscription not found by remna_id '{remna_user.uuid}', "
                f"using current subscription '{subscription.id}' for user '{user.telegram_id}'"
            )

    remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_user.model_dump())
    matched_plan = await service._resolve_matched_plan_for_sync(
        remna_subscription=remna_subscription,
        telegram_id=user.telegram_id,
    )
    await service._hydrate_panel_subscription_url(
        remna_user=remna_user,
        remna_subscription=remna_subscription,
        subscription=subscription,
        telegram_id=user.telegram_id,
    )

    if not subscription:
        if not creating:
            logger.debug(
                f"No subscription found for remna_id '{remna_user.uuid}' "
                f"and creating=False, skipping sync for user '{user.telegram_id}'"
            )
            return

        logger.info(f"No subscription found for '{user.telegram_id}', creating")
        await service._create_subscription_from_sync(
            user=user,
            remna_user=remna_user,
            remna_subscription=remna_subscription,
            matched_plan=matched_plan,
        )
    else:
        await service._update_subscription_from_sync(
            user=user,
            subscription=subscription,
            remna_subscription=remna_subscription,
            matched_plan=matched_plan,
        )

    logger.info(f"Sync completed for user '{remna_user.telegram_id}'")
