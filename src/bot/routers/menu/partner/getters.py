from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.enums import Currency
from src.infrastructure.database.models.dto import UserDto
from src.services.partner_portal import PartnerPortalService
from src.services.settings import SettingsService

PARTNER_BALANCE_CURRENCIES: tuple[Currency, ...] = (
    Currency.RUB,
    Currency.USD,
    Currency.USDT,
    Currency.TON,
    Currency.BTC,
    Currency.ETH,
    Currency.LTC,
    Currency.BNB,
    Currency.DASH,
    Currency.SOL,
    Currency.XMR,
    Currency.USDC,
    Currency.TRX,
)


def _normalize_status(status: str | None) -> str:
    if not status:
        return "PENDING"

    normalized = status.upper()
    if normalized == "CANCELLED":
        return "CANCELED"
    return normalized


def _currency_quantum(currency: Currency) -> Decimal:
    if currency == Currency.BTC:
        return Decimal("0.00000001")
    if currency in {
        Currency.TON,
        Currency.ETH,
        Currency.LTC,
        Currency.BNB,
        Currency.DASH,
        Currency.SOL,
        Currency.XMR,
        Currency.TRX,
    }:
        return Decimal("0.000001")
    return Decimal("0.01")


def _format_amount(value: Decimal | float | int, currency: Currency) -> str:
    amount = Decimal(str(value)).quantize(_currency_quantum(currency), rounding=ROUND_HALF_UP)
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text} {currency.value}"


async def _convert_kopecks_to_display(
    *,
    amount_kopecks: int,
    currency: Currency,
    partner_portal_service: PartnerPortalService,
) -> Decimal:
    amount_rub = (Decimal(amount_kopecks) / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    if currency == Currency.RUB:
        return amount_rub

    conversion = await partner_portal_service.market_quote_service.convert_from_rub(
        amount_rub=amount_rub,
        target_currency=currency,
    )
    return conversion.amount


def _format_with_rub_equivalent(
    *,
    display_amount: Decimal | float,
    display_currency: Currency,
    amount_kopecks: int,
) -> str:
    display_text = _format_amount(display_amount, display_currency)
    if display_currency == Currency.RUB:
        return display_text

    rub_amount = Decimal(amount_kopecks) / Decimal("100")
    rub_text = _format_amount(rub_amount, Currency.RUB)
    return f"{display_text} ({rub_text})"


@inject
async def partner_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_portal_service: FromDishka[PartnerPortalService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.get_info(user)
    settings = await settings_service.get()
    effective_currency = Currency(snapshot.effective_currency)
    level_settings = {item.level: item for item in snapshot.level_settings}

    async def format_level_earned(level: int) -> str:
        amount_kopecks = level_settings.get(level).earned_amount if level in level_settings else 0
        display_amount = await _convert_kopecks_to_display(
            amount_kopecks=amount_kopecks,
            currency=effective_currency,
            partner_portal_service=partner_portal_service,
        )
        return _format_with_rub_equivalent(
            display_amount=display_amount,
            display_currency=effective_currency,
            amount_kopecks=amount_kopecks,
        )

    referral_link = snapshot.telegram_referral_link or snapshot.referral_link or ""
    invite_text = i18n.get("referral-invite-message", url=referral_link) if referral_link else ""

    return {
        "is_partner": snapshot.is_partner,
        "partner_active": snapshot.is_active,
        "partner_enabled": settings.partner.enabled,
        "display_currency": effective_currency.value,
        "balance": _format_with_rub_equivalent(
            display_amount=Decimal(str(snapshot.balance_display)),
            display_currency=effective_currency,
            amount_kopecks=snapshot.balance,
        ),
        "total_earned": _format_with_rub_equivalent(
            display_amount=Decimal(str(snapshot.total_earned_display)),
            display_currency=effective_currency,
            amount_kopecks=snapshot.total_earned,
        ),
        "total_withdrawn": _format_with_rub_equivalent(
            display_amount=Decimal(str(snapshot.total_withdrawn_display)),
            display_currency=effective_currency,
            amount_kopecks=snapshot.total_withdrawn,
        ),
        "level1_count": snapshot.referrals_count,
        "level2_count": snapshot.level2_referrals_count,
        "level3_count": snapshot.level3_referrals_count,
        "level1_earned": await format_level_earned(1),
        "level2_earned": await format_level_earned(2),
        "level3_earned": await format_level_earned(3),
        "count": (
            snapshot.referrals_count
            + snapshot.level2_referrals_count
            + snapshot.level3_referrals_count
        ),
        "level1_percent": (
            level_settings.get(1).effective_percent
            if level_settings.get(1) and level_settings.get(1).effective_percent is not None
            else level_settings.get(1).global_percent
            if level_settings.get(1)
            else 0
        ),
        "level2_percent": (
            level_settings.get(2).effective_percent
            if level_settings.get(2) and level_settings.get(2).effective_percent is not None
            else level_settings.get(2).global_percent
            if level_settings.get(2)
            else 0
        ),
        "level3_percent": (
            level_settings.get(3).effective_percent
            if level_settings.get(3) and level_settings.get(3).effective_percent is not None
            else level_settings.get(3).global_percent
            if level_settings.get(3)
            else 0
        ),
        "referral_link": referral_link,
        "invite": invite_text,
    }


@inject
async def partner_balance_currency_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_portal_service: FromDishka[PartnerPortalService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.get_info(user)
    current_override = user.partner_balance_currency_override

    currency_list = [
        {
            "id": "AUTO",
            "label": i18n.get(
                "btn-partner-balance-currency-auto",
                currency=snapshot.effective_currency,
            ),
            "selected": current_override is None,
        }
    ]
    currency_list.extend(
        {
            "id": currency.value,
            "label": f"{currency.symbol} {currency.value}",
            "selected": current_override == currency,
        }
        for currency in PARTNER_BALANCE_CURRENCIES
    )

    return {
        "currency_list": currency_list,
        "current_currency": current_override.value if current_override else "AUTO",
        "effective_currency": snapshot.effective_currency,
    }


@inject
async def partner_referrals_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    partner_portal_service: FromDishka[PartnerPortalService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.list_referrals(
        current_user=user,
        page=1,
        limit=1000,
    )

    referrals = [
        {
            "id": f"{item.telegram_id}:{item.level}",
            "referral_user_id": item.telegram_id,
            "level": item.level,
            "total_earned": _format_amount(
                item.total_earned_display,
                Currency(item.display_currency),
            ),
        }
        for item in snapshot.referrals
    ]
    return {
        "referrals": referrals,
        "count": snapshot.total,
    }


@inject
async def partner_earnings_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    partner_portal_service: FromDishka[PartnerPortalService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.list_earnings(
        current_user=user,
        page=1,
        limit=20,
    )

    earnings = [
        {
            "id": item.id,
            "amount": _format_amount(
                item.earned_amount_display,
                Currency(item.display_currency),
            ),
            "level": item.level,
            "level_emoji": {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}.get(item.level, str(item.level)),
            "referral_id": item.referral_telegram_id,
            "payment_amount": _format_amount(
                item.payment_amount_display,
                Currency(item.display_currency),
            ),
            "created_at": item.created_at or "—",
        }
        for item in snapshot.earnings
    ]
    return {
        "earnings": earnings,
        "count": snapshot.total,
    }


@inject
async def partner_withdraw_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    partner_portal_service: FromDishka[PartnerPortalService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.get_info(user)
    effective_currency = Currency(snapshot.effective_currency)

    return {
        "balance": _format_with_rub_equivalent(
            display_amount=Decimal(str(snapshot.balance_display)),
            display_currency=effective_currency,
            amount_kopecks=snapshot.balance,
        ),
        "min_withdrawal": _format_with_rub_equivalent(
            display_amount=Decimal(str(snapshot.min_withdrawal_display)),
            display_currency=effective_currency,
            amount_kopecks=int(Decimal(str(snapshot.min_withdrawal_rub)) * Decimal("100")),
        ),
        "can_withdraw": snapshot.can_withdraw,
    }


@inject
async def partner_withdraw_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    partner_portal_service: FromDishka[PartnerPortalService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.get_info(user)
    effective_currency = Currency(snapshot.effective_currency)
    amount = Decimal(str(dialog_manager.dialog_data.get("withdraw_amount", 0))).quantize(
        _currency_quantum(effective_currency),
        rounding=ROUND_HALF_UP,
    )

    return {
        "amount": _format_amount(amount, effective_currency),
        "fee": _format_amount(Decimal("0"), effective_currency),
        "fee_percent": 0.0,
        "net_amount": _format_amount(amount, effective_currency),
        "can_withdraw": snapshot.is_active and Decimal(str(snapshot.balance_display)) >= amount,
    }


@inject
async def partner_history_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    partner_portal_service: FromDishka[PartnerPortalService],
    **kwargs: Any,
) -> dict[str, Any]:
    snapshot = await partner_portal_service.list_withdrawals(current_user=user)

    withdrawals = []
    for item in snapshot.withdrawals:
        normalized_status = _normalize_status(item.status)
        status_emoji = {
            "PENDING": "🕓",
            "APPROVED": "✅",
            "COMPLETED": "✅",
            "REJECTED": "❌",
            "CANCELED": "🚫",
        }.get(normalized_status, "❓")

        display_currency = Currency(item.display_currency)
        amount_text = _format_amount(item.display_amount, display_currency)
        if display_currency != Currency.RUB:
            rub_amount = _format_amount(
                Decimal(item.amount) / Decimal("100"),
                Currency.RUB,
            )
            amount_text = f"{amount_text} ({rub_amount})"

        withdrawals.append(
            {
                "id": item.id,
                "amount": amount_text,
                "status": normalized_status,
                "status_emoji": status_emoji,
                "created_at": item.created_at or "—",
            }
        )

    return {
        "withdrawals": withdrawals,
        "count": len(withdrawals),
    }
