from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from remnawave.exceptions import NotFoundError

from src.core.constants import IMPORTED_TAG
from src.core.enums import DeviceType, SubscriptionStatus, UserRole
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto, UserDto

from .plan import PlanService
from .remnawave import RemnawaveService
from .subscription import SubscriptionService
from .subscription_runtime import SubscriptionRuntimeService
from .user import UserService


class SubscriptionPortalError(Exception):
    """Base error for user-facing subscription management flows."""


class SubscriptionPortalNotFoundError(SubscriptionPortalError):
    def __init__(self) -> None:
        self.message = "Subscription not found"
        super().__init__(self.message)


class SubscriptionPortalAccessDeniedError(SubscriptionPortalError):
    def __init__(self, message: str = "Access denied to this subscription") -> None:
        self.message = message
        super().__init__(message)


class SubscriptionPortalBadRequestError(SubscriptionPortalError):
    pass


class SubscriptionPortalStateError(SubscriptionPortalError):
    pass


@dataclass(slots=True, frozen=True)
class SubscriptionAssignmentUpdate:
    plan_id: int | None = None
    plan_id_provided: bool = False
    device_type: DeviceType | None = None
    device_type_provided: bool = False


@dataclass(slots=True, frozen=True)
class DeletedSubscriptionResult:
    success: bool
    message: str


class SubscriptionPortalService:
    def __init__(
        self,
        subscription_service: SubscriptionService,
        subscription_runtime_service: SubscriptionRuntimeService,
        plan_service: PlanService,
        remnawave_service: RemnawaveService,
        user_service: UserService,
    ) -> None:
        self.subscription_service = subscription_service
        self.subscription_runtime_service = subscription_runtime_service
        self.plan_service = plan_service
        self.remnawave_service = remnawave_service
        self.user_service = user_service

    async def get_detail(
        self,
        *,
        subscription_id: int,
        current_user: UserDto,
    ) -> SubscriptionDto:
        subscription = await self._get_owned_subscription(
            subscription_id=subscription_id,
            user_telegram_id=current_user.telegram_id,
        )
        return await self.subscription_runtime_service.prepare_for_detail(subscription)

    async def update_assignment(
        self,
        *,
        subscription_id: int,
        current_user: UserDto,
        update: SubscriptionAssignmentUpdate,
    ) -> SubscriptionDto:
        subscription = await self._get_owned_subscription(
            subscription_id=subscription_id,
            user_telegram_id=current_user.telegram_id,
        )

        if not update.plan_id_provided and not update.device_type_provided:
            raise SubscriptionPortalBadRequestError("At least one field must be provided")

        if update.plan_id_provided and current_user.role != UserRole.DEV:
            raise SubscriptionPortalAccessDeniedError("Only DEV can change plan assignment")

        changed = False

        if update.plan_id_provided:
            changed = await self._apply_plan_assignment_update(
                update=update,
                subscription=subscription,
                current_user=current_user,
            )

        if update.device_type_provided:
            subscription.device_type = update.device_type
            changed = True

        if not changed:
            raise SubscriptionPortalBadRequestError("Nothing to update")

        updated_subscription = await self.subscription_service.update(subscription)
        if not updated_subscription:
            raise SubscriptionPortalStateError("Failed to update subscription assignment")
        return updated_subscription

    async def delete_subscription(
        self,
        *,
        subscription_id: int,
        current_user: UserDto,
    ) -> DeletedSubscriptionResult:
        subscription = await self._get_owned_subscription(
            subscription_id=subscription_id,
            user_telegram_id=current_user.telegram_id,
        )
        if subscription.status == SubscriptionStatus.DELETED:
            raise SubscriptionPortalBadRequestError("Subscription is already deleted")

        if subscription.user_remna_id:
            try:
                await self.remnawave_service.delete_user(
                    current_user,
                    uuid=subscription.user_remna_id,
                )
            except NotFoundError:
                logger.info(
                    f"Remnawave profile '{subscription.user_remna_id}' is already missing for "
                    f"user '{current_user.telegram_id}', continuing with local deletion"
                )
            except Exception as exception:
                logger.exception(
                    f"Failed to delete Remnawave profile '{subscription.user_remna_id}' for "
                    f"user '{current_user.telegram_id}': {exception}"
                )
                raise SubscriptionPortalStateError(
                    "Failed to delete subscription in Remnawave"
                ) from exception

        deleted = await self.subscription_service.delete_subscription(subscription_id)
        if not deleted:
            raise SubscriptionPortalStateError("Failed to delete subscription")

        await self._switch_current_subscription_after_delete(
            user_telegram_id=current_user.telegram_id,
            deleted_subscription_id=subscription_id,
        )
        return DeletedSubscriptionResult(
            success=True,
            message="Subscription deleted successfully",
        )

    async def _get_owned_subscription(
        self,
        *,
        subscription_id: int,
        user_telegram_id: int,
    ) -> SubscriptionDto:
        subscription = await self.subscription_service.get(subscription_id)
        if not subscription:
            raise SubscriptionPortalNotFoundError()
        if subscription.user_telegram_id != user_telegram_id:
            raise SubscriptionPortalAccessDeniedError()
        return subscription

    async def _apply_plan_assignment_update(
        self,
        *,
        update: SubscriptionAssignmentUpdate,
        subscription: SubscriptionDto,
        current_user: UserDto,
    ) -> bool:
        if not update.plan_id_provided:
            return False

        if update.plan_id is None:
            # Reset local snapshot assignment back to imported/unassigned identity.
            subscription.plan.id = -1
            subscription.plan.tag = IMPORTED_TAG
            subscription.plan.name = IMPORTED_TAG
            return True

        available_plans = await self.plan_service.get_assignable_active_plans()
        selected_plan = next((plan for plan in available_plans if plan.id == update.plan_id), None)
        if not selected_plan:
            raise SubscriptionPortalBadRequestError(
                "Selected plan is not available for this user"
            )

        current_duration = subscription.plan.duration if subscription.plan else 30
        if selected_plan.durations and not any(
            duration.days == current_duration for duration in selected_plan.durations
        ):
            current_duration = selected_plan.durations[0].days

        subscription.plan = PlanSnapshotDto.from_plan(selected_plan, current_duration)
        return True

    async def _switch_current_subscription_after_delete(
        self,
        *,
        user_telegram_id: int,
        deleted_subscription_id: int,
    ) -> None:
        subscriptions = await self.subscription_service.get_all_by_user(user_telegram_id)
        remaining_subscriptions = [
            subscription
            for subscription in subscriptions
            if subscription.status != SubscriptionStatus.DELETED
            and subscription.id != deleted_subscription_id
        ]

        next_subscription = self._select_next_current_subscription(remaining_subscriptions)
        if next_subscription and next_subscription.id:
            await self.user_service.set_current_subscription(
                telegram_id=user_telegram_id,
                subscription_id=next_subscription.id,
            )
        else:
            await self.user_service.delete_current_subscription(user_telegram_id)

        await self.user_service.uow.commit()

    @staticmethod
    def _select_next_current_subscription(
        subscriptions: list[SubscriptionDto],
    ) -> SubscriptionDto | None:
        if not subscriptions:
            return None

        status_priority = {
            SubscriptionStatus.ACTIVE: 0,
            SubscriptionStatus.DISABLED: 1,
            SubscriptionStatus.EXPIRED: 2,
        }
        return sorted(
            subscriptions,
            key=lambda subscription: (
                status_priority.get(subscription.get_status, 99),
                -subscription.expire_at.timestamp(),
                -(subscription.id or 0),
            ),
        )[0]
