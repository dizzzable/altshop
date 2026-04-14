from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, cast

from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.infrastructure.database.uow import UnitOfWork

from .web_account_auth import (
    bootstrap_credentials_for_telegram_user as _bootstrap_credentials_for_telegram_user_impl,
)
from .web_account_auth import (
    build_profile_sync_update_data as _build_profile_sync_update_data_impl,
)
from .web_account_auth import (
    generate_tokens as _generate_tokens_impl,
)
from .web_account_auth import (
    get_or_create_for_telegram_user as _get_or_create_for_telegram_user_impl,
)
from .web_account_auth import login as _login_impl
from .web_account_auth import normalize_email as _normalize_email_impl
from .web_account_auth import normalize_username as _normalize_username_impl
from .web_account_auth import register as _register_impl
from .web_account_binding import (
    allocate_telegram_username as _allocate_telegram_username_impl,
)
from .web_account_binding import (
    cleanup_provisional_account_on_logout as _cleanup_provisional_account_on_logout_impl,
)
from .web_account_binding import create_real_user as _create_real_user_impl
from .web_account_binding import create_shadow_user as _create_shadow_user_impl
from .web_account_binding import (
    delete_reclaimable_account_for_telegram_id as _delete_reclaimable_account_for_telegram_id_impl,
)
from .web_account_binding import (
    inspect_telegram_account_occupancy as _inspect_telegram_account_occupancy_impl,
)
from .web_account_binding import (
    inspect_telegram_account_occupancy_locked as _inspect_telegram_account_occupancy_locked_impl,
)
from .web_account_binding import next_shadow_telegram_id as _next_shadow_telegram_id_impl
from .web_account_lifecycle import clear_link_prompt_snooze as _clear_link_prompt_snooze_impl
from .web_account_lifecycle import delete_by_id as _delete_by_id_impl
from .web_account_lifecycle import get_by_email as _get_by_email_impl
from .web_account_lifecycle import get_by_id as _get_by_id_impl
from .web_account_lifecycle import (
    get_by_user_telegram_id as _get_by_user_telegram_id_impl,
)
from .web_account_lifecycle import get_by_username as _get_by_username_impl
from .web_account_lifecycle import (
    increment_token_version as _increment_token_version_impl,
)
from .web_account_lifecycle import mark_email_verified as _mark_email_verified_impl
from .web_account_lifecycle import rebind_user as _rebind_user_impl
from .web_account_lifecycle import rename_login as _rename_login_impl
from .web_account_lifecycle import set_email as _set_email_impl
from .web_account_lifecycle import set_link_prompt_snooze as _set_link_prompt_snooze_impl
from .web_account_lifecycle import update as _update_impl

if TYPE_CHECKING:
    from src.infrastructure.database.models.sql import User

else:
    User = Any


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


def _as_web_account_service(instance: object) -> Any:
    return cast(Any, instance)


def _build_web_auth_result(payload: tuple[UserDto, WebAccountDto, str, str, bool]) -> WebAuthResult:
    user, web_account, access_token, refresh_token, is_new_user = payload
    return WebAuthResult(
        user=user,
        web_account=web_account,
        access_token=access_token,
        refresh_token=refresh_token,
        is_new_user=is_new_user,
    )


def _build_occupancy_snapshot(
    *,
    telegram_id: int,
    payload: tuple[WebAccountDto | None, UserDto | None, bool, bool],
) -> TelegramAccountOccupancySnapshot:
    web_account, user, has_material_data, is_reclaimable_provisional = payload
    return TelegramAccountOccupancySnapshot(
        telegram_id=telegram_id,
        web_account=web_account,
        user=user,
        has_material_data=has_material_data,
        is_reclaimable_provisional=is_reclaimable_provisional,
    )


class WebAccountService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    @staticmethod
    def normalize_username(username: str) -> str:
        return _normalize_username_impl(username)

    @staticmethod
    def normalize_email(email: str) -> str:
        return _normalize_email_impl(email)

    @staticmethod
    def _build_profile_sync_update_data(
        *,
        current_username: str | None,
        fallback_username: str,
        current_name: str | None,
        fallback_name: str | None,
    ) -> dict[str, object]:
        return _build_profile_sync_update_data_impl(
            current_username=current_username,
            fallback_username=fallback_username,
            current_name=current_name,
            fallback_name=fallback_name,
        )

    async def register(
        self,
        *,
        username: str,
        password: str,
        telegram_id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> WebAuthResult:
        return _build_web_auth_result(
            await _register_impl(
                _as_web_account_service(self),
                username=username,
                password=password,
                telegram_id=telegram_id,
                name=name,
            )
        )

    async def login(self, *, username: str, password: str) -> WebAuthResult:
        return _build_web_auth_result(
            await _login_impl(
                _as_web_account_service(self),
                username=username,
                password=password,
            )
        )

    async def get_by_user_telegram_id(self, telegram_id: int) -> Optional[WebAccountDto]:
        return await _get_by_user_telegram_id_impl(_as_web_account_service(self), telegram_id)

    async def get_by_username(self, username: str) -> Optional[WebAccountDto]:
        return await _get_by_username_impl(_as_web_account_service(self), username)

    async def get_by_email(self, email: str) -> Optional[WebAccountDto]:
        return await _get_by_email_impl(_as_web_account_service(self), email)

    async def get_by_id(self, account_id: int) -> Optional[WebAccountDto]:
        return await _get_by_id_impl(_as_web_account_service(self), account_id)

    async def update(self, account_id: int, **data: object) -> Optional[WebAccountDto]:
        return await _update_impl(_as_web_account_service(self), account_id, **data)

    async def set_email(self, account_id: int, email: Optional[str]) -> Optional[WebAccountDto]:
        return await _set_email_impl(_as_web_account_service(self), account_id, email)

    async def mark_email_verified(self, account_id: int) -> Optional[WebAccountDto]:
        return await _mark_email_verified_impl(_as_web_account_service(self), account_id)

    async def increment_token_version(self, account_id: int) -> Optional[WebAccountDto]:
        return await _increment_token_version_impl(_as_web_account_service(self), account_id)

    async def get_or_create_for_telegram_user(
        self,
        *,
        user: UserDto,
        preferred_username: Optional[str] = None,
    ) -> WebAuthResult:
        return _build_web_auth_result(
            await _get_or_create_for_telegram_user_impl(
                _as_web_account_service(self),
                user=user,
                preferred_username=preferred_username,
            )
        )

    async def bootstrap_credentials_for_telegram_user(
        self,
        *,
        telegram_id: int,
        username: str,
        password: str,
        name: Optional[str] = None,
    ) -> WebAuthResult:
        return _build_web_auth_result(
            await _bootstrap_credentials_for_telegram_user_impl(
                _as_web_account_service(self),
                telegram_id=telegram_id,
                username=username,
                password=password,
                name=name,
            )
        )

    async def rename_login(
        self,
        *,
        user_telegram_id: int,
        username: str,
    ) -> WebAccountDto:
        return await _rename_login_impl(
            _as_web_account_service(self),
            user_telegram_id=user_telegram_id,
            username=username,
        )

    async def set_link_prompt_snooze(self, account_id: int, days: int) -> Optional[WebAccountDto]:
        return await _set_link_prompt_snooze_impl(
            _as_web_account_service(self),
            account_id,
            days,
        )

    async def clear_link_prompt_snooze(self, account_id: int) -> Optional[WebAccountDto]:
        return await _clear_link_prompt_snooze_impl(_as_web_account_service(self), account_id)

    async def rebind_user(
        self, account_id: int, target_telegram_id: int
    ) -> Optional[WebAccountDto]:
        return await _rebind_user_impl(
            _as_web_account_service(self),
            account_id,
            target_telegram_id,
        )

    async def delete_by_id(self, *, account_id: int) -> bool:
        return await _delete_by_id_impl(_as_web_account_service(self), account_id=account_id)

    async def inspect_telegram_account_occupancy(
        self,
        *,
        telegram_id: int,
        exclude_account_id: int | None = None,
    ) -> TelegramAccountOccupancySnapshot:
        return _build_occupancy_snapshot(
            telegram_id=telegram_id,
            payload=await _inspect_telegram_account_occupancy_impl(
                _as_web_account_service(self),
                telegram_id=telegram_id,
                exclude_account_id=exclude_account_id,
            ),
        )

    async def cleanup_provisional_account_on_logout(
        self,
        *,
        web_account_id: int,
        expected_user_telegram_id: int,
    ) -> bool:
        return await _cleanup_provisional_account_on_logout_impl(
            _as_web_account_service(self),
            web_account_id=web_account_id,
            expected_user_telegram_id=expected_user_telegram_id,
        )

    async def delete_reclaimable_account_for_telegram_id(
        self,
        *,
        telegram_id: int,
        exclude_account_id: int | None = None,
    ) -> bool:
        return await _delete_reclaimable_account_for_telegram_id_impl(
            _as_web_account_service(self),
            telegram_id=telegram_id,
            exclude_account_id=exclude_account_id,
        )

    async def _inspect_telegram_account_occupancy_locked(
        self,
        *,
        telegram_id: int,
        exclude_account_id: int | None = None,
    ) -> tuple[WebAccountDto | None, UserDto | None, bool, bool]:
        return await _inspect_telegram_account_occupancy_locked_impl(
            _as_web_account_service(self),
            telegram_id=telegram_id,
            exclude_account_id=exclude_account_id,
        )

    async def _create_real_user(
        self, *, telegram_id: int, username: str, name: Optional[str]
    ) -> User:
        return await _create_real_user_impl(
            _as_web_account_service(self),
            telegram_id=telegram_id,
            username=username,
            name=name,
        )

    async def _create_shadow_user(self, *, username: str, name: Optional[str]) -> User:
        return await _create_shadow_user_impl(
            _as_web_account_service(self),
            username=username,
            name=name,
        )

    async def _next_shadow_telegram_id(self) -> int:
        return await _next_shadow_telegram_id_impl(_as_web_account_service(self))

    async def _allocate_telegram_username(
        self,
        *,
        preferred_username: Optional[str],
        telegram_id: int,
    ) -> str:
        return await _allocate_telegram_username_impl(
            _as_web_account_service(self),
            preferred_username=preferred_username,
            telegram_id=telegram_id,
        )

    def _generate_tokens(self, *, account: WebAccountDto, user: UserDto) -> tuple[str, str]:
        return _generate_tokens_impl(account=account, user=user)
