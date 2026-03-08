from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import (
    PointsExchangeType,
    PromocodeAvailability,
    PromocodeRewardType,
    SubscriptionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    PromocodeDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.settings import ExchangeTypeSettingsDto
from src.infrastructure.redis import RedisRepository

from .base import BaseService
from .plan import PlanService
from .promocode import PromocodeService
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

    async def get_options(self, *, user_telegram_id: int) -> ReferralExchangeOptions:
        user = await self.user_service.get(user_telegram_id)
        if not user:
            raise ReferralExchangeError(code="USER_NOT_FOUND", message="User not found")

        referral_settings = await self.settings_service.get_referral_settings()
        exchange_settings = referral_settings.points_exchange
        subscriptions = await self._get_exchangeable_subscriptions(user.telegram_id)
        has_subscriptions = bool(subscriptions)
        gift_plans = await self._get_active_gift_plans()

        type_options: list[ReferralExchangeTypeOption] = []
        for exchange_type in PointsExchangeType:
            type_settings = exchange_settings.get_settings_for_type(exchange_type)
            effective_points = self._get_effective_points(
                user_points=user.points,
                max_points=type_settings.max_points,
            )
            computed_value = self._compute_value(exchange_type, effective_points, type_settings)
            requires_subscription = exchange_type in (
                PointsExchangeType.SUBSCRIPTION_DAYS,
                PointsExchangeType.TRAFFIC,
            )
            has_plan_for_gift = (
                bool(gift_plans) if exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION else True
            )
            available = (
                exchange_settings.exchange_enabled
                and type_settings.enabled
                and user.points >= type_settings.min_points
                and computed_value > 0
                and (not requires_subscription or has_subscriptions)
                and has_plan_for_gift
            )
            type_options.append(
                ReferralExchangeTypeOption(
                    type=exchange_type,
                    enabled=exchange_settings.exchange_enabled and type_settings.enabled,
                    available=available,
                    points_cost=type_settings.points_cost,
                    min_points=type_settings.min_points,
                    max_points=type_settings.max_points,
                    computed_value=computed_value,
                    requires_subscription=requires_subscription,
                    gift_plan_id=type_settings.gift_plan_id,
                    gift_duration_days=type_settings.gift_duration_days,
                    max_discount_percent=type_settings.max_discount_percent,
                    max_traffic_gb=type_settings.max_traffic_gb,
                )
            )

        return ReferralExchangeOptions(
            exchange_enabled=exchange_settings.exchange_enabled,
            points_balance=user.points,
            types=type_options,
            gift_plans=gift_plans,
        )

    async def execute(
        self,
        *,
        user_telegram_id: int,
        exchange_type: PointsExchangeType,
        subscription_id: int | None = None,
        gift_plan_id: int | None = None,
    ) -> ReferralExchangeExecutionResult:
        referral_settings = await self.settings_service.get_referral_settings()
        exchange_settings = referral_settings.points_exchange

        if not exchange_settings.exchange_enabled:
            raise ReferralExchangeError(
                code="EXCHANGE_DISABLED",
                message="Points exchange is disabled",
            )
        if not exchange_settings.is_type_enabled(exchange_type):
            raise ReferralExchangeError(
                code="EXCHANGE_TYPE_DISABLED",
                message=f"Exchange type '{exchange_type.value}' is disabled",
            )

        db_user = await self.uow.repository.users.get_for_update(user_telegram_id)
        if not db_user:
            raise ReferralExchangeError(code="USER_NOT_FOUND", message="User not found")
        user = UserDto.from_model(db_user)
        if user is None:
            raise ReferralExchangeError(code="USER_NOT_FOUND", message="User not found")

        type_settings = exchange_settings.get_settings_for_type(exchange_type)
        effective_points = self._get_effective_points(
            user_points=user.points,
            max_points=type_settings.max_points,
        )
        if effective_points < type_settings.min_points:
            raise ReferralExchangeError(
                code="NOT_ENOUGH_POINTS",
                message=f"Minimum points required: {type_settings.min_points}",
            )

        if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
            result = await self._execute_subscription_days(
                user=user,
                effective_points=effective_points,
                points_cost=type_settings.points_cost,
                subscription_id=subscription_id,
            )
        elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
            result = await self._execute_gift_subscription(
                user=user,
                points_cost=type_settings.points_cost,
                configured_plan_id=type_settings.gift_plan_id,
                requested_plan_id=gift_plan_id,
                duration_days=type_settings.gift_duration_days,
            )
        elif exchange_type == PointsExchangeType.DISCOUNT:
            result = await self._execute_discount(
                user_telegram_id=user.telegram_id,
                current_points=user.points,
                current_discount=user.purchase_discount,
                effective_points=effective_points,
                points_cost=type_settings.points_cost,
                max_discount_percent=type_settings.max_discount_percent,
            )
        elif exchange_type == PointsExchangeType.TRAFFIC:
            result = await self._execute_traffic(
                user=user,
                effective_points=effective_points,
                points_cost=type_settings.points_cost,
                max_traffic_gb=type_settings.max_traffic_gb,
                subscription_id=subscription_id,
            )
        else:
            raise ReferralExchangeError(
                code="UNSUPPORTED_EXCHANGE_TYPE",
                message=f"Unsupported exchange type '{exchange_type.value}'",
            )

        await self.user_service.clear_user_cache(user.telegram_id)
        return result

    async def _execute_subscription_days(
        self,
        *,
        user: UserDto,
        effective_points: int,
        points_cost: int,
        subscription_id: int | None,
    ) -> ReferralExchangeExecutionResult:
        if not subscription_id:
            raise ReferralExchangeError(
                code="SUBSCRIPTION_REQUIRED",
                message="Subscription ID is required for this exchange type",
            )
        if points_cost <= 0:
            raise ReferralExchangeError(
                code="INVALID_POINTS_COST",
                message="Points cost must be greater than zero",
            )

        subscription = await self._get_exchangeable_subscription(
            user_telegram_id=user.telegram_id,
            subscription_id=subscription_id,
        )
        days_to_add = effective_points // points_cost
        points_spent = days_to_add * points_cost
        if days_to_add <= 0 or points_spent <= 0:
            raise ReferralExchangeError(
                code="NOT_ENOUGH_POINTS",
                message="Not enough points for exchange",
            )

        base_expire_at = max(subscription.expire_at, datetime_now())
        subscription.expire_at = base_expire_at + timedelta(days=days_to_add)
        await self.subscription_service.update(subscription, auto_commit=False)

        points_after = user.points - points_spent
        await self.uow.repository.users.update(user.telegram_id, points=points_after)
        await self.remnawave_service.updated_user(
            user=user,
            uuid=subscription.user_remna_id,
            subscription=subscription,
        )

        return ReferralExchangeExecutionResult(
            exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
            points_spent=points_spent,
            points_balance_after=points_after,
            result=ReferralExchangeResultPayload(days_added=days_to_add),
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
        if points_cost <= 0:
            raise ReferralExchangeError(
                code="INVALID_POINTS_COST",
                message="Points cost must be greater than zero",
            )
        if user.points < points_cost:
            raise ReferralExchangeError(
                code="NOT_ENOUGH_POINTS",
                message="Not enough points for exchange",
            )

        selected_plan_id = requested_plan_id or configured_plan_id
        if not selected_plan_id:
            raise ReferralExchangeError(
                code="PLAN_REQUIRED",
                message="Gift plan is required for this exchange type",
            )

        plan = await self.plan_service.get(selected_plan_id)
        if not plan or not plan.is_active:
            raise ReferralExchangeError(
                code="PLAN_NOT_FOUND",
                message="Selected gift plan not found",
            )

        safe_duration_days = max(duration_days, 1)
        promocode_code = await self._generate_gift_promocode_code()
        plan_snapshot = PlanSnapshotDto.from_plan(plan, safe_duration_days)
        promocode = PromocodeDto(
            code=promocode_code,
            reward_type=PromocodeRewardType.SUBSCRIPTION,
            availability=PromocodeAvailability.ALL,
            reward=safe_duration_days,
            plan=plan_snapshot,
            lifetime=-1,
            max_activations=1,
            is_active=True,
        )
        await self.promocode_service.create(promocode, auto_commit=False)

        points_after = user.points - points_cost
        await self.uow.repository.users.update(user.telegram_id, points=points_after)

        return ReferralExchangeExecutionResult(
            exchange_type=PointsExchangeType.GIFT_SUBSCRIPTION,
            points_spent=points_cost,
            points_balance_after=points_after,
            result=ReferralExchangeResultPayload(
                gift_promocode=promocode_code,
                gift_plan_name=plan.name,
                gift_duration_days=safe_duration_days,
            ),
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
        if points_cost <= 0:
            raise ReferralExchangeError(
                code="INVALID_POINTS_COST",
                message="Points cost must be greater than zero",
            )

        discount_percent = effective_points // points_cost
        if max_discount_percent > 0:
            discount_percent = min(discount_percent, max_discount_percent)
        points_spent = discount_percent * points_cost
        if discount_percent <= 0 or points_spent <= 0:
            raise ReferralExchangeError(
                code="NOT_ENOUGH_POINTS",
                message="Not enough points for exchange",
            )

        points_after = current_points - points_spent
        purchase_discount_after = min(max(current_discount, 0) + discount_percent, 100)
        await self.uow.repository.users.update(
            user_telegram_id,
            points=points_after,
            purchase_discount=purchase_discount_after,
        )

        return ReferralExchangeExecutionResult(
            exchange_type=PointsExchangeType.DISCOUNT,
            points_spent=points_spent,
            points_balance_after=points_after,
            result=ReferralExchangeResultPayload(discount_percent_added=discount_percent),
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
        if not subscription_id:
            raise ReferralExchangeError(
                code="SUBSCRIPTION_REQUIRED",
                message="Subscription ID is required for this exchange type",
            )
        if points_cost <= 0:
            raise ReferralExchangeError(
                code="INVALID_POINTS_COST",
                message="Points cost must be greater than zero",
            )

        subscription = await self._get_exchangeable_subscription(
            user_telegram_id=user.telegram_id,
            subscription_id=subscription_id,
        )
        traffic_gb = effective_points // points_cost
        if max_traffic_gb > 0:
            traffic_gb = min(traffic_gb, max_traffic_gb)
        points_spent = traffic_gb * points_cost
        if traffic_gb <= 0 or points_spent <= 0:
            raise ReferralExchangeError(
                code="NOT_ENOUGH_POINTS",
                message="Not enough points for exchange",
            )

        subscription.traffic_limit = (subscription.traffic_limit or 0) + traffic_gb
        await self.subscription_service.update(subscription, auto_commit=False)

        points_after = user.points - points_spent
        await self.uow.repository.users.update(user.telegram_id, points=points_after)
        await self.remnawave_service.updated_user(
            user=user,
            uuid=subscription.user_remna_id,
            subscription=subscription,
        )

        return ReferralExchangeExecutionResult(
            exchange_type=PointsExchangeType.TRAFFIC,
            points_spent=points_spent,
            points_balance_after=points_after,
            result=ReferralExchangeResultPayload(traffic_gb_added=traffic_gb),
        )

    async def _get_exchangeable_subscriptions(
        self,
        user_telegram_id: int,
    ) -> list[SubscriptionDto]:
        subscriptions = await self.subscription_service.get_all_by_user(user_telegram_id)
        return [
            subscription
            for subscription in subscriptions
            if subscription.status
            in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.EXPIRED,
                SubscriptionStatus.LIMITED,
            )
            and not subscription.is_unlimited
        ]

    async def _get_exchangeable_subscription(
        self,
        *,
        user_telegram_id: int,
        subscription_id: int,
    ) -> SubscriptionDto:
        subscription = await self.subscription_service.get(subscription_id)
        if not subscription or subscription.user_telegram_id != user_telegram_id:
            raise ReferralExchangeError(
                code="SUBSCRIPTION_NOT_FOUND",
                message="Subscription not found",
            )
        if (
            subscription.status
            not in (
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.EXPIRED,
                SubscriptionStatus.LIMITED,
            )
            or subscription.is_unlimited
        ):
            raise ReferralExchangeError(
                code="SUBSCRIPTION_NOT_ELIGIBLE",
                message="Subscription is not eligible for this exchange",
            )
        return subscription

    async def _get_active_gift_plans(self) -> list[ReferralGiftPlanOption]:
        plans = await self.plan_service.get_all()
        return [
            ReferralGiftPlanOption(plan_id=plan.id, plan_name=plan.name)
            for plan in plans
            if plan.id is not None and plan.is_active
        ]

    async def _generate_gift_promocode_code(self) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = "GIFT_" + "".join(secrets.choice(alphabet) for _ in range(8))
            exists = await self.promocode_service.get_by_code(code)
            if not exists:
                return code
        raise ReferralExchangeError(
            code="PROMOCODE_GENERATION_FAILED",
            message="Could not generate unique promocode",
        )

    @staticmethod
    def _get_effective_points(*, user_points: int, max_points: int) -> int:
        if max_points > 0:
            return min(user_points, max_points)
        return user_points

    @staticmethod
    def _compute_value(
        exchange_type: PointsExchangeType,
        points: int,
        type_settings: ExchangeTypeSettingsDto,
    ) -> int:
        points_cost = type_settings.points_cost
        if points_cost <= 0:
            return 0

        if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
            return points // points_cost
        if exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
            return type_settings.gift_duration_days if points >= points_cost else 0
        if exchange_type == PointsExchangeType.DISCOUNT:
            discount = points // points_cost
            if type_settings.max_discount_percent > 0:
                discount = min(discount, type_settings.max_discount_percent)
            return discount
        if exchange_type == PointsExchangeType.TRAFFIC:
            traffic = points // points_cost
            if type_settings.max_traffic_gb > 0:
                traffic = min(traffic, type_settings.max_traffic_gb)
            return traffic
        return 0
