from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from http import HTTPStatus

from loguru import logger

from src.core.config import AppConfig
from src.core.crypto_assets import get_supported_payment_assets
from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    PaymentGatewayType,
    PaymentSource,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    SubscriptionDto,
    UserDto,
)

from .market_quote import CurrencyConversionQuote, MarketQuoteService
from .partner import PartnerService
from .payment_gateway import PaymentGatewayService
from .plan import PlanService
from .pricing import PricingService
from .purchase_access import PurchaseAccessService
from .purchase_gateway_policy import (
    filter_gateways_by_channel,
    is_gateway_available_for_channel,
)
from .settings import SettingsService
from .subscription import SubscriptionService
from .subscription_purchase_flows import (
    ExternalPurchaseFlow,
    PartnerBalancePurchaseFlow,
    PurchaseExecutionResult,
    PurchaseFlowError,
)
from .subscription_purchase_policy import (
    SubscriptionActionPolicy,
    SubscriptionPurchaseOptionsResult,
    SubscriptionPurchasePolicyService,
)

PurchaseErrorDetail = str | dict[str, str]
ARCHIVED_PLAN_NOT_PURCHASABLE_CODE = "ARCHIVED_PLAN_NOT_PURCHASABLE"
ARCHIVED_PLAN_NOT_PURCHASABLE_MESSAGE = (
    "Archived plans cannot be purchased as a new subscription"
)


class SubscriptionPurchaseError(Exception):
    def __init__(self, *, status_code: int, detail: PurchaseErrorDetail) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseRequest:
    purchase_type: PurchaseType = PurchaseType.NEW
    payment_source: PaymentSource = PaymentSource.EXTERNAL
    channel: PurchaseChannel = PurchaseChannel.WEB
    plan_id: int | None = None
    duration_days: int | None = None
    device_type: DeviceType | None = None
    gateway_type: str | None = None
    renew_subscription_id: int | None = None
    renew_subscription_ids: tuple[int, ...] | None = None
    device_types: tuple[DeviceType, ...] | None = None
    quantity: int = 1
    promocode: str | None = None
    payment_asset: CryptoAsset | None = None
    success_redirect_url: str | None = None
    fail_redirect_url: str | None = None


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseResult:
    transaction_id: str
    payment_url: str | None
    url: str | None
    status: str
    message: str


@dataclass(slots=True, frozen=True)
class SubscriptionPurchaseQuoteResult:
    price: float
    original_price: float
    currency: str
    settlement_price: float
    settlement_original_price: float
    settlement_currency: str
    discount_percent: int
    discount_source: str
    payment_asset: str | None
    quote_source: str
    quote_expires_at: str
    quote_provider_count: int


@dataclass(slots=True, frozen=True)
class ValidatedPurchaseContext:
    plan: PlanDto
    source_subscription: SubscriptionDto | None = None


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
        self.partner_balance_purchase_flow = PartnerBalancePurchaseFlow(
            payment_gateway_service=payment_gateway_service,
            partner_service=partner_service,
        )
        self.external_purchase_flow = ExternalPurchaseFlow(
            config=config,
            payment_gateway_service=payment_gateway_service,
        )

    async def execute(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        await self.purchase_access_service.assert_can_purchase(current_user)
        return await self._execute_without_access_assert(
            request=request,
            current_user=current_user,
        )

    async def quote(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseQuoteResult:
        await self.purchase_access_service.assert_can_purchase(current_user)
        validated_context = await self._validate_purchase_context(
            request=request,
            current_user=current_user,
        )
        plan = validated_context.plan
        _, duration = self._resolve_purchase_duration(request=request, plan=plan)
        effective_multiplier, _ = self._resolve_effective_subscription_count(request=request)
        gateway, gateway_type = await self._resolve_purchase_gateway(request=request)
        payment_asset = self._resolve_payment_asset(
            request=request,
            gateway_type=gateway_type,
        )
        settlement_pricing = await self._calculate_settlement_pricing(
            request=request,
            current_user=current_user,
            plan=plan,
            duration=duration,
            gateway=gateway,
            effective_multiplier=effective_multiplier,
        )
        if request.payment_source == PaymentSource.PARTNER_BALANCE:
            try:
                await self.partner_balance_purchase_flow.assert_allowed(
                    current_user=current_user,
                    channel=request.channel,
                    gateway=gateway,
                    is_gateway_explicitly_selected=bool(request.gateway_type),
                )
            except PurchaseFlowError as exception:
                raise SubscriptionPurchaseError(
                    status_code=exception.status_code,
                    detail=exception.detail,
                ) from exception

        final_display_quote = await self._build_display_quote(
            current_user=current_user,
            request=request,
            gateway=gateway,
            settlement_amount=settlement_pricing.final_amount,
            payment_asset=payment_asset,
        )
        original_display_quote = await self._build_display_quote(
            current_user=current_user,
            request=request,
            gateway=gateway,
            settlement_amount=settlement_pricing.original_amount,
            payment_asset=payment_asset,
        )
        return SubscriptionPurchaseQuoteResult(
            price=float(final_display_quote.amount),
            original_price=float(original_display_quote.amount),
            currency=final_display_quote.currency.value,
            settlement_price=float(settlement_pricing.final_amount),
            settlement_original_price=float(settlement_pricing.original_amount),
            settlement_currency=gateway.currency.value,
            discount_percent=settlement_pricing.discount_percent,
            discount_source=settlement_pricing.discount_source.value,
            payment_asset=payment_asset.value if payment_asset else None,
            quote_source=final_display_quote.quote_source,
            quote_expires_at=final_display_quote.quote_expires_at,
            quote_provider_count=final_display_quote.quote_provider_count,
        )

    @staticmethod
    def _build_purchase_result(
        execution_result: PurchaseExecutionResult,
    ) -> SubscriptionPurchaseResult:
        return SubscriptionPurchaseResult(
            transaction_id=execution_result.transaction_id,
            payment_url=execution_result.payment_url,
            url=execution_result.url,
            status=execution_result.status,
            message=execution_result.message,
        )

    async def _execute_without_access_assert(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        validated_context = await self._validate_purchase_context(
            request=request,
            current_user=current_user,
        )
        plan = validated_context.plan
        duration_days, duration = self._resolve_purchase_duration(request=request, plan=plan)
        effective_multiplier, effective_subscription_count = (
            self._resolve_effective_subscription_count(request=request)
        )

        gateway, gateway_type = await self._resolve_purchase_gateway(request=request)
        payment_asset = self._resolve_payment_asset(
            request=request,
            gateway_type=gateway_type,
        )
        final_price = await self._calculate_settlement_pricing(
            request=request,
            current_user=current_user,
            plan=plan,
            duration=duration,
            gateway=gateway,
            effective_multiplier=effective_multiplier,
        )
        await self._validate_subscription_limit(
            request=request,
            current_user=current_user,
            effective_subscription_count=effective_subscription_count,
        )

        plan_snapshot = PlanSnapshotDto.from_plan(plan, duration_days)
        device_types = self._resolve_purchase_device_types(
            request=request,
            effective_subscription_count=effective_subscription_count,
        )

        try:
            if request.payment_source == PaymentSource.PARTNER_BALANCE:
                return self._build_purchase_result(
                    await self.partner_balance_purchase_flow.handle(
                        current_user=current_user,
                        channel=request.channel,
                        purchase_type=request.purchase_type,
                        gateway=gateway,
                        gateway_type=gateway_type,
                        is_gateway_explicitly_selected=bool(request.gateway_type),
                        final_price=final_price,
                        payment_asset=payment_asset,
                        plan_snapshot=plan_snapshot,
                        renew_subscription_id=request.renew_subscription_id,
                        renew_subscription_ids=list(request.renew_subscription_ids or ()) or None,
                        device_types=device_types,
                    )
                )

            return self._build_purchase_result(
                await self.external_purchase_flow.handle(
                    current_user=current_user,
                    gateway_type=gateway_type,
                    final_price=final_price,
                    payment_asset=payment_asset,
                    plan_snapshot=plan_snapshot,
                    purchase_type=request.purchase_type,
                    channel=request.channel,
                    renew_subscription_id=request.renew_subscription_id,
                    renew_subscription_ids=list(request.renew_subscription_ids or ()) or None,
                    device_types=device_types,
                    success_redirect_url=request.success_redirect_url,
                    fail_redirect_url=request.fail_redirect_url,
                )
            )
        except PurchaseFlowError as exception:
            raise SubscriptionPurchaseError(
                status_code=exception.status_code,
                detail=exception.detail,
            ) from exception

    async def execute_renewal_alias(
        self,
        *,
        subscription_id: int,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        await self.purchase_access_service.assert_can_purchase(current_user)
        base_subscription = await self.subscription_service.get(subscription_id)
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

        return await self._execute_without_access_assert(
            request=renew_request,
            current_user=current_user,
        )

    async def execute_upgrade_alias(
        self,
        *,
        subscription_id: int,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionPurchaseResult:
        await self.purchase_access_service.assert_can_purchase(current_user)
        base_subscription = await self.subscription_service.get(subscription_id)
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

        return await self._execute_without_access_assert(
            request=upgrade_request,
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
        if purchase_type not in {PurchaseType.RENEW, PurchaseType.UPGRADE}:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="purchase_type must be RENEW or UPGRADE",
            )

        subscription = await self.subscription_service.get(subscription_id)
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

        return await self.subscription_purchase_policy_service.get_purchase_options(
            current_user=current_user,
            subscription=subscription,
            purchase_type=purchase_type,
            channel=channel,
        )

    async def get_action_policy(
        self,
        *,
        current_user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionActionPolicy:
        return await self.subscription_purchase_policy_service.get_action_policy(
            current_user=current_user,
            subscription=subscription,
        )

    async def _validate_purchase_context(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> ValidatedPurchaseContext:
        if request.purchase_type in {PurchaseType.NEW, PurchaseType.ADDITIONAL}:
            await self._assert_non_deleted_trial_requires_upgrade(
                request=request,
                current_user=current_user,
            )
            plan = await self._get_valid_catalog_purchase_plan(
                request=request,
                current_user=current_user,
            )
            return ValidatedPurchaseContext(plan=plan)

        if request.purchase_type == PurchaseType.RENEW:
            return await self._validate_renew_purchase_context(
                request=request,
                current_user=current_user,
            )

        if request.purchase_type == PurchaseType.UPGRADE:
            return await self._validate_upgrade_purchase_context(
                request=request,
                current_user=current_user,
            )

        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unsupported purchase type: {request.purchase_type}",
        )

    async def _get_valid_catalog_purchase_plan(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> PlanDto:
        plan_id = self._get_purchase_plan_id(request)
        available_plans = await self.plan_service.get_available_plans(current_user)
        plan = next((candidate for candidate in available_plans if candidate.id == plan_id), None)
        if not plan:
            archived_plan = await self.plan_service.get(plan_id)
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
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> ValidatedPurchaseContext:
        renew_ids = self._collect_renew_ids(request)
        if len(renew_ids) > 1:
            await self._validate_multi_renew_selection(
                current_user=current_user,
                renew_ids=renew_ids,
            )
            plan = await self._get_valid_multi_renew_display_plan(
                request=request,
                current_user=current_user,
                renew_ids=renew_ids,
            )
            return ValidatedPurchaseContext(plan=plan)

        source_subscription = await self._get_single_owned_subscription(
            request=request,
            current_user=current_user,
        )
        selection = await self.subscription_purchase_policy_service.build_selection(
            current_user=current_user,
            subscription=source_subscription,
        )
        candidates = self.subscription_purchase_policy_service.get_purchase_candidates(
            selection=selection,
            purchase_type=PurchaseType.RENEW,
        )
        selected_plan = self._select_plan_from_candidates(
            request=request,
            purchase_type=PurchaseType.RENEW,
            candidates=candidates,
        )
        return ValidatedPurchaseContext(
            plan=selected_plan,
            source_subscription=source_subscription,
        )

    async def _validate_upgrade_purchase_context(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> ValidatedPurchaseContext:
        if len(self._collect_renew_ids(request)) > 1:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Upgrade is only available for a single subscription",
            )

        source_subscription = await self._get_single_owned_subscription(
            request=request,
            current_user=current_user,
        )
        selection = await self.subscription_purchase_policy_service.build_selection(
            current_user=current_user,
            subscription=source_subscription,
        )
        candidates = self.subscription_purchase_policy_service.get_purchase_candidates(
            selection=selection,
            purchase_type=PurchaseType.UPGRADE,
        )
        selected_plan = self._select_plan_from_candidates(
            request=request,
            purchase_type=PurchaseType.UPGRADE,
            candidates=candidates,
        )
        return ValidatedPurchaseContext(
            plan=selected_plan,
            source_subscription=source_subscription,
        )

    async def _get_single_owned_subscription(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> SubscriptionDto:
        renew_ids = self._collect_renew_ids(request)
        subscription_id = renew_ids[0] if renew_ids else None
        if subscription_id is None:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Subscription ID is required",
            )

        subscription = await self.subscription_service.get(subscription_id)
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

    async def _validate_multi_renew_selection(
        self,
        *,
        current_user: UserDto,
        renew_ids: list[int],
    ) -> None:
        for renew_id in renew_ids:
            renew_subscription = await self.subscription_service.get(renew_id)
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

            action_policy = await self.subscription_purchase_policy_service.get_action_policy(
                current_user=current_user,
                subscription=renew_subscription,
            )
            if not action_policy.can_multi_renew:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Subscription {renew_id} is not available for multi-renew",
                )

    async def _get_valid_multi_renew_display_plan(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        renew_ids: list[int],
    ) -> PlanDto:
        if request.plan_id:
            return await self._get_valid_catalog_purchase_plan(
                request=request,
                current_user=current_user,
            )

        first_subscription = await self.subscription_service.get(renew_ids[0])
        if not first_subscription:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Subscription {renew_ids[0]} not found",
            )

        source_plan_id = getattr(first_subscription.plan, "id", None)
        if not source_plan_id or source_plan_id <= 0:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Source plan is not available for multi-renew",
            )

        source_plan = await self.plan_service.get(source_plan_id)
        if not source_plan:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Source plan is not available for multi-renew",
            )
        return source_plan

    @staticmethod
    def _select_plan_from_candidates(
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
            (candidate for candidate in candidates if candidate.id == request.plan_id), None
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

    @staticmethod
    def _get_purchase_plan_id(request: SubscriptionPurchaseRequest) -> int:
        if not request.plan_id:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Plan ID is required",
            )
        return request.plan_id

    @staticmethod
    def _resolve_purchase_duration(
        *,
        request: SubscriptionPurchaseRequest,
        plan: PlanDto,
    ) -> tuple[int, PlanDurationDto]:
        duration_days = request.duration_days
        if not duration_days:
            if not plan.durations:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="No durations available for this plan",
                )
            duration_days = plan.durations[0].days

        duration = next((item for item in plan.durations if item.days == duration_days), None)
        if not duration:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Duration {duration_days} days not available for this plan",
            )

        return duration_days, duration

    @staticmethod
    def _resolve_effective_subscription_count(
        *,
        request: SubscriptionPurchaseRequest,
    ) -> tuple[int, int]:
        if (
            request.purchase_type in (PurchaseType.RENEW, PurchaseType.UPGRADE)
            and request.quantity > 1
        ):
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Quantity greater than 1 is not supported for renew or upgrade purchases",
            )

        effective_multiplier = (
            request.quantity
            if request.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL)
            else 1
        )
        return effective_multiplier, effective_multiplier

    async def _resolve_purchase_gateway(
        self,
        *,
        request: SubscriptionPurchaseRequest,
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        available_gateways = filter_gateways_by_channel(
            await self.payment_gateway_service.filter_active(is_active=True),
            channel=request.channel,
        )
        available_by_type = {gateway.type: gateway for gateway in available_gateways}

        if request.gateway_type:
            return await self._resolve_explicit_purchase_gateway(
                request=request,
                available_by_type=available_by_type,
            )

        return self._resolve_implicit_purchase_gateway(
            request=request,
            available_gateways=available_gateways,
            available_by_type=available_by_type,
        )

    async def _resolve_explicit_purchase_gateway(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        try:
            gateway_type = PaymentGatewayType(request.gateway_type or "")
        except ValueError as exception:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid gateway type: {request.gateway_type}",
            ) from exception

        if not is_gateway_available_for_channel(gateway_type, request.channel):
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"Gateway {gateway_type.value} is not available for "
                    f"{request.channel.value.lower()} purchases"
                ),
            )

        gateway = available_by_type.get(gateway_type)
        if gateway:
            return gateway, gateway_type

        configured_gateway = await self.payment_gateway_service.get_by_type(gateway_type)
        if not configured_gateway:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Gateway {gateway_type.value} is not configured",
            )
        if not configured_gateway.is_active:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Gateway {gateway_type.value} is disabled",
            )
        raise SubscriptionPurchaseError(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Gateway {gateway_type.value} is not available for "
                f"{request.channel.value.lower()} purchases"
            ),
        )

    @staticmethod
    def _resolve_implicit_purchase_gateway(
        *,
        request: SubscriptionPurchaseRequest,
        available_gateways: list[PaymentGatewayDto],
        available_by_type: dict[PaymentGatewayType, PaymentGatewayDto],
    ) -> tuple[PaymentGatewayDto, PaymentGatewayType]:
        if request.channel == PurchaseChannel.TELEGRAM:
            preferred_gateway = available_by_type.get(PaymentGatewayType.TELEGRAM_STARS)
            if preferred_gateway:
                return preferred_gateway, preferred_gateway.type
            if len(available_gateways) == 1:
                only_gateway = available_gateways[0]
                return only_gateway, only_gateway.type
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Gateway type is required for Telegram purchase",
            )

        if not available_gateways:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="No active web payment gateways are available",
            )
        if len(available_gateways) > 1:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Gateway type is required when multiple web gateways are available",
            )

        only_gateway = available_gateways[0]
        return only_gateway, only_gateway.type

    @staticmethod
    def _resolve_gateway_price(
        *,
        duration: PlanDurationDto,
        gateway: PaymentGatewayDto,
    ) -> PlanPriceDto:
        price_obj = next(
            (price for price in duration.prices if price.currency == gateway.currency),
            None,
        )
        if not price_obj:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Price not found for gateway currency {gateway.currency.value}",
            )
        return price_obj

    def _calculate_final_purchase_price(
        self,
        *,
        current_user: UserDto,
        gateway: PaymentGatewayDto,
        price_obj: PlanPriceDto,
        effective_multiplier: int,
    ) -> PriceDetailsDto:
        price_for_calculation = Decimal(price_obj.price) * Decimal(effective_multiplier)
        return self.pricing_service.calculate(
            user=current_user,
            price=price_for_calculation,
            currency=gateway.currency,
        )

    async def _calculate_settlement_pricing(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        plan: PlanDto,
        duration: PlanDurationDto,
        gateway: PaymentGatewayDto,
        effective_multiplier: int,
    ) -> PriceDetailsDto:
        renew_ids = self._collect_renew_ids(request)
        if request.purchase_type == PurchaseType.RENEW and len(renew_ids) > 1:
            total_base_price = await self._calculate_multi_renew_base_price(
                duration_days=duration.days,
                gateway=gateway,
                renew_ids=renew_ids,
            )
            return self.pricing_service.calculate(
                user=current_user,
                price=total_base_price,
                currency=gateway.currency,
            )

        price_obj = self._resolve_gateway_price(duration=duration, gateway=gateway)
        return self._calculate_final_purchase_price(
            current_user=current_user,
            gateway=gateway,
            price_obj=price_obj,
            effective_multiplier=effective_multiplier,
        )

    async def _calculate_multi_renew_base_price(
        self,
        *,
        duration_days: int,
        gateway: PaymentGatewayDto,
        renew_ids: list[int],
    ) -> Decimal:
        total_price = Decimal("0")

        for renew_id in renew_ids:
            renew_subscription = await self.subscription_service.get(renew_id)
            if not renew_subscription:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.NOT_FOUND,
                    detail=f"Subscription {renew_id} not found",
                )

            source_plan_id = getattr(renew_subscription.plan, "id", None)
            if not source_plan_id or source_plan_id <= 0:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Source plan is unavailable for subscription {renew_id}",
                )

            matched_plan = await self.plan_service.get(source_plan_id)
            if not matched_plan:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Source plan is unavailable for subscription {renew_id}",
                )

            renew_duration = matched_plan.get_duration(duration_days)
            if not renew_duration:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=(
                        f"Duration {duration_days} days not available for subscription {renew_id}"
                    ),
                )

            renew_price = next(
                (
                    price.price
                    for price in renew_duration.prices
                    if price.currency == gateway.currency
                ),
                None,
            )
            if renew_price is None:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=(
                        f"Price not found for gateway currency {gateway.currency.value} "
                        f"on subscription {renew_id}"
                    ),
                )

            total_price += Decimal(renew_price)

        return total_price

    async def _build_display_quote(
        self,
        *,
        current_user: UserDto,
        request: SubscriptionPurchaseRequest,
        gateway: PaymentGatewayDto,
        settlement_amount: Decimal,
        payment_asset: CryptoAsset | None,
    ) -> CurrencyConversionQuote:
        if request.payment_source == PaymentSource.PARTNER_BALANCE:
            effective_currency = await self.settings_service.resolve_partner_balance_currency(
                current_user
            )
            return await self.market_quote_service.convert_from_rub(
                amount_rub=settlement_amount,
                target_currency=effective_currency,
            )

        if payment_asset is not None:
            if gateway.currency != Currency.USD:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=(
                        f"Gateway {gateway.type.value} must use USD settlement "
                        "for crypto payment quotes"
                    ),
                )
            return await self.market_quote_service.convert_from_usd(
                amount_usd=settlement_amount,
                target_currency=Currency(payment_asset.value),
            )

        return self._build_static_display_quote(
            amount=settlement_amount,
            currency=gateway.currency,
        )

    def _build_static_display_quote(
        self,
        *,
        amount: Decimal,
        currency: Currency,
    ) -> CurrencyConversionQuote:
        if amount <= 0:
            normalized_amount = Decimal(0)
        else:
            normalized_amount = self.pricing_service.apply_currency_rules(amount, currency)
        return CurrencyConversionQuote(
            amount=normalized_amount,
            currency=currency,
            quote_rate=Decimal("1"),
            quote_source="STATIC",
            quote_provider_count=0,
            quote_expires_at=datetime_now().replace(microsecond=0).isoformat(),
        )

    @staticmethod
    def _resolve_payment_asset(
        *,
        request: SubscriptionPurchaseRequest,
        gateway_type: PaymentGatewayType,
    ) -> CryptoAsset | None:
        supported_assets = get_supported_payment_assets(gateway_type)
        requested_asset = request.payment_asset

        if not supported_assets:
            if requested_asset is not None:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"Gateway {gateway_type.value} does not support payment_asset",
                )
            return None

        if requested_asset is None:
            if len(supported_assets) == 1:
                return supported_assets[0]
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"payment_asset is required for gateway {gateway_type.value}",
            )

        if requested_asset not in supported_assets:
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=(
                    f"Unsupported payment_asset '{requested_asset.value}' for "
                    f"gateway {gateway_type.value}"
                ),
            )

        return requested_asset

    @staticmethod
    def _collect_renew_ids(
        request: SubscriptionPurchaseRequest,
    ) -> list[int]:
        renew_ids: list[int] = []
        if request.renew_subscription_id:
            renew_ids.append(request.renew_subscription_id)
        if request.renew_subscription_ids:
            renew_ids.extend(request.renew_subscription_ids)
        return list(dict.fromkeys(renew_ids))

    async def _assert_non_deleted_trial_requires_upgrade(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
    ) -> None:
        if request.purchase_type not in {PurchaseType.NEW, PurchaseType.ADDITIONAL}:
            return

        existing_subs = await self.subscription_service.get_all_by_user(current_user.telegram_id)
        if any(
            subscription.is_trial and not self._is_deleted_subscription(subscription)
            for subscription in existing_subs
        ):
            raise SubscriptionPurchaseError(
                status_code=HTTPStatus.BAD_REQUEST,
                detail={
                    "code": "TRIAL_UPGRADE_REQUIRED",
                    "message": "An existing trial subscription can only be continued via upgrade",
                },
            )

    async def _validate_subscription_limit(
        self,
        *,
        request: SubscriptionPurchaseRequest,
        current_user: UserDto,
        effective_subscription_count: int,
    ) -> None:
        if request.purchase_type not in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
            return

        existing_subs = await self.subscription_service.get_all_by_user(current_user.telegram_id)
        active_subs = [
            subscription
            for subscription in existing_subs
            if not self._is_deleted_subscription(subscription)
        ]
        active_count = len(active_subs)

        required_new = effective_subscription_count

        max_subscriptions = await self.settings_service.get_max_subscriptions_for_user(current_user)
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

    @staticmethod
    def _resolve_purchase_device_types(
        *,
        request: SubscriptionPurchaseRequest,
        effective_subscription_count: int,
    ) -> list[DeviceType] | None:
        raw_device_types = list(request.device_types or ())
        if request.device_type and not raw_device_types:
            raw_device_types = [request.device_type] * effective_subscription_count

        if (
            request.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL)
            and raw_device_types
        ):
            if len(raw_device_types) != effective_subscription_count:
                raise SubscriptionPurchaseError(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=(
                        "Device types count does not match requested subscriptions count: "
                        f"{len(raw_device_types)} != {effective_subscription_count}"
                    ),
                )

        return raw_device_types or None

    @staticmethod
    def _is_deleted_subscription(subscription: SubscriptionDto) -> bool:
        status_value = subscription.status
        if hasattr(status_value, "value"):
            return str(getattr(status_value, "value")) == SubscriptionStatus.DELETED.value
        return str(status_value) == SubscriptionStatus.DELETED.value
