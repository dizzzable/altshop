from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.enums import Locale, UserRole
from src.core.security.jwt_handler import create_access_token, create_refresh_token
from src.core.security.password import hash_password, verify_password
from src.core.utils.time import datetime_now
from src.core.utils.validators import validate_web_login_or_raise
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.infrastructure.database.models.sql import User, WebAccount
from src.infrastructure.database.uow import UnitOfWork


@dataclass
class WebAuthResult:
    user: UserDto
    web_account: WebAccountDto
    access_token: str
    refresh_token: str
    is_new_user: bool = False


@dataclass(slots=True, frozen=True)
class TelegramAccountOccupancySnapshot:
    telegram_id: int
    web_account: WebAccountDto | None
    user: UserDto | None
    has_material_data: bool
    is_reclaimable_provisional: bool


class WebAccountService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    @staticmethod
    def normalize_username(username: str) -> str:
        return username.strip().lower()

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _build_profile_sync_update_data(
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

    async def register(
        self,
        *,
        username: str,
        password: str,
        telegram_id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> WebAuthResult:
        normalized_username = validate_web_login_or_raise(username)
        password_hashed = hash_password(password)

        async with self.uow:
            existing_account = await self.uow.repository.web_accounts.get_by_username(
                normalized_username
            )
            if existing_account:
                raise ValueError("Username already taken")

            created_new_user = False
            if telegram_id is not None:
                user_model = await self.uow.repository.users.get(telegram_id)
                if user_model and user_model.is_blocked:
                    raise ValueError("User is blocked")
                if user_model is None:
                    user_model = await self._create_real_user(
                        telegram_id=telegram_id,
                        username=normalized_username,
                        name=name,
                    )
                    created_new_user = True

                linked_account = await self.uow.repository.web_accounts.get_by_user_telegram_id(
                    user_model.telegram_id
                )
                if linked_account:
                    raise ValueError("Telegram ID already linked. Please login.")
            else:
                user_model = await self._create_shadow_user(
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
                created_account = await self.uow.repository.web_accounts.create(web_account)
            except IntegrityError as exc:
                await self.uow.rollback()
                raise ValueError("Username already taken") from exc

            await self.uow.repository.users.update(
                telegram_id=user_model.telegram_id,
                **self._build_profile_sync_update_data(
                    current_username=user_model.username,
                    fallback_username=normalized_username,
                    current_name=user_model.name,
                    fallback_name=name,
                ),
            )
            await self.uow.commit()

            account_dto = WebAccountDto.from_model(created_account)
            user_dto = UserDto.from_model(
                await self.uow.repository.users.get(user_model.telegram_id)
            )
            if not account_dto or not user_dto:
                raise ValueError("Failed to create web account")

            access_token, refresh_token = self._generate_tokens(
                account=account_dto,
                user=user_dto,
            )

            logger.info(
                f"Web account registered: username={normalized_username}, "
                f"user_telegram_id={user_dto.telegram_id}"
            )
            return WebAuthResult(
                user=user_dto,
                web_account=account_dto,
                access_token=access_token,
                refresh_token=refresh_token,
                is_new_user=created_new_user,
            )

    async def login(self, *, username: str, password: str) -> WebAuthResult:
        normalized_username = self.normalize_username(username)
        async with self.uow:
            account_model = await self.uow.repository.web_accounts.get_by_username(
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

            user_model = await self.uow.repository.users.get(account_model.user_telegram_id)
            if not user_model:
                raise ValueError("User not found")
            if user_model.is_blocked:
                raise ValueError("User is blocked")

            account_dto = WebAccountDto.from_model(account_model)
            user_dto = UserDto.from_model(user_model)
            if not account_dto or not user_dto:
                raise ValueError("Failed to load account")

            access_token, refresh_token = self._generate_tokens(account=account_dto, user=user_dto)
            return WebAuthResult(
                user=user_dto,
                web_account=account_dto,
                access_token=access_token,
                refresh_token=refresh_token,
                is_new_user=False,
            )

    async def get_by_user_telegram_id(self, telegram_id: int) -> Optional[WebAccountDto]:
        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_user_telegram_id(telegram_id)
            return WebAccountDto.from_model(account)

    async def get_by_username(self, username: str) -> Optional[WebAccountDto]:
        normalized_username = self.normalize_username(username)
        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_username(normalized_username)
            return WebAccountDto.from_model(account)

    async def get_by_email(self, email: str) -> Optional[WebAccountDto]:
        normalized_email = self.normalize_email(email)
        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_email(normalized_email)
            return WebAccountDto.from_model(account)

    async def get_by_id(self, account_id: int) -> Optional[WebAccountDto]:
        async with self.uow:
            account = await self.uow.repository.web_accounts.get(account_id)
            return WebAccountDto.from_model(account)

    async def update(self, account_id: int, **data: object) -> Optional[WebAccountDto]:
        async with self.uow:
            account = await self.uow.repository.web_accounts.update(account_id, **data)
            if not account:
                return None
            await self.uow.commit()
            return WebAccountDto.from_model(account)

    async def set_email(self, account_id: int, email: Optional[str]) -> Optional[WebAccountDto]:
        normalized_email = self.normalize_email(email) if email else None
        return await self.update(
            account_id,
            email=email,
            email_normalized=normalized_email,
            email_verified_at=None,
        )

    async def mark_email_verified(self, account_id: int) -> Optional[WebAccountDto]:
        return await self.update(account_id, email_verified_at=datetime_now())

    async def increment_token_version(self, account_id: int) -> Optional[WebAccountDto]:
        current = await self.get_by_id(account_id)
        if not current:
            return None
        return await self.update(account_id, token_version=current.token_version + 1)

    async def get_or_create_for_telegram_user(
        self,
        *,
        user: UserDto,
        preferred_username: Optional[str] = None,
    ) -> WebAuthResult:
        async with self.uow:
            existing_account = await self.uow.repository.web_accounts.get_by_user_telegram_id(
                user.telegram_id
            )
            if existing_account:
                account_dto = WebAccountDto.from_model(existing_account)
                if account_dto is None:
                    raise ValueError("Failed to load existing web account")
                access_token, refresh_token = self._generate_tokens(account=account_dto, user=user)
                return WebAuthResult(
                    user=user,
                    web_account=account_dto,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    is_new_user=False,
                )

            username = await self._allocate_telegram_username(
                preferred_username=preferred_username,
                telegram_id=user.telegram_id,
            )
            password_hash = hash_password(secrets.token_urlsafe(32))
            created_account = await self.uow.repository.web_accounts.create(
                WebAccount(
                    user_telegram_id=user.telegram_id,
                    username=username,
                    password_hash=password_hash,
                    credentials_bootstrapped_at=None,
                    token_version=0,
                )
            )
            await self.uow.repository.users.update(
                telegram_id=user.telegram_id,
                **self._build_profile_sync_update_data(
                    current_username=user.username,
                    fallback_username=username,
                    current_name=user.name,
                    fallback_name=None,
                ),
            )
            await self.uow.commit()

            account_dto = WebAccountDto.from_model(created_account)
            refreshed_user = UserDto.from_model(
                await self.uow.repository.users.get(user.telegram_id)
            )
            if account_dto is None or refreshed_user is None:
                raise ValueError("Failed to create Telegram web account")

            access_token, refresh_token = self._generate_tokens(
                account=account_dto,
                user=refreshed_user,
            )
            return WebAuthResult(
                user=refreshed_user,
                web_account=account_dto,
                access_token=access_token,
                refresh_token=refresh_token,
                is_new_user=False,
            )

    async def bootstrap_credentials_for_telegram_user(
        self,
        *,
        telegram_id: int,
        username: str,
        password: str,
        name: Optional[str] = None,
    ) -> WebAuthResult:
        normalized_username = validate_web_login_or_raise(username)
        password_hashed = hash_password(password)

        async with self.uow:
            user_model = await self.uow.repository.users.get(telegram_id)
            if user_model is None:
                raise ValueError("Telegram account is required for web bootstrap")
            if user_model.is_blocked:
                raise ValueError("User is blocked")

            existing_username = await self.uow.repository.web_accounts.get_by_username(
                normalized_username
            )
            account_model = await self.uow.repository.web_accounts.get_by_user_telegram_id(
                telegram_id
            )
            if account_model is None:
                if existing_username is not None:
                    raise ValueError("Username already taken")
                created_account = await self.uow.repository.web_accounts.create(
                    WebAccount(
                        user_telegram_id=user_model.telegram_id,
                        username=normalized_username,
                        password_hash=password_hashed,
                        credentials_bootstrapped_at=datetime_now(),
                        token_version=0,
                    )
                )
                await self.uow.repository.users.update(
                    telegram_id=user_model.telegram_id,
                    **self._build_profile_sync_update_data(
                        current_username=user_model.username,
                        fallback_username=normalized_username,
                        current_name=user_model.name,
                        fallback_name=name,
                    ),
                )
                await self.uow.commit()

                account_dto = WebAccountDto.from_model(created_account)
                refreshed_user = UserDto.from_model(
                    await self.uow.repository.users.get(user_model.telegram_id)
                )
                if account_dto is None or refreshed_user is None:
                    raise ValueError("Failed to bootstrap web account")

                access_token, refresh_token = self._generate_tokens(
                    account=account_dto,
                    user=refreshed_user,
                )
                return WebAuthResult(
                    user=refreshed_user,
                    web_account=account_dto,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    is_new_user=False,
                )

            if account_model.credentials_bootstrapped_at is not None:
                raise ValueError("Web credentials already configured")

            if existing_username and existing_username.id != account_model.id:
                raise ValueError("Username already taken")

            updated_account = await self.uow.repository.web_accounts.update(
                account_model.id,
                username=normalized_username,
                password_hash=password_hashed,
                credentials_bootstrapped_at=datetime_now(),
                requires_password_change=False,
                temporary_password_expires_at=None,
            )
            if updated_account is None:
                raise ValueError("Failed to update web account")

            await self.uow.repository.users.update(
                telegram_id=user_model.telegram_id,
                **self._build_profile_sync_update_data(
                    current_username=user_model.username,
                    fallback_username=normalized_username,
                    current_name=user_model.name,
                    fallback_name=name,
                ),
            )
            await self.uow.commit()

            account_dto = WebAccountDto.from_model(updated_account)
            refreshed_user = UserDto.from_model(
                await self.uow.repository.users.get(user_model.telegram_id)
            )
            if account_dto is None or refreshed_user is None:
                raise ValueError("Failed to bootstrap web account")

            access_token, refresh_token = self._generate_tokens(
                account=account_dto,
                user=refreshed_user,
            )
            return WebAuthResult(
                user=refreshed_user,
                web_account=account_dto,
                access_token=access_token,
                refresh_token=refresh_token,
                is_new_user=False,
            )


    async def rename_login(
        self,
        *,
        user_telegram_id: int,
        username: str,
    ) -> WebAccountDto:
        normalized_username = validate_web_login_or_raise(username)

        async with self.uow:
            account_model = await self.uow.repository.web_accounts.get_by_user_telegram_id(
                user_telegram_id
            )
            if account_model is None:
                raise ValueError("Web account not found")

            existing_username = await self.uow.repository.web_accounts.get_by_username(
                normalized_username
            )
            if existing_username is not None and existing_username.id != account_model.id:
                raise ValueError("Username already taken")

            updated_account = await self.uow.repository.web_accounts.update(
                account_model.id,
                username=normalized_username,
            )
            if updated_account is None:
                raise ValueError("Failed to update web login")

            user_model = await self.uow.repository.users.get(user_telegram_id)
            if user_model is not None:
                profile_sync_data: dict[str, str] = {}
                if not user_model.username or user_model.username == account_model.username:
                    profile_sync_data["username"] = normalized_username
                if not user_model.name or user_model.name == account_model.username:
                    profile_sync_data["name"] = normalized_username
                if profile_sync_data:
                    await self.uow.repository.users.update(
                        telegram_id=user_telegram_id,
                        **profile_sync_data,
                    )

            await self.uow.commit()

        dto = WebAccountDto.from_model(updated_account)
        if dto is None:
            raise ValueError("Failed to reload web account after login rename")
        return dto

    async def set_link_prompt_snooze(self, account_id: int, days: int) -> Optional[WebAccountDto]:
        return await self.update(
            account_id,
            link_prompt_snooze_until=datetime_now() + timedelta(days=days),
        )

    async def clear_link_prompt_snooze(self, account_id: int) -> Optional[WebAccountDto]:
        return await self.update(account_id, link_prompt_snooze_until=None)

    async def rebind_user(
        self, account_id: int, target_telegram_id: int
    ) -> Optional[WebAccountDto]:
        return await self.update(account_id, user_telegram_id=target_telegram_id)

    async def delete_by_id(self, *, account_id: int) -> bool:
        async with self.uow:
            deleted = await self.uow.repository.web_accounts.delete(account_id)
            if deleted:
                await self.uow.commit()
            return deleted

    async def inspect_telegram_account_occupancy(
        self,
        *,
        telegram_id: int,
        exclude_account_id: int | None = None,
    ) -> TelegramAccountOccupancySnapshot:
        async with self.uow:
            return await self._inspect_telegram_account_occupancy_locked(
                telegram_id=telegram_id,
                exclude_account_id=exclude_account_id,
            )

    async def cleanup_provisional_account_on_logout(
        self,
        *,
        web_account_id: int,
        expected_user_telegram_id: int,
    ) -> bool:
        async with self.uow:
            account_model = await self.uow.repository.web_accounts.get(web_account_id)
            if not account_model or account_model.user_telegram_id != expected_user_telegram_id:
                return False

            occupancy = await self._inspect_telegram_account_occupancy_locked(
                telegram_id=expected_user_telegram_id,
                exclude_account_id=None,
            )
            if not occupancy.is_reclaimable_provisional:
                return False

            await self.uow.repository.web_accounts.delete(web_account_id)

            if occupancy.user is not None:
                user_has_material_data = await self.uow.repository.users.has_material_data(
                    occupancy.user.telegram_id,
                    include_referrals=True,
                )
                if not user_has_material_data:
                    await self.uow.repository.users.delete(occupancy.user.telegram_id)

            await self.uow.commit()
            logger.info(
                "Deleted reclaimable provisional web account '{}' "
                "for telegram_id='{}' during logout",
                web_account_id,
                expected_user_telegram_id,
            )
            return True

    async def delete_reclaimable_account_for_telegram_id(
        self,
        *,
        telegram_id: int,
        exclude_account_id: int | None = None,
    ) -> bool:
        async with self.uow:
            account_model = await self.uow.repository.web_accounts.get_by_user_telegram_id(
                telegram_id
            )
            if account_model is None:
                return False
            if exclude_account_id is not None and account_model.id == exclude_account_id:
                return False

            occupancy = await self._inspect_telegram_account_occupancy_locked(
                telegram_id=telegram_id,
                exclude_account_id=exclude_account_id,
            )
            if not occupancy.is_reclaimable_provisional or occupancy.web_account is None:
                return False

            await self.uow.repository.web_accounts.delete(occupancy.web_account.id or 0)
            if occupancy.user is not None:
                user_has_material_data = await self.uow.repository.users.has_material_data(
                    occupancy.user.telegram_id,
                    include_referrals=True,
                )
                if not user_has_material_data:
                    await self.uow.repository.users.delete(occupancy.user.telegram_id)

            await self.uow.commit()
            logger.info(
                "Reclaimed provisional target web account '{}' for telegram_id='{}'",
                occupancy.web_account.id,
                telegram_id,
            )
            return True

    async def _inspect_telegram_account_occupancy_locked(
        self,
        *,
        telegram_id: int,
        exclude_account_id: int | None = None,
    ) -> TelegramAccountOccupancySnapshot:
        account_model = await self.uow.repository.web_accounts.get_by_user_telegram_id(
            telegram_id
        )
        if (
            account_model
            and exclude_account_id is not None
            and account_model.id == exclude_account_id
        ):
            account_model = None
        user_model = await self.uow.repository.users.get(telegram_id)
        has_material_data = (
            await self.uow.repository.users.has_material_data(
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

        return TelegramAccountOccupancySnapshot(
            telegram_id=telegram_id,
            web_account=account_dto,
            user=user_dto,
            has_material_data=has_material_data,
            is_reclaimable_provisional=is_reclaimable_provisional,
        )

    async def _create_real_user(
        self, *, telegram_id: int, username: str, name: Optional[str]
    ) -> User:
        referral_code = await self.uow.repository.users.generate_unique_referral_code()
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
        created = await self.uow.repository.users.create(user)
        return created

    async def _create_shadow_user(self, *, username: str, name: Optional[str]) -> User:
        for _ in range(10):
            candidate_telegram_id = await self._next_shadow_telegram_id()
            referral_code = await self.uow.repository.users.generate_unique_referral_code()
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
                return await self.uow.repository.users.create(user)
            except IntegrityError:
                await self.uow.rollback()
                continue
        raise ValueError("Failed to allocate shadow account")

    async def _next_shadow_telegram_id(self) -> int:
        min_telegram_id = await self.uow.repository.users.get_min_telegram_id()
        if min_telegram_id is None or min_telegram_id >= 0:
            return -1
        return min_telegram_id - 1

    async def _allocate_telegram_username(
        self,
        *,
        preferred_username: Optional[str],
        telegram_id: int,
    ) -> str:
        base_username = self.normalize_username(preferred_username or f"tg_{telegram_id}")
        candidate = base_username

        for suffix in range(0, 20):
            if suffix > 0:
                candidate = f"{base_username}_{suffix}"

            existing_account = await self.uow.repository.web_accounts.get_by_username(candidate)
            if existing_account is None:
                return candidate

        raise ValueError("Failed to allocate Telegram web account username")

    def _generate_tokens(self, *, account: WebAccountDto, user: UserDto) -> tuple[str, str]:
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
