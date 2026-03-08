from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.types import ContentType
from remnawave.enums.users import TrafficLimitStrategy

from src.bot.routers.dashboard.remnashop.banners.handlers import (
    _resolve_banner_upload_file,
)
from src.bot.routers.dashboard.remnashop.branding.handlers import _apply_field_value
from src.bot.routers.dashboard.remnashop.plans.handlers import (
    _normalize_plan_limits,
    _prepare_trial_plan,
)
from src.bot.routers.subscription import handlers as subscription_handlers
from src.bot.routers.subscription.getters import confirm_getter, payment_method_getter
from src.bot.routers.subscription.handlers import (
    _get_active_promocode_subscriptions,
    _handle_gateway_selection,
    _get_renewable_subscriptions,
    _store_pending_promocode_state,
)
from src.bot.routers.subscription.payment_helpers import build_payment_cache_key
from src.bot.states import Subscription
from src.core.constants import USER_KEY
from src.core.enums import (
    Currency,
    DeviceType,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PromocodeRewardType,
    PurchaseType,
    SubscriptionStatus,
)
from src.core.utils.adapter import DialogDataAdapter
from src.infrastructure.database.models.dto import (
    BrandingSettingsDto,
    PaymentGatewayDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    PriceDetailsDto,
    UserDto,
)


def _build_plan(
    *,
    plan_id: int = 1,
    availability: PlanAvailability = PlanAvailability.ALL,
    currency: Currency = Currency.RUB,
) -> PlanDto:
    return PlanDto(
        id=plan_id,
        name=f"Plan {plan_id}",
        type=PlanType.BOTH,
        availability=availability,
        traffic_limit=100,
        device_limit=2,
        subscription_count=1,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        internal_squads=[],
        durations=[
            PlanDurationDto(
                days=30,
                prices=[PlanPriceDto(currency=currency, price=Decimal("199"))],
            )
        ],
    )


def _build_user() -> UserDto:
    return UserDto(
        telegram_id=1001,
        referral_code="ref1001",
        name="Test User",
    )


def test_apply_field_value_updates_global_and_localized_branding_fields() -> None:
    branding = BrandingSettingsDto()

    _apply_field_value(branding, "project_name", "AltShop Pro")
    _apply_field_value(branding, "telegram_template", "Verification: {code}", locale="en")

    assert branding.project_name == "AltShop Pro"
    assert branding.verification.telegram_template.en == "Verification: {code}"


def test_resolve_banner_upload_file_accepts_supported_document() -> None:
    message = SimpleNamespace(
        content_type=ContentType.DOCUMENT,
        document=SimpleNamespace(file_id="file-1", mime_type="image/webp"),
    )

    file_id, file_ext = _resolve_banner_upload_file(message)

    assert file_id == "file-1"
    assert file_ext == "webp"


def test_get_renewable_subscriptions_skips_unlimited_and_non_matching_items() -> None:
    matched_plan = _build_plan()
    renewable = SimpleNamespace(
        status=SubscriptionStatus.ACTIVE,
        is_unlimited=False,
        find_matching_plan=lambda plans: plans[0],
    )
    unlimited = SimpleNamespace(
        status=SubscriptionStatus.ACTIVE,
        is_unlimited=True,
        find_matching_plan=lambda plans: plans[0],
    )
    deleted = SimpleNamespace(
        status=SubscriptionStatus.DELETED,
        is_unlimited=False,
        find_matching_plan=lambda plans: plans[0],
    )
    missing_match = SimpleNamespace(
        status=SubscriptionStatus.EXPIRED,
        is_unlimited=False,
        find_matching_plan=lambda plans: None,
    )

    result = _get_renewable_subscriptions(
        [renewable, unlimited, deleted, missing_match],
        [matched_plan],
    )

    assert result == [(renewable, matched_plan)]


def test_get_active_promocode_subscriptions_filters_deleted_and_unlimited() -> None:
    active = SimpleNamespace(status=SubscriptionStatus.ACTIVE, is_unlimited=False)
    expired = SimpleNamespace(status=SubscriptionStatus.EXPIRED, is_unlimited=False)
    deleted = SimpleNamespace(status=SubscriptionStatus.DELETED, is_unlimited=False)
    unlimited = SimpleNamespace(status=SubscriptionStatus.ACTIVE, is_unlimited=True)

    result = _get_active_promocode_subscriptions([active, expired, deleted, unlimited])

    assert result == [active, expired]


def test_store_pending_promocode_state_updates_and_clears_plan_name() -> None:
    dialog_manager = SimpleNamespace(dialog_data={})

    _store_pending_promocode_state(
        dialog_manager,
        code="WELCOME",
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        days=30,
        plan_name="Starter",
    )
    _store_pending_promocode_state(
        dialog_manager,
        code="BONUS",
        reward_type=PromocodeRewardType.DURATION,
        days=14,
    )

    assert dialog_manager.dialog_data["pending_promocode_code"] == "BONUS"
    assert dialog_manager.dialog_data["pending_promocode_days"] == 14
    assert dialog_manager.dialog_data["pending_promocode_reward_type"] == "DURATION"
    assert "pending_promocode_plan_name" not in dialog_manager.dialog_data


def test_normalize_plan_limits_resets_unlimited_and_non_allowed_lists() -> None:
    plan = _build_plan(availability=PlanAvailability.ALL)
    plan.type = PlanType.UNLIMITED
    plan.allowed_user_ids = [1001, 1002]

    _normalize_plan_limits(plan)

    assert plan.traffic_limit == -1
    assert plan.device_limit == -1
    assert plan.allowed_user_ids == []


def test_prepare_trial_plan_zeroes_prices_for_single_duration_trial() -> None:
    plan = _build_plan(plan_id=5, availability=PlanAvailability.TRIAL)
    notification_service = SimpleNamespace(notify_user=AsyncMock())
    plan_service = SimpleNamespace(get_trial_plan=AsyncMock(return_value=None))

    result = asyncio.run(
        _prepare_trial_plan(
            user=SimpleNamespace(telegram_id=1001),
            plan_dto=plan,
            notification_service=notification_service,
            plan_service=plan_service,
        )
    )

    assert result is True
    assert plan.durations[0].prices[0].price == Decimal("0")
    notification_service.notify_user.assert_not_awaited()


def test_prepare_trial_plan_rejects_duplicate_trial() -> None:
    plan = _build_plan(plan_id=5, availability=PlanAvailability.TRIAL)
    notification_service = SimpleNamespace(notify_user=AsyncMock())
    plan_service = SimpleNamespace(get_trial_plan=AsyncMock(return_value=SimpleNamespace(id=99)))

    result = asyncio.run(
        _prepare_trial_plan(
            user=SimpleNamespace(telegram_id=1001),
            plan_dto=plan,
            notification_service=notification_service,
            plan_service=plan_service,
        )
    )

    assert result is False
    notification_service.notify_user.assert_awaited_once()


def test_build_payment_cache_key_depends_on_asset_and_normalizes_context() -> None:
    left = build_payment_cache_key(
        plan_id=11,
        duration_days=30,
        gateway_type=PaymentGatewayType.CRYPTOMUS,
        purchase_type=PurchaseType.RENEW,
        renew_ids=[9, 3, 9],
        payment_asset="USDT",
        device_types=[DeviceType.MAC, DeviceType.WINDOWS],
    )
    right = build_payment_cache_key(
        plan_id=11,
        duration_days=30,
        gateway_type=PaymentGatewayType.CRYPTOMUS,
        purchase_type=PurchaseType.RENEW,
        renew_ids=[3, 9],
        payment_asset="USDT",
        device_types=[DeviceType.WINDOWS, DeviceType.MAC],
    )
    different_asset = build_payment_cache_key(
        plan_id=11,
        duration_days=30,
        gateway_type=PaymentGatewayType.CRYPTOMUS,
        purchase_type=PurchaseType.RENEW,
        renew_ids=[3, 9],
        payment_asset="BTC",
        device_types=[DeviceType.WINDOWS, DeviceType.MAC],
    )

    assert left == right
    assert left != different_asset


def test_handle_gateway_selection_routes_multi_asset_crypto_to_coin_step() -> None:
    user = _build_user()
    dialog_manager = SimpleNamespace(
        dialog_data={"purchase_type": PurchaseType.NEW},
        middleware_data={USER_KEY: user},
        switch_to=AsyncMock(),
    )

    result = asyncio.run(
        _handle_gateway_selection(
            dialog_manager=dialog_manager,
            plan=_build_plan(currency=Currency.USD),
            duration_days=30,
            gateway_type=PaymentGatewayType.CRYPTOMUS,
            auto_selected=False,
            subscription_purchase_service=SimpleNamespace(),
            notification_service=SimpleNamespace(),
            subscription_service=SimpleNamespace(),
            device_types=[DeviceType.MAC],
        )
    )

    assert result is True
    assert dialog_manager.dialog_data["selected_payment_method"] == PaymentGatewayType.CRYPTOMUS
    assert dialog_manager.dialog_data["payment_gateway_auto_selected"] is False
    assert "selected_payment_asset" not in dialog_manager.dialog_data
    dialog_manager.switch_to.assert_awaited_once_with(state=Subscription.PAYMENT_ASSET)


def test_handle_gateway_selection_routes_tbank_directly_to_confirm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _build_user()
    dialog_manager = SimpleNamespace(
        dialog_data={"purchase_type": PurchaseType.NEW},
        middleware_data={USER_KEY: user},
        switch_to=AsyncMock(),
    )
    create_payment = AsyncMock(
        return_value={
            "payment_id": "payment-1",
            "payment_url": "https://pay.test/tbank",
            "final_quote": {
                "price": 199.0,
                "original_price": 199.0,
                "discount_percent": 0,
                "currency": "RUB",
            },
        }
    )
    monkeypatch.setattr(subscription_handlers, "_create_payment_and_get_data", create_payment)

    result = asyncio.run(
        _handle_gateway_selection(
            dialog_manager=dialog_manager,
            plan=_build_plan(currency=Currency.RUB),
            duration_days=30,
            gateway_type=PaymentGatewayType.TBANK,
            auto_selected=False,
            subscription_purchase_service=SimpleNamespace(),
            notification_service=SimpleNamespace(),
            subscription_service=SimpleNamespace(),
        )
    )

    assert result is True
    assert dialog_manager.dialog_data["selected_payment_method"] == PaymentGatewayType.TBANK
    assert dialog_manager.dialog_data["payment_url"] == "https://pay.test/tbank"
    assert dialog_manager.dialog_data["final_quote"]["currency"] == "RUB"
    dialog_manager.switch_to.assert_awaited_once_with(state=Subscription.CONFIRM)
    create_payment.assert_awaited_once()


def test_payment_method_getter_includes_tbank_for_telegram_purchase() -> None:
    user = _build_user()
    dialog_manager = SimpleNamespace(
        dialog_data={
            "selected_duration": 30,
            "only_single_duration": True,
            "purchase_type": PurchaseType.NEW,
        }
    )
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(_build_plan(currency=Currency.RUB))
    payment_gateway_service = SimpleNamespace(
        filter_active=AsyncMock(
            return_value=[
                PaymentGatewayDto(
                    id=77,
                    order_index=1,
                    type=PaymentGatewayType.TBANK,
                    currency=Currency.RUB,
                    is_active=True,
                )
            ]
        )
    )
    pricing_service = SimpleNamespace(
        calculate=lambda user, price, currency: PriceDetailsDto(
            original_amount=price,
            final_amount=price,
        )
    )
    i18n = SimpleNamespace(get=lambda key, **kwargs: "30 days")
    dishka_container = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                payment_gateway_service,
                SimpleNamespace(),
                SimpleNamespace(),
                pricing_service,
                i18n,
            ]
        )
    )

    result = asyncio.run(
        payment_method_getter(
            dialog_manager=dialog_manager,
            user=user,
            dishka_container=dishka_container,
        )
    )

    assert [item["gateway_type"] for item in result["payment_methods"]] == [
        PaymentGatewayType.TBANK
    ]


def test_confirm_getter_uses_final_quote_values_for_crypto_payment() -> None:
    user = _build_user()
    dialog_manager = SimpleNamespace(
        dialog_data={
            "selected_duration": 30,
            "only_single_duration": True,
            "is_free": False,
            "selected_payment_method": PaymentGatewayType.CRYPTOMUS,
            "selected_payment_asset": "USDT",
            "purchase_type": PurchaseType.NEW,
            "payment_url": "https://pay.test/crypto",
            "final_quote": {
                "price": 16.0,
                "discount_percent": 20,
                "original_price": 20.0,
                "currency": "USDT",
            },
        }
    )
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(_build_plan(currency=Currency.USD))
    payment_gateway_service = SimpleNamespace(
        filter_active=AsyncMock(
            return_value=[
                PaymentGatewayDto(
                    id=91,
                    order_index=1,
                    type=PaymentGatewayType.CRYPTOMUS,
                    currency=Currency.USD,
                    is_active=True,
                )
            ]
        )
    )
    i18n = SimpleNamespace(get=lambda key, **kwargs: "30 days")
    dishka_container = SimpleNamespace(
        get=AsyncMock(
            side_effect=[
                i18n,
                payment_gateway_service,
                SimpleNamespace(),
                SimpleNamespace(),
            ]
        )
    )

    result = asyncio.run(
        confirm_getter(
            dialog_manager=dialog_manager,
            user=user,
            dishka_container=dishka_container,
        )
    )

    assert result["final_amount"] == 16.0
    assert result["original_amount"] == 20.0
    assert result["currency"] == Currency.USDT.symbol
    assert result["url"] == "https://pay.test/crypto"
    assert result["show_payment_asset_back"] is True
