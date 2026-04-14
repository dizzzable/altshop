from __future__ import annotations

from dataclasses import replace
from http import HTTPStatus
from typing import TYPE_CHECKING

from src.core.enums import PaymentSource, PurchaseChannel, PurchaseType
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
)

from .subscription_purchase_models import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseResult,
)
from .subscription_purchase_policy import (
    SubscriptionActionPolicy,
    SubscriptionPurchaseOptionsResult,
)

if TYPE_CHECKING:
    from .subscription_purchase import SubscriptionPurchaseService


async def _execute_without_access_assert(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionPurchaseResult:
    validated_context = await service._validate_purchase_context(
        request=request,
        current_user=current_user,
    )
    plan = validated_context.plan
    duration_days, duration = service._resolve_purchase_duration(request=request, plan=plan)
    effective_multiplier, effective_subscription_count = (
        service._resolve_effective_subscription_count(request=request)
    )

    gateway, gateway_type = await service._resolve_purchase_gateway(request=request)
    payment_asset = service._resolve_payment_asset(
        request=request,
        gateway_type=gateway_type,
    )
    final_price, renew_items = await service._calculate_settlement_pricing(
        request=request,
        current_user=current_user,
        validated_context=validated_context,
        duration=duration,
        gateway=gateway,
        effective_multiplier=effective_multiplier,
    )
    await service._validate_subscription_limit(
        request=request,
        current_user=current_user,
        effective_subscription_count=effective_subscription_count,
    )

    plan_snapshot = (
        renew_items[0].plan.model_copy(deep=True)
        if renew_items
        else PlanSnapshotDto.from_plan(plan, duration_days)
    )
    device_types = service._resolve_purchase_device_types(
        request=request,
        effective_subscription_count=effective_subscription_count,
    )

    if request.payment_source == PaymentSource.PARTNER_BALANCE:
        return await service._handle_partner_balance_purchase(
            request=request,
            current_user=current_user,
            gateway=gateway,
            gateway_type=gateway_type,
            final_price=final_price,
            payment_asset=payment_asset,
            plan_snapshot=plan_snapshot,
            renew_items=renew_items,
            device_types=device_types,
        )

    return await service._handle_external_purchase(
        request=request,
        current_user=current_user,
        gateway_type=gateway_type,
        final_price=final_price,
        payment_asset=payment_asset,
        plan_snapshot=plan_snapshot,
        renew_items=renew_items,
        device_types=device_types,
    )


async def _execute_renewal_alias(
    service: SubscriptionPurchaseService,
    *,
    subscription_id: int,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionPurchaseResult:
    await service.purchase_access_service.assert_can_purchase(current_user)
    base_subscription = await service.subscription_service.get(subscription_id)
    if not base_subscription:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Subscription not found",
        )
    if base_subscription.user_telegram_id != current_user.telegram_id:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Access denied to this subscription",
        )

    renew_request = replace(request, purchase_type=PurchaseType.RENEW)
    if not renew_request.renew_subscription_id and not renew_request.renew_subscription_ids:
        renew_request = replace(renew_request, renew_subscription_id=subscription_id)

    return await service._execute_without_access_assert(
        request=renew_request,
        current_user=current_user,
    )


async def _execute_upgrade_alias(
    service: SubscriptionPurchaseService,
    *,
    subscription_id: int,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
) -> SubscriptionPurchaseResult:
    await service.purchase_access_service.assert_can_purchase(current_user)
    base_subscription = await service.subscription_service.get(subscription_id)
    if not base_subscription:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Subscription not found",
        )
    if base_subscription.user_telegram_id != current_user.telegram_id:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Access denied to this subscription",
        )

    upgrade_request = replace(request, purchase_type=PurchaseType.UPGRADE)
    if not upgrade_request.renew_subscription_id and not upgrade_request.renew_subscription_ids:
        upgrade_request = replace(upgrade_request, renew_subscription_id=subscription_id)

    return await service._execute_without_access_assert(
        request=upgrade_request,
        current_user=current_user,
    )


async def _get_purchase_options(
    service: SubscriptionPurchaseService,
    *,
    subscription_id: int,
    purchase_type: PurchaseType,
    current_user: UserDto,
    channel: PurchaseChannel,
) -> SubscriptionPurchaseOptionsResult:
    if purchase_type not in {PurchaseType.RENEW, PurchaseType.UPGRADE}:
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="purchase_type must be RENEW or UPGRADE",
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

    return await service.subscription_purchase_policy_service.get_purchase_options(
        current_user=current_user,
        subscription=subscription,
        purchase_type=purchase_type,
        channel=channel,
    )


async def _get_action_policy(
    service: SubscriptionPurchaseService,
    *,
    current_user: UserDto,
    subscription: SubscriptionDto,
) -> SubscriptionActionPolicy:
    return await service.subscription_purchase_policy_service.get_action_policy(
        current_user=current_user,
        subscription=subscription,
    )
