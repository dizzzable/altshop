from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.api.utils.user_identity import resolve_public_username
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PartnerWithdrawalDto, UserDto
from src.services.partner_portal_models import (
    PartnerPortalBadRequestError,
    PartnerPortalNotPartnerError,
    PartnerPortalStateError,
    PartnerPortalWithdrawalDisabledError,
    PartnerWithdrawalSnapshot,
)

if TYPE_CHECKING:
    from .partner_portal import PartnerPortalService


async def request_withdrawal(
    service: PartnerPortalService,
    *,
    current_user: UserDto,
    amount: Decimal,
    method: str,
    requisites: str,
) -> PartnerWithdrawalSnapshot:
    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner:
        raise PartnerPortalNotPartnerError("Not a partner")
    if partner.id is None:
        raise PartnerPortalStateError("Partner record is missing id")
    if not partner.is_active:
        raise PartnerPortalWithdrawalDisabledError()

    effective_currency = (
        await service.partner_service.settings_service.resolve_partner_balance_currency(
            current_user
        )
    )
    amount_input = service._normalize_display_amount(amount, effective_currency)
    if amount_input <= 0:
        raise PartnerPortalBadRequestError("Withdrawal amount must be positive")

    amount_rub, quote_rate, quote_source = await service._convert_display_amount_to_rub(
        amount=amount_input,
        source_currency=effective_currency,
    )
    amount_kopecks = service._rub_to_kopecks(amount_rub)
    withdrawal = await service.partner_service.create_withdrawal_request(
        partner_id=partner.id,
        amount=amount_rub,
        method=method.strip(),
        requisites=requisites.strip(),
        requested_amount=amount_input,
        requested_currency=effective_currency,
        quote_rate=quote_rate,
        quote_source=quote_source,
    )

    if not withdrawal:
        settings = await service.partner_service.settings_service.get()
        min_withdrawal_rub = Decimal(settings.partner.min_withdrawal_amount) / Decimal("100")

        if amount_kopecks < settings.partner.min_withdrawal_amount:
            raise PartnerPortalBadRequestError(
                f"Minimum withdrawal amount is {min_withdrawal_rub}"
            )

        if amount_kopecks > partner.balance:
            available_rub = Decimal(partner.balance) / Decimal("100")
            raise PartnerPortalBadRequestError(
                f"Insufficient balance. Available: {available_rub}"
            )

        raise PartnerPortalBadRequestError("Failed to create withdrawal request")

    await service._notify_withdrawal_requested(
        current_user=current_user,
        partner_balance_before=partner.balance,
        withdrawal=withdrawal,
    )

    return await service._serialize_withdrawal(
        withdrawal,
        effective_currency=effective_currency,
    )


async def _notify_withdrawal_requested(
    service: PartnerPortalService,
    *,
    current_user: UserDto,
    partner_balance_before: int,
    withdrawal: PartnerWithdrawalDto,
) -> None:
    remaining_balance_kopecks = max(0, partner_balance_before - withdrawal.amount)
    amount_str = (
        f"{(Decimal(withdrawal.amount) / Decimal('100')).quantize(Decimal('0.01'))} RUB"
    )
    balance_str = (
        f"{(Decimal(remaining_balance_kopecks) / Decimal('100')).quantize(Decimal('0.01'))} RUB"
    )
    web_account = None
    if not current_user.username:
        web_account = await service.web_account_service.get_by_user_telegram_id(
            current_user.telegram_id
        )
    notification_username = resolve_public_username(current_user, web_account=web_account)

    await service.notification_service.notify_super_dev(
        MessagePayload(
            i18n_key="ntf-event-partner-withdrawal-request",
            i18n_kwargs={
                "user_id": current_user.telegram_id,
                "user_name": current_user.name or str(current_user.telegram_id),
                "username": notification_username,
                "amount": amount_str,
                "partner_balance": balance_str,
            },
        )
    )
