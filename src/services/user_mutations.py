from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.core.enums import Currency, UserRole
from src.core.storage.key_builder import build_key
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.user import BaseUserDto

if TYPE_CHECKING:
    from .user import UserService


async def set_block(service: UserService, user: UserDto, blocked: bool) -> None:
    user.is_blocked = blocked
    await service.uow.repository.users.update(
        user.telegram_id,
        **user.prepare_changed_data(),
    )
    await service.clear_user_cache(user.telegram_id)
    logger.info("Set block={} for user '{}'", blocked, user.telegram_id)


async def set_bot_blocked(service: UserService, user: UserDto, blocked: bool) -> None:
    user.is_bot_blocked = blocked
    await service.uow.repository.users.update(
        user.telegram_id,
        **user.prepare_changed_data(),
    )
    await service.clear_user_cache(user.telegram_id)
    logger.info("Set bot_blocked={} for user '{}'", blocked, user.telegram_id)


async def set_role(service: UserService, user: UserDto, role: UserRole) -> None:
    user.role = role
    await service.uow.repository.users.update(
        user.telegram_id,
        **user.prepare_changed_data(),
    )
    await service.clear_user_cache(user.telegram_id)
    logger.info("Set role='{}' for user '{}'", role.name, user.telegram_id)


async def set_purchase_discount(service: UserService, user: UserDto, discount: int) -> None:
    user.purchase_discount = discount
    await service.uow.repository.users.update(
        user.telegram_id,
        **user.prepare_changed_data(),
    )
    await service.clear_user_cache(user.telegram_id)
    logger.info("Set purchase_discount={} for user '{}'", discount, user.telegram_id)


async def set_partner_balance_currency_override(
    service: UserService,
    user: UserDto,
    currency: Currency | None,
) -> None:
    user.partner_balance_currency_override = currency
    await service.uow.repository.users.update(
        user.telegram_id,
        **user.prepare_changed_data(),
    )
    await service.clear_user_cache(user.telegram_id)
    logger.info(
        "Set partner_balance_currency_override='{}' for user '{}'",
        getattr(currency, "value", currency),
        user.telegram_id,
    )


async def set_current_subscription(
    service: UserService,
    telegram_id: int,
    subscription_id: int,
) -> None:
    await service.uow.repository.users.update(
        telegram_id=telegram_id,
        current_subscription_id=subscription_id,
    )
    await service.clear_user_cache(telegram_id)
    logger.info("Set current_subscription='{}' for user '{}'", subscription_id, telegram_id)


async def delete_current_subscription(service: UserService, telegram_id: int) -> None:
    await service.uow.repository.users.update(
        telegram_id=telegram_id,
        current_subscription_id=None,
    )
    await service.clear_user_cache(telegram_id)
    logger.info("Delete current subscription for user '{}'", telegram_id)


async def add_points(service: UserService, user: BaseUserDto | UserDto, points: int) -> None:
    await service.uow.repository.users.update(
        telegram_id=user.telegram_id,
        points=user.points + points,
    )
    await service.clear_user_cache(user.telegram_id)
    logger.info("Add '{}' points for user '{}'", points, user.telegram_id)


async def reset_rules_acceptance_for_non_privileged(
    service: UserService,
    accepted: bool,
) -> int:
    updated_count = await service.uow.repository.users.set_rules_accepted_for_non_privileged(
        accepted
    )
    await service.uow.commit()

    try:
        pattern = build_key("cache", "get_user", "*")
        await service.redis_repository.delete_pattern(pattern)
    except Exception as exc:
        logger.warning("Failed to invalidate user cache after rules reset: {}", exc)

    await service._clear_list_caches()
    logger.info(
        "Updated rules acceptance for non-privileged users: accepted='{}', updated='{}'",
        accepted,
        updated_count,
    )
    return updated_count
