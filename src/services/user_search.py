from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import Message
from loguru import logger

from src.core.constants import REMNASHOP_PREFIX
from src.core.utils.validators import parse_int
from src.infrastructure.database.models.dto import UserDto

if TYPE_CHECKING:
    from .user import UserService


async def search_users(service: UserService, message: Message) -> list[UserDto]:
    if message.forward_from and not message.forward_from.is_bot:
        return await service._search_users_by_forward(message)

    if message.text:
        return await service._search_users_by_query(message.text.strip())

    return []


async def search_users_by_forward(service: UserService, message: Message) -> list[UserDto]:
    target_telegram_id = message.forward_from.id  # type: ignore[union-attr]
    single_user = await service.get(telegram_id=target_telegram_id)
    if not single_user:
        logger.warning("Search by forwarded message, user '{}' not found", target_telegram_id)
        return []

    logger.info("Search by forwarded message, found user '{}'", target_telegram_id)
    return [single_user]


async def search_users_by_query(service: UserService, search_query: str) -> list[UserDto]:
    logger.debug("Searching users by query '{}'", search_query)

    telegram_id = parse_int(search_query)
    if telegram_id is not None:
        return await service._search_users_by_telegram_id(telegram_id)

    if search_query.startswith(REMNASHOP_PREFIX):
        return await service._search_users_by_remnashop_id(search_query)

    referral_user = await service.get_by_referral_code(search_query.upper())
    if referral_user:
        logger.info("Searched by referral code '{}', user found", search_query.upper())
        return [referral_user]

    return await service._search_users_by_login_or_name(search_query)


async def search_users_by_telegram_id(
    service: UserService,
    target_telegram_id: int,
) -> list[UserDto]:
    single_user = await service.get(telegram_id=target_telegram_id)
    if not single_user:
        logger.warning("Searched by Telegram ID '{}', user not found", target_telegram_id)
        return []

    logger.info("Searched by Telegram ID '{}', user found", target_telegram_id)
    return [single_user]


async def search_users_by_remnashop_id(
    service: UserService,
    search_query: str,
) -> list[UserDto]:
    try:
        target_id = int(search_query.split("_", maxsplit=1)[1])
    except (IndexError, ValueError):
        logger.warning("Failed to parse Remnashop ID from query '{}'", search_query)
        return []

    single_user = await service.get(telegram_id=target_id)
    if not single_user:
        logger.warning("Searched by Remnashop ID '{}', user not found", target_id)
        return []

    logger.info("Searched by Remnashop ID '{}', user found", target_id)
    return [single_user]


async def search_users_by_login_or_name(
    service: UserService,
    search_query: str,
) -> list[UserDto]:
    normalized_query = search_query.lower()
    async with service.uow:
        web_account = await service.uow.repository.web_accounts.get_by_username(normalized_query)
        matched_user = None
        if web_account:
            matched_user = await service.uow.repository.users.get(web_account.user_telegram_id)

    if matched_user:
        user_dto = UserDto.from_model(matched_user)
        if not user_dto:
            return []
        logger.info("Searched users by exact web login '{}', found 1 user", normalized_query)
        return [user_dto]

    found_users = await service.get_by_partial_name(query=search_query)

    async with service.uow:
        partial_accounts = await service.uow.repository.web_accounts.get_by_partial_username(
            normalized_query
        )
        partial_account_user_ids = list({account.user_telegram_id for account in partial_accounts})
        partial_login_users = UserDto.from_model_list(
            await service.uow.repository.users.get_by_ids(partial_account_user_ids)
        )

    deduplicated_users: dict[int, UserDto] = {}
    for found_user in [*found_users, *partial_login_users]:
        deduplicated_users[found_user.telegram_id] = found_user

    merged_users = list(deduplicated_users.values())
    logger.info(
        "Searched users by query '{}', found '{}' users (partial name/login)",
        search_query,
        len(merged_users),
    )
    return merged_users
