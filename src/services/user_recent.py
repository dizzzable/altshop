from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.core.constants import RECENT_ACTIVITY_MAX_COUNT, RECENT_REGISTERED_MAX_COUNT
from src.core.storage.key_builder import StorageKey, build_key
from src.core.storage.keys import RecentActivityUsersKey, RecentRegisteredUsersKey
from src.infrastructure.database.models.dto import UserDto

if TYPE_CHECKING:
    from .user import UserService


async def add_to_recent_registered(service: UserService, telegram_id: int) -> None:
    await service._add_to_recent_list(RecentRegisteredUsersKey(), telegram_id)


async def update_recent_activity(service: UserService, telegram_id: int) -> None:
    await service._add_to_recent_list(RecentActivityUsersKey(), telegram_id)


async def get_recent_registered_users(service: UserService) -> list[UserDto]:
    telegram_ids = await service._get_recent_registered()
    db_users = await service.uow.repository.users.get_by_ids(telegram_ids)

    found_ids = {user.telegram_id for user in db_users}
    for telegram_id in telegram_ids:
        if telegram_id not in found_ids:
            logger.warning(
                "User '{}' not found in DB, removing from recent registered cache",
                telegram_id,
            )
            await service._remove_from_recent_registered(telegram_id)

    logger.debug("Retrieved '{}' recent registered users", len(db_users))
    return UserDto.from_model_list(list(reversed(db_users)))


async def get_recent_activity_users(service: UserService) -> list[UserDto]:
    telegram_ids = await service._get_recent_activity()
    users: list[UserDto] = []

    for telegram_id in telegram_ids:
        user = await service.get(telegram_id)

        if user:
            users.append(user)
        else:
            logger.warning(
                "User '{}' not found in DB, removing from recent activity cache",
                telegram_id,
            )
            await service._remove_from_recent_activity(telegram_id)

    logger.debug("Retrieved '{}' recent active users", len(users))
    return users


async def clear_user_cache(service: UserService, telegram_id: int) -> None:
    user_cache_key = build_key("cache", "get_user", telegram_id)
    await service.redis_client.delete(user_cache_key)
    await service._clear_list_caches()
    logger.debug("User cache for '{}' invalidated", telegram_id)


async def clear_list_caches(service: UserService) -> None:
    list_cache_keys_to_invalidate = [
        build_key("cache", "get_blocked_users"),
        build_key("cache", "count"),
    ]

    for role in service._user_roles():
        key = build_key("cache", "get_by_role", role=role)
        list_cache_keys_to_invalidate.append(key)

    await service.redis_client.delete(*list_cache_keys_to_invalidate)
    logger.debug("List caches invalidated")


async def add_to_recent_list(
    service: UserService,
    key: StorageKey,
    telegram_id: int,
) -> None:
    await service.redis_repository.list_remove(key, value=telegram_id, count=0)
    await service.redis_repository.list_push(key, telegram_id)

    if key == RecentRegisteredUsersKey():
        end = RECENT_REGISTERED_MAX_COUNT - 1
        log_message = "registered"
    else:
        end = RECENT_ACTIVITY_MAX_COUNT - 1
        log_message = "activity updated"

    await service.redis_repository.list_trim(key, start=0, end=end)
    logger.debug("User '{}' {} in recent cache", telegram_id, log_message)


async def remove_from_recent_registered(service: UserService, telegram_id: int) -> None:
    await service.redis_repository.list_remove(
        key=RecentRegisteredUsersKey(),
        value=telegram_id,
        count=0,
    )
    logger.debug("User '{}' removed from recent registered cache", telegram_id)


async def get_recent_registered(service: UserService) -> list[int]:
    telegram_ids_str = await service.redis_repository.list_range(
        key=RecentRegisteredUsersKey(),
        start=0,
        end=RECENT_REGISTERED_MAX_COUNT - 1,
    )
    ids = [int(uid) for uid in telegram_ids_str]
    logger.debug("Retrieved '{}' recent registered user IDs from cache", len(ids))
    return ids


async def remove_from_recent_activity(service: UserService, telegram_id: int) -> None:
    await service.redis_repository.list_remove(
        key=RecentActivityUsersKey(),
        value=telegram_id,
        count=0,
    )
    logger.debug("User '{}' removed from recent activity cache", telegram_id)


async def get_recent_activity(service: UserService) -> list[int]:
    telegram_ids_str = await service.redis_repository.list_range(
        key=RecentActivityUsersKey(),
        start=0,
        end=RECENT_ACTIVITY_MAX_COUNT - 1,
    )
    ids = [int(uid) for uid in telegram_ids_str]
    logger.debug("Retrieved '{}' recent activity user IDs from cache", len(ids))
    return ids
