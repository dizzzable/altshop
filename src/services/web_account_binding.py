from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.infrastructure.database.models.sql import User

if TYPE_CHECKING:
    from .web_account import WebAccountService
else:
    WebAccountService = Any


type OccupancySnapshotPayload = tuple[WebAccountDto | None, UserDto | None, bool, bool]


async def inspect_telegram_account_occupancy(
    service: WebAccountService,
    *,
    telegram_id: int,
    exclude_account_id: int | None = None,
) -> OccupancySnapshotPayload:
    async with service.uow:
        return await service._inspect_telegram_account_occupancy_locked(
            telegram_id=telegram_id,
            exclude_account_id=exclude_account_id,
        )


async def cleanup_provisional_account_on_logout(
    service: WebAccountService,
    *,
    web_account_id: int,
    expected_user_telegram_id: int,
) -> bool:
    async with service.uow:
        account_model = await service.uow.repository.web_accounts.get(web_account_id)
        if not account_model or account_model.user_telegram_id != expected_user_telegram_id:
            return False

        occupancy = await service._inspect_telegram_account_occupancy_locked(
            telegram_id=expected_user_telegram_id,
            exclude_account_id=None,
        )
        _web_account, user, _has_material_data, is_reclaimable_provisional = occupancy
        if not is_reclaimable_provisional:
            return False

        await service.uow.repository.web_accounts.delete(web_account_id)

        if user is not None:
            user_has_material_data = await service.uow.repository.users.has_material_data(
                user.telegram_id,
                include_referrals=True,
            )
            if not user_has_material_data:
                await service.uow.repository.users.delete(user.telegram_id)

        await service.uow.commit()
        logger.info(
            "Deleted reclaimable provisional web account '{}' "
            "for telegram_id='{}' during logout",
            web_account_id,
            expected_user_telegram_id,
        )
        return True


async def delete_reclaimable_account_for_telegram_id(
    service: WebAccountService,
    *,
    telegram_id: int,
    exclude_account_id: int | None = None,
) -> bool:
    async with service.uow:
        account_model = await service.uow.repository.web_accounts.get_by_user_telegram_id(
            telegram_id
        )
        if account_model is None:
            return False
        if exclude_account_id is not None and account_model.id == exclude_account_id:
            return False

        occupancy = await service._inspect_telegram_account_occupancy_locked(
            telegram_id=telegram_id,
            exclude_account_id=exclude_account_id,
        )
        web_account, user, _has_material_data, is_reclaimable_provisional = occupancy
        if not is_reclaimable_provisional or web_account is None:
            return False

        await service.uow.repository.web_accounts.delete(web_account.id or 0)
        if user is not None:
            user_has_material_data = await service.uow.repository.users.has_material_data(
                user.telegram_id,
                include_referrals=True,
            )
            if not user_has_material_data:
                await service.uow.repository.users.delete(user.telegram_id)

        await service.uow.commit()
        logger.info(
            "Reclaimed provisional target web account '{}' for telegram_id='{}'",
            web_account.id,
            telegram_id,
        )
        return True


async def inspect_telegram_account_occupancy_locked(
    service: WebAccountService,
    *,
    telegram_id: int,
    exclude_account_id: int | None = None,
) -> OccupancySnapshotPayload:
    account_model = await service.uow.repository.web_accounts.get_by_user_telegram_id(
        telegram_id
    )
    if (
        account_model
        and exclude_account_id is not None
        and account_model.id == exclude_account_id
    ):
        account_model = None
    user_model = await service.uow.repository.users.get(telegram_id)
    has_material_data = (
        await service.uow.repository.users.has_material_data(
            telegram_id,
            include_referrals=True,
        )
        if user_model is not None
        else False
    )
    account_dto = WebAccountDto.from_model(account_model)
    user_dto = UserDto.from_model(user_model)
    is_reclaimable_provisional = bool(
        account_dto is not None
        and account_dto.credentials_bootstrapped_at is None
        and not has_material_data
    )

    return (
        account_dto,
        user_dto,
        has_material_data,
        is_reclaimable_provisional,
    )


async def create_real_user(
    service: WebAccountService,
    *,
    telegram_id: int,
    username: str,
    name: Optional[str],
) -> User:
    referral_code = await service.uow.repository.users.generate_unique_referral_code()
    user = User(
        telegram_id=telegram_id,
        username=username,
        referral_code=referral_code,
        name=name or username,
        role=UserRole.USER,
        language=Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
    )
    created = await service.uow.repository.users.create(user)
    return created


async def create_shadow_user(
    service: WebAccountService,
    *,
    username: str,
    name: Optional[str],
) -> User:
    for _ in range(10):
        candidate_telegram_id = await service._next_shadow_telegram_id()
        referral_code = await service.uow.repository.users.generate_unique_referral_code()
        user = User(
            telegram_id=candidate_telegram_id,
            username=username,
            referral_code=referral_code,
            name=name or username,
            role=UserRole.USER,
            language=Locale.EN,
            personal_discount=0,
            purchase_discount=0,
            points=0,
            is_blocked=False,
            is_bot_blocked=False,
            is_rules_accepted=True,
        )
        try:
            return await service.uow.repository.users.create(user)
        except IntegrityError:
            await service.uow.rollback()
            continue
    raise ValueError("Failed to allocate shadow account")


async def next_shadow_telegram_id(service: WebAccountService) -> int:
    min_telegram_id = await service.uow.repository.users.get_min_telegram_id()
    if min_telegram_id is None or min_telegram_id >= 0:
        return -1
    return min_telegram_id - 1


async def allocate_telegram_username(
    service: WebAccountService,
    *,
    preferred_username: Optional[str],
    telegram_id: int,
) -> str:
    base_username = service.normalize_username(preferred_username or f"tg_{telegram_id}")
    candidate = base_username

    for suffix in range(0, 20):
        if suffix > 0:
            candidate = f"{base_username}_{suffix}"

        existing_account = await service.uow.repository.web_accounts.get_by_username(candidate)
        if existing_account is None:
            return candidate

    raise ValueError("Failed to allocate Telegram web account username")
