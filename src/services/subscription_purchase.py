from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from src.core.config import AppConfig
from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    SubscriptionDto,
    TransactionDto,
    TransactionRenewItemDto,
    UserDto,
)

from .market_quote import CurrencyConversionQuote, MarketQuoteService
from .partner import PartnerService
from .payment_gateway import PaymentGatewayService
from .plan import PlanService
from .pricing import PricingService
from .purchase_access import PurchaseAccessService
from .settings import SettingsService
from .subscription import SubscriptionService
from .subscription_purchase_entrypoints import _execute as _execute_impl
from .subscription_purchase_entrypoints import _quote as _quote_impl
from .subscription_purchase_execution import (
    _create_partner_balance_transaction as _create_partner_balance_transaction_impl,
)
from .subscription_purchase_execution import (
    _debit_partner_balance_or_fail as _debit_partner_balance_or_fail_impl,
)
from .subscription_purchase_execution import (
    _handle_external_purchase as _handle_external_purchase_impl,
)
from .subscription_purchase_execution import (
    _handle_partner_balance_purchase as _handle_partner_balance_purchase_impl,
)
from .subscription_purchase_execution import (
    _mark_purchase_transaction_failed_if_present as _mark_transaction_failed_impl,
)
from .subscription_purchase_gateway import (
    _assert_partner_balance_purchase_allowed as _assert_partner_balance_purchase_allowed_impl,
)
from .subscription_purchase_gateway import (
    _resolve_explicit_purchase_gateway as _resolve_explicit_purchase_gateway_impl,
)
from .subscription_purchase_gateway import (
    _resolve_implicit_purchase_gateway as _resolve_implicit_purchase_gateway_impl,
)
from .subscription_purchase_gateway import (
    _resolve_payment_asset as _resolve_payment_asset_impl,
)
from .subscription_purchase_gateway import (
    _resolve_purchase_gateway as _resolve_purchase_gateway_impl,
)
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
    SubscriptionPurchaseQuoteResult,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseResult,
    ValidatedPurchaseContext,
)
from .subscription_purchase_orchestration import (
    _execute_renewal_alias as _execute_renewal_alias_impl,
)
from .subscription_purchase_orchestration import (
    _execute_upgrade_alias as _execute_upgrade_alias_impl,
)
from .subscription_purchase_orchestration import (
    _execute_without_access_assert as _execute_without_access_assert_impl,
)
from .subscription_purchase_orchestration import (
    _get_action_policy as _get_action_policy_impl,
)
from .subscription_purchase_orchestration import (
    _get_purchase_options as _get_purchase_options_impl,
)
from .subscription_purchase_policy import (
    SubscriptionActionPolicy,
    SubscriptionPurchaseOptionsResult,
    SubscriptionPurchasePolicyService,
)
from .subscription_purchase_quote import (
    _build_display_quote as _build_display_quote_impl,
)
from .subscription_purchase_quote import (
    _build_renew_transaction_items as _build_renew_transaction_items_impl,
)
from .subscription_purchase_quote import (
    _build_static_display_quote as _build_static_display_quote_impl,
)
from .subscription_purchase_quote import (
    _calculate_final_purchase_price as _calculate_final_purchase_price_impl,
)
from .subscription_purchase_quote import (
    _calculate_settlement_pricing as _calculate_settlement_pricing_impl,
)
from .subscription_purchase_quote import (
    _resolve_effective_subscription_count as _resolve_effective_subscription_count_impl,
)
from .subscription_purchase_quote import (
    _resolve_gateway_price as _resolve_gateway_price_impl,
)
from .subscription_purchase_quote import (
    _resolve_purchase_device_types as _resolve_purchase_device_types_impl,
)
from .subscription_purchase_quote import (
    _resolve_purchase_duration as _resolve_purchase_duration_impl,
)
from .subscription_purchase_validation import (
    _assert_non_deleted_trial_requires_upgrade as _assert_non_deleted_trial_requires_upgrade_impl,
)
from .subscription_purchase_validation import (
    _build_multi_renew_item_contexts as _build_multi_renew_item_contexts_impl,
)
from .subscription_purchase_validation import (
    _collect_renew_ids as _collect_renew_ids_impl,
)
from .subscription_purchase_validation import (
    _get_active_trial_subscriptions as _get_active_trial_subscriptions_impl,
)
from .subscription_purchase_validation import (
    _get_purchase_plan_id as _get_purchase_plan_id_impl,
)
from .subscription_purchase_validation import (
    _get_single_owned_subscription as _get_single_owned_subscription_impl,
)
from .subscription_purchase_validation import (
    _get_valid_catalog_purchase_plan as _get_valid_catalog_purchase_plan_impl,
)
from .subscription_purchase_validation import (
    _normalize_trial_catalog_purchase_request as _normalize_trial_catalog_purchase_request_impl,
)
from .subscription_purchase_validation import (
    _select_plan_from_candidates as _select_plan_from_candidates_impl,
)
from .subscription_purchase_validation import (
    _validate_purchase_context as _validate_purchase_context_impl,
)
from .subscription_purchase_validation import (
    _validate_renew_purchase_context as _validate_renew_purchase_context_impl,
)
from .subscription_purchase_validation import (
    _validate_subscription_limit as _validate_subscription_limit_impl,
)
from .subscription_purchase_validation import (
    _validate_upgrade_purchase_context as _validate_upgrade_purchase_context_impl,
)

__all__ = [
    "ARCHIVED_PLAN_NOT_PURCHASABLE_CODE",
    "ARCHIVED_PLAN_NOT_PURCHASABLE_MESSAGE",
    "TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_CODE",
    "TRIAL_UPGRADE_QUANTITY_UNSUPPORTED_MESSAGE",
    "TRIAL_UPGRADE_REQUIRED_CODE",
    "TRIAL_UPGRADE_REQUIRED_MESSAGE",
    "TRIAL_UPGRADE_SELECTION_REQUIRED_CODE",
    "TRIAL_UPGRADE_SELECTION_REQUIRED_MESSAGE",
    "ResolvedRenewItemContext",
    "SubscriptionPurchaseError",
    "SubscriptionPurchaseQuoteResult",
    "SubscriptionPurchaseRequest",
    "SubscriptionPurchaseResult",
    "SubscriptionPurchaseService",
    "ValidatedPurchaseContext",
]


class SubscriptionPurchaseService:
    def __init__(
        self,
        config: AppConfig,
        plan_service: PlanService,
        pricing_service: PricingService,
        purchase_access_service: PurchaseAccessService,
        subscription_service: SubscriptionService,
        subscription_purchase_policy_service: SubscriptionPurchasePolicyService,
        settings_service: SettingsService,
        payment_gateway_service: PaymentGatewayService,
        partner_service: PartnerService,
        market_quote_service: MarketQuoteService,
    ) -> None:
        self.config = config
        self.plan_service = plan_service
        self.pricing_service = pricing_service
        self.purchase_access_service = purchase_access_service
        self.subscription_service = subscription_service
        self.subscription_purchase_policy_service = subscription_purchase_policy_service
        self.settings_service = settings_service
        self.payment_gateway_service = payment_gateway_service
        self.partner_service = partner_service
        self.market_quote_service = market_quote_service

    async def execute(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        return await _execute_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def quote(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseQuoteResult:
        return await _quote_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _execute_without_access_assert(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        return await _execute_without_access_assert_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def execute_renewal_alias(
        self,
        *,
        subscription_id: int,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        return await _execute_renewal_alias_impl(
            self,
            subscription_id=subscription_id,
            request=request,
            current_user=current_user,
        )

    async def execute_upgrade_alias(
        self,
        *,
        subscription_id: int,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        return await _execute_upgrade_alias_impl(
            self,
            subscription_id=subscription_id,
            request=request,
            current_user=current_user,
        )

    async def get_purchase_options(
        self,
        *,
        subscription_id: int,
        purchase_type: PurchaseType,
        current_user: UserDto,
        channel: PurchaseChannel,
    ) -> SubscriptionPurchaseOptionsResult:
        return await _get_purchase_options_impl(
            self,
            subscription_id=subscription_id,
            purchase_type=purchase_type,
            current_user=current_user,
            channel=channel,
        )

    async def get_action_policy(
        self,
        *,
        current_user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionActionPolicy:
        return await _get_action_policy_impl(
            self,
            current_user=current_user,
            subscription=subscription,
        )

    async def _validate_purchase_context(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> ValidatedPurchaseContext:
        return await _validate_purchase_context_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _normalize_trial_catalog_purchase_request(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseRequest:
        return await _normalize_trial_catalog_purchase_request_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _get_active_trial_subscriptions(
        self,
        *,
        current_user: UserDto,
    ) -> tuple[SubscriptionDto, ...]:
        return await _get_active_trial_subscriptions_impl(
            self,
            current_user=current_user,
        )

    async def _get_valid_catalog_purchase_plan(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> PlanDto:
        return await _get_valid_catalog_purchase_plan_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _validate_renew_purchase_context(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> ValidatedPurchaseContext:
        return await _validate_renew_purchase_context_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _validate_upgrade_purchase_context(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> ValidatedPurchaseContext:
        return await _validate_upgrade_purchase_context_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _get_single_owned_subscription(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionDto:
        return await _get_single_owned_subscription_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _build_multi_renew_item_contexts(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        renew_ids: list[int],
    ) -> tuple[ResolvedRenewItemContext, ...]:
        return await _build_multi_renew_item_contexts_impl(
            self,
            request=request,
            current_user=current_user,
            renew_ids=renew_ids,
        )

    def _select_plan_from_candidates(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        purchase_type: PurchaseType,
        candidates: tuple[PlanDto, ...],
    ) -> PlanDto:
        return _select_plan_from_candidates_impl(
            self,
            request=request,
            purchase_type=purchase_type,
            candidates=candidates,
        )

    def _get_purchase_plan_id(self, request: SubscriptionPurchaseRequest) -> int:
        return _get_purchase_plan_id_impl(self, request)

    def _resolve_purchase_duration(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        plan: PlanDto,
    ) -> tuple[int, PlanDurationDto]:
        return _resolve_purchase_duration_impl(
            self,
            request=request,
            plan=plan,
        )

    def _resolve_effective_subscription_count(
        self,
        *,
        request: SubscriptionPurchaseRequest,
    ) -> tuple[int, int]:
        return _resolve_effective_subscription_count_impl(
            self,
            request=request,
        )

    async def _resolve_purchase_gateway(
        self,
        *,
        request: SubscriptionPurchaseRequest,
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        return await _resolve_purchase_gateway_impl(
            self,
            request=request,
        )

    async def _resolve_explicit_purchase_gateway(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        return await _resolve_explicit_purchase_gateway_impl(
            self,
            request=request,
            available_by_type=available_by_type,
        )

    def _resolve_implicit_purchase_gateway(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        available_gateways: list[PaymentGatewayDto],
        available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        return _resolve_implicit_purchase_gateway_impl(
            self,
            request=request,
            available_gateways=available_gateways,
            available_by_type=available_by_type,
        )

    def _resolve_gateway_price(
        self,
        *,
        duration: PlanDurationDto,
        gateway: PaymentGatewayDto,
    ) -> PlanPriceDto:
        return _resolve_gateway_price_impl(
            self,
            duration=duration,
            gateway=gateway,
        )

    def _calculate_final_purchase_price(
        self,
        *,
        current_user: UserDto,
        gateway: PaymentGatewayDto,
        price_obj: PlanPriceDto,
        effective_multiplier: int,
    ) -> PriceDetailsDto:
        return _calculate_final_purchase_price_impl(
            self,
            current_user=current_user,
            gateway=gateway,
            price_obj=price_obj,
            effective_multiplier=effective_multiplier,
        )

    async def _calculate_settlement_pricing(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        validated_context: ValidatedPurchaseContext,
        duration: PlanDurationDto,
        gateway: PaymentGatewayDto,
        effective_multiplier: int,
    ) -> tuple[PriceDetailsDto, tuple[TransactionRenewItemDto, ...]]:
        return await _calculate_settlement_pricing_impl(
            self,
            request=request,
            current_user=current_user,
            validated_context=validated_context,
            duration=duration,
            gateway=gateway,
            effective_multiplier=effective_multiplier,
        )

    def _build_renew_transaction_items(
        self,
        *,
        duration_days: int,
        gateway: PaymentGatewayDto,
        renew_item_contexts: tuple[ResolvedRenewItemContext, ...],
    ) -> tuple[tuple[TransactionRenewItemDto, ...], Decimal]:
        return _build_renew_transaction_items_impl(
            self,
            duration_days=duration_days,
            gateway=gateway,
            renew_item_contexts=renew_item_contexts,
        )

    async def _build_display_quote(
        self,
        *,
        current_user: UserDto,
        request: SubscriptionPurchaseRequest,
        gateway: PaymentGatewayDto,
        settlement_amount: Decimal,
        payment_asset: CryptoAsset | None,
    ) -> CurrencyConversionQuote:
        return await _build_display_quote_impl(
            self,
            current_user=current_user,
            request=request,
            gateway=gateway,
            settlement_amount=settlement_amount,
            payment_asset=payment_asset,
        )

    def _build_static_display_quote(
        self,
        *,
        amount: Decimal,
        currency: Currency,
    ) -> CurrencyConversionQuote:
        return _build_static_display_quote_impl(
            self,
            amount=amount,
            currency=currency,
        )

    def _resolve_payment_asset(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        gateway_type: PaymentGatewayType,
    ) -> CryptoAsset | None:
        return _resolve_payment_asset_impl(
            self,
            request=request,
            gateway_type=gateway_type,
        )

    def _collect_renew_ids(
        self,
        request: SubscriptionPurchaseRequest,
    ) -> list[int]:
        return _collect_renew_ids_impl(self, request)

    async def _assert_non_deleted_trial_requires_upgrade(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> None:
        await _assert_non_deleted_trial_requires_upgrade_impl(
            self,
            request=request,
            current_user=current_user,
        )

    async def _validate_subscription_limit(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        effective_subscription_count: int,
    ) -> None:
        await _validate_subscription_limit_impl(
            self,
            request=request,
            current_user=current_user,
            effective_subscription_count=effective_subscription_count,
        )

    def _resolve_purchase_device_types(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        effective_subscription_count: int,
    ) -> list[DeviceType] | None:
        return _resolve_purchase_device_types_impl(
            self,
            request=request,
            effective_subscription_count=effective_subscription_count,
        )

    async def _assert_partner_balance_purchase_allowed(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        gateway: PaymentGatewayDto,
    ) -> None:
        await _assert_partner_balance_purchase_allowed_impl(
            self,
            request=request,
            current_user=current_user,
            gateway=gateway,
        )

    async def _mark_purchase_transaction_failed_if_present(
        self,
        *,
        payment_id: UUID,
    ) -> TransactionDto | None:
        return await _mark_transaction_failed_impl(
            self,
            payment_id=payment_id,
        )

    async def _create_partner_balance_transaction(
        self,
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
        await _create_partner_balance_transaction_impl(
            self,
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

    async def _debit_partner_balance_or_fail(
        self,
        *,
        current_user: UserDto,
        payment_id: UUID,
        amount_kopecks: int,
    ) -> bool:
        return await _debit_partner_balance_or_fail_impl(
            self,
            current_user=current_user,
            payment_id=payment_id,
            amount_kopecks=amount_kopecks,
        )

    async def _handle_partner_balance_purchase(
        self,
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
        return await _handle_partner_balance_purchase_impl(
            self,
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

    async def _handle_external_purchase(
        self,
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
        return await _handle_external_purchase_impl(
            self,
            request=request,
            current_user=current_user,
            gateway_type=gateway_type,
            final_price=final_price,
            payment_asset=payment_asset,
            plan_snapshot=plan_snapshot,
            renew_items=renew_items,
            device_types=device_types,
        )
