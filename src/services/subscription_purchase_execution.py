from __future__ import annotations

import uuid
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import UUID

from httpx import HTTPStatusError
from loguru import logger

from src.api.utils.web_app_urls import build_web_payment_redirect_urls
from src.core.enums import (
    CryptoAsset,
    DeviceType,
    PaymentGatewayType,
    PurchaseChannel,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionDto,
    TransactionRenewItemDto,
    UserDto,
)

from .subscription_purchase_models import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseResult,
)

if TYPE_CHECKING:
    from .subscription_purchase import SubscriptionPurchaseService


async def _mark_purchase_transaction_failed_if_present(
    service: SubscriptionPurchaseService,
    *,
    payment_id: UUID,
) -> TransactionDto | None:
    failed_transaction = await service.payment_gateway_service.transaction_service.get(payment_id)
    if failed_transaction and not failed_transaction.is_completed:
        failed_transaction.status = TransactionStatus.FAILED
        await service.payment_gateway_service.transaction_service.update(failed_transaction)
    return failed_transaction


async def _create_partner_balance_transaction(
    service: SubscriptionPurchaseService,
    *,
    payment_id: UUID,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    gateway_type: PaymentGatewayType,
    gateway: PaymentGatewayDto,
    final_price: PriceDetailsDto,
    payment_asset: CryptoAsset | None,
    plan_snapshot: PlanSnapshotDto,
    renew_items: tuple[TransactionRenewItemDto, ...],
    device_types: list[DeviceType] | None,
) -> None:
    transaction = TransactionDto(
        payment_id=payment_id,
        status=TransactionStatus.PENDING,
        purchase_type=request.purchase_type,
        channel=request.channel,
        gateway_type=gateway_type,
        pricing=final_price,
        currency=gateway.currency,
        payment_asset=payment_asset,
        plan=plan_snapshot,
        renew_subscription_id=request.renew_subscription_id,
        renew_subscription_ids=list(request.renew_subscription_ids or ()),
        renew_items=list(renew_items) or None,
        device_types=device_types,
    )
    await service.payment_gateway_service.transaction_service.create(current_user, transaction)


async def _debit_partner_balance_or_fail(
    service: SubscriptionPurchaseService,
    *,
    current_user: UserDto,
    payment_id: UUID,
    amount_kopecks: int,
) -> bool:
    if amount_kopecks <= 0:
        return False

    balance_debited = await service.partner_service.debit_balance_for_subscription_purchase(
        user_telegram_id=current_user.telegram_id,
        amount_kopecks=amount_kopecks,
    )
    if balance_debited:
        return True

    await service._mark_purchase_transaction_failed_if_present(payment_id=payment_id)
    raise SubscriptionPurchaseError(
        status_code=HTTPStatus.BAD_REQUEST,
        detail={
            "code": "INSUFFICIENT_PARTNER_BALANCE",
            "message": "Insufficient partner balance for this purchase",
        },
    )


async def _handle_partner_balance_purchase(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    gateway: PaymentGatewayDto,
    gateway_type: PaymentGatewayType,
    final_price: PriceDetailsDto,
    payment_asset: CryptoAsset | None,
    plan_snapshot: PlanSnapshotDto,
    renew_items: tuple[TransactionRenewItemDto, ...],
    device_types: list[DeviceType] | None,
) -> SubscriptionPurchaseResult:
    await service._assert_partner_balance_purchase_allowed(
        request=request,
        current_user=current_user,
        gateway=gateway,
    )

    amount_kopecks = int(final_price.final_amount * Decimal(100))
    balance_debited = False
    payment_id = uuid.uuid4()

    try:
        await service._create_partner_balance_transaction(
            payment_id=payment_id,
            request=request,
            current_user=current_user,
            gateway_type=gateway_type,
            gateway=gateway,
            final_price=final_price,
            payment_asset=payment_asset,
            plan_snapshot=plan_snapshot,
            renew_items=renew_items,
            device_types=device_types,
        )

        balance_debited = await service._debit_partner_balance_or_fail(
            current_user=current_user,
            payment_id=payment_id,
            amount_kopecks=amount_kopecks,
        )

        await service.payment_gateway_service.handle_payment_succeeded(payment_id)
        return SubscriptionPurchaseResult(
            transaction_id=str(payment_id),
            payment_url=None,
            url=None,
            status=TransactionStatus.COMPLETED.value,
            message="Payment completed from partner balance",
            renew_items=renew_items,
        )
    except SubscriptionPurchaseError:
        raise
    except Exception as exception:
        logger.exception(f"Partner balance payment failed for '{payment_id}': {exception}")
        failed_transaction = await service._mark_purchase_transaction_failed_if_present(
            payment_id=payment_id
        )
        if (
            balance_debited
            and amount_kopecks > 0
            and (not failed_transaction or not failed_transaction.is_completed)
        ):
            await service.partner_service.credit_balance_for_failed_subscription_purchase(
                user_telegram_id=current_user.telegram_id,
                amount_kopecks=amount_kopecks,
            )

        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to process partner balance payment",
        ) from exception


async def _handle_external_purchase(
    service: SubscriptionPurchaseService,
    *,
    request: SubscriptionPurchaseRequest,
    current_user: UserDto,
    gateway_type: PaymentGatewayType,
    final_price: PriceDetailsDto,
    payment_asset: CryptoAsset | None,
    plan_snapshot: PlanSnapshotDto,
    renew_items: tuple[TransactionRenewItemDto, ...],
    device_types: list[DeviceType] | None,
) -> SubscriptionPurchaseResult:
    success_redirect_url: str | None = request.success_redirect_url
    fail_redirect_url: str | None = request.fail_redirect_url
    if request.channel == PurchaseChannel.WEB:
        default_success_url, default_fail_url = build_web_payment_redirect_urls(service.config)
        success_redirect_url = success_redirect_url or default_success_url
        fail_redirect_url = fail_redirect_url or default_fail_url

    try:
        payment_result = await service.payment_gateway_service.create_payment(
            user=current_user,
            plan=plan_snapshot,
            pricing=final_price,
            purchase_type=request.purchase_type,
            gateway_type=gateway_type,
            payment_asset=payment_asset,
            renew_subscription_id=request.renew_subscription_id,
            renew_subscription_ids=list(request.renew_subscription_ids or ()) or None,
            renew_items=list(renew_items) or None,
            device_types=device_types,
            channel=request.channel,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
        )
    except HTTPStatusError as exception:
        provider_status = exception.response.status_code if exception.response else None
        logger.exception(
            "Payment provider '{}' rejected create_payment request with status '{}': {}",
            gateway_type.value,
            provider_status,
            exception,
        )
        provider_suffix = f" ({provider_status})" if provider_status is not None else ""
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=(
                f"Payment provider '{gateway_type.value}' rejected the request{provider_suffix}"
            ),
        ) from exception
    except Exception as exception:
        logger.exception(f"Payment creation failed: {exception}")
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(exception)}",
        ) from exception

    return SubscriptionPurchaseResult(
        transaction_id=str(payment_result.id),
        payment_url=payment_result.url,
        url=payment_result.url,
        status=TransactionStatus.PENDING.value,
        message="Payment initiated successfully",
        renew_items=renew_items,
    )
