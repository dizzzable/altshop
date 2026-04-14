from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.enums import Currency
from src.infrastructure.database.models.dto import (
    PartnerReferralDto,
    PartnerTransactionDto,
    PartnerWithdrawalDto,
    UserDto,
)
from src.services.partner_portal_models import (
    PartnerEarningItemSnapshot,
    PartnerEarningsPageSnapshot,
    PartnerPortalStateError,
    PartnerReferralItemSnapshot,
    PartnerReferralsPageSnapshot,
    PartnerWithdrawalSnapshot,
    PartnerWithdrawalsSnapshot,
)

if TYPE_CHECKING:
    from .partner_portal import PartnerPortalService


async def list_referrals(
    service: PartnerPortalService,
    *,
    current_user: UserDto,
    page: int,
    limit: int,
) -> PartnerReferralsPageSnapshot:
    effective_currency = (
        await service.partner_service.settings_service.resolve_partner_balance_currency(
            current_user
        )
    )
    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner or not partner.id:
        return PartnerReferralsPageSnapshot(referrals=[], total=0, page=page, limit=limit)

    referrals = await service.partner_service.get_partner_referrals(partner.id)
    total = len(referrals)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_referrals = referrals[start_idx:end_idx]

    referral_telegram_ids = [ref.referral_telegram_id for ref in paginated_referrals]
    transaction_stats_map = await service.partner_service.get_partner_referral_transaction_stats(
        partner_id=partner.id,
        referral_telegram_ids=referral_telegram_ids,
    )
    invite_source_map = await service.partner_service.get_referral_invite_sources(
        referral_telegram_ids=referral_telegram_ids,
    )

    referral_items = [
        await service._build_referral_item(
            referral=ref,
            transaction_stats_map=transaction_stats_map,
            invite_source_map=invite_source_map,
            effective_currency=effective_currency,
        )
        for ref in paginated_referrals
    ]
    return PartnerReferralsPageSnapshot(
        referrals=referral_items,
        total=total,
        page=page,
        limit=limit,
    )


async def list_earnings(
    service: PartnerPortalService,
    *,
    current_user: UserDto,
    page: int,
    limit: int,
) -> PartnerEarningsPageSnapshot:
    effective_currency = (
        await service.partner_service.settings_service.resolve_partner_balance_currency(
            current_user
        )
    )
    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner:
        return PartnerEarningsPageSnapshot(earnings=[], total=0, page=page, limit=limit)
    if partner.id is None:
        raise PartnerPortalStateError("Partner record is missing id")

    transactions = await service.partner_service.get_partner_transactions(partner.id)
    total = len(transactions)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_transactions = transactions[start_idx:end_idx]

    earnings = [
        await service._build_earning_item(
            txn,
            effective_currency=effective_currency,
        )
        for txn in paginated_transactions
    ]

    return PartnerEarningsPageSnapshot(
        earnings=earnings,
        total=total,
        page=page,
        limit=limit,
    )


async def list_withdrawals(
    service: PartnerPortalService,
    *,
    current_user: UserDto,
) -> PartnerWithdrawalsSnapshot:
    effective_currency = (
        await service.partner_service.settings_service.resolve_partner_balance_currency(
            current_user
        )
    )
    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner:
        return PartnerWithdrawalsSnapshot(withdrawals=[])
    if partner.id is None:
        raise PartnerPortalStateError("Partner record is missing id")

    withdrawals = await service.partner_service.get_partner_withdrawals(partner.id)
    return PartnerWithdrawalsSnapshot(
        withdrawals=[
            await service._serialize_withdrawal(
                withdrawal,
                effective_currency=effective_currency,
            )
            for withdrawal in withdrawals
        ]
    )


async def _build_earning_item(
    service: PartnerPortalService,
    txn: PartnerTransactionDto,
    *,
    effective_currency: Currency,
) -> PartnerEarningItemSnapshot:
    if txn.id is None:
        raise PartnerPortalStateError("Partner transaction is missing id")

    payment_amount_display, earned_amount_display = await service._convert_display_bundle(
        effective_currency=effective_currency,
        amounts_kopecks=(txn.payment_amount, txn.earned_amount),
    )
    return PartnerEarningItemSnapshot(
        id=txn.id,
        referral_telegram_id=txn.referral_telegram_id,
        referral_username=txn.referral.username if txn.referral else None,
        level=txn.level.value if hasattr(txn.level, "value") else int(txn.level),
        payment_amount=txn.payment_amount,
        payment_amount_display=float(payment_amount_display),
        percent=float(txn.percent),
        earned_amount=txn.earned_amount,
        earned_amount_display=float(earned_amount_display),
        display_currency=effective_currency.value,
        created_at=txn.created_at.isoformat() if txn.created_at else "",
    )


async def _build_referral_item(
    service: PartnerPortalService,
    *,
    referral: PartnerReferralDto,
    transaction_stats_map: dict[int, dict[str, Any]],
    invite_source_map: dict[int, str],
    effective_currency: Currency,
) -> PartnerReferralItemSnapshot:
    referred_user = referral.referral
    stats = transaction_stats_map.get(referral.referral_telegram_id, {})
    total_earned = int(stats.get("total_earned", 0) or 0)
    total_paid_amount = int(stats.get("total_paid_amount", 0) or 0)
    first_paid_at_obj = stats.get("first_paid_at")
    first_paid_at = first_paid_at_obj.isoformat() if first_paid_at_obj else None
    total_paid_display, total_earned_display = await service._convert_display_bundle(
        effective_currency=effective_currency,
        amounts_kopecks=(total_paid_amount, total_earned),
    )

    return PartnerReferralItemSnapshot(
        telegram_id=referral.referral_telegram_id,
        username=referred_user.username if referred_user else None,
        name=referred_user.name if referred_user else None,
        level=referral.level.value if hasattr(referral.level, "value") else int(referral.level),
        joined_at=referral.created_at.isoformat() if referral.created_at else "",
        invite_source=invite_source_map.get(referral.referral_telegram_id, "UNKNOWN"),
        is_active=(not referred_user.is_blocked) if referred_user else True,
        is_paid=total_paid_amount > 0,
        first_paid_at=first_paid_at,
        total_paid_amount=total_paid_amount,
        total_paid_amount_display=float(total_paid_display),
        total_earned=total_earned,
        total_earned_display=float(total_earned_display),
        display_currency=effective_currency.value,
    )


async def _serialize_withdrawal(
    service: PartnerPortalService,
    withdrawal: PartnerWithdrawalDto,
    *,
    effective_currency: Currency,
) -> PartnerWithdrawalSnapshot:
    if withdrawal.id is None:
        raise PartnerPortalStateError("Partner withdrawal is missing id")

    requested_amount = (
        float(withdrawal.requested_amount) if withdrawal.requested_amount is not None else None
    )
    requested_currency = (
        withdrawal.requested_currency.value if withdrawal.requested_currency is not None else None
    )
    display_amount_decimal = await service._convert_kopecks_to_display(
        withdrawal.amount,
        effective_currency,
    )
    status = (
        withdrawal.status.value if hasattr(withdrawal.status, "value") else str(withdrawal.status)
    )
    return PartnerWithdrawalSnapshot(
        id=withdrawal.id,
        amount=withdrawal.amount,
        display_amount=float(display_amount_decimal),
        display_currency=effective_currency.value,
        requested_amount=requested_amount,
        requested_currency=requested_currency,
        quote_rate=float(withdrawal.quote_rate) if withdrawal.quote_rate is not None else None,
        quote_source=withdrawal.quote_source,
        status=service._normalize_withdrawal_status(status),
        method=withdrawal.method or "",
        requisites=withdrawal.requisites or "",
        admin_comment=withdrawal.admin_comment,
        created_at=withdrawal.created_at.isoformat() if withdrawal.created_at else "",
        updated_at=withdrawal.updated_at.isoformat() if withdrawal.updated_at else "",
    )
