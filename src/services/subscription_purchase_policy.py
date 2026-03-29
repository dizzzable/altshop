from __future__ import annotations

from dataclasses import dataclass
from math import inf

from src.core.enums import (
    ArchivedPlanRenewMode,
    PurchaseChannel,
    PurchaseType,
    SubscriptionRenewMode,
    SubscriptionStatus,
)
from src.infrastructure.database.models.dto import PlanDto, SubscriptionDto, UserDto

from .plan import PlanService
from .plan_catalog import PlanCatalogItemSnapshot, PlanCatalogService

UPGRADE_WARNING_CODE = "UPGRADE_RESETS_EXPIRY"
UPGRADE_WARNING_MESSAGE = (
    "Upgrade starts immediately and resets the expiration date from the moment of payment."
)
ARCHIVED_REPLACEMENT_WARNING_CODE = "ARCHIVED_PLAN_REPLACEMENT"
ARCHIVED_REPLACEMENT_WARNING_MESSAGE = (
    "This plan is no longer available. Choose one of the currently available plans to continue."
)
LEGACY_SOURCE_PLAN_WARNING_CODE = "LEGACY_SOURCE_PLAN_UNAVAILABLE"
LEGACY_SOURCE_PLAN_WARNING_MESSAGE = (
    "This subscription plan is no longer available for self-service renewal or upgrade."
)


@dataclass(slots=True, frozen=True)
class SubscriptionActionPolicy:
    can_renew: bool
    can_upgrade: bool
    can_multi_renew: bool
    renew_mode: SubscriptionRenewMode | None


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseOptionsResult:
    purchase_type: PurchaseType
    subscription_id: int
    source_plan_missing: bool
    selection_locked: bool
    renew_mode: SubscriptionRenewMode | None
    warning_code: str | None
    warning_message: str | None
    plans: list[PlanCatalogItemSnapshot]


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseSelection:
    source_subscription: SubscriptionDto
    source_plan: PlanDto | None
    source_plan_missing: bool
    renew_mode: SubscriptionRenewMode | None
    renew_plans: tuple[PlanDto, ...]
    upgrade_plans: tuple[PlanDto, ...]


class SubscriptionPurchasePolicyService:
    def __init__(
        self,
        plan_service: PlanService,
        plan_catalog_service: PlanCatalogService,
    ) -> None:
        self.plan_service = plan_service
        self.plan_catalog_service = plan_catalog_service

    async def get_action_policy(
        self,
        *,
        current_user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionActionPolicy:
        selection = await self.build_selection(
            current_user=current_user,
            subscription=subscription,
        )
        return SubscriptionActionPolicy(
            can_renew=bool(selection.renew_plans),
            can_upgrade=bool(selection.upgrade_plans),
            can_multi_renew=(
                subscription.status != SubscriptionStatus.DELETED
                and not subscription.is_trial
                and selection.renew_mode is not None
                and (
                    selection.renew_mode in {
                        SubscriptionRenewMode.STANDARD,
                        SubscriptionRenewMode.SELF_RENEW,
                    }
                    or (
                        selection.renew_mode == SubscriptionRenewMode.REPLACE_ON_RENEW
                        and len(selection.renew_plans) == 1
                    )
                )
                and bool(selection.renew_plans)
            ),
            renew_mode=selection.renew_mode,
        )

    async def get_purchase_options(
        self,
        *,
        current_user: UserDto,
        subscription: SubscriptionDto,
        purchase_type: PurchaseType,
        channel: PurchaseChannel,
    ) -> SubscriptionPurchaseOptionsResult:
        selection = await self.build_selection(
            current_user=current_user,
            subscription=subscription,
        )
        plans = list(self.get_purchase_candidates(selection=selection, purchase_type=purchase_type))
        catalog_items = await self.plan_catalog_service.build_items_from_plans(
            current_user=current_user,
            channel=channel,
            plans=plans,
        )
        warning_code, warning_message = self._resolve_warning(
            purchase_type=purchase_type,
            selection=selection,
        )
        return SubscriptionPurchaseOptionsResult(
            purchase_type=purchase_type,
            subscription_id=subscription.id or 0,
            source_plan_missing=selection.source_plan_missing,
            selection_locked=(
                purchase_type == PurchaseType.RENEW
                and selection.renew_mode
                in {SubscriptionRenewMode.STANDARD, SubscriptionRenewMode.SELF_RENEW}
            ),
            renew_mode=selection.renew_mode,
            warning_code=warning_code,
            warning_message=warning_message,
            plans=catalog_items,
        )

    async def build_selection(
        self,
        *,
        current_user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionPurchaseSelection:
        source_plan = await self._load_source_plan(subscription)
        source_plan_missing = source_plan is None
        renew_mode: SubscriptionRenewMode | None = None
        renew_plans: tuple[PlanDto, ...] = ()

        subscription_deleted = subscription.status == SubscriptionStatus.DELETED

        if not subscription_deleted and not subscription.is_trial and source_plan:
            if source_plan.is_archived:
                if source_plan.archived_renew_mode == ArchivedPlanRenewMode.REPLACE_ON_RENEW:
                    renew_mode = SubscriptionRenewMode.REPLACE_ON_RENEW
                    renew_plans = await self._get_candidate_plans(
                        current_user=current_user,
                        plan_ids=source_plan.replacement_plan_ids,
                    )
                else:
                    renew_mode = SubscriptionRenewMode.SELF_RENEW
                    renew_plans = (source_plan,)
            elif source_plan.is_publicly_purchasable:
                renew_mode = SubscriptionRenewMode.STANDARD
                renew_plans = (source_plan,)

        upgrade_plans: tuple[PlanDto, ...] = ()
        if not subscription_deleted and source_plan:
            candidate_plans = await self._get_candidate_plans(
                current_user=current_user,
                plan_ids=source_plan.upgrade_to_plan_ids,
            )
            upgrade_plans = tuple(
                target_plan
                for target_plan in candidate_plans
                if self._is_upgrade_candidate(source_plan=source_plan, target_plan=target_plan)
            )

        return SubscriptionPurchaseSelection(
            source_subscription=subscription,
            source_plan=source_plan,
            source_plan_missing=source_plan_missing,
            renew_mode=renew_mode,
            renew_plans=renew_plans,
            upgrade_plans=upgrade_plans,
        )

    @staticmethod
    def get_purchase_candidates(
        *,
        selection: SubscriptionPurchaseSelection,
        purchase_type: PurchaseType,
    ) -> tuple[PlanDto, ...]:
        if purchase_type == PurchaseType.RENEW:
            return selection.renew_plans
        if purchase_type == PurchaseType.UPGRADE:
            return selection.upgrade_plans
        raise ValueError(f"Unsupported purchase type for options: {purchase_type}")

    async def _load_source_plan(self, subscription: SubscriptionDto) -> PlanDto | None:
        plan_id = getattr(subscription.plan, "id", None)
        if not plan_id or plan_id <= 0:
            return None
        return await self.plan_service.get(plan_id)

    async def _get_candidate_plans(
        self,
        *,
        current_user: UserDto,
        plan_ids: list[int],
    ) -> tuple[PlanDto, ...]:
        return tuple(
            await self.plan_service.get_purchase_available_plans_by_ids(
                user=current_user,
                plan_ids=plan_ids,
            )
        )

    def _resolve_warning(
        self,
        *,
        purchase_type: PurchaseType,
        selection: SubscriptionPurchaseSelection,
    ) -> tuple[str | None, str | None]:
        if selection.source_plan_missing:
            return LEGACY_SOURCE_PLAN_WARNING_CODE, LEGACY_SOURCE_PLAN_WARNING_MESSAGE

        if (
            purchase_type == PurchaseType.RENEW
            and selection.renew_mode == SubscriptionRenewMode.REPLACE_ON_RENEW
        ):
            return ARCHIVED_REPLACEMENT_WARNING_CODE, ARCHIVED_REPLACEMENT_WARNING_MESSAGE

        if purchase_type == PurchaseType.UPGRADE:
            return UPGRADE_WARNING_CODE, UPGRADE_WARNING_MESSAGE

        return None, None

    @staticmethod
    def _is_upgrade_candidate(*, source_plan: PlanDto, target_plan: PlanDto) -> bool:
        if source_plan.id == target_plan.id:
            return False

        source_device_limit = SubscriptionPurchasePolicyService._normalize_limit(
            source_plan.device_limit
        )
        target_device_limit = SubscriptionPurchasePolicyService._normalize_limit(
            target_plan.device_limit
        )
        source_traffic_limit = SubscriptionPurchasePolicyService._normalize_limit(
            source_plan.traffic_limit
        )
        target_traffic_limit = SubscriptionPurchasePolicyService._normalize_limit(
            target_plan.traffic_limit
        )

        return (
            target_device_limit >= source_device_limit
            and target_traffic_limit >= source_traffic_limit
            and (
                target_device_limit > source_device_limit
                or target_traffic_limit > source_traffic_limit
            )
        )

    @staticmethod
    def _normalize_limit(value: int) -> float:
        return inf if value <= 0 else float(value)
