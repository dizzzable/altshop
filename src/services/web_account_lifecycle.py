from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Optional

from src.core.utils.time import datetime_now
from src.core.utils.validators import validate_web_login_or_raise
from src.infrastructure.database.models.dto import WebAccountDto

if TYPE_CHECKING:
    from .web_account import WebAccountService
else:
    WebAccountService = Any


async def get_by_user_telegram_id(
    service: WebAccountService,
    telegram_id: int,
) -> Optional[WebAccountDto]:
    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_user_telegram_id(telegram_id)
        return WebAccountDto.from_model(account)


async def get_by_username(
    service: WebAccountService,
    username: str,
) -> Optional[WebAccountDto]:
    normalized_username = service.normalize_username(username)
    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_username(normalized_username)
        return WebAccountDto.from_model(account)


async def get_by_email(
    service: WebAccountService,
    email: str,
) -> Optional[WebAccountDto]:
    normalized_email = service.normalize_email(email)
    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_email(normalized_email)
        return WebAccountDto.from_model(account)


async def get_by_id(service: WebAccountService, account_id: int) -> Optional[WebAccountDto]:
    async with service.uow:
        account = await service.uow.repository.web_accounts.get(account_id)
        return WebAccountDto.from_model(account)


async def update(
    service: WebAccountService,
    account_id: int,
    **data: object,
) -> Optional[WebAccountDto]:
    async with service.uow:
        account = await service.uow.repository.web_accounts.update(account_id, **data)
        if not account:
            return None
        await service.uow.commit()
        return WebAccountDto.from_model(account)


async def set_email(
    service: WebAccountService,
    account_id: int,
    email: Optional[str],
) -> Optional[WebAccountDto]:
    normalized_email = service.normalize_email(email) if email else None
    return await service.update(
        account_id,
        email=email,
        email_normalized=normalized_email,
        email_verified_at=None,
    )


async def mark_email_verified(
    service: WebAccountService,
    account_id: int,
) -> Optional[WebAccountDto]:
    return await service.update(account_id, email_verified_at=datetime_now())


async def increment_token_version(
    service: WebAccountService,
    account_id: int,
) -> Optional[WebAccountDto]:
    current = await service.get_by_id(account_id)
    if not current:
        return None
    return await service.update(account_id, token_version=current.token_version + 1)


async def rename_login(
    service: WebAccountService,
    *,
    user_telegram_id: int,
    username: str,
) -> WebAccountDto:
    normalized_username = validate_web_login_or_raise(username)

    async with service.uow:
        account_model = await service.uow.repository.web_accounts.get_by_user_telegram_id(
            user_telegram_id
        )
        if account_model is None:
            raise ValueError("Web account not found")

        existing_username = await service.uow.repository.web_accounts.get_by_username(
            normalized_username
        )
        if existing_username is not None and existing_username.id != account_model.id:
            raise ValueError("Username already taken")

        updated_account = await service.uow.repository.web_accounts.update(
            account_model.id,
            username=normalized_username,
        )
        if updated_account is None:
            raise ValueError("Failed to update web login")

        user_model = await service.uow.repository.users.get(user_telegram_id)
        if user_model is not None:
            profile_sync_data: dict[str, str] = {}
            if not user_model.username or user_model.username == account_model.username:
                profile_sync_data["username"] = normalized_username
            if not user_model.name or user_model.name == account_model.username:
                profile_sync_data["name"] = normalized_username
            if profile_sync_data:
                await service.uow.repository.users.update(
                    telegram_id=user_telegram_id,
                    **profile_sync_data,
                )

        await service.uow.commit()

    dto = WebAccountDto.from_model(updated_account)
    if dto is None:
        raise ValueError("Failed to reload web account after login rename")
    return dto


async def set_link_prompt_snooze(
    service: WebAccountService,
    account_id: int,
    days: int,
) -> Optional[WebAccountDto]:
    return await service.update(
        account_id,
        link_prompt_snooze_until=datetime_now() + timedelta(days=days),
    )


async def clear_link_prompt_snooze(
    service: WebAccountService,
    account_id: int,
) -> Optional[WebAccountDto]:
    return await service.update(account_id, link_prompt_snooze_until=None)


async def rebind_user(
    service: WebAccountService,
    account_id: int,
    target_telegram_id: int,
) -> Optional[WebAccountDto]:
    return await service.update(account_id, user_telegram_id=target_telegram_id)


async def delete_by_id(service: WebAccountService, *, account_id: int) -> bool:
    async with service.uow:
        deleted = await service.uow.repository.web_accounts.delete(account_id)
        if deleted:
            await service.uow.commit()
        return deleted
