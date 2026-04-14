from __future__ import annotations

from dataclasses import replace
from http import HTTPStatus
from typing import TYPE_CHECKING

from loguru import logger

from src.core.enums import PurchaseType, SubscriptionRenewMode
from src.infrastructure.database.models.dto import PlanDto, SubscriptionDto, UserDto

from .subscription_purchase_models import (
    ARCHIVED_PLAN_NOT_PURCHASABLE_CODE,
    ARCHIVED_PLAN_NOT_PURCHASABLE_MESSAGE,
    TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_CODE,
    TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_MESSAGE,
    TRIAL_UPGRADE_REQUIRED_CODE,
    TRIAL_UPGRADE_REQUIRED_MESSAGE,
    TRIAL_UPGRADE_SELECTION_REQUIRED_CODE,
    TRIAL_UPGRADE_SELECTION_REQUIRED_MESSAGE,
    ResolvedRenewItemContext,
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    ValidatedPurchaseContext,
)
from .subscription_status import is_deleted_subscription

if TYPE_CHECKING:
    from .subscription_purchase import SubscriptionPurchaseService


async def _validate_purchase_context(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> ValidatedPurchaseContext:
    if request.purchase_type in {PurchaseType.NEW, PurchaseType.ADDITIONAL}:
        await service._assert_non_deleted_trial_requires_upgrade(
            request=request,
            current_user=current_user,
        )
        plan = await service._get_valid_catalog_purchase_plan(
            request=request,
            current_user=current_user,
        )
        return ValidatedPurchaseContext(plan=plan)

    if request.purchase_type == PurchaseType.RENEW:
        return await service._validate_renew_purchase_context(
            request=request,
            current_user=current_user,
        )

    if request.purchase_type == PurchaseType.UPGRADE:
        return await service._validate_upgrade_purchase_context(
            request=request,
            current_user=current_user,
        )

    raise SubscriptionPurchaseError(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=f"Unsupported purchase type: {request.purchase_type}",
    )


async def _normalize_trial_catalog_purchase_request(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionPurchaseRequest:
    if request.purchase_type != PurchaseType.NEW:
        return request

    trial_subscriptions = await service._get_active_trial_subscriptions(current_user=current_user)
    if not trial_subscriptions:
        return request

    if request.quantity > 1:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_CODE,
                "message": TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_MESSAGE,
            },
        )

    if len(trial_subscriptions) != 1 or trial_subscriptions[0].id is None:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": TRIAL_UPGRADE_SELECTION_REQUIRED_CODE,
                "message": TRIAL_UPGRADE_SELECTION_REQUIRED_MESSAGE,
            },
        )

    return replace(
        request,
        purchase_type=PurchaseType.UPGRADE,
        renew_subscription_id=trial_subscriptions[0].id,
        renew_subscription_ids=None,
        quantity=1,
        device_type=None,
        device_types=None,
    )


async def _get_active_trial_subscriptions(
    service: SubscriptionPurchaseService,
    *,
    current_user: UserDto,
) -> tuple[SubscriptionDto, ...]:
    existing_subs = await service.subscription_service.get_all_by_user(current_user.telegram_id)
    return tuple(
        subscription
        for subscription in existing_subs
        if subscription.is_trial and not is_deleted_subscription(subscription)
    )


async def _get_valid_catalog_purchase_plan(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> PlanDto:
    plan_id = service._get_purchase_plan_id(request)
    available_plans = await service.plan_service.get_available_plans(current_user)
    plan = next((candidate for candidate in available_plans if candidate.id == plan_id), None)
    if not plan:
        archived_plan = await service.plan_service.get(plan_id)
        if archived_plan and archived_plan.is_archived:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail={
                    "code": ARCHIVED_PLAN_NOT_PURCHASABLE_CODE,
                    "message": ARCHIVED_PLAN_NOT_PURCHASABLE_MESSAGE,
                },
            )
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Plan is not available",
        )
    return plan


async def _validate_renew_purchase_context(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> ValidatedPurchaseContext:
    renew_ids = service._collect_renew_ids(request)
    if len(renew_ids) > 1:
        renew_items = await service._build_multi_renew_item_contexts(
            request=request,
            current_user=current_user,
            renew_ids=renew_ids,
        )
        return ValidatedPurchaseContext(
            plan=renew_items[0].target_plan,
            renew_items=renew_items,
        )

    source_subscription = await service._get_single_owned_subscription(
        request=request,
        current_user=current_user,
    )
    selection = await service.subscription_purchase_policy_service.build_selection(
        current_user=current_user,
        subscription=source_subscription,
    )
    candidates = service.subscription_purchase_policy_service.get_purchase_candidates(
        selection=selection,
        purchase_type=PurchaseType.RENEW,
    )
    selected_plan = service._select_plan_from_candidates(
        request=request,
        purchase_type=PurchaseType.RENEW,
        candidates=candidates,
    )
    return ValidatedPurchaseContext(
        plan=selected_plan,
        source_subscription=source_subscription,
        renew_items=(
            ResolvedRenewItemContext(
                subscription_id=source_subscription.id or 0,
                source_subscription=source_subscription,
                renew_mode=selection.renew_mode or SubscriptionRenewMode.STANDARD,
                target_plan=selected_plan,
            ),
        ),
    )


async def _validate_upgrade_purchase_context(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> ValidatedPurchaseContext:
    if len(service._collect_renew_ids(request)) > 1:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Upgrade is only available for a single subscription",
        )

    source_subscription = await service._get_single_owned_subscription(
        request=request,
        current_user=current_user,
    )
    selection = await service.subscription_purchase_policy_service.build_selection(
        current_user=current_user,
        subscription=source_subscription,
    )
    candidates = service.subscription_purchase_policy_service.get_purchase_candidates(
        selection=selection,
        purchase_type=PurchaseType.UPGRADE,
    )
    selected_plan = service._select_plan_from_candidates(
        request=request,
        purchase_type=PurchaseType.UPGRADE,
        candidates=candidates,
    )
    return ValidatedPurchaseContext(
        plan=selected_plan,
        source_subscription=source_subscription,
    )


async def _get_single_owned_subscription(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionDto:
    renew_ids = service._collect_renew_ids(request)
    subscription_id = renew_ids[0] if renew_ids else None
    if subscription_id is None:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Subscription ID is required",
        )

    subscription = await service.subscription_service.get(subscription_id)
    if not subscription:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Subscription not found",
        )
    if subscription.user_telegram_id != current_user.telegram_id:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Access denied to this subscription",
        )
    return subscription


async def _build_multi_renew_item_contexts(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    renew_ids: list[int],
) -> tuple[ResolvedRenewItemContext, ...]:
    renew_items: list[ResolvedRenewItemContext] = []

    for renew_id in renew_ids:
        renew_subscription = await service.subscription_service.get(renew_id)
        if not renew_subscription:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Subscription {renew_id} not found",
            )
        if renew_subscription.user_telegram_id != current_user.telegram_id:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.FORBIDDEN,
                detail=f"Access denied to subscription {renew_id}",
            )

        selection = await service.subscription_purchase_policy_service.build_selection(
            current_user=current_user,
            subscription=renew_subscription,
        )
        action_policy = await service.subscription_purchase_policy_service.get_action_policy(
            current_user=current_user,
            subscription=renew_subscription,
        )
        if not action_policy.can_multi_renew:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Subscription {renew_id} is not available for multi-renew",
            )

        candidates = service.subscription_purchase_policy_service.get_purchase_candidates(
            selection=selection,
            purchase_type=PurchaseType.RENEW,
        )
        selected_plan = service._select_plan_from_candidates(
            request=request,
            purchase_type=PurchaseType.RENEW,
            candidates=candidates,
        )
        renew_items.append(
            ResolvedRenewItemContext(
                subscription_id=renew_id,
                source_subscription=renew_subscription,
                renew_mode=selection.renew_mode or SubscriptionRenewMode.STANDARD,
                target_plan=selected_plan,
            )
        )

    return tuple(renew_items)


def _select_plan_from_candidates(
    _service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    purchase_type: PurchaseType,
    candidates: tuple[PlanDto, ...],
) -> PlanDto:
    if not candidates:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                "No available renewal options"
                if purchase_type == PurchaseType.RENEW
                else "No available upgrade options"
            ),
        )

    if request.plan_id is None:
        if len(candidates) == 1:
            return candidates[0]
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Plan ID is required",
        )

    selected_plan = next(
        (candidate for candidate in candidates if candidate.id == request.plan_id),
        None,
    )
    if not selected_plan:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                "Selected plan is not available for renewal"
                if purchase_type == PurchaseType.RENEW
                else "Selected plan is not available for upgrade"
            ),
        )
    return selected_plan


def _get_purchase_plan_id(
    _service: SubscriptionPurchaseService,
    request: SubscriptionPurchaseRequest,
) -> int:
    if not request.plan_id:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Plan ID is required",
        )
    return request.plan_id


def _collect_renew_ids(
    _service: SubscriptionPurchaseService,
    request: SubscriptionPurchaseRequest,
) -> list[int]:
    renew_ids: list[int] = []
    if request.renew_subscription_id:
        renew_ids.append(request.renew_subscription_id)
    if request.renew_subscription_ids:
        renew_ids.extend(request.renew_subscription_ids)
    return list(dict.fromkeys(renew_ids))


async def _assert_non_deleted_trial_requires_upgrade(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> None:
    if request.purchase_type not in {PurchaseType.NEW, PurchaseType.ADDITIONAL}:
        return

    if await service._get_active_trial_subscriptions(current_user=current_user):
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": TRIAL_UPGRADE_REQUIRED_CODE,
                "message": TRIAL_UPGRADE_REQUIRED_MESSAGE,
            },
        )


async def _validate_subscription_limit(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    effective_subscription_count: int,
) -> None:
    if request.purchase_type not in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        return

    existing_subs = await service.subscription_service.get_all_by_user(current_user.telegram_id)
    active_subs = [
        subscription
        for subscription in existing_subs
        if not is_deleted_subscription(subscription)
    ]
    active_count = len(active_subs)
    required_new = effective_subscription_count

    max_subscriptions = await service.settings_service.get_max_subscriptions_for_user(current_user)
    if max_subscriptions < 1:
        logger.warning(
            f"Invalid max subscriptions '{max_subscriptions}' "
            f"for user '{current_user.telegram_id}', "
            "falling back to 1"
        )
        max_subscriptions = 1

    if active_count + required_new > max_subscriptions:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Maximum subscriptions limit reached ({max_subscriptions}). "
                f"Current active: {active_count}, requested new: {required_new}"
            ),
        )
