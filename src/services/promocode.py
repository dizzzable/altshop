from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import PromocodeRewardType
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PromocodeDto, SubscriptionDto, UserDto
from src.infrastructure.database.models.dto.promocode import PromocodeActivationBaseDto
from src.infrastructure.redis import RedisRepository

from .base import BaseService
from .promocode_lifecycle import activate as _activate_impl
from .promocode_lifecycle import create as _create_impl
from .promocode_lifecycle import delete as _delete_impl
from .promocode_lifecycle import filter_active as _filter_active_impl
from .promocode_lifecycle import filter_by_type as _filter_by_type_impl
from .promocode_lifecycle import get as _get_impl
from .promocode_lifecycle import get_activations_count as _get_activations_count_impl
from .promocode_lifecycle import get_all as _get_all_impl
from .promocode_lifecycle import get_by_code as _get_by_code_impl
from .promocode_lifecycle import (
    get_user_activation_history as _get_user_activation_history_impl,
)
from .promocode_lifecycle import get_user_activations as _get_user_activations_impl
from .promocode_lifecycle import update as _update_impl
from .promocode_rewards import (
    apply_reward as _apply_reward_impl,
)
from .promocode_rewards import (
    apply_subscription_mutation_reward as _apply_subscription_mutation_reward_impl,
)
from .promocode_rewards import (
    apply_subscription_reward as _apply_subscription_reward_impl,
)
from .promocode_rewards import (
    apply_user_discount_reward as _apply_user_discount_reward_impl,
)
from .promocode_rewards import (
    get_success_message_key as _get_success_message_key_impl,
)
from .promocode_rewards import (
    resolve_target_subscription_for_reward as _resolve_target_subscription_for_reward_impl,
)
from .promocode_rewards import (
    sync_subscription_with_panel as _sync_subscription_with_panel_impl,
)
from .promocode_validation import ActivationError, ActivationResult
from .promocode_validation import check_availability as _check_availability_impl
from .promocode_validation import check_user_activation as _check_user_activation_impl
from .promocode_validation import validate_promocode as _validate_promocode_impl
from .remnawave import RemnawaveService

if TYPE_CHECKING:
    from .subscription import SubscriptionService
    from .user import UserService


class PromocodeService(BaseService):
    uow: UnitOfWork
    remnawave_service: RemnawaveService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        remnawave_service: RemnawaveService,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.remnawave_service = remnawave_service
        self.uow = uow

    async def create(
        self,
        promocode: PromocodeDto,
        *,
        auto_commit: bool = True,
    ) -> PromocodeDto:
        return await _create_impl(self, promocode, auto_commit=auto_commit)

    async def get(self, promocode_id: int) -> Optional[PromocodeDto]:
        return await _get_impl(self, promocode_id)

    async def get_by_code(self, promocode_code: str) -> Optional[PromocodeDto]:
        return await _get_by_code_impl(self, promocode_code)

    async def get_all(self) -> list[PromocodeDto]:
        return await _get_all_impl(self)

    async def update(self, promocode: PromocodeDto) -> Optional[PromocodeDto]:
        return await _update_impl(self, promocode)

    async def delete(self, promocode_id: int) -> bool:
        return await _delete_impl(self, promocode_id)

    async def filter_by_type(
        self,
        promocode_type: PromocodeRewardType,
    ) -> list[PromocodeDto]:
        return await _filter_by_type_impl(self, promocode_type)

    async def filter_active(self, is_active: bool = True) -> list[PromocodeDto]:
        return await _filter_active_impl(self, is_active=is_active)

    async def check_user_activation(
        self,
        promocode_id: int,
        user_telegram_id: int,
    ) -> bool:
        return await _check_user_activation_impl(self, promocode_id, user_telegram_id)

    async def _check_availability(self, promocode: PromocodeDto, user: UserDto) -> bool:
        return await _check_availability_impl(self, promocode, user)

    async def validate_promocode(self, code: str, user: UserDto) -> ActivationResult:
        return await _validate_promocode_impl(self, code, user)

    async def activate(
        self,
        code: str,
        user: UserDto,
        user_service: "UserService",
        subscription_service: Optional["SubscriptionService"] = None,
        target_subscription_id: Optional[int] = None,
    ) -> ActivationResult:
        return await _activate_impl(
            self,
            code,
            user,
            user_service,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )

    async def _sync_subscription_with_panel(
        self,
        *,
        user: UserDto,
        subscription: SubscriptionDto,
        subscription_service: "SubscriptionService",
    ) -> None:
        await _sync_subscription_with_panel_impl(
            self,
            user=user,
            subscription=subscription,
            subscription_service=subscription_service,
        )

    async def _apply_user_discount_reward(
        self,
        *,
        reward_type: PromocodeRewardType,
        reward: Optional[int],
        user: UserDto,
        user_service: "UserService",
    ) -> bool:
        return await _apply_user_discount_reward_impl(
            self,
            reward_type=reward_type,
            reward=reward,
            user=user,
            user_service=user_service,
        )

    async def _apply_subscription_reward(
        self,
        *,
        promocode: PromocodeDto,
        user: UserDto,
        subscription_service: "SubscriptionService",
        target_subscription_id: Optional[int],
    ) -> bool:
        return await _apply_subscription_reward_impl(
            self,
            promocode=promocode,
            user=user,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )

    async def _resolve_target_subscription_for_reward(
        self,
        *,
        reward_type: PromocodeRewardType,
        user: UserDto,
        subscription_service: "SubscriptionService",
        target_subscription_id: Optional[int],
    ) -> tuple[Optional[int], Optional[SubscriptionDto]]:
        return await _resolve_target_subscription_for_reward_impl(
            self,
            reward_type=reward_type,
            user=user,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )

    async def _apply_subscription_mutation_reward(
        self,
        *,
        reward_type: PromocodeRewardType,
        reward: Optional[int],
        target_id: int,
        user: UserDto,
        subscription: SubscriptionDto,
        subscription_service: "SubscriptionService",
    ) -> bool:
        return await _apply_subscription_mutation_reward_impl(
            self,
            reward_type=reward_type,
            reward=reward,
            target_id=target_id,
            user=user,
            subscription=subscription,
            subscription_service=subscription_service,
        )

    async def _apply_reward(
        self,
        promocode: PromocodeDto,
        user: UserDto,
        user_service: "UserService",
        subscription_service: Optional["SubscriptionService"] = None,
        target_subscription_id: Optional[int] = None,
    ) -> bool:
        return await _apply_reward_impl(
            self,
            promocode,
            user,
            user_service,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )

    def _get_success_message_key(self, reward_type: PromocodeRewardType) -> str:
        return _get_success_message_key_impl(self, reward_type)

    async def get_activations_count(self, promocode_id: int) -> int:
        return await _get_activations_count_impl(self, promocode_id)

    async def get_user_activations(
        self,
        user_telegram_id: int,
    ) -> list[PromocodeActivationBaseDto]:
        return await _get_user_activations_impl(self, user_telegram_id)

    async def get_user_activation_history(
        self,
        user_telegram_id: int,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[PromocodeActivationBaseDto], int]:
        return await _get_user_activation_history_impl(
            self,
            user_telegram_id,
            page=page,
            limit=limit,
        )


__all__ = ["ActivationError", "ActivationResult", "PromocodeService"]
