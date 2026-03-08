from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.core.enums import PartnerAccrualStrategy, PartnerLevel, PaymentGatewayType
from src.infrastructure.database.models.dto import PartnerSettingsDto
from src.services.partner import PartnerService


def _build_partner_service(
    *,
    partner_chain: list[SimpleNamespace],
    already_received: bool = False,
) -> PartnerService:
    service = object.__new__(PartnerService)
    service.settings_service = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                partner=SimpleNamespace(
                    enabled=True,
                    get_gateway_commission=lambda _gateway: Decimal("2.5"),
                )
            )
        )
    )
    service.uow = SimpleNamespace(
        repository=SimpleNamespace(
            partners=SimpleNamespace(
                get_partner_chain_for_user=AsyncMock(return_value=partner_chain),
                has_partner_received_payment_from_referral=AsyncMock(return_value=already_received),
            )
        )
    )
    service.user_service = SimpleNamespace(get=AsyncMock())
    service.notification_service = SimpleNamespace(notify_user=AsyncMock())
    service.get_partner = AsyncMock()
    service._calculate_partner_earning = AsyncMock()
    service.create_partner_transaction = AsyncMock()
    return service


def _build_partner(
    *,
    use_global_settings: bool,
    accrual_strategy: PartnerAccrualStrategy,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=501,
        is_active=True,
        user_telegram_id=9001,
        balance=1000,
        total_earned=2000,
        individual_settings=SimpleNamespace(
            use_global_settings=use_global_settings,
            accrual_strategy=accrual_strategy,
        ),
    )


def test_process_partner_earning_skips_on_first_payment_repeat() -> None:
    referral = SimpleNamespace(partner_id=501, level=PartnerLevel.LEVEL_1)
    partner = _build_partner(
        use_global_settings=False,
        accrual_strategy=PartnerAccrualStrategy.ON_FIRST_PAYMENT,
    )
    service = _build_partner_service(partner_chain=[referral], already_received=True)
    service.get_partner = AsyncMock(return_value=partner)
    service.user_service.get = AsyncMock(return_value=SimpleNamespace(name="Payer", username=None))

    asyncio.run(
        service.process_partner_earning(
            payer_user_id=7001,
            payment_amount=Decimal("100"),
            gateway_type=PaymentGatewayType.YOOKASSA,
        )
    )

    service._calculate_partner_earning.assert_not_awaited()
    service.create_partner_transaction.assert_not_awaited()
    service.notification_service.notify_user.assert_not_awaited()


def test_process_partner_earning_skips_zero_earning() -> None:
    referral = SimpleNamespace(partner_id=501, level=PartnerLevel.LEVEL_1)
    partner = _build_partner(
        use_global_settings=True,
        accrual_strategy=PartnerAccrualStrategy.ON_EACH_PAYMENT,
    )
    service = _build_partner_service(partner_chain=[referral], already_received=False)
    service.get_partner = AsyncMock(return_value=partner)
    service._calculate_partner_earning = AsyncMock(return_value=(0, Decimal("0")))
    service.user_service.get = AsyncMock(return_value=SimpleNamespace(name="Payer", username=None))

    asyncio.run(
        service.process_partner_earning(
            payer_user_id=7002,
            payment_amount=Decimal("50"),
            gateway_type=PaymentGatewayType.YOOKASSA,
        )
    )

    service.create_partner_transaction.assert_not_awaited()
    service.notification_service.notify_user.assert_not_awaited()


def test_process_partner_earning_creates_transaction_and_notifies() -> None:
    referral = SimpleNamespace(partner_id=501, level=PartnerLevel.LEVEL_1)
    partner = _build_partner(
        use_global_settings=True,
        accrual_strategy=PartnerAccrualStrategy.ON_EACH_PAYMENT,
    )
    service = _build_partner_service(partner_chain=[referral], already_received=False)
    service.get_partner = AsyncMock(return_value=partner)
    service._calculate_partner_earning = AsyncMock(return_value=(350, Decimal("7")))
    service.user_service.get = AsyncMock(
        side_effect=[
            SimpleNamespace(name="Payer", username=None),
            SimpleNamespace(telegram_id=9001),
        ]
    )

    asyncio.run(
        service.process_partner_earning(
            payer_user_id=7003,
            payment_amount=Decimal("200"),
            gateway_type=PaymentGatewayType.YOOKASSA,
        )
    )

    service.create_partner_transaction.assert_awaited_once()
    create_kwargs = service.create_partner_transaction.await_args.kwargs
    assert create_kwargs["earned_amount"] == 350
    assert create_kwargs["referral_telegram_id"] == 7003
    assert create_kwargs["level"] == PartnerLevel.LEVEL_1

    assert partner.balance == 1350
    assert partner.total_earned == 2350
    service.notification_service.notify_user.assert_awaited_once()


def test_partner_settings_support_new_gateway_commissions() -> None:
    settings = PartnerSettingsDto()

    assert settings.get_gateway_commission("CRYPTOMUS") == settings.cryptomus_commission
    assert settings.get_gateway_commission("ROBOKASSA") == settings.robokassa_commission
    assert settings.get_gateway_commission("STRIPE") == settings.stripe_commission
    assert settings.get_gateway_commission("MULENPAY") == settings.mulenpay_commission
    assert (
        settings.get_gateway_commission("CLOUDPAYMENTS")
        == settings.cloudpayments_commission
    )
