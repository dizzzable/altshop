from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, List, Optional

from loguru import logger

from src.core.enums import Currency, WithdrawalStatus
from src.infrastructure.database.models.dto import (
    PartnerDto,
    PartnerSettingsDto,
    PartnerWithdrawalDto,
)
from src.infrastructure.database.models.sql import PartnerWithdrawal

if TYPE_CHECKING:
    from .partner import PartnerService


async def request_withdrawal(
    service: PartnerService,
    partner: PartnerDto,
    amount: int,
    method: str,
    requisites: str,
    settings: PartnerSettingsDto,
) -> Optional[PartnerWithdrawalDto]:
    if amount < settings.min_withdrawal_amount:
        logger.warning(
            f"Withdrawal amount {amount} is less than minimum {settings.min_withdrawal_amount}"
        )
        return None

    if amount > partner.balance:
        logger.warning(f"Withdrawal amount {amount} exceeds partner balance {partner.balance}")
        return None

    withdrawal = await service.uow.repository.partners.create_withdrawal(
        PartnerWithdrawal(
            partner_id=partner.id,
            amount=amount,
            status=WithdrawalStatus.PENDING.value,
            method=method,
            requisites=requisites,
        )
    )

    assert partner.id is not None, "Partner ID is required for withdrawal"
    await service.uow.repository.partners.update_partner(
        partner.id,
        balance=partner.balance - amount,
    )

    logger.info(f"Partner '{partner.id}' requested withdrawal of {amount} kopecks via {method}")
    return PartnerWithdrawalDto.from_model(withdrawal)


async def get_withdrawal(
    service: PartnerService,
    withdrawal_id: int,
) -> Optional[PartnerWithdrawalDto]:
    withdrawal = await service.uow.repository.partners.get_withdrawal_by_id(withdrawal_id)
    return PartnerWithdrawalDto.from_model(withdrawal) if withdrawal else None


async def get_all_withdrawals(
    service: PartnerService,
    status: Optional[WithdrawalStatus] = None,
) -> List[PartnerWithdrawalDto]:
    withdrawals = await service.uow.repository.partners.get_all_withdrawals(status)
    return PartnerWithdrawalDto.from_model_list(withdrawals)


async def approve_withdrawal(
    service: PartnerService,
    withdrawal_id: int,
    admin_telegram_id: int,
    comment: Optional[str] = None,
) -> bool:
    withdrawal = await service.uow.repository.partners.get_withdrawal_by_id(withdrawal_id)
    if not withdrawal:
        return False

    await service.uow.repository.partners.update_withdrawal(
        withdrawal_id,
        status=WithdrawalStatus.COMPLETED,
        processed_by=admin_telegram_id,
        admin_comment=comment,
    )

    partner = await service.uow.repository.partners.get_partner_by_id(withdrawal.partner_id)
    if partner and partner.id:
        await service.uow.repository.partners.update_partner(
            partner.id,
            total_withdrawn=partner.total_withdrawn + withdrawal.amount,
        )

    logger.info(f"Withdrawal '{withdrawal_id}' approved by admin '{admin_telegram_id}'")
    return True


async def reject_withdrawal(
    service: PartnerService,
    withdrawal_id: int,
    admin_telegram_id: int,
    reason: Optional[str] = None,
) -> bool:
    withdrawal = await service.uow.repository.partners.get_withdrawal_by_id(withdrawal_id)
    if not withdrawal:
        return False

    await service.uow.repository.partners.update_withdrawal(
        withdrawal_id,
        status=WithdrawalStatus.REJECTED,
        processed_by=admin_telegram_id,
        admin_comment=reason,
    )

    partner = await service.uow.repository.partners.get_partner_by_id(withdrawal.partner_id)
    if partner:
        await service.uow.repository.partners.update_partner(
            partner.id,
            balance=partner.balance + withdrawal.amount,
        )

    logger.info(f"Withdrawal '{withdrawal_id}' rejected by admin '{admin_telegram_id}'")
    return True


async def get_pending_withdrawals(service: PartnerService) -> List[PartnerWithdrawalDto]:
    withdrawals = await service.uow.repository.partners.get_pending_withdrawals()
    return PartnerWithdrawalDto.from_model_list(withdrawals)


async def get_partner_withdrawals(
    service: PartnerService,
    partner_id: int,
) -> List[PartnerWithdrawalDto]:
    withdrawals = await service.uow.repository.partners.get_withdrawals_by_partner(partner_id)
    return PartnerWithdrawalDto.from_model_list(withdrawals)


async def create_withdrawal_request(
    service: PartnerService,
    partner_id: int,
    amount: Decimal,
    method: str = "",
    requisites: str = "",
    requested_amount: Decimal | None = None,
    requested_currency: Currency | None = None,
    quote_rate: Decimal | None = None,
    quote_source: str | None = None,
) -> Optional[PartnerWithdrawalDto]:
    partner = await service.get_partner(partner_id)
    if not partner:
        logger.warning(f"Partner '{partner_id}' not found for withdrawal request")
        return None

    if amount <= 0:
        logger.warning(f"Withdrawal amount must be positive: {amount}")
        return None

    amount_kopecks = int(
        (amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    if amount_kopecks <= 0:
        logger.warning(f"Withdrawal amount is too small after conversion: {amount}")
        return None

    settings = await service.settings_service.get()
    partner_settings = settings.partner
    if amount_kopecks < partner_settings.min_withdrawal_amount:
        logger.warning(
            f"Withdrawal amount {amount_kopecks} is less than minimum "
            f"{partner_settings.min_withdrawal_amount}"
        )
        return None

    if amount_kopecks > partner.balance:
        logger.warning(
            f"Withdrawal amount {amount_kopecks} exceeds partner balance {partner.balance}"
        )
        return None

    withdrawal = await service.uow.repository.partners.create_withdrawal(
        PartnerWithdrawal(
            partner_id=partner.id,
            amount=amount_kopecks,
            status=WithdrawalStatus.PENDING.value,
            method=method,
            requisites=requisites,
            requested_amount=requested_amount or amount,
            requested_currency=requested_currency or Currency.RUB,
            quote_rate=quote_rate,
            quote_source=quote_source,
        )
    )

    assert partner.id is not None, "Partner ID is required for withdrawal request"
    await service.uow.repository.partners.update_partner(
        partner.id,
        balance=partner.balance - amount_kopecks,
    )

    logger.info(
        f"Partner '{partner.id}' created withdrawal request for {amount_kopecks} kopecks"
    )
    return PartnerWithdrawalDto.from_model(withdrawal)
