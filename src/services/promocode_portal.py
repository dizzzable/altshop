from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from src.core.enums import PromocodeRewardType, SubscriptionStatus
from src.infrastructure.database.models.dto import PromocodeDto, SubscriptionDto, UserDto

from .promocode import PromocodeService
from .purchase_access import PurchaseAccessService
from .subscription import SubscriptionService
from .user import UserService


class PromocodePortalError(Exception):
    def __init__(self, *, status_code: int, detail: str | dict[str, str]) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


@dataclass(slots=True, frozen=True)
class PromocodeRewardSnapshot:
    type: str
    value: int


@dataclass(slots=True, frozen=True)
class PromocodeActivationSnapshot:
    message: str
    reward: PromocodeRewardSnapshot | None = None
    next_step: str | None = None
    available_subscriptions: list[int] | None = None


class PromocodePortalService:
    def __init__(
        self,
        promocode_service: PromocodeService,
        purchase_access_service: PurchaseAccessService,
        subscription_service: SubscriptionService,
        user_service: UserService,
    ) -> None:
        self.promocode_service = promocode_service
        self.purchase_access_service = purchase_access_service
        self.subscription_service = subscription_service
        self.user_service = user_service

    async def activate(
        self,
        *,
        current_user: UserDto,
        code: str,
        subscription_id: int | None,
        create_new: bool,
    ) -> PromocodeActivationSnapshot:
        await self.purchase_access_service.assert_can_purchase(current_user)

        normalized_code = code.strip().upper()
        if not normalized_code:
            raise PromocodePortalError(status_code=400, detail="Invalid promocode")

        promocode = await self.promocode_service.get_by_code(normalized_code)
        if not promocode:
            raise PromocodePortalError(status_code=400, detail="Invalid promocode")

        reward_type = promocode.reward_type
        reward = self._build_promocode_reward(promocode)

        async def activate_target(
            target_subscription_id: int | None,
        ) -> PromocodeActivationSnapshot:
            result = await self.promocode_service.activate(
                code=normalized_code,
                user=current_user,
                user_service=self.user_service,
                subscription_service=self.subscription_service,
                target_subscription_id=target_subscription_id,
            )
            if not result.success:
                raise PromocodePortalError(
                    status_code=400,
                    detail=result.message_key or "Failed to activate promocode",
                )

            return PromocodeActivationSnapshot(
                message="Promocode activated successfully",
                reward=reward,
                next_step=None,
            )

        target_subscription = await self._resolve_target_subscription(
            subscription_id=subscription_id,
            current_user=current_user,
        )
        available_subscription_ids = await self._get_eligible_subscription_ids(
            current_user=current_user,
            promocode=promocode,
        )

        if reward_type == PromocodeRewardType.SUBSCRIPTION:
            self._assert_target_subscription_eligible_for_promocode(
                promocode=promocode,
                target_subscription=target_subscription,
            )
            return await self._resolve_subscription_reward_activation(
                target_subscription=target_subscription,
                available_subscription_ids=available_subscription_ids,
                create_new=create_new,
                reward=reward,
                activate=activate_target,
            )

        if reward_type in (
            PromocodeRewardType.DURATION,
            PromocodeRewardType.TRAFFIC,
            PromocodeRewardType.DEVICES,
        ):
            self._assert_target_subscription_eligible_for_promocode(
                promocode=promocode,
                target_subscription=target_subscription,
            )
            return await self._resolve_resource_reward_activation(
                target_subscription=target_subscription,
                available_subscription_ids=available_subscription_ids,
                reward=reward,
                activate=activate_target,
            )

        return await activate_target(None)

    @staticmethod
    def _assert_target_subscription_eligible_for_promocode(
        *,
        promocode: PromocodeDto,
        target_subscription: SubscriptionDto | None,
    ) -> None:
        if (
            target_subscription
            and target_subscription.id is not None
            and not promocode.is_plan_eligible(getattr(target_subscription.plan, "id", None))
        ):
            raise PromocodePortalError(
                status_code=400,
                detail="Subscription plan is not eligible for this promocode",
            )

    async def _resolve_target_subscription(
        self,
        *,
        subscription_id: int | None,
        current_user: UserDto,
    ) -> SubscriptionDto | None:
        if subscription_id is None:
            return None

        target_subscription = await self.subscription_service.get(subscription_id)
        if not target_subscription:
            raise PromocodePortalError(status_code=404, detail="Subscription not found")
        if target_subscription.user_telegram_id != current_user.telegram_id:
            raise PromocodePortalError(
                status_code=403,
                detail="Access denied to this subscription",
            )
        if not self._is_active_subscription(target_subscription):
            raise PromocodePortalError(status_code=400, detail="Subscription is not active")

        return target_subscription

    async def _get_eligible_subscription_ids(
        self,
        *,
        current_user: UserDto,
        promocode: PromocodeDto,
    ) -> list[int]:
        subscriptions = await self.subscription_service.get_all_by_user(current_user.telegram_id)
        active_subs = [
            subscription
            for subscription in subscriptions
            if self._is_active_subscription(subscription)
        ]
        eligible_active_subs = [
            subscription
            for subscription in active_subs
            if promocode.is_plan_eligible(getattr(subscription.plan, "id", None))
        ]
        return [
            subscription.id
            for subscription in eligible_active_subs
            if subscription.id is not None
        ]

    @staticmethod
    async def _resolve_subscription_reward_activation(
        *,
        target_subscription: SubscriptionDto | None,
        available_subscription_ids: list[int],
        create_new: bool,
        reward: PromocodeRewardSnapshot,
        activate: Callable[[int | None], Awaitable[PromocodeActivationSnapshot]],
    ) -> PromocodeActivationSnapshot:
        if target_subscription and target_subscription.id is not None:
            return await activate(target_subscription.id)

        if create_new:
            return await activate(None)

        if not available_subscription_ids:
            return PromocodeActivationSnapshot(
                message="This promocode can create a new subscription. Confirm to continue.",
                reward=reward,
                next_step="CREATE_NEW",
            )

        if len(available_subscription_ids) == 1:
            return await activate(available_subscription_ids[0])

        return PromocodeActivationSnapshot(
            message="Select a subscription for applying this promocode",
            reward=reward,
            next_step="SELECT_SUBSCRIPTION",
            available_subscriptions=available_subscription_ids,
        )

    @staticmethod
    async def _resolve_resource_reward_activation(
        *,
        target_subscription: SubscriptionDto | None,
        available_subscription_ids: list[int],
        reward: PromocodeRewardSnapshot,
        activate: Callable[[int | None], Awaitable[PromocodeActivationSnapshot]],
    ) -> PromocodeActivationSnapshot:
        if target_subscription and target_subscription.id is not None:
            return await activate(target_subscription.id)

        if not available_subscription_ids:
            raise PromocodePortalError(
                status_code=400,
                detail="No eligible active subscriptions to apply this promocode",
            )

        if len(available_subscription_ids) == 1:
            return await activate(available_subscription_ids[0])

        return PromocodeActivationSnapshot(
            message="Select a subscription for applying this promocode",
            reward=reward,
            next_step="SELECT_SUBSCRIPTION",
            available_subscriptions=available_subscription_ids,
        )

    @staticmethod
    def _build_promocode_reward(promocode: PromocodeDto) -> PromocodeRewardSnapshot:
        reward_type = promocode.reward_type
        reward_value = promocode.reward or 0
        if (
            reward_value == 0
            and reward_type == PromocodeRewardType.SUBSCRIPTION
            and promocode.plan
            and promocode.plan.duration
        ):
            reward_value = promocode.plan.duration

        return PromocodeRewardSnapshot(
            type=reward_type.value if hasattr(reward_type, "value") else str(reward_type),
            value=reward_value,
        )

    @staticmethod
    def _is_active_subscription(subscription: SubscriptionDto) -> bool:
        status = subscription.status
        if hasattr(status, "value"):
            return str(getattr(status, "value")) == SubscriptionStatus.ACTIVE.value
        return str(status) == SubscriptionStatus.ACTIVE.value
