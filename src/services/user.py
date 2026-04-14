from typing import Optional, Union

from aiogram import Bot
from aiogram.types import Message
from aiogram.types import User as AiogramUser
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import TIME_1M, TIME_10M
from src.core.enums import Currency, UserRole
from src.core.storage.key_builder import StorageKey
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.redis import RedisRepository, redis_cache

from .base import BaseService
from .user_lifecycle import (
    compare_and_update as _compare_and_update_impl,
)
from .user_lifecycle import (
    count as _count_impl,
)
from .user_lifecycle import (
    create as _create_impl,
)
from .user_lifecycle import (
    create_from_panel as _create_from_panel_impl,
)
from .user_lifecycle import (
    create_placeholder_user as _create_placeholder_user_impl,
)
from .user_lifecycle import (
    delete as _delete_impl,
)
from .user_lifecycle import (
    ensure_referral_code as _ensure_referral_code_impl,
)
from .user_lifecycle import (
    get as _get_impl,
)
from .user_lifecycle import (
    get_all as _get_all_impl,
)
from .user_lifecycle import (
    get_blocked_users as _get_blocked_users_impl,
)
from .user_lifecycle import (
    get_by_partial_name as _get_by_partial_name_impl,
)
from .user_lifecycle import (
    get_by_referral_code as _get_by_referral_code_impl,
)
from .user_lifecycle import (
    get_by_role as _get_by_role_impl,
)
from .user_lifecycle import (
    update as _update_impl,
)
from .user_mutations import (
    add_points as _add_points_impl,
)
from .user_mutations import (
    delete_current_subscription as _delete_current_subscription_impl,
)
from .user_mutations import (
    reset_rules_acceptance_for_non_privileged as _reset_rules_acceptance_impl,
)
from .user_mutations import (
    set_block as _set_block_impl,
)
from .user_mutations import (
    set_bot_blocked as _set_bot_blocked_impl,
)
from .user_mutations import (
    set_current_subscription as _set_current_subscription_impl,
)
from .user_mutations import (
    set_partner_balance_currency_override as _set_partner_balance_currency_override_impl,
)
from .user_mutations import (
    set_purchase_discount as _set_purchase_discount_impl,
)
from .user_mutations import (
    set_role as _set_role_impl,
)
from .user_recent import (
    add_to_recent_list as _add_to_recent_list_impl,
)
from .user_recent import (
    add_to_recent_registered as _add_to_recent_registered_impl,
)
from .user_recent import (
    clear_list_caches as _clear_list_caches_impl,
)
from .user_recent import (
    clear_user_cache as _clear_user_cache_impl,
)
from .user_recent import (
    get_recent_activity as _get_recent_activity_impl,
)
from .user_recent import (
    get_recent_activity_users as _get_recent_activity_users_impl,
)
from .user_recent import (
    get_recent_registered as _get_recent_registered_impl,
)
from .user_recent import (
    get_recent_registered_users as _get_recent_registered_users_impl,
)
from .user_recent import (
    remove_from_recent_activity as _remove_from_recent_activity_impl,
)
from .user_recent import (
    remove_from_recent_registered as _remove_from_recent_registered_impl,
)
from .user_recent import (
    update_recent_activity as _update_recent_activity_impl,
)
from .user_search import (
    search_users as _search_users_impl,
)
from .user_search import (
    search_users_by_forward as _search_users_by_forward_impl,
)
from .user_search import (
    search_users_by_login_or_name as _search_users_by_login_or_name_impl,
)
from .user_search import (
    search_users_by_query as _search_users_by_query_impl,
)
from .user_search import (
    search_users_by_remnashop_id as _search_users_by_remnashop_id_impl,
)
from .user_search import (
    search_users_by_telegram_id as _search_users_by_telegram_id_impl,
)


class UserService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    @staticmethod
    def _user_roles() -> tuple[UserRole, ...]:
        return tuple(UserRole)

    async def create(self, aiogram_user: AiogramUser) -> UserDto:
        return await _create_impl(self, aiogram_user)

    async def create_from_panel(self, remna_user: RemnaUserDto) -> UserDto:
        return await _create_from_panel_impl(self, remna_user)

    async def create_placeholder_user(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        name: str | None = None,
    ) -> UserDto:
        return await _create_placeholder_user_impl(
            self,
            telegram_id=telegram_id,
            username=username,
            name=name,
        )

    @redis_cache(prefix="get_user", ttl=TIME_1M)
    async def get(self, telegram_id: int) -> Optional[UserDto]:
        return await _get_impl(self, telegram_id)

    async def update(self, user: UserDto) -> Optional[UserDto]:
        return await _update_impl(self, user)

    async def ensure_referral_code(self, user: UserDto) -> UserDto:
        return await _ensure_referral_code_impl(self, user)

    async def compare_and_update(
        self,
        user: UserDto,
        aiogram_user: AiogramUser,
    ) -> Optional[UserDto]:
        return await _compare_and_update_impl(self, user, aiogram_user)

    async def delete(self, user: UserDto) -> bool:
        return await _delete_impl(self, user)

    async def get_by_partial_name(self, query: str) -> list[UserDto]:
        return await _get_by_partial_name_impl(self, query)

    async def get_by_referral_code(self, referral_code: str) -> Optional[UserDto]:
        return await _get_by_referral_code_impl(self, referral_code)

    @redis_cache(prefix="users_count", ttl=TIME_10M)
    async def count(self) -> int:
        return await _count_impl(self)

    @redis_cache(prefix="get_by_role", ttl=TIME_10M)
    async def get_by_role(self, role: UserRole) -> list[UserDto]:
        return await _get_by_role_impl(self, role)

    @redis_cache(prefix="get_blocked_users", ttl=TIME_10M)
    async def get_blocked_users(self) -> list[UserDto]:
        return await _get_blocked_users_impl(self)

    @redis_cache(prefix="get_all", ttl=TIME_10M)
    async def get_all(self) -> list[UserDto]:
        return await _get_all_impl(self)

    async def set_block(self, user: UserDto, blocked: bool) -> None:
        await _set_block_impl(self, user, blocked)

    async def set_bot_blocked(self, user: UserDto, blocked: bool) -> None:
        await _set_bot_blocked_impl(self, user, blocked)

    async def set_role(self, user: UserDto, role: UserRole) -> None:
        await _set_role_impl(self, user, role)

    async def set_purchase_discount(self, user: UserDto, discount: int) -> None:
        await _set_purchase_discount_impl(self, user, discount)

    async def set_partner_balance_currency_override(
        self,
        user: UserDto,
        currency: Currency | None,
    ) -> None:
        await _set_partner_balance_currency_override_impl(self, user, currency)

    async def add_to_recent_registered(self, telegram_id: int) -> None:
        await _add_to_recent_registered_impl(self, telegram_id)

    async def update_recent_activity(self, telegram_id: int) -> None:
        await _update_recent_activity_impl(self, telegram_id)

    async def get_recent_registered_users(self) -> list[UserDto]:
        return await _get_recent_registered_users_impl(self)

    async def get_recent_activity_users(self) -> list[UserDto]:
        return await _get_recent_activity_users_impl(self)

    async def search_users(self, message: Message) -> list[UserDto]:
        return await _search_users_impl(self, message)

    async def _search_users_by_forward(self, message: Message) -> list[UserDto]:
        return await _search_users_by_forward_impl(self, message)

    async def _search_users_by_query(self, search_query: str) -> list[UserDto]:
        return await _search_users_by_query_impl(self, search_query)

    async def _search_users_by_telegram_id(self, target_telegram_id: int) -> list[UserDto]:
        return await _search_users_by_telegram_id_impl(self, target_telegram_id)

    async def _search_users_by_remnashop_id(self, search_query: str) -> list[UserDto]:
        return await _search_users_by_remnashop_id_impl(self, search_query)

    async def _search_users_by_login_or_name(self, search_query: str) -> list[UserDto]:
        return await _search_users_by_login_or_name_impl(self, search_query)

    async def set_current_subscription(self, telegram_id: int, subscription_id: int) -> None:
        await _set_current_subscription_impl(self, telegram_id, subscription_id)

    async def delete_current_subscription(self, telegram_id: int) -> None:
        await _delete_current_subscription_impl(self, telegram_id)

    async def add_points(self, user: Union[BaseUserDto, UserDto], points: int) -> None:
        await _add_points_impl(self, user, points)

    async def reset_rules_acceptance_for_non_privileged(self, accepted: bool) -> int:
        return await _reset_rules_acceptance_impl(self, accepted)

    async def clear_user_cache(self, telegram_id: int) -> None:
        await _clear_user_cache_impl(self, telegram_id)

    async def _clear_list_caches(self) -> None:
        await _clear_list_caches_impl(self)

    async def _add_to_recent_list(self, key: StorageKey, telegram_id: int) -> None:
        await _add_to_recent_list_impl(self, key, telegram_id)

    async def _remove_from_recent_registered(self, telegram_id: int) -> None:
        await _remove_from_recent_registered_impl(self, telegram_id)

    async def _get_recent_registered(self) -> list[int]:
        return await _get_recent_registered_impl(self)

    async def _remove_from_recent_activity(self, telegram_id: int) -> None:
        await _remove_from_recent_activity_impl(self, telegram_id)

    async def _get_recent_activity(self) -> list[int]:
        return await _get_recent_activity_impl(self)
