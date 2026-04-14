from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import PointsExchangeType
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.database.models.dto.settings import ExchangeTypeSettingsDto
from src.infrastructure.redis import RedisRepository

from .base import BaseService
from .plan import PlanService
from .promocode import PromocodeService
from .referral_exchange_execution import (
    execute as _execute_impl,
)
from .referral_exchange_execution import (
    execute_discount as _execute_discount_impl,
)
from .referral_exchange_execution import (
    execute_gift_subscription as _execute_gift_subscription_impl,
)
from .referral_exchange_execution import (
    execute_subscription_days as _execute_subscription_days_impl,
)
from .referral_exchange_execution import (
    execute_traffic as _execute_traffic_impl,
)
from .referral_exchange_execution import (
    generate_gift_promocode_code as _generate_gift_promocode_code_impl,
)
from .referral_exchange_execution import (
    get_exchangeable_subscription as _get_exchangeable_subscription_impl,
)
from .referral_exchange_options import (
    get_active_gift_plans as _get_active_gift_plans_impl,
)
from .referral_exchange_options import (
    get_exchangeable_subscriptions as _get_exchangeable_subscriptions_impl,
)
from .referral_exchange_options import (
    get_options as _get_options_impl,
)
from .referral_exchange_options import (
    resolve_availability_reason as _resolve_availability_reason_impl,
)
from .referral_exchange_values import (
    compute_value as _compute_value_impl,
)
from .referral_exchange_values import (
    get_effective_points as _get_effective_points_impl,
)
from .remnawave import RemnawaveService
from .settings import SettingsService
from .subscription import SubscriptionService
from .user import UserService


class ReferralExchangeError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ReferralGiftPlanOption:
    plan_id: int
    plan_name: str


@dataclass(slots=True)
class ReferralExchangeTypeOption:
    type: PointsExchangeType
    enabled: bool
    available: bool
    availability_reason: str | None
    points_cost: int
    min_points: int
    max_points: int
    computed_value: int
    requires_subscription: bool
    gift_plan_id: int | None = None
    gift_duration_days: int | None = None
    max_discount_percent: int | None = None
    max_traffic_gb: int | None = None


@dataclass(slots=True)
class ReferralExchangeOptions:
    exchange_enabled: bool
    points_balance: int
    types: list[ReferralExchangeTypeOption]
    gift_plans: list[ReferralGiftPlanOption]


@dataclass(slots=True)
class ReferralExchangeResultPayload:
    days_added: int | None = None
    traffic_gb_added: int | None = None
    discount_percent_added: int | None = None
    gift_promocode: str | None = None
    gift_plan_name: str | None = None
    gift_duration_days: int | None = None


@dataclass(slots=True)
class ReferralExchangeExecutionResult:
    exchange_type: PointsExchangeType
    points_spent: int
    points_balance_after: int
    result: ReferralExchangeResultPayload


class ReferralExchangeService(BaseService):
    uow: UnitOfWork
    settings_service: SettingsService
    user_service: UserService
    subscription_service: SubscriptionService
    plan_service: PlanService
    promocode_service: PromocodeService
    remnawave_service: RemnawaveService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        settings_service: SettingsService,
        user_service: UserService,
        subscription_service: SubscriptionService,
        plan_service: PlanService,
        promocode_service: PromocodeService,
        remnawave_service: RemnawaveService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.settings_service = settings_service
        self.user_service = user_service
        self.subscription_service = subscription_service
        self.plan_service = plan_service
        self.promocode_service = promocode_service
        self.remnawave_service = remnawave_service

    @staticmethod
    def _user_dto_from_model(model: Any) -> UserDto | None:
        return UserDto.from_model(model)

    @staticmethod
    def _exchange_error(*, code: str, message: str) -> ReferralExchangeError:
        return ReferralExchangeError(code=code, message=message)

    @staticmethod
    def _gift_plan_option(*, plan_id: int, plan_name: str) -> ReferralGiftPlanOption:
        return ReferralGiftPlanOption(plan_id=plan_id, plan_name=plan_name)

    @staticmethod
    def _type_option(
        *,
        type: PointsExchangeType,
        enabled: bool,
        available: bool,
        availability_reason: str | None,
        points_cost: int,
        min_points: int,
        max_points: int,
        computed_value: int,
        requires_subscription: bool,
        gift_plan_id: int | None = None,
        gift_duration_days: int | None = None,
        max_discount_percent: int | None = None,
        max_traffic_gb: int | None = None,
    ) -> ReferralExchangeTypeOption:
        return ReferralExchangeTypeOption(
            type=type,
            enabled=enabled,
            available=available,
            availability_reason=availability_reason,
            points_cost=points_cost,
            min_points=min_points,
            max_points=max_points,
            computed_value=computed_value,
            requires_subscription=requires_subscription,
            gift_plan_id=gift_plan_id,
            gift_duration_days=gift_duration_days,
            max_discount_percent=max_discount_percent,
            max_traffic_gb=max_traffic_gb,
        )

    @staticmethod
    def _options(
        *,
        exchange_enabled: bool,
        points_balance: int,
        types: list[ReferralExchangeTypeOption],
        gift_plans: list[ReferralGiftPlanOption],
    ) -> ReferralExchangeOptions:
        return ReferralExchangeOptions(
            exchange_enabled=exchange_enabled,
            points_balance=points_balance,
            types=types,
            gift_plans=gift_plans,
        )

    @staticmethod
    def _result_payload(
        *,
        days_added: int | None = None,
        traffic_gb_added: int | None = None,
        discount_percent_added: int | None = None,
        gift_promocode: str | None = None,
        gift_plan_name: str | None = None,
        gift_duration_days: int | None = None,
    ) -> ReferralExchangeResultPayload:
        return ReferralExchangeResultPayload(
            days_added=days_added,
            traffic_gb_added=traffic_gb_added,
            discount_percent_added=discount_percent_added,
            gift_promocode=gift_promocode,
            gift_plan_name=gift_plan_name,
            gift_duration_days=gift_duration_days,
        )

    @staticmethod
    def _execution_result(
        *,
        exchange_type: PointsExchangeType,
        points_spent: int,
        points_balance_after: int,
        result: ReferralExchangeResultPayload,
    ) -> ReferralExchangeExecutionResult:
        return ReferralExchangeExecutionResult(
            exchange_type=exchange_type,
            points_spent=points_spent,
            points_balance_after=points_balance_after,
            result=result,
        )

    async def get_options(self, *, user_telegram_id: int) -> ReferralExchangeOptions:
        return await _get_options_impl(self, user_telegram_id=user_telegram_id)

    @staticmethod
    def _resolve_availability_reason(
        *,
        exchange_enabled: bool,
        type_enabled: bool,
        user_points: int,
        min_points: int,
        points_cost: int,
        computed_value: int,
        requires_subscription: bool,
        has_subscriptions: bool,
        has_plan_for_gift: bool,
    ) -> str | None:
        return _resolve_availability_reason_impl(
            exchange_enabled=exchange_enabled,
            type_enabled=type_enabled,
            user_points=user_points,
            min_points=min_points,
            points_cost=points_cost,
            computed_value=computed_value,
            requires_subscription=requires_subscription,
            has_subscriptions=has_subscriptions,
            has_plan_for_gift=has_plan_for_gift,
        )

    async def execute(
        self,
        *,
        user_telegram_id: int,
        exchange_type: PointsExchangeType,
        subscription_id: int | None = None,
        gift_plan_id: int | None = None,
    ) -> ReferralExchangeExecutionResult:
        return await _execute_impl(
            self,
            user_telegram_id=user_telegram_id,
            exchange_type=exchange_type,
            subscription_id=subscription_id,
            gift_plan_id=gift_plan_id,
        )

    async def _execute_subscription_days(
        self,
        *,
        user: UserDto,
        effective_points: int,
        points_cost: int,
        subscription_id: int | None,
    ) -> ReferralExchangeExecutionResult:
        return await _execute_subscription_days_impl(
            self,
            user=user,
            effective_points=effective_points,
            points_cost=points_cost,
            subscription_id=subscription_id,
        )

    async def _execute_gift_subscription(
        self,
        *,
        user: UserDto,
        points_cost: int,
        configured_plan_id: int | None,
        requested_plan_id: int | None,
        duration_days: int,
    ) -> ReferralExchangeExecutionResult:
        return await _execute_gift_subscription_impl(
            self,
            user=user,
            points_cost=points_cost,
            configured_plan_id=configured_plan_id,
            requested_plan_id=requested_plan_id,
            duration_days=duration_days,
        )

    async def _execute_discount(
        self,
        *,
        user_telegram_id: int,
        current_points: int,
        current_discount: int,
        effective_points: int,
        points_cost: int,
        max_discount_percent: int,
    ) -> ReferralExchangeExecutionResult:
        return await _execute_discount_impl(
            self,
            user_telegram_id=user_telegram_id,
            current_points=current_points,
            current_discount=current_discount,
            effective_points=effective_points,
            points_cost=points_cost,
            max_discount_percent=max_discount_percent,
        )

    async def _execute_traffic(
        self,
        *,
        user: UserDto,
        effective_points: int,
        points_cost: int,
        max_traffic_gb: int,
        subscription_id: int | None,
    ) -> ReferralExchangeExecutionResult:
        return await _execute_traffic_impl(
            self,
            user=user,
            effective_points=effective_points,
            points_cost=points_cost,
            max_traffic_gb=max_traffic_gb,
            subscription_id=subscription_id,
        )

    async def _get_exchangeable_subscriptions(
        self,
        user_telegram_id: int,
    ) -> list[SubscriptionDto]:
        return await _get_exchangeable_subscriptions_impl(self, user_telegram_id)

    async def _get_exchangeable_subscription(
        self,
        *,
        user_telegram_id: int,
        subscription_id: int,
    ) -> SubscriptionDto:
        return await _get_exchangeable_subscription_impl(
            self,
            user_telegram_id=user_telegram_id,
            subscription_id=subscription_id,
        )

    async def _get_active_gift_plans(self) -> list[ReferralGiftPlanOption]:
        return await _get_active_gift_plans_impl(self)

    async def _generate_gift_promocode_code(self) -> str:
        return await _generate_gift_promocode_code_impl(self)

    @staticmethod
    def _get_effective_points(*, user_points: int, max_points: int) -> int:
        return _get_effective_points_impl(user_points=user_points, max_points=max_points)

    @staticmethod
    def _compute_value(
        exchange_type: PointsExchangeType,
        points: int,
        type_settings: ExchangeTypeSettingsDto,
    ) -> int:
        return _compute_value_impl(exchange_type, points, type_settings)
