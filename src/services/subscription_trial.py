from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from src.core.enums import PlanAvailability, PurchaseChannel, SubscriptionStatus
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)

from .partner import PartnerService
from .plan import PlanService
from .purchase_access import PurchaseAccessService
from .remnawave import RemnawaveService
from .subscription import SubscriptionService

TRIAL_REASON_TELEGRAM_LINK_REQUIRED = "TRIAL_TELEGRAM_LINK_REQUIRED"
TRIAL_REASON_ALREADY_USED = "TRIAL_ALREADY_USED"
TRIAL_REASON_NOT_FIRST_SUBSCRIPTION = "TRIAL_NOT_FIRST_SUBSCRIPTION"
TRIAL_REASON_PLAN_NOT_CONFIGURED = "TRIAL_PLAN_NOT_CONFIGURED"
TRIAL_REASON_PLAN_NOT_FOUND = "TRIAL_PLAN_NOT_FOUND"
TRIAL_REASON_PLAN_NOT_TRIAL = "TRIAL_PLAN_NOT_TRIAL"
TRIAL_REASON_PLAN_INACTIVE = "TRIAL_PLAN_INACTIVE"
TRIAL_REASON_PLAN_NO_DURATION = "TRIAL_PLAN_NO_DURATION"


class SubscriptionTrialError(Exception):
    def __init__(self, *, status_code: int, detail: str | dict[str, str]) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


@dataclass(slots=True, frozen=True)
class TrialEligibilitySnapshot:
    eligible: bool
    reason_code: str | None = None
    reason_message: str | None = None
    requires_telegram_link: bool = False
    trial_plan_id: int | None = None


@dataclass(slots=True, frozen=True)
class TrialEligibilityCheck:
    eligible: bool
    status_code: int
    reason_code: str | None = None
    reason_message: str | None = None


class SubscriptionTrialService:
    def __init__(
        self,
        plan_service: PlanService,
        partner_service: PartnerService,
        purchase_access_service: PurchaseAccessService,
        remnawave_service: RemnawaveService,
        subscription_service: SubscriptionService,
    ) -> None:
        self.plan_service = plan_service
        self.partner_service = partner_service
        self.purchase_access_service = purchase_access_service
        self.remnawave_service = remnawave_service
        self.subscription_service = subscription_service

    async def get_eligibility(
        self,
        current_user: UserDto,
        *,
        channel: PurchaseChannel = PurchaseChannel.WEB,
    ) -> TrialEligibilitySnapshot:
        await self.purchase_access_service.assert_can_purchase(current_user)

        user_check = await self._check_user_eligibility(current_user, channel=channel)
        if not user_check.eligible:
            return TrialEligibilitySnapshot(
                eligible=False,
                reason_code=user_check.reason_code,
                reason_message=user_check.reason_message,
                requires_telegram_link=(
                    user_check.reason_code == TRIAL_REASON_TELEGRAM_LINK_REQUIRED
                ),
                trial_plan_id=None,
            )

        trial_plan = await self.plan_service.get_trial_plan()
        plan_check = self._check_plan_availability(trial_plan)
        if not plan_check.eligible:
            return TrialEligibilitySnapshot(
                eligible=False,
                reason_code=plan_check.reason_code,
                reason_message=plan_check.reason_message,
                requires_telegram_link=False,
                trial_plan_id=None,
            )

        return TrialEligibilitySnapshot(
            eligible=True,
            trial_plan_id=trial_plan.id if trial_plan and trial_plan.id else None,
        )

    async def create_trial_subscription(
        self,
        *,
        current_user: UserDto,
        plan_id: int | None,
        channel: PurchaseChannel = PurchaseChannel.WEB,
    ) -> SubscriptionDto:
        await self.purchase_access_service.assert_can_purchase(current_user)

        user_check = await self._check_user_eligibility(current_user, channel=channel)
        self._raise_trial_failure(user_check)

        plan = await self._resolve_requested_trial_plan(plan_id=plan_id)
        plan_check = self._check_plan_availability(plan)
        self._raise_trial_failure(plan_check)

        asserted_plan = cast(PlanDto, plan)
        trial_plan = PlanSnapshotDto.from_plan(asserted_plan, asserted_plan.durations[0].days)
        created_user = await self.remnawave_service.create_user(current_user, trial_plan)
        subscription_url = (
            created_user.subscription_url
            or await self.remnawave_service.get_subscription_url(created_user.uuid)
        )
        if not subscription_url:
            raise SubscriptionTrialError(
                status_code=500,
                detail="Failed to create trial subscription URL",
            )

        trial_subscription = SubscriptionDto(
            user_remna_id=created_user.uuid,
            status=created_user.status,
            is_trial=True,
            traffic_limit=trial_plan.traffic_limit,
            device_limit=trial_plan.device_limit,
            internal_squads=trial_plan.internal_squads,
            external_squad=trial_plan.external_squad,
            expire_at=created_user.expire_at,
            url=subscription_url,
            plan=trial_plan,
        )
        return await self.subscription_service.create(current_user, trial_subscription)

    async def _resolve_requested_trial_plan(self, *, plan_id: int | None) -> PlanDto | None:
        if plan_id:
            plan = await self.plan_service.get(plan_id)
            if not plan:
                self._raise_trial_failure(
                    self._trial_failure(
                        404,
                        TRIAL_REASON_PLAN_NOT_FOUND,
                        "Trial plan not found",
                    )
                )
            if not self._is_trial_plan(cast(PlanDto, plan)):
                self._raise_trial_failure(
                    self._trial_failure(
                        400,
                        TRIAL_REASON_PLAN_NOT_TRIAL,
                        "Selected plan is not a trial plan",
                    )
                )
            return plan

        return await self.plan_service.get_trial_plan()

    async def _check_user_eligibility(
        self,
        current_user: UserDto,
        *,
        channel: PurchaseChannel,
    ) -> TrialEligibilityCheck:
        if await self._requires_telegram_link(current_user, channel=channel):
            return self._trial_failure(
                403,
                TRIAL_REASON_TELEGRAM_LINK_REQUIRED,
                "Link Telegram account to activate trial subscription in web",
            )

        if await self.subscription_service.has_used_trial(current_user):
            return self._trial_failure(
                400,
                TRIAL_REASON_ALREADY_USED,
                "Trial subscription already used",
            )

        existing_subscriptions = await self.subscription_service.get_all_by_user(
            current_user.telegram_id
        )
        if any(
            not self._is_deleted_subscription(subscription)
            for subscription in existing_subscriptions
        ):
            return self._trial_failure(
                400,
                TRIAL_REASON_NOT_FIRST_SUBSCRIPTION,
                "Trial is only available before first active subscription",
            )

        return TrialEligibilityCheck(eligible=True, status_code=200)

    async def _requires_telegram_link(
        self,
        user: UserDto,
        *,
        channel: PurchaseChannel,
    ) -> bool:
        if channel == PurchaseChannel.TELEGRAM:
            return False
        if self._is_linked_telegram_identity(user):
            return False
        if getattr(user, "is_invited_user", False):
            return False
        if await self._has_partner_attribution(user):
            return False
        return True

    async def _has_partner_attribution(self, user: UserDto) -> bool:
        telegram_id = int(getattr(user, "telegram_id", 0) or 0)
        if telegram_id == 0:
            return False
        return await self.partner_service.has_partner_attribution(telegram_id)

    @staticmethod
    def _check_plan_availability(plan: PlanDto | None) -> TrialEligibilityCheck:
        if not plan:
            return SubscriptionTrialService._trial_failure(
                404,
                TRIAL_REASON_PLAN_NOT_CONFIGURED,
                "Trial plan is not configured",
            )
        if not plan.is_active:
            return SubscriptionTrialService._trial_failure(
                400,
                TRIAL_REASON_PLAN_INACTIVE,
                "Trial plan is inactive",
            )
        if not plan.durations:
            return SubscriptionTrialService._trial_failure(
                400,
                TRIAL_REASON_PLAN_NO_DURATION,
                "Trial plan has no available duration",
            )
        return TrialEligibilityCheck(eligible=True, status_code=200)

    @staticmethod
    def _is_trial_plan(plan: PlanDto) -> bool:
        availability = plan.availability
        if hasattr(availability, "value"):
            return str(getattr(availability, "value")) == PlanAvailability.TRIAL.value
        return str(availability) == PlanAvailability.TRIAL.value

    @staticmethod
    def _raise_trial_failure(check: TrialEligibilityCheck) -> None:
        if check.eligible:
            return

        detail: str | dict[str, str]
        if check.reason_code:
            detail = {
                "code": check.reason_code,
                "message": check.reason_message or "Trial is unavailable",
            }
        else:
            detail = check.reason_message or "Trial is unavailable"

        raise SubscriptionTrialError(status_code=check.status_code, detail=detail)

    @staticmethod
    def _trial_failure(status_code: int, code: str, message: str) -> TrialEligibilityCheck:
        return TrialEligibilityCheck(
            eligible=False,
            status_code=status_code,
            reason_code=code,
            reason_message=message,
        )

    @staticmethod
    def _is_linked_telegram_identity(user: UserDto) -> bool:
        return int(getattr(user, "telegram_id", 0) or 0) > 0

    @staticmethod
    def _is_deleted_subscription(subscription: SubscriptionDto) -> bool:
        status = subscription.status
        if hasattr(status, "value"):
            return str(getattr(status, "value")) == SubscriptionStatus.DELETED.value
        return str(status) == SubscriptionStatus.DELETED.value
