from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import WebAccountDto
from src.infrastructure.database.models.sql import User, WebAccount

if TYPE_CHECKING:
    from .telegram_link import TelegramLinkService


async def safe_auto_link(
    service: TelegramLinkService,
    *,
    web_account_id: int,
    telegram_id: int,
) -> WebAccountDto:
    async with service.uow:
        current_account = await service._get_web_account_or_error(web_account_id)
        already_linked = await service._handle_already_linked_account(
            current_account=current_account,
            telegram_id=telegram_id,
        )
        if already_linked:
            return already_linked

        await service._assert_telegram_not_linked_elsewhere(
            current_account_id=current_account.id,
            telegram_id=telegram_id,
        )
        source_user = await service._get_source_user_or_error(current_account.user_telegram_id)
        target_user = await service._get_or_create_target_user(
            telegram_id=telegram_id,
            source_user=source_user,
        )
        source_has_data = await service._assert_merge_allowed(
            source_user=source_user,
            target_user=target_user,
        )

        if source_user.telegram_id != target_user.telegram_id and source_has_data:
            try:
                await service.uow.repository.users.reassign_telegram_id_references(
                    source_telegram_id=source_user.telegram_id,
                    target_telegram_id=target_user.telegram_id,
                )
            except IntegrityError as exception:
                logger.warning(
                    "Automatic Telegram link merge failed for source='{}' target='{}': {}",
                    source_user.telegram_id,
                    target_user.telegram_id,
                    exception,
                )
                raise service._telegram_link_error(
                    code="MANUAL_MERGE_REQUIRED",
                    message="Automatic merge failed because referral attribution already exists.",
                ) from exception

        await service._merge_user_values(
            source_user_telegram_id=source_user.telegram_id,
            target_user_telegram_id=target_user.telegram_id,
            source_has_data=source_has_data,
        )

        updated_account = await service.uow.repository.web_accounts.update(
            current_account.id,
            user_telegram_id=target_user.telegram_id,
            token_version=current_account.token_version + 1,
            link_prompt_snooze_until=None,
        )
        if not updated_account:
            raise service._telegram_link_error(
                code="LINK_UPDATE_FAILED",
                message="Failed to link Telegram account.",
            )

        if source_user.telegram_id < 0 and source_user.telegram_id != target_user.telegram_id:
            await service.uow.repository.users.delete(source_user.telegram_id)

        await service.uow.commit()

    account_dto = WebAccountDto.from_model(updated_account)
    if not account_dto:
        raise service._telegram_link_error(
            code="LINK_UPDATE_FAILED",
            message="Failed to link Telegram account.",
        )
    return account_dto


async def get_web_account_or_error(
    service: TelegramLinkService,
    web_account_id: int,
) -> WebAccount:
    account = await service.uow.repository.web_accounts.get(web_account_id)
    if not account:
        raise service._telegram_link_error(
            code="WEB_ACCOUNT_NOT_FOUND",
            message="Web account not found.",
        )
    return account


async def handle_already_linked_account(
    service: TelegramLinkService,
    *,
    current_account: WebAccount,
    telegram_id: int,
) -> Optional[WebAccountDto]:
    if current_account.user_telegram_id != telegram_id:
        return None

    updated = await service.uow.repository.web_accounts.update(
        current_account.id,
        link_prompt_snooze_until=None,
    )
    await service.uow.commit()
    account_dto = WebAccountDto.from_model(updated)
    if not account_dto:
        raise service._telegram_link_error(
            code="WEB_ACCOUNT_NOT_FOUND",
            message="Web account not found.",
        )
    return account_dto


async def assert_telegram_not_linked_elsewhere(
    service: TelegramLinkService,
    *,
    current_account_id: int,
    telegram_id: int,
) -> None:
    other_account = await service.uow.repository.web_accounts.get_by_user_telegram_id(telegram_id)
    if other_account and other_account.id != current_account_id:
        raise service._telegram_link_error(
            code="TELEGRAM_ALREADY_LINKED",
            message="Telegram ID is already linked to another account.",
        )


async def get_source_user_or_error(
    service: TelegramLinkService,
    source_telegram_id: int,
) -> User:
    source_user = await service.uow.repository.users.get(source_telegram_id)
    if not source_user:
        raise service._telegram_link_error(
            code="SOURCE_USER_NOT_FOUND",
            message="Source profile not found.",
        )
    return source_user


async def get_or_create_target_user(
    service: TelegramLinkService,
    *,
    telegram_id: int,
    source_user: User,
) -> User:
    target_user = await service.uow.repository.users.get(telegram_id)
    if target_user:
        return target_user
    return await service._create_target_user(
        telegram_id=telegram_id,
        source_user=source_user,
    )


async def assert_merge_allowed(
    service: TelegramLinkService,
    *,
    source_user: User,
    target_user: User,
) -> bool:
    source_has_data = await service.uow.repository.users.has_material_data(
        source_user.telegram_id,
        include_referrals=True,
    )
    source_has_conflicting_data = await service.uow.repository.users.has_material_data(
        source_user.telegram_id,
        include_referrals=False,
    )
    target_has_conflicting_data = await service.uow.repository.users.has_material_data(
        target_user.telegram_id,
        include_referrals=False,
    )
    is_source_provisional = source_user.telegram_id < 0

    if source_has_conflicting_data and target_has_conflicting_data and not is_source_provisional:
        raise service._telegram_link_error(
            code="MANUAL_MERGE_REQUIRED",
            message="Both profiles contain material data. Manual merge is required.",
        )

    return source_has_data


async def create_target_user(
    service: TelegramLinkService,
    *,
    telegram_id: int,
    source_user: User,
) -> User:
    referral_code = await service.uow.repository.users.generate_unique_referral_code()
    target = User(
        telegram_id=telegram_id,
        username=source_user.username,
        referral_code=referral_code,
        name=source_user.name or str(telegram_id),
        role=source_user.role or UserRole.USER,
        language=source_user.language or Locale.EN,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
    )
    try:
        return await service.uow.repository.users.create(target)
    except IntegrityError:
        existing = await service.uow.repository.users.get(telegram_id)
        if not existing:
            raise
        return existing


async def merge_user_values(
    service: TelegramLinkService,
    *,
    source_user_telegram_id: int,
    target_user_telegram_id: int,
    source_has_data: bool,
) -> None:
    source_user = await service.uow.repository.users.get(source_user_telegram_id)
    target_user = await service.uow.repository.users.get(target_user_telegram_id)
    if not source_user or not target_user:
        return

    update_data: dict[str, object] = {}
    if not target_user.username and source_user.username:
        update_data["username"] = source_user.username

    if (
        not target_user.name or target_user.name.strip() == str(target_user.telegram_id)
    ) and source_user.name:
        update_data["name"] = source_user.name

    if source_has_data:
        update_data["points"] = max(target_user.points, source_user.points)
        update_data["personal_discount"] = max(
            target_user.personal_discount,
            source_user.personal_discount,
        )
        update_data["purchase_discount"] = max(
            target_user.purchase_discount,
            source_user.purchase_discount,
        )

    if update_data:
        await service.uow.repository.users.update(target_user.telegram_id, **update_data)
