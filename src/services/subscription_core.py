from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.database.models.sql import Subscription

if TYPE_CHECKING:
    from .subscription import SubscriptionService


async def create(
    service: SubscriptionService,
    user: UserDto,
    subscription: SubscriptionDto,
    *,
    auto_commit: bool = True,
) -> SubscriptionDto:
    data = subscription.model_dump(exclude=service._CREATE_EXCLUDE_FIELDS)
    data["plan"] = subscription.plan.model_dump(mode="json")

    db_subscription = Subscription(**data, user_telegram_id=user.telegram_id)
    db_created_subscription = await service.uow.repository.subscriptions.create(db_subscription)

    await service.user_service.set_current_subscription(
        telegram_id=user.telegram_id,
        subscription_id=db_created_subscription.id,
    )
    if auto_commit:
        await service.uow.commit()

    logger.info(
        "Created subscription '{}' for user '{}'",
        db_created_subscription.id,
        user.telegram_id,
    )
    return SubscriptionDto.from_model(db_created_subscription)  # type: ignore[return-value]


async def get(service: SubscriptionService, subscription_id: int) -> SubscriptionDto | None:
    db_subscription = await service.uow.repository.subscriptions.get(subscription_id)

    if db_subscription:
        logger.debug("Retrieved subscription '{}'", subscription_id)
    else:
        logger.warning("Subscription '{}' not found", subscription_id)

    return SubscriptionDto.from_model(db_subscription)


async def get_by_remna_id(
    service: SubscriptionService,
    user_remna_id: UUID,
) -> SubscriptionDto | None:
    db_subscription = await service.uow.repository.subscriptions.get_by_remna_id(user_remna_id)

    if db_subscription:
        logger.debug("Retrieved subscription by remna_id '{}'", user_remna_id)
    else:
        logger.debug("Subscription with remna_id '{}' not found", user_remna_id)

    return SubscriptionDto.from_model(db_subscription)


async def update(
    service: SubscriptionService,
    subscription: SubscriptionDto,
    *,
    auto_commit: bool = True,
) -> SubscriptionDto | None:
    changed_data = subscription.changed_data.copy()
    data = {
        key: value for key, value in changed_data.items() if key in service._UPDATE_ALLOWED_FIELDS
    }
    ignored_fields = set(changed_data.keys()) - set(data.keys()) - {"plan"}
    if ignored_fields:
        logger.debug(
            "Ignoring non-persisted subscription fields for update '{}': {}",
            subscription.id,
            sorted(ignored_fields),
        )

    if subscription.plan.changed_data or "plan" in changed_data:
        data["plan"] = subscription.plan.model_dump(mode="json")

    db_updated_subscription = await service.uow.repository.subscriptions.update(
        subscription_id=subscription.id,  # type: ignore[arg-type]
        **data,
    )

    if auto_commit:
        await service.uow.commit()

    if db_updated_subscription:
        if subscription.user:
            await service.user_service.clear_user_cache(telegram_id=subscription.user.telegram_id)
        logger.info("Updated subscription '{}' successfully", subscription.id)
    else:
        logger.warning(
            "Attempted to update subscription '{}', "
            "but subscription was not found or update failed",
            subscription.id,
        )

    return SubscriptionDto.from_model(db_updated_subscription)


async def rebind_user(
    service: SubscriptionService,
    *,
    subscription_id: int,
    user_telegram_id: int,
    previous_user_telegram_id: int | None = None,
    auto_commit: bool = True,
) -> SubscriptionDto | None:
    db_updated_subscription = await service.uow.repository.subscriptions.rebind_user(
        subscription_id=subscription_id,
        user_telegram_id=user_telegram_id,
    )

    if auto_commit:
        await service.uow.commit()

    if previous_user_telegram_id is not None:
        await service.user_service.clear_user_cache(previous_user_telegram_id)
    await service.user_service.clear_user_cache(user_telegram_id)

    if db_updated_subscription:
        logger.info("Rebound subscription '{}' to user '{}'", subscription_id, user_telegram_id)
    else:
        logger.warning(
            "Failed to rebind subscription '{}' to user '{}'",
            subscription_id,
            user_telegram_id,
        )

    return SubscriptionDto.from_model(db_updated_subscription)


async def delete_subscription(service: SubscriptionService, subscription_id: int) -> bool:
    db_subscription = await service.uow.repository.subscriptions.update(
        subscription_id=subscription_id,
        status=service._deleted_status(),
    )
    await service.uow.commit()

    if db_subscription:
        logger.info("Marked subscription '{}' as deleted", subscription_id)
        return True

    logger.warning("Failed to mark subscription '{}' as deleted", subscription_id)
    return False
