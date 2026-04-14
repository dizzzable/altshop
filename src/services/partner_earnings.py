from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

from src.core.enums import (
    PartnerAccrualStrategy,
    PartnerLevel,
    PartnerRewardType,
    PaymentGatewayType,
    UserNotificationType,
)
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import (
    PartnerDto,
    PartnerSettingsDto,
    PartnerTransactionDto,
)
from src.infrastructure.database.models.sql import PartnerTransaction

if TYPE_CHECKING:
    from .partner import PartnerService


async def debit_balance_for_subscription_purchase(
    service: PartnerService,
    *,
    user_telegram_id: int,
    amount_kopecks: int,
) -> bool:
    if amount_kopecks <= 0:
        logger.warning(
            f"Invalid partner balance debit amount '{amount_kopecks}' "
            f"for user '{user_telegram_id}'"
        )
        return False

    partner = await service.get_partner_by_user(user_telegram_id)
    if not partner or not partner.id:
        logger.warning(f"Partner for user '{user_telegram_id}' not found for balance debit")
        return False
    if not partner.is_active:
        logger.warning(
            f"Partner '{partner.id}' for user '{user_telegram_id}' is inactive, "
            "partner balance debit is not allowed"
        )
        return False

    success = await service.uow.repository.partners.deduct_partner_balance_if_possible(
        partner_id=partner.id,
        amount=amount_kopecks,
    )
    if success:
        logger.info(
            f"Debited '{amount_kopecks}' kopecks from partner '{partner.id}' "
            f"for user '{user_telegram_id}' subscription purchase"
        )
    else:
        logger.warning(
            f"Failed to debit '{amount_kopecks}' kopecks from partner '{partner.id}' "
            f"(insufficient balance or race condition)"
        )

    return success


async def credit_balance_for_failed_subscription_purchase(
    service: PartnerService,
    *,
    user_telegram_id: int,
    amount_kopecks: int,
) -> bool:
    if amount_kopecks <= 0:
        return False

    partner = await service.get_partner_by_user(user_telegram_id)
    if not partner or not partner.id:
        logger.warning(f"Partner for user '{user_telegram_id}' not found for balance restore")
        return False

    success = await service.uow.repository.partners.add_partner_balance(
        partner_id=partner.id,
        amount=amount_kopecks,
    )
    if success:
        logger.info(
            f"Restored '{amount_kopecks}' kopecks to partner '{partner.id}' "
            f"for user '{user_telegram_id}' after failed subscription purchase"
        )
    else:
        logger.warning(
            f"Failed to restore '{amount_kopecks}' kopecks to partner '{partner.id}' "
            f"for user '{user_telegram_id}'"
        )

    return success


def _format_rub(_service: PartnerService, value_kopecks: int) -> str:
    amount_rub = (Decimal(value_kopecks) / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return f"{amount_rub} RUB"


async def _resolve_payer_name(service: PartnerService, payer_user_id: int) -> str:
    payer_user = await service.user_service.get(payer_user_id)
    payer_name = (payer_user.name or payer_user.username) if payer_user else None
    return payer_name or str(payer_user_id)


def _resolve_accrual_strategy(
    _service: PartnerService,
    partner: PartnerDto,
) -> PartnerAccrualStrategy:
    individual_settings = partner.individual_settings
    if individual_settings.use_global_settings:
        return PartnerAccrualStrategy.ON_EACH_PAYMENT
    return individual_settings.accrual_strategy


async def _should_skip_partner_earning(
    service: PartnerService,
    *,
    partner: PartnerDto,
    payer_user_id: int,
) -> bool:
    if service._resolve_accrual_strategy(partner) != PartnerAccrualStrategy.ON_FIRST_PAYMENT:
        return False

    assert partner.id is not None, "Partner ID is required"
    already_received = (
        await service.uow.repository.partners.has_partner_received_payment_from_referral(
            partner_id=partner.id,
            referral_telegram_id=payer_user_id,
        )
    )
    if not already_received:
        return False

    logger.debug(
        f"Partner '{partner.id}' already received payment from referral "
        f"'{payer_user_id}', skipping (ON_FIRST_PAYMENT strategy)"
    )
    return True


async def _notify_partner_earning(
    service: PartnerService,
    *,
    partner: PartnerDto,
    payer_name: str,
    level: PartnerLevel,
    earning: int,
) -> None:
    try:
        partner_user = await service.user_service.get(telegram_id=partner.user_telegram_id)
        if not partner_user:
            return

        await service.notification_service.notify_user(
            user=partner_user,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-partner-earning",
                i18n_kwargs={
                    "referral_name": payer_name,
                    "level": level.value,
                    "amount": service._format_rub(earning),
                    "new_balance": service._format_rub(partner.balance),
                },
            ),
            ntf_type=UserNotificationType.PARTNER_EARNING,
        )
    except Exception as exception:
        logger.warning(
            f"Failed to send partner earning notification to '{partner.user_telegram_id}': "
            f"{exception}"
        )


async def _process_partner_referral_earning(
    service: PartnerService,
    *,
    referral: Any,
    payer_user_id: int,
    payer_name: str,
    payment_amount_kopecks: int,
    partner_settings: PartnerSettingsDto,
    gateway_commission: Decimal,
    gateway_name: str,
    source_transaction_id: Optional[int] = None,
) -> None:
    partner = await service.get_partner(referral.partner_id)
    if not partner or not partner.is_active:
        return
    assert partner.id is not None, "Partner ID is required"

    level = PartnerLevel(referral.level)
    if await service._should_skip_partner_earning(partner=partner, payer_user_id=payer_user_id):
        return

    earning, percent_used = await service._calculate_partner_earning(
        partner=partner,
        partner_settings=partner_settings,
        payment_amount=payment_amount_kopecks,
        level=level,
        gateway_commission=gateway_commission,
    )
    if earning <= 0:
        logger.debug(f"Zero earning for partner '{partner.id}' at level {level}")
        return

    if source_transaction_id is not None:
        existing_transaction = (
            await service.uow.repository.partners.get_transaction_by_partner_and_source(
                partner_id=partner.id,
                source_transaction_id=source_transaction_id,
            )
        )
        if existing_transaction:
            logger.info(
                "Partner earning already exists for partner '{}' and source transaction '{}'",
                partner.id,
                source_transaction_id,
            )
            return

    await service.create_partner_transaction(
        partner=partner,
        referral_telegram_id=payer_user_id,
        level=level,
        payment_amount=payment_amount_kopecks,
        percent=percent_used,
        earned_amount=earning,
        source_transaction_id=source_transaction_id,
        description=(
            "Earnings from referral payment via "
            f"{gateway_name} "
            f"(level {level.value})"
        ),
    )
    logger.info(
        f"Partner '{partner.id}' earned {earning} kopecks from "
        f"user '{payer_user_id}' payment via {gateway_name} "
        f"(level {level}, gateway_commission={gateway_commission}%)"
    )

    partner.balance += earning
    partner.total_earned += earning
    await service._notify_partner_earning(
        partner=partner,
        payer_name=payer_name,
        level=level,
        earning=earning,
    )


async def process_partner_earning(
    service: PartnerService,
    payer_user_id: int,
    payment_amount: Decimal,
    gateway_type: Optional[PaymentGatewayType] = None,
    source_transaction_id: Optional[int] = None,
) -> None:
    settings = await service.settings_service.get()
    partner_settings = settings.partner

    if not partner_settings.enabled:
        logger.debug("Partner program is disabled, skipping earning")
        return

    partner_chain = await service.uow.repository.partners.get_partner_chain_for_user(
        payer_user_id
    )
    if not partner_chain:
        logger.debug(f"No partner chain for user '{payer_user_id}'")
        return

    payer_name = await service._resolve_payer_name(payer_user_id)
    payment_amount_kopecks = int(payment_amount * 100)

    gateway_commission = Decimal("0")
    if gateway_type:
        gateway_commission = partner_settings.get_gateway_commission(gateway_type.value)
        logger.debug(f"Gateway '{gateway_type.value}' commission: {gateway_commission}%")
    gateway_name = gateway_type.value if gateway_type else "unknown"

    for referral in partner_chain:
        await service._process_partner_referral_earning(
            referral=referral,
            payer_user_id=payer_user_id,
            payer_name=payer_name,
            payment_amount_kopecks=payment_amount_kopecks,
            partner_settings=partner_settings,
            gateway_commission=gateway_commission,
            gateway_name=gateway_name,
            source_transaction_id=source_transaction_id,
        )


async def _calculate_partner_earning(
    _service: PartnerService,
    partner: PartnerDto,
    partner_settings: PartnerSettingsDto,
    payment_amount: int,
    level: PartnerLevel,
    gateway_commission: Decimal,
) -> tuple[int, Decimal]:
    individual_settings = partner.individual_settings

    if individual_settings.use_global_settings:
        earning = partner_settings.calculate_partner_earning(
            payment_amount=payment_amount,
            level=level,
            gateway_commission=gateway_commission,
        )
        return earning, partner_settings.get_level_percent(level)

    reward_type = individual_settings.reward_type
    if reward_type == PartnerRewardType.FIXED_AMOUNT:
        fixed_amount = individual_settings.get_level_fixed_amount(level)
        if fixed_amount is not None and fixed_amount > 0:
            return fixed_amount, Decimal("0")

        earning = partner_settings.calculate_partner_earning(
            payment_amount=payment_amount,
            level=level,
            gateway_commission=gateway_commission,
        )
        return earning, partner_settings.get_level_percent(level)

    individual_percent = individual_settings.get_level_percent(level)
    percent = individual_percent or partner_settings.get_level_percent(level)

    if partner_settings.auto_calculate_commission:
        net_amount = Decimal(payment_amount) * (100 - gateway_commission) / 100
        net_amount = net_amount * (100 - partner_settings.tax_percent) / 100
    else:
        net_amount = Decimal(payment_amount)

    earning = int(net_amount * percent / 100)
    return max(0, earning), percent


async def create_partner_transaction(
    service: PartnerService,
    partner: PartnerDto,
    referral_telegram_id: int,
    level: PartnerLevel,
    payment_amount: int,
    percent: Decimal,
    earned_amount: int,
    source_transaction_id: Optional[int] = None,
    description: Optional[str] = None,
) -> PartnerTransactionDto:
    transaction = await service.uow.repository.partners.create_transaction(
        PartnerTransaction(
            partner_id=partner.id,
            referral_telegram_id=referral_telegram_id,
            level=level,
            payment_amount=payment_amount,
            percent=percent,
            earned_amount=earned_amount,
            source_transaction_id=source_transaction_id,
            description=description,
        )
    )

    assert partner.id is not None, "Partner ID is required for balance update"
    await service.uow.repository.partners.update_partner(
        partner.id,
        balance=partner.balance + earned_amount,
        total_earned=partner.total_earned + earned_amount,
    )

    return PartnerTransactionDto.from_model(transaction)  # type: ignore[return-value]


async def get_partner_transactions(
    service: PartnerService,
    partner_id: int,
    limit: Optional[int] = None,
) -> list[PartnerTransactionDto]:
    transactions = await service.uow.repository.partners.get_transactions_by_partner(
        partner_id,
        limit=limit,
    )
    return PartnerTransactionDto.from_model_list(transactions)


async def get_partner_statistics(
    service: PartnerService,
    partner: Optional[PartnerDto] = None,
) -> Dict[str, Any]:
    if partner:
        assert partner.id is not None, "Partner ID is required for statistics"
        await service.uow.repository.partners.sum_earnings_by_partner(partner.id)
        level1_earnings = await service.uow.repository.partners.sum_earnings_by_level(
            partner.id,
            PartnerLevel.LEVEL_1,
        )
        level2_earnings = await service.uow.repository.partners.sum_earnings_by_level(
            partner.id,
            PartnerLevel.LEVEL_2,
        )
        level3_earnings = await service.uow.repository.partners.sum_earnings_by_level(
            partner.id,
            PartnerLevel.LEVEL_3,
        )

        return {
            "balance": partner.balance,
            "total_earned": partner.total_earned,
            "total_withdrawn": partner.total_withdrawn,
            "referrals_count": partner.referrals_count,
            "level2_referrals_count": partner.level2_referrals_count,
            "level3_referrals_count": partner.level3_referrals_count,
            "total_referrals": partner.total_referrals,
            "level1_earnings": level1_earnings,
            "level2_earnings": level2_earnings,
            "level3_earnings": level3_earnings,
        }

    all_partners = await service.get_all_partners()
    pending_withdrawals = await service.get_pending_withdrawals()

    total_referrals = sum(item.total_referrals for item in all_partners)
    total_earned = sum(item.total_earned for item in all_partners)
    total_withdrawn = sum(item.total_withdrawn for item in all_partners)

    return {
        "total_partners": len(all_partners),
        "total_referrals": total_referrals,
        "pending_withdrawals": len(pending_withdrawals),
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,
    }
