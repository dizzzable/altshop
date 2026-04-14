from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import User as AiogramUser
from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.enums import UserRole
from src.core.utils.generators import generate_referral_code
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.sql import User

if TYPE_CHECKING:
    from .user import UserService


async def create(service: UserService, aiogram_user: AiogramUser) -> UserDto:
    user = UserDto(
        telegram_id=aiogram_user.id,
        username=aiogram_user.username,
        referral_code=generate_referral_code(
            aiogram_user.id,
            secret=service.config.crypt_key.get_secret_value(),
        ),
        name=aiogram_user.full_name,
        role=(UserRole.DEV if aiogram_user.id in service.config.bot.dev_id else UserRole.USER),
        language=(
            aiogram_user.language_code
            if aiogram_user.language_code in service.config.locales
            else service.config.default_locale
        ),
    )
    db_user = User(**user.model_dump())
    created = False

    try:
        db_created_user = await service.uow.repository.users.create(db_user)
        await service.uow.commit()
        created = True
    except IntegrityError:
        await service.uow.rollback()
        existing_user = await service.uow.repository.users.get(user.telegram_id)
        if not existing_user:
            raise

        db_created_user = existing_user

    await service.add_to_recent_registered(user.telegram_id)
    await service.clear_user_cache(user.telegram_id)
    if created:
        logger.info("Created new user '{}'", user.telegram_id)
    else:
        logger.warning(
            "User '{}' already exists during create(), reusing existing record",
            user.telegram_id,
        )
    return UserDto.from_model(db_created_user)  # type: ignore[return-value]


async def create_from_panel(service: UserService, remna_user: RemnaUserDto) -> UserDto:
    user = UserDto(
        telegram_id=remna_user.telegram_id,
        referral_code=generate_referral_code(
            remna_user.telegram_id,  # type: ignore[arg-type]
            secret=service.config.crypt_key.get_secret_value(),
        ),
        name=str(remna_user.telegram_id),
        role=UserRole.USER,
        language=service.config.default_locale,
    )
    db_user = User(**user.model_dump())
    created = False

    try:
        db_created_user = await service.uow.repository.users.create(db_user)
        await service.uow.commit()
        created = True
    except IntegrityError:
        await service.uow.rollback()
        existing_user = await service.uow.repository.users.get(user.telegram_id)
        if not existing_user:
            raise

        db_created_user = existing_user

    await service.add_to_recent_registered(user.telegram_id)
    await service.clear_user_cache(user.telegram_id)
    if created:
        logger.info("Created new user '{}' from panel", user.telegram_id)
    else:
        logger.warning(
            "User '{}' already exists during panel sync, reusing existing record",
            user.telegram_id,
        )
    return UserDto.from_model(db_created_user)  # type: ignore[return-value]


async def create_placeholder_user(
    service: UserService,
    *,
    telegram_id: int,
    username: str | None = None,
    name: str | None = None,
) -> UserDto:
    existing_user = await service.get(telegram_id)
    if existing_user is not None:
        return existing_user

    referral_code = await service.uow.repository.users.generate_unique_referral_code()
    user = User(
        telegram_id=telegram_id,
        username=username,
        referral_code=referral_code,
        name=name or username or str(telegram_id),
        role=UserRole.USER,
        language=service.config.default_locale,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
    )
    created = await service.uow.repository.users.create(user)
    await service.uow.commit()
    await service.clear_user_cache(telegram_id)
    logger.info("Created placeholder user '{}'", telegram_id)
    dto = UserDto.from_model(created)
    if dto is None:
        raise ValueError(f"Failed to create placeholder user '{telegram_id}'")
    return dto


async def get(service: UserService, telegram_id: int) -> UserDto | None:
    db_user = await service.uow.repository.users.get(telegram_id)

    if db_user:
        logger.debug("Retrieved user '{}'", telegram_id)
    else:
        logger.warning("User '{}' not found", telegram_id)

    return UserDto.from_model(db_user)


async def update(service: UserService, user: UserDto) -> UserDto | None:
    db_updated_user = await service.uow.repository.users.update(
        telegram_id=user.telegram_id,
        **user.prepare_changed_data(),
    )

    if db_updated_user:
        await service.clear_user_cache(db_updated_user.telegram_id)
        logger.info("Updated user '{}' successfully", user.telegram_id)
    else:
        logger.warning(
            "Attempted to update user '{}', but user was not found or update failed",
            user.telegram_id,
        )

    return UserDto.from_model(db_updated_user)


async def ensure_referral_code(service: UserService, user: UserDto) -> UserDto:
    referral_code = (user.referral_code or "").strip()
    if referral_code:
        return user

    generated_code = await service.uow.repository.users.generate_unique_referral_code()
    db_updated_user = await service.uow.repository.users.update(
        telegram_id=user.telegram_id,
        referral_code=generated_code,
    )
    if not db_updated_user:
        raise ValueError(f"Failed to generate referral code for user '{user.telegram_id}'")

    await service.clear_user_cache(user.telegram_id)
    logger.info("Generated referral code for user '{}'", user.telegram_id)

    updated_user = UserDto.from_model(db_updated_user)
    if not updated_user:
        raise ValueError(
            f"Failed to load user '{user.telegram_id}' after referral code generation"
        )

    return updated_user


async def compare_and_update(
    service: UserService,
    user: UserDto,
    aiogram_user: AiogramUser,
) -> UserDto | None:
    new_username = aiogram_user.username
    if user.username != new_username:
        logger.debug(
            "User '{}' username changed ({} -> {})",
            user.telegram_id,
            user.username,
            new_username,
        )
        user.username = new_username

    new_name = aiogram_user.full_name
    if user.name != new_name:
        logger.debug(
            "User '{}' name changed ({} -> {})",
            user.telegram_id,
            user.name,
            new_name,
        )
        user.name = new_name

    new_language = aiogram_user.language_code
    if user.language != new_language:
        if new_language in service.config.locales:
            logger.debug(
                "User '{}' language changed ({} -> {})",
                user.telegram_id,
                user.language,
                new_language,
            )
            user.language = type(user.language)(new_language)
        else:
            logger.warning(
                "User '{}' language changed. New language is not supported. "
                "Used default ({} -> {})",
                user.telegram_id,
                user.language,
                service.config.default_locale,
            )
            user.language = service.config.default_locale

    if not user.prepare_changed_data():
        return None

    return await service.update(user)


async def delete(service: UserService, user: UserDto) -> bool:
    result = await service.uow.repository.users.delete(user.telegram_id)

    if result:
        await service.clear_user_cache(user.telegram_id)
        await service._remove_from_recent_registered(user.telegram_id)
        await service._remove_from_recent_activity(user.telegram_id)

    logger.info("Deleted user '{}': '{}'", user.telegram_id, result)
    return result


async def get_by_partial_name(service: UserService, query: str) -> list[UserDto]:
    db_users = await service.uow.repository.users.get_by_partial_name(query)
    logger.debug("Retrieved '{}' users for query '{}'", len(db_users), query)
    return UserDto.from_model_list(db_users)


async def get_by_referral_code(service: UserService, referral_code: str) -> UserDto | None:
    user = await service.uow.repository.users.get_by_referral_code(referral_code)
    return UserDto.from_model(user)


async def count(service: UserService) -> int:
    total = await service.uow.repository.users.count()
    logger.debug("Total users count: '{}'", total)
    return total


async def get_by_role(service: UserService, role: UserRole) -> list[UserDto]:
    db_users = await service.uow.repository.users.filter_by_role(role)
    logger.debug("Retrieved '{}' users with role '{}'", len(db_users), role)
    return UserDto.from_model_list(db_users)


async def get_blocked_users(service: UserService) -> list[UserDto]:
    db_users = await service.uow.repository.users.filter_by_blocked(blocked=True)
    logger.debug("Retrieved '{}' blocked users", len(db_users))
    return UserDto.from_model_list(list(reversed(db_users)))


async def get_all(service: UserService) -> list[UserDto]:
    db_users = await service.uow.repository.users.get_all()
    logger.debug("Retrieved '{}' users", len(db_users))
    return UserDto.from_model_list(db_users)
