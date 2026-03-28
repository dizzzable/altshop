from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from http import HTTPStatus
from uuid import UUID

from httpx import HTTPStatusError
from loguru import logger

from src.api.utils.web_app_urls import build_web_payment_redirect_urls
from src.core.config import AppConfig
from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.core.exceptions import SubscriptionPurchaseError
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionDto,
    UserDto,
)
from src.services.partner import PartnerService
from src.services.payment_gateway import PaymentGatewayService


@dataclass(slots=True, frozen=True)
class PurchaseExecutionResult:
    transaction_id: str
    payment_url: str | None
    url: str | None
    status: str
    message: str


class PartnerBalancePurchaseFlow:
    def __init__(
        self,
        *,
        payment_gateway_service: PaymentGatewayService,
        partner_service: PartnerService,
    ) -> None:
        self.payment_gateway_service = payment_gateway_service
        self.partner_service = partner_service

    async def assert_allowed(
        self,
        *,
        current_user: UserDto,
        channel: PurchaseChannel,
        gateway: PaymentGatewayDto,
        is_gateway_explicitly_selected: bool,
    ) -> None:
        if channel != PurchaseChannel.WEB:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail={
                    "code": "PARTNER_BALANCE_WEB_ONLY",
                    "message": "Partner balance payments are allowed only in WEB channel",
                },
            )

        if not is_gateway_explicitly_selected:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail={
                    "code": "PARTNER_BALANCE_GATEWAY_REQUIRED",
                    "message": "gateway_type is required for partner balance payment",
                },
            )

        if gateway.currency != Currency.RUB:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail={
                    "code": "PARTNER_BALANCE_RUB_ONLY",
                    "message": "Partner balance payments are available only with RUB gateways",
                },
            )

        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if not partner or not partner.is_active:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.FORBIDDEN,
                detail={
                    "code": "PARTNER_BALANCE_PARTNER_INACTIVE",
                    "message": "Partner balance payments are available only for active partners",
                },
            )

    async def handle(
        self,
        *,
        current_user: UserDto,
        channel: PurchaseChannel,
        purchase_type: PurchaseType,
        gateway: PaymentGatewayDto,
        gateway_type: PaymentGatewayType,
        is_gateway_explicitly_selected: bool,
        final_price: PriceDetailsDto,
        payment_asset: CryptoAsset | None,
        plan_snapshot: PlanSnapshotDto,
        renew_subscription_id: int | None,
        renew_subscription_ids: list[int] | None,
        device_types: list[DeviceType] | None,
    ) -> PurchaseExecutionResult:
        await self.assert_allowed(
            current_user=current_user,
            channel=channel,
            gateway=gateway,
            is_gateway_explicitly_selected=is_gateway_explicitly_selected,
        )

        amount_kopecks = int(final_price.final_amount * Decimal(100))
        balance_debited = False
        payment_id = uuid.uuid4()

        try:
            await self._create_transaction(
                payment_id=payment_id,
                current_user=current_user,
                purchase_type=purchase_type,
                channel=channel,
                gateway=gateway,
                gateway_type=gateway_type,
                final_price=final_price,
                payment_asset=payment_asset,
                plan_snapshot=plan_snapshot,
                renew_subscription_id=renew_subscription_id,
                renew_subscription_ids=renew_subscription_ids,
                device_types=device_types,
            )

            balance_debited = await self._debit_balance_or_fail(
                current_user=current_user,
                payment_id=payment_id,
                amount_kopecks=amount_kopecks,
            )

            await self.payment_gateway_service.handle_payment_succeeded(payment_id)
            return PurchaseExecutionResult(
                transaction_id=str(payment_id),
                payment_url=None,
                url=None,
                status=TransactionStatus.COMPLETED.value,
                message="Payment completed from partner balance",
            )
        except SubscriptionPurchaseError:
            raise
        except Exception as exception:
            logger.exception(f"Partner balance payment failed for '{payment_id}': {exception}")
            failed_transaction = await self._mark_transaction_failed_if_present(
                payment_id=payment_id
            )
            if (
                balance_debited
                and amount_kopecks > 0
                and (not failed_transaction or not failed_transaction.is_completed)
            ):
                await self.partner_service.credit_balance_for_failed_subscription_purchase(
                    user_telegram_id=current_user.telegram_id,
                    amount_kopecks=amount_kopecks,
                )

            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to process partner balance payment",
            ) from exception

    async def _mark_transaction_failed_if_present(
        self,
        *,
        payment_id: UUID,
    ) -> TransactionDto | None:
        failed_transaction = await self.payment_gateway_service.transaction_service.get(payment_id)
        if failed_transaction and not failed_transaction.is_completed:
            failed_transaction.status = TransactionStatus.FAILED
            await self.payment_gateway_service.transaction_service.update(failed_transaction)
        return failed_transaction

    async def _create_transaction(
        self,
        *,
        payment_id: UUID,
        current_user: UserDto,
        purchase_type: PurchaseType,
        channel: PurchaseChannel,
        gateway: PaymentGatewayDto,
        gateway_type: PaymentGatewayType,
        final_price: PriceDetailsDto,
        payment_asset: CryptoAsset | None,
        plan_snapshot: PlanSnapshotDto,
        renew_subscription_id: int | None,
        renew_subscription_ids: list[int] | None,
        device_types: list[DeviceType] | None,
    ) -> None:
        transaction = TransactionDto(
            payment_id=payment_id,
            status=TransactionStatus.PENDING,
            purchase_type=purchase_type,
            channel=channel,
            gateway_type=gateway_type,
            pricing=final_price,
            currency=gateway.currency,
            payment_asset=payment_asset,
            plan=plan_snapshot,
            renew_subscription_id=renew_subscription_id,
            renew_subscription_ids=renew_subscription_ids,
            device_types=device_types,
        )
        await self.payment_gateway_service.transaction_service.create(current_user, transaction)

    async def _debit_balance_or_fail(
        self,
        *,
        current_user: UserDto,
        payment_id: UUID,
        amount_kopecks: int,
    ) -> bool:
        if amount_kopecks <= 0:
            return False

        balance_debited = await self.partner_service.debit_balance_for_subscription_purchase(
            user_telegram_id=current_user.telegram_id,
            amount_kopecks=amount_kopecks,
        )
        if balance_debited:
            return True

        await self._mark_transaction_failed_if_present(payment_id=payment_id)
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={
                "code": "INSUFFICIENT_PARTNER_BALANCE",
                "message": "Insufficient partner balance for this purchase",
            },
        )


class ExternalPurchaseFlow:
    def __init__(
        self,
        *,
        config: AppConfig,
        payment_gateway_service: PaymentGatewayService,
    ) -> None:
        self.config = config
        self.payment_gateway_service = payment_gateway_service

    async def handle(
        self,
        *,
        current_user: UserDto,
        purchase_type: PurchaseType,
        channel: PurchaseChannel,
        gateway_type: PaymentGatewayType,
        final_price: PriceDetailsDto,
        payment_asset: CryptoAsset | None,
        plan_snapshot: PlanSnapshotDto,
        renew_subscription_id: int | None,
        renew_subscription_ids: list[int] | None,
        device_types: list[DeviceType] | None,
        success_redirect_url: str | None,
        fail_redirect_url: str | None,
    ) -> PurchaseExecutionResult:
        if channel == PurchaseChannel.WEB:
            default_success_url, default_fail_url = build_web_payment_redirect_urls(self.config)
            success_redirect_url = success_redirect_url or default_success_url
            fail_redirect_url = fail_redirect_url or default_fail_url

        try:
            payment_result = await self.payment_gateway_service.create_payment(
                user=current_user,
                plan=plan_snapshot,
                pricing=final_price,
                purchase_type=purchase_type,
                gateway_type=gateway_type,
                payment_asset=payment_asset,
                renew_subscription_id=renew_subscription_id,
                renew_subscription_ids=renew_subscription_ids,
                device_types=device_types,
                channel=channel,
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
                detail="Failed to create payment",
            ) from exception

        return PurchaseExecutionResult(
            transaction_id=str(payment_result.id),
            payment_url=payment_result.url,
            url=payment_result.url,
            status=TransactionStatus.PENDING.value,
            message="Payment initiated successfully",
        )
