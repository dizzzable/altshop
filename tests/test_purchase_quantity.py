from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from httpx import HTTPStatusError, Request, Response

from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    DiscountSource,
    PaymentGatewayType,
    PaymentSource,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    PriceDetailsDto,
    UserDto,
)
from src.services.subscription_purchase import (
    SubscriptionPurchaseError,
    SubscriptionPurchaseRequest,
    SubscriptionPurchaseService,
)


def _build_user() -> UserDto:
    return UserDto(
        telegram_id=1001,
        referral_code="ref1001",
        name="Test User",
    )


def _build_plan(
    *,
    subscription_count: int,
    price: Decimal = Decimal("100"),
    currency: Currency = Currency.XTR,
) -> PlanDto:
    return PlanDto(
        id=11,
        name="Test Plan",
        is_active=True,
        durations=[
            PlanDurationDto(
                days=30,
                prices=[PlanPriceDto(currency=currency, price=price)],
            )
        ],
    )


def _build_telegram_gateway() -> PaymentGatewayDto:
    return PaymentGatewayDto(
        id=7,
        order_index=1,
        type=PaymentGatewayType.TELEGRAM_STARS,
        currency=Currency.XTR,
        is_active=True,
    )


def _build_rub_gateway() -> PaymentGatewayDto:
    return PaymentGatewayDto(
        id=8,
        order_index=1,
        type=PaymentGatewayType.YOOKASSA,
        currency=Currency.RUB,
        is_active=True,
    )


def _build_crypto_gateway(
    gateway_type: PaymentGatewayType = PaymentGatewayType.CRYPTOMUS,
) -> PaymentGatewayDto:
    return PaymentGatewayDto(
        id=9,
        order_index=1,
        type=gateway_type,
        currency=Currency.USD,
        is_active=True,
    )


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        web_app=SimpleNamespace(url_str="https://example.com/webapp"),
        domain=SimpleNamespace(get_secret_value=lambda: "example.com"),
    )


def _build_service(
    *,
    plan: PlanDto,
    active_subscriptions: list[SimpleNamespace],
    max_subscriptions: int,
    gateways: list[PaymentGatewayDto] | None = None,
    partner_service: SimpleNamespace | None = None,
    pricing_amount: Decimal = Decimal("100"),
) -> tuple[SubscriptionPurchaseService, SimpleNamespace, SimpleNamespace]:
    plan_service = SimpleNamespace(get=AsyncMock(return_value=plan))
    pricing_service = SimpleNamespace(
        calculate=Mock(
            return_value=PriceDetailsDto(
                original_amount=pricing_amount,
                final_amount=pricing_amount,
            )
        )
    )
    subscription_service = SimpleNamespace(
        get=AsyncMock(return_value=None),
        get_all_by_user=AsyncMock(return_value=active_subscriptions),
    )
    settings_service = SimpleNamespace(
        get_max_subscriptions_for_user=AsyncMock(return_value=max_subscriptions),
        resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
    )
    market_quote_service = SimpleNamespace(
        convert_from_usd=AsyncMock(),
        convert_from_rub=AsyncMock(),
        convert_to_rub=AsyncMock(),
        get_usd_rub_quote=AsyncMock(),
        get_asset_usd_quote=AsyncMock(),
    )
    purchase_access_service = SimpleNamespace(assert_can_purchase=AsyncMock())
    payment_gateway_service = SimpleNamespace(
        filter_active=AsyncMock(return_value=gateways or [_build_telegram_gateway()]),
        get_by_type=AsyncMock(return_value=(gateways or [_build_telegram_gateway()])[0]),
        create_payment=AsyncMock(return_value=SimpleNamespace(id=uuid4(), url="https://pay.test")),
        handle_payment_succeeded=AsyncMock(),
        transaction_service=SimpleNamespace(
            get=AsyncMock(return_value=None),
            create=AsyncMock(),
            update=AsyncMock(),
        ),
    )
    resolved_partner_service = partner_service or SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=None),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=False),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    service = SubscriptionPurchaseService(
        config=_build_config(),
        plan_service=plan_service,
        pricing_service=pricing_service,
        purchase_access_service=purchase_access_service,
        subscription_service=subscription_service,
        settings_service=settings_service,
        payment_gateway_service=payment_gateway_service,
        partner_service=resolved_partner_service,
        market_quote_service=market_quote_service,
    )
    return service, payment_gateway_service, subscription_service


def test_purchase_rejects_quantity_for_renew() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1)
    service, _, _ = _build_service(plan=plan, active_subscriptions=[], max_subscriptions=10)

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.RENEW,
                    channel=PurchaseChannel.TELEGRAM,
                    plan_id=plan.id,
                    duration_days=30,
                    quantity=2,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "Quantity greater than 1" in str(exc_info.value.detail)


def test_purchase_quantity_is_used_in_limit_check() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=2)
    active_subscriptions = [
        SimpleNamespace(status=SubscriptionStatus.ACTIVE, is_trial=False),
        SimpleNamespace(status=SubscriptionStatus.ACTIVE, is_trial=False),
    ]
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=active_subscriptions,
        max_subscriptions=3,
    )

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.TELEGRAM,
                    plan_id=plan.id,
                    duration_days=30,
                    quantity=2,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "requested new: 2" in str(exc_info.value.detail)


def test_purchase_expands_device_types_and_updates_snapshot_count() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=2)
    service, payment_gateway_service, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=20,
    )

    asyncio.run(
        service.execute(
            request=SubscriptionPurchaseRequest(
                purchase_type=PurchaseType.NEW,
                channel=PurchaseChannel.TELEGRAM,
                plan_id=plan.id,
                duration_days=30,
                quantity=2,
                device_type=DeviceType.WINDOWS,
            ),
            current_user=user,
        )
    )

    calculate_call = service.pricing_service.calculate.call_args.kwargs
    assert calculate_call["price"] == Decimal("200")

    create_payment_call = payment_gateway_service.create_payment.call_args.kwargs
    assert len(create_payment_call["device_types"]) == 2
    assert all(
        device_type == DeviceType.WINDOWS for device_type in create_payment_call["device_types"]
    )
    assert not hasattr(create_payment_call["plan"], "subscription_count")


def test_purchase_requires_gateway_with_multiple_web_gateways() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1)
    gateways = [
        PaymentGatewayDto(
            id=1,
            order_index=1,
            type=PaymentGatewayType.YOOKASSA,
            currency=Currency.RUB,
            is_active=True,
        ),
        PaymentGatewayDto(
            id=2,
            order_index=2,
            type=PaymentGatewayType.CRYPTOMUS,
            currency=Currency.USD,
            is_active=True,
        ),
    ]
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=gateways,
    )

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.WEB,
                    plan_id=plan.id,
                    duration_days=30,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "Gateway type is required when multiple web gateways are available" in str(
        exc_info.value.detail
    )


def test_purchase_rejects_renew_for_foreign_subscription() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1)
    service, _, subscription_service = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
    )
    subscription_service.get = AsyncMock(return_value=SimpleNamespace(user_telegram_id=999999))

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.RENEW,
                    channel=PurchaseChannel.TELEGRAM,
                    plan_id=plan.id,
                    duration_days=30,
                    gateway_type=PaymentGatewayType.TELEGRAM_STARS.value,
                    renew_subscription_id=777,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 403
    assert "Access denied to subscription 777" in str(exc_info.value.detail)


def test_purchase_rejects_device_types_count_mismatch() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=2)
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=20,
    )

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.TELEGRAM,
                    plan_id=plan.id,
                    duration_days=30,
                    quantity=2,
                    device_types=(DeviceType.IPHONE,),
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "Device types count does not match requested subscriptions count" in str(
        exc_info.value.detail
    )


def test_partner_balance_debit_failure_marks_transaction_failed() -> None:
    user = _build_user()
    plan = PlanDto(
        id=11,
        name="Test Plan",
        is_active=True,
        durations=[
            PlanDurationDto(
                days=30,
                prices=[PlanPriceDto(currency=Currency.RUB, price=Decimal("15"))],
            )
        ],
    )
    pending_tx = SimpleNamespace(is_completed=False, status=TransactionStatus.PENDING)
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(
            return_value=SimpleNamespace(id=55, is_active=True, balance=500)
        ),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=False),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    service, payment_gateway_service, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_rub_gateway()],
        partner_service=partner_service,
        pricing_amount=Decimal("15"),
    )
    payment_gateway_service.transaction_service.get = AsyncMock(return_value=pending_tx)

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    payment_source=PaymentSource.PARTNER_BALANCE,
                    channel=PurchaseChannel.WEB,
                    plan_id=plan.id,
                    duration_days=30,
                    gateway_type=PaymentGatewayType.YOOKASSA.value,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INSUFFICIENT_PARTNER_BALANCE"
    assert pending_tx.status == TransactionStatus.FAILED
    payment_gateway_service.transaction_service.update.assert_awaited_once_with(pending_tx)


def test_execute_renewal_alias_sets_default_renew_subscription_id() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1)
    service, payment_gateway_service, subscription_service = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
    )
    subscription_service.get = AsyncMock(
        return_value=SimpleNamespace(user_telegram_id=user.telegram_id)
    )

    asyncio.run(
        service.execute_renewal_alias(
            subscription_id=77,
            request=SubscriptionPurchaseRequest(
                channel=PurchaseChannel.TELEGRAM,
                plan_id=plan.id,
                duration_days=30,
                gateway_type=PaymentGatewayType.TELEGRAM_STARS.value,
            ),
            current_user=user,
        )
    )

    create_payment_call = payment_gateway_service.create_payment.call_args.kwargs
    assert create_payment_call["renew_subscription_id"] == 77


def test_crypto_purchase_requires_payment_asset_for_multi_asset_gateway() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1, currency=Currency.USD)
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_crypto_gateway()],
    )

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.WEB,
                    plan_id=plan.id,
                    duration_days=30,
                    gateway_type=PaymentGatewayType.CRYPTOMUS.value,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "payment_asset is required for gateway CRYPTOMUS" in str(exc_info.value.detail)


def test_crypto_purchase_rejects_unsupported_payment_asset() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1, currency=Currency.USD)
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_crypto_gateway(PaymentGatewayType.CRYPTOPAY)],
    )

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.WEB,
                    plan_id=plan.id,
                    duration_days=30,
                    gateway_type=PaymentGatewayType.CRYPTOPAY.value,
                    payment_asset=CryptoAsset.DASH,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert "Unsupported payment_asset 'DASH' for gateway CRYPTOPAY" in str(
        exc_info.value.detail
    )


def test_crypto_purchase_passes_selected_payment_asset_to_gateway_service() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1, currency=Currency.USD)
    service, payment_gateway_service, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_crypto_gateway()],
    )

    asyncio.run(
        service.execute(
            request=SubscriptionPurchaseRequest(
                purchase_type=PurchaseType.NEW,
                channel=PurchaseChannel.WEB,
                plan_id=plan.id,
                duration_days=30,
                gateway_type=PaymentGatewayType.CRYPTOMUS.value,
                payment_asset=CryptoAsset.USDC,
            ),
            current_user=user,
        )
    )

    create_payment_call = payment_gateway_service.create_payment.call_args.kwargs
    assert create_payment_call["payment_asset"] == CryptoAsset.USDC


def test_quote_converts_crypto_amount_into_selected_asset() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1, currency=Currency.USD)
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_crypto_gateway()],
    )
    service.pricing_service.calculate = Mock(
        return_value=PriceDetailsDto(
            original_amount=Decimal("100"),
            final_amount=Decimal("80"),
            discount_percent=20,
            discount_source=DiscountSource.PERSONAL,
        )
    )
    service.market_quote_service.convert_from_usd = AsyncMock(
        return_value=SimpleNamespace(
            amount=Decimal("16"),
            currency=Currency.USDT,
            quote_rate=Decimal("5"),
            quote_source="MARKET_MAX_REAL",
            quote_provider_count=3,
            quote_expires_at="2026-03-08T00:00:00+00:00",
        )
    )

    result = asyncio.run(
        service.quote(
            request=SubscriptionPurchaseRequest(
                purchase_type=PurchaseType.NEW,
                channel=PurchaseChannel.WEB,
                plan_id=plan.id,
                duration_days=30,
                gateway_type=PaymentGatewayType.CRYPTOMUS.value,
                payment_asset=CryptoAsset.USDT,
            ),
            current_user=user,
        )
    )

    assert result.price == 16.0
    assert result.original_price == 16.0
    assert result.currency == Currency.USDT.value
    assert result.settlement_price == 80.0
    assert result.settlement_original_price == 100.0
    assert result.settlement_currency == Currency.USD.value
    assert result.discount_percent == 20
    assert result.discount_source == DiscountSource.PERSONAL.value
    assert result.payment_asset == CryptoAsset.USDT.value
    assert result.quote_source == "MARKET_MAX_REAL"
    assert result.quote_provider_count == 3


def test_quote_converts_partner_balance_display_to_effective_currency() -> None:
    user = _build_user()
    plan = PlanDto(
        id=11,
        name="Test Plan",
        is_active=True,
        durations=[
            PlanDurationDto(
                days=30,
                prices=[PlanPriceDto(currency=Currency.RUB, price=Decimal("1000"))],
            )
        ],
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(
            return_value=SimpleNamespace(id=55, is_active=True, balance=500000)
        ),
        debit_balance_for_subscription_purchase=AsyncMock(return_value=True),
        credit_balance_for_failed_subscription_purchase=AsyncMock(),
    )
    service, _, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_rub_gateway()],
        partner_service=partner_service,
        pricing_amount=Decimal("1000"),
    )
    service.pricing_service.calculate = Mock(
        return_value=PriceDetailsDto(
            original_amount=Decimal("1000"),
            final_amount=Decimal("900"),
            discount_percent=10,
            discount_source=DiscountSource.PURCHASE,
        )
    )
    service.settings_service.resolve_partner_balance_currency = AsyncMock(
        return_value=Currency.USDT
    )
    service.market_quote_service.convert_from_rub = AsyncMock(
        return_value=SimpleNamespace(
            amount=Decimal("12.5"),
            currency=Currency.USDT,
            quote_rate=Decimal("72"),
            quote_source="MARKET_MAX_REAL",
            quote_provider_count=2,
            quote_expires_at="2026-03-08T00:00:00+00:00",
        )
    )

    result = asyncio.run(
        service.quote(
            request=SubscriptionPurchaseRequest(
                purchase_type=PurchaseType.NEW,
                payment_source=PaymentSource.PARTNER_BALANCE,
                channel=PurchaseChannel.WEB,
                plan_id=plan.id,
                duration_days=30,
                gateway_type=PaymentGatewayType.YOOKASSA.value,
            ),
            current_user=user,
        )
    )

    assert result.price == 12.5
    assert result.original_price == 12.5
    assert result.currency == Currency.USDT.value
    assert result.settlement_price == 900.0
    assert result.settlement_original_price == 1000.0
    assert result.settlement_currency == Currency.RUB.value
    assert result.discount_percent == 10
    assert result.discount_source == DiscountSource.PURCHASE.value
    assert result.quote_source == "MARKET_MAX_REAL"


def test_external_provider_http_error_is_normalized_to_bad_gateway() -> None:
    user = _build_user()
    plan = _build_plan(subscription_count=1, currency=Currency.USD)
    service, payment_gateway_service, _ = _build_service(
        plan=plan,
        active_subscriptions=[],
        max_subscriptions=10,
        gateways=[_build_crypto_gateway(PaymentGatewayType.HELEKET)],
    )
    payment_gateway_service.create_payment = AsyncMock(
        side_effect=HTTPStatusError(
            "invalid sign",
            request=Request("POST", "https://api.heleket.com/v1/payment"),
            response=Response(401),
        )
    )

    with pytest.raises(SubscriptionPurchaseError) as exc_info:
        asyncio.run(
            service.execute(
                request=SubscriptionPurchaseRequest(
                    purchase_type=PurchaseType.NEW,
                    channel=PurchaseChannel.WEB,
                    plan_id=plan.id,
                    duration_days=30,
                    gateway_type=PaymentGatewayType.HELEKET.value,
                    payment_asset=CryptoAsset.USDT,
                ),
                current_user=user,
            )
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Payment provider 'HELEKET' rejected the request (401)"
