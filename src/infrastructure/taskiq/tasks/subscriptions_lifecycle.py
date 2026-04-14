from __future__ import annotations

from typing import Optional
from uuid import UUID

from loguru import logger
from remnawave import RemnawaveSDK

from src.core.constants import EXPIRED_SUBSCRIPTION_CLEANUP_DAYS
from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.services.subscription import SubscriptionService
from src.services.subscription_runtime import SubscriptionRuntimeService
from src.services.user import UserService


async def _refresh_user_subscriptions_runtime_task(
    *,
    subscription_ids: list[int],
    subscription_runtime_service: SubscriptionRuntimeService,
) -> None:
    await subscription_runtime_service.refresh_user_subscriptions_runtime(subscription_ids)


async def _resolve_target_subscription(
    *,
    user_telegram_id: int,
    user_service: UserService,
    subscription_service: SubscriptionService,
    user_remna_id: UUID | None = None,
) -> tuple[UserDto | None, SubscriptionDto | None]:
    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"User '{user_telegram_id}' not found, skipping task")
        return None, None

    subscription: Optional[SubscriptionDto]
    if user_remna_id:
        subscription = await subscription_service.get_by_remna_id(user_remna_id)
        if not subscription:
            current = await subscription_service.get_current(user.telegram_id)
            if current and current.user_remna_id == user_remna_id:
                subscription = current
    else:
        subscription = await subscription_service.get_current(user.telegram_id)

    return user, subscription


async def _delete_current_subscription_task(
    *,
    user_telegram_id: int,
    user_service: UserService,
    subscription_service: SubscriptionService,
    user_remna_id: UUID | None = None,
) -> None:
    logger.info(f"Delete current subscription started for user '{user_telegram_id}'")

    user, subscription = await _resolve_target_subscription(
        user_telegram_id=user_telegram_id,
        user_service=user_service,
        subscription_service=subscription_service,
        user_remna_id=user_remna_id,
    )
    if not user:
        return
    if not subscription:
        logger.debug(
            f"No subscription found for user '{user.telegram_id}' "
            f"(user_remna_id='{user_remna_id}'), skipping deletion"
        )
        return

    subscription.status = SubscriptionStatus.DELETED
    await subscription_service.update(subscription)

    current = await subscription_service.get_current(user.telegram_id)
    if current and current.user_remna_id == subscription.user_remna_id:
        all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
        active_subscriptions = [
            item
            for item in all_subscriptions
            if item.status != SubscriptionStatus.DELETED and item.id != subscription.id
        ]
        if active_subscriptions:
            await user_service.set_current_subscription(
                user.telegram_id,
                active_subscriptions[0].id,  # type: ignore[arg-type]
            )
        else:
            await user_service.delete_current_subscription(user.telegram_id)


async def _update_status_current_subscription_task(
    *,
    user_telegram_id: int,
    status: SubscriptionStatus,
    user_service: UserService,
    subscription_service: SubscriptionService,
    user_remna_id: UUID | None = None,
) -> None:
    logger.info(f"Update status current subscription started for user '{user_telegram_id}'")

    user, subscription = await _resolve_target_subscription(
        user_telegram_id=user_telegram_id,
        user_service=user_service,
        subscription_service=subscription_service,
        user_remna_id=user_remna_id,
    )
    if not user:
        return
    if not subscription:
        logger.debug(
            f"No subscription found for user '{user.telegram_id}' "
            f"(user_remna_id='{user_remna_id}'), skipping status update"
        )
        return

    subscription.status = status
    await subscription_service.update(subscription)


async def _cleanup_expired_subscriptions_task(
    *,
    subscription_service: SubscriptionService,
    remnawave: RemnawaveSDK,
) -> None:
    logger.info(
        f"Starting cleanup of subscriptions expired more than "
        f"{EXPIRED_SUBSCRIPTION_CLEANUP_DAYS} days ago"
    )

    expired_subscriptions = await subscription_service.get_expired_subscriptions_older_than(
        days=EXPIRED_SUBSCRIPTION_CLEANUP_DAYS
    )

    if not expired_subscriptions:
        logger.info("No expired subscriptions to cleanup")
        return

    deleted_count = 0
    failed_count = 0

    for subscription in expired_subscriptions:
        try:
            remna_user_uuid = subscription.user_remna_id
            if remna_user_uuid:
                result = await remnawave.users.delete_user(uuid=str(remna_user_uuid))
                if result and hasattr(result, "is_deleted") and result.is_deleted:
                    logger.info(
                        f"Deleted RemnaUser '{remna_user_uuid}' from panel "
                        f"(subscription '{subscription.id}')"
                    )
                else:
                    logger.warning(f"Failed to delete RemnaUser '{remna_user_uuid}' from panel")

            await subscription_service.delete_subscription(subscription.id)  # type: ignore[arg-type]
            deleted_count += 1

        except Exception as exception:
            logger.error(f"Error cleaning up subscription '{subscription.id}': {exception}")
            failed_count += 1

    logger.info(f"Cleanup completed: {deleted_count} subscriptions deleted, {failed_count} failed")
