from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from . import partner_earnings

if TYPE_CHECKING:
    from src.core.enums import PartnerAccrualStrategy, PartnerLevel, PaymentGatewayType
    from src.infrastructure.database.models.dto import PartnerDto, PartnerSettingsDto

    from .partner import PartnerService


async def debit_balance_for_subscription_purchase(
    service: PartnerService,
    *,
    user_telegram_id: int,
    amount_kopecks: int,
) -> bool:
    return await partner_earnings.debit_balance_for_subscription_purchase(
        service,
        user_telegram_id=user_telegram_id,
        amount_kopecks=amount_kopecks,
    )


async def credit_balance_for_failed_subscription_purchase(
    service: PartnerService,
    *,
    user_telegram_id: int,
    amount_kopecks: int,
) -> bool:
    return await partner_earnings.credit_balance_for_failed_subscription_purchase(
        service,
        user_telegram_id=user_telegram_id,
        amount_kopecks=amount_kopecks,
    )


def format_rub(service: PartnerService, value_kopecks: int) -> str:
    return partner_earnings._format_rub(service, value_kopecks)


async def resolve_payer_name(service: PartnerService, payer_user_id: int) -> str:
    return await partner_earnings._resolve_payer_name(service, payer_user_id)


def resolve_accrual_strategy(
    service: PartnerService,
    partner: PartnerDto,
) -> PartnerAccrualStrategy:
    return partner_earnings._resolve_accrual_strategy(service, partner)


async def should_skip_partner_earning(
    service: PartnerService,
    *,
    partner: PartnerDto,
    payer_user_id: int,
) -> bool:
    return await partner_earnings._should_skip_partner_earning(
        service,
        partner=partner,
        payer_user_id=payer_user_id,
    )


async def notify_partner_earning(
    service: PartnerService,
    *,
    partner: PartnerDto,
    payer_name: str,
    level: PartnerLevel,
    earning: int,
) -> None:
    await partner_earnings._notify_partner_earning(
        service,
        partner=partner,
        payer_name=payer_name,
        level=level,
        earning=earning,
    )


async def process_partner_referral_earning(
    service: PartnerService,
    *,
    referral: Any,
    payer_user_id: int,
    payer_name: str,
    payment_amount_kopecks: int,
    partner_settings: PartnerSettingsDto,
    gateway_commission: Decimal,
    gateway_name: str,
    source_transaction_id: int | None = None,
) -> None:
    await partner_earnings._process_partner_referral_earning(
        service,
        referral=referral,
        payer_user_id=payer_user_id,
        payer_name=payer_name,
        payment_amount_kopecks=payment_amount_kopecks,
        partner_settings=partner_settings,
        gateway_commission=gateway_commission,
        gateway_name=gateway_name,
        source_transaction_id=source_transaction_id,
    )


async def calculate_partner_earning(
    service: PartnerService,
    partner: PartnerDto,
    partner_settings: PartnerSettingsDto,
    payment_amount: int,
    level: PartnerLevel,
    gateway_commission: Decimal,
) -> tuple[int, Decimal]:
    return await partner_earnings._calculate_partner_earning(
        service,
        partner=partner,
        partner_settings=partner_settings,
        payment_amount=payment_amount,
        level=level,
        gateway_commission=gateway_commission,
    )


async def process_partner_earning(
    service: PartnerService,
    payer_user_id: int,
    payment_amount: Decimal,
    gateway_type: PaymentGatewayType | None = None,
    source_transaction_id: int | None = None,
) -> None:
    await partner_earnings.process_partner_earning(
        service,
        payer_user_id=payer_user_id,
        payment_amount=payment_amount,
        gateway_type=gateway_type,
        source_transaction_id=source_transaction_id,
    )
