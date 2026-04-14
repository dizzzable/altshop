from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.security.jwt_handler import create_access_token, create_refresh_token
from src.core.security.password import hash_password, verify_password
from src.core.utils.time import datetime_now
from src.core.utils.validators import validate_web_login_or_raise
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.infrastructure.database.models.sql import WebAccount

if TYPE_CHECKING:
    from .web_account import WebAccountService
else:
    WebAccountService = Any


type WebAuthPayload = tuple[UserDto, WebAccountDto, str, str, bool]


def normalize_username(username: str) -> str:
    return username.strip().lower()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def build_profile_sync_update_data(
    *,
    current_username: str | None,
    fallback_username: str,
    current_name: str | None,
    fallback_name: str | None,
) -> dict[str, object]:
    # Web accounts are the auth source of truth. Keep the user profile row
    # hydrated with username/name for the rest of the application surface.
    return {
        "username": current_username or fallback_username,
        "name": current_name or fallback_name or fallback_username,
    }


def generate_tokens(
    *,
    account: WebAccountDto,
    user: UserDto,
) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=user.telegram_id,
        username=account.username,
        token_version=account.token_version,
    )
    refresh_token = create_refresh_token(
        user_id=user.telegram_id,
        username=account.username,
        token_version=account.token_version,
    )
    return access_token, refresh_token


async def register(
    service: WebAccountService,
    *,
    username: str,
    password: str,
    telegram_id: Optional[int] = None,
    name: Optional[str] = None,
) -> WebAuthPayload:
    normalized_username = validate_web_login_or_raise(username)
    password_hashed = hash_password(password)

    async with service.uow:
        existing_account = await service.uow.repository.web_accounts.get_by_username(
            normalized_username
        )
        if existing_account:
            raise ValueError("Username already taken")

        created_new_user = False
        if telegram_id is not None:
            user_model = await service.uow.repository.users.get(telegram_id)
            if user_model and user_model.is_blocked:
                raise ValueError("User is blocked")
            if user_model is None:
                user_model = await service._create_real_user(
                    telegram_id=telegram_id,
                    username=normalized_username,
                    name=name,
                )
                created_new_user = True

            linked_account = await service.uow.repository.web_accounts.get_by_user_telegram_id(
                user_model.telegram_id
            )
            if linked_account:
                raise ValueError("Telegram ID already linked. Please login.")
        else:
            user_model = await service._create_shadow_user(
                username=normalized_username,
                name=name,
            )
            created_new_user = True

        web_account = WebAccount(
            user_telegram_id=user_model.telegram_id,
            username=normalized_username,
            password_hash=password_hashed,
            credentials_bootstrapped_at=datetime_now(),
            token_version=0,
        )

        try:
            created_account = await service.uow.repository.web_accounts.create(web_account)
        except IntegrityError as exc:
            await service.uow.rollback()
            raise ValueError("Username already taken") from exc

        await service.uow.repository.users.update(
            telegram_id=user_model.telegram_id,
            **service._build_profile_sync_update_data(
                current_username=user_model.username,
                fallback_username=normalized_username,
                current_name=user_model.name,
                fallback_name=name,
            ),
        )
        await service.uow.commit()

        account_dto = WebAccountDto.from_model(created_account)
        user_dto = UserDto.from_model(
            await service.uow.repository.users.get(user_model.telegram_id)
        )
        if not account_dto or not user_dto:
            raise ValueError("Failed to create web account")

        access_token, refresh_token = service._generate_tokens(
            account=account_dto,
            user=user_dto,
        )

        logger.info(
            f"Web account registered: username={normalized_username}, "
            f"user_telegram_id={user_dto.telegram_id}"
        )
        return (
            user_dto,
            account_dto,
            access_token,
            refresh_token,
            created_new_user,
        )


async def login(
    service: WebAccountService,
    *,
    username: str,
    password: str,
) -> WebAuthPayload:
    normalized_username = service.normalize_username(username)
    async with service.uow:
        account_model = await service.uow.repository.web_accounts.get_by_username(
            normalized_username
        )
        if not account_model or not verify_password(password, account_model.password_hash):
            raise ValueError("Invalid username or password")
        if (
            account_model.requires_password_change
            and account_model.temporary_password_expires_at is not None
            and account_model.temporary_password_expires_at <= datetime_now()
        ):
            raise ValueError("Temporary password expired. Contact support.")

        user_model = await service.uow.repository.users.get(account_model.user_telegram_id)
        if not user_model:
            raise ValueError("User not found")
        if user_model.is_blocked:
            raise ValueError("User is blocked")

        account_dto = WebAccountDto.from_model(account_model)
        user_dto = UserDto.from_model(user_model)
        if not account_dto or not user_dto:
            raise ValueError("Failed to load account")

        access_token, refresh_token = service._generate_tokens(account=account_dto, user=user_dto)
        return (
            user_dto,
            account_dto,
            access_token,
            refresh_token,
            False,
        )


async def get_or_create_for_telegram_user(
    service: WebAccountService,
    *,
    user: UserDto,
    preferred_username: Optional[str] = None,
) -> WebAuthPayload:
    async with service.uow:
        existing_account = await service.uow.repository.web_accounts.get_by_user_telegram_id(
            user.telegram_id
        )
        if existing_account:
            account_dto = WebAccountDto.from_model(existing_account)
            if account_dto is None:
                raise ValueError("Failed to load existing web account")
            access_token, refresh_token = service._generate_tokens(account=account_dto, user=user)
            return (
                user,
                account_dto,
                access_token,
                refresh_token,
                False,
            )

        username = await service._allocate_telegram_username(
            preferred_username=preferred_username,
            telegram_id=user.telegram_id,
        )
        password_hash = hash_password(secrets.token_urlsafe(32))
        created_account = await service.uow.repository.web_accounts.create(
            WebAccount(
                user_telegram_id=user.telegram_id,
                username=username,
                password_hash=password_hash,
                credentials_bootstrapped_at=None,
                token_version=0,
            )
        )
        await service.uow.repository.users.update(
            telegram_id=user.telegram_id,
            **service._build_profile_sync_update_data(
                current_username=user.username,
                fallback_username=username,
                current_name=user.name,
                fallback_name=None,
            ),
        )
        await service.uow.commit()

        account_dto = WebAccountDto.from_model(created_account)
        refreshed_user = UserDto.from_model(
            await service.uow.repository.users.get(user.telegram_id)
        )
        if account_dto is None or refreshed_user is None:
            raise ValueError("Failed to create Telegram web account")

        access_token, refresh_token = service._generate_tokens(
            account=account_dto,
            user=refreshed_user,
        )
        return (
            refreshed_user,
            account_dto,
            access_token,
            refresh_token,
            False,
        )


async def bootstrap_credentials_for_telegram_user(
    service: WebAccountService,
    *,
    telegram_id: int,
    username: str,
    password: str,
    name: Optional[str] = None,
) -> WebAuthPayload:
    normalized_username = validate_web_login_or_raise(username)
    password_hashed = hash_password(password)

    async with service.uow:
        user_model = await service.uow.repository.users.get(telegram_id)
        if user_model is None:
            raise ValueError("Telegram account is required for web bootstrap")
        if user_model.is_blocked:
            raise ValueError("User is blocked")

        existing_username = await service.uow.repository.web_accounts.get_by_username(
            normalized_username
        )
        account_model = await service.uow.repository.web_accounts.get_by_user_telegram_id(
            telegram_id
        )
        if account_model is None:
            if existing_username is not None:
                raise ValueError("Username already taken")
            created_account = await service.uow.repository.web_accounts.create(
                WebAccount(
                    user_telegram_id=user_model.telegram_id,
                    username=normalized_username,
                    password_hash=password_hashed,
                    credentials_bootstrapped_at=datetime_now(),
                    token_version=0,
                )
            )
            await service.uow.repository.users.update(
                telegram_id=user_model.telegram_id,
                **service._build_profile_sync_update_data(
                    current_username=user_model.username,
                    fallback_username=normalized_username,
                    current_name=user_model.name,
                    fallback_name=name,
                ),
            )
            await service.uow.commit()

            account_dto = WebAccountDto.from_model(created_account)
            refreshed_user = UserDto.from_model(
                await service.uow.repository.users.get(user_model.telegram_id)
            )
            if account_dto is None or refreshed_user is None:
                raise ValueError("Failed to bootstrap web account")

            access_token, refresh_token = service._generate_tokens(
                account=account_dto,
                user=refreshed_user,
            )
            return (
                refreshed_user,
                account_dto,
                access_token,
                refresh_token,
                False,
            )

        if account_model.credentials_bootstrapped_at is not None:
            raise ValueError("Web credentials already configured")

        if existing_username and existing_username.id != account_model.id:
            raise ValueError("Username already taken")

        updated_account = await service.uow.repository.web_accounts.update(
            account_model.id,
            username=normalized_username,
            password_hash=password_hashed,
            credentials_bootstrapped_at=datetime_now(),
            requires_password_change=False,
            temporary_password_expires_at=None,
        )
        if updated_account is None:
            raise ValueError("Failed to update web account")

        await service.uow.repository.users.update(
            telegram_id=user_model.telegram_id,
            **service._build_profile_sync_update_data(
                current_username=user_model.username,
                fallback_username=normalized_username,
                current_name=user_model.name,
                fallback_name=name,
            ),
        )
        await service.uow.commit()

        account_dto = WebAccountDto.from_model(updated_account)
        refreshed_user = UserDto.from_model(
            await service.uow.repository.users.get(user_model.telegram_id)
        )
        if account_dto is None or refreshed_user is None:
            raise ValueError("Failed to bootstrap web account")

        access_token, refresh_token = service._generate_tokens(
            account=account_dto,
            user=refreshed_user,
        )
        return (
            refreshed_user,
            account_dto,
            access_token,
            refresh_token,
            False,
        )
