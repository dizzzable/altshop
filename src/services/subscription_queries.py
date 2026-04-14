from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Sequence

from loguru import logger
from sqlalchemy import and_

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.database.models.sql import Subscription, User

if TYPE_CHECKING:
    from .subscription import SubscriptionService


async def get_current(service: SubscriptionService, telegram_id: int) -> SubscriptionDto | None:
    db_user = await service.uow.repository.users.get(telegram_id)

    if not db_user or not db_user.current_subscription_id:
        logger.debug(
            "Current subscription check: User '{}' has no active subscription",
            telegram_id,
        )
        return None

    subscription_id = db_user.current_subscription_id
    db_active_subscription = await service.uow.repository.subscriptions.get(subscription_id)

    if db_active_subscription:
        logger.debug(
            "Current subscription check: Subscription '{}' retrieved for user '{}'",
            subscription_id,
            telegram_id,
        )
    else:
        logger.warning(
            "User '{}' linked to subscription ID '{}', but subscription object was not found",
            telegram_id,
            subscription_id,
        )

    return SubscriptionDto.from_model(db_active_subscription)


async def get_all_by_user(
    service: SubscriptionService,
    telegram_id: int,
) -> list[SubscriptionDto]:
    db_subscriptions = await service.uow.repository.subscriptions.get_all_by_user(telegram_id)
    logger.debug("Retrieved '{}' subscriptions for user '{}'", len(db_subscriptions), telegram_id)
    return SubscriptionDto.from_model_list(db_subscriptions)


async def get_all(service: SubscriptionService) -> list[SubscriptionDto]:
    db_subscriptions = await service.uow.repository.subscriptions.get_all()
    logger.debug("Retrieved '{}' total subscriptions", len(db_subscriptions))
    return SubscriptionDto.from_model_list(db_subscriptions)


async def get_by_ids(
    service: SubscriptionService,
    subscription_ids: Sequence[int],
) -> list[SubscriptionDto]:
    db_subscriptions = await service.uow.repository.subscriptions.get_by_ids(subscription_ids)
    logger.debug(
        "Retrieved '{}' subscriptions by ids (requested={})",
        len(db_subscriptions),
        len(subscription_ids),
    )
    return SubscriptionDto.from_model_list(db_subscriptions)


async def get_subscribed_users(service: SubscriptionService) -> list[UserDto]:
    db_users = await service.uow.repository.users._get_many(User)
    users = [user for user in db_users if user.current_subscription]
    logger.debug("Retrieved '{}' users with subscription", len(users))
    return UserDto.from_model_list(users)


async def get_users_by_plan(service: SubscriptionService, plan_id: int) -> list[UserDto]:
    db_subscriptions = await service.uow.repository.subscriptions.filter_by_plan_id(plan_id)
    active_subs = [
        subscription
        for subscription in db_subscriptions
        if subscription.status == service._active_status()
    ]

    if not active_subs:
        logger.debug("No active subscriptions found for plan '{}'", plan_id)
        return []

    user_ids = [subscription.user_telegram_id for subscription in active_subs]
    db_users = await service.uow.repository.users.get_by_ids(telegram_ids=user_ids)
    users = UserDto.from_model_list(db_users)
    logger.debug("Retrieved '{}' users for active plan '{}'", len(users), plan_id)
    return users


async def get_unsubscribed_users(service: SubscriptionService) -> list[UserDto]:
    db_users = await service.uow.repository.users._get_many(User)
    users = [user for user in db_users if not user.current_subscription]
    logger.debug("Retrieved '{}' users without subscription", len(users))
    return UserDto.from_model_list(users)


async def get_expired_users(service: SubscriptionService) -> list[UserDto]:
    db_users = await service.uow.repository.users._get_many(User)
    users = [
        user
        for user in db_users
        if user.current_subscription
        and user.current_subscription.status == service._expired_status()
    ]

    logger.debug("Retrieved '{}' users with expired subscription", len(users))
    return UserDto.from_model_list(users)


async def get_trial_users(service: SubscriptionService) -> list[UserDto]:
    db_users = await service.uow.repository.users._get_many(User)
    users = [
        user
        for user in db_users
        if user.current_subscription and user.current_subscription.is_trial
    ]

    logger.debug("Retrieved '{}' users with trial subscription", len(users))
    return UserDto.from_model_list(users)


async def has_any_subscription(service: SubscriptionService, user: UserDto) -> bool:
    count = await service.uow.repository.subscriptions._count(
        Subscription,
        Subscription.user_telegram_id == user.telegram_id,
    )
    return count > 0


async def has_used_trial(service: SubscriptionService, user: UserDto) -> bool:
    conditions = and_(
        Subscription.user_telegram_id == user.telegram_id,
        Subscription.is_trial.is_(True),
    )
    count = await service.uow.repository.subscriptions._count(Subscription, conditions)
    return count > 0


async def get_expired_subscriptions_older_than(
    service: SubscriptionService,
    days: int,
) -> list[SubscriptionDto]:
    cutoff_date = datetime_now() - timedelta(days=days)
    conditions = and_(
        Subscription.status == service._expired_status(),
        Subscription.expire_at < cutoff_date,
    )

    db_subscriptions = await service.uow.repository.subscriptions._get_many(
        Subscription,
        conditions,
    )

    logger.debug(
        "Retrieved '{}' subscriptions expired more than {} days ago",
        len(db_subscriptions),
        days,
    )
    return SubscriptionDto.from_model_list(db_subscriptions)
