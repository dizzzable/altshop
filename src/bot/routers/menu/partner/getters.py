from typing import Any
from decimal import Decimal

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.config import AppConfig
from src.core.enums import PartnerLevel
from src.infrastructure.database.models.dto import UserDto
from src.services.partner import PartnerService
from src.services.settings import SettingsService
from src.services.referral import ReferralService


@inject
async def partner_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для главного окна партнерской программы клиента."""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    settings = await settings_service.get()
    partner_settings = settings.partner
    
    if not partner:
        # min_withdrawal_amount в копейках, конвертируем в рубли
        min_withdrawal_rubles = partner_settings.min_withdrawal_amount / 100
        return {
            "is_partner": False,
            "partner_enabled": partner_settings.enabled,
            "min_withdrawal": min_withdrawal_rubles,
        }
    
    # Получаем статистику по уровням
    stats = await partner_service.get_partner_statistics(partner=partner)
    
    # Получаем реферальную ссылку (используем партнерский код)
    ref_link = await referral_service.get_ref_link(user.referral_code)
    
    # Рассчитываем общую сумму выведенных средств
    total_withdrawn = partner.total_earned - partner.balance
    
    # Подсчёт общего количества рефералов всех уровней
    total_referrals_count = (
        stats.get("referrals_count", 0) +
        stats.get("level2_referrals_count", 0) +
        stats.get("level3_referrals_count", 0)
    )
    
    return {
        "is_partner": True,
        "partner_active": partner.is_active,
        "partner_enabled": partner_settings.enabled,
        "balance": float(partner.balance),
        "total_earned": float(partner.total_earned),
        "total_withdrawn": float(total_withdrawn),
        # Статистика по уровням
        "level1_count": stats.get("referrals_count", 0),
        "level2_count": stats.get("level2_referrals_count", 0),
        "level3_count": stats.get("level3_referrals_count", 0),
        "level1_earned": float(stats.get("level1_earnings", 0)),
        "level2_earned": float(stats.get("level2_earnings", 0)),
        "level3_earned": float(stats.get("level3_earnings", 0)),
        # Общее количество рефералов для кнопки
        "count": total_referrals_count,
        # Проценты
        "level1_percent": float(partner_settings.level1_percent),
        "level2_percent": float(partner_settings.level2_percent),
        "level3_percent": float(partner_settings.level3_percent),
        # Минимальный вывод (из копеек в рубли)
        "min_withdrawal": partner_settings.min_withdrawal_amount / 100,
        "can_withdraw": partner.balance >= Decimal(partner_settings.min_withdrawal_amount) / 100,
        # Ссылка
        "referral_link": ref_link,
        "invite": i18n.get("referral-invite-message", url=ref_link),
    }


@inject
async def partner_referrals_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для списка рефералов партнера."""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    
    if not partner:
        return {"referrals": [], "count": 0}
    
    referrals = await partner_service.get_partner_referrals(partner.id)
    
    formatted_referrals = []
    for ref in referrals:
        level_emoji = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}.get(ref.level, str(ref.level))
        formatted_referrals.append({
            "id": ref.id,
            "referral_user_id": ref.referral_user_id,
            "level": ref.level,
            "level_emoji": level_emoji,
            "total_earned": float(ref.total_earned),
            "created_at": ref.created_at.strftime("%d.%m.%Y %H:%M") if ref.created_at else "—",
        })
    
    return {
        "referrals": formatted_referrals,
        "count": len(formatted_referrals),
    }


@inject
async def partner_earnings_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для истории начислений партнера."""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    
    if not partner:
        return {"earnings": [], "count": 0}
    
    transactions = await partner_service.get_partner_transactions(partner.id, limit=20)
    
    formatted_earnings = []
    for tx in transactions:
        level_emoji = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}.get(tx.level, str(tx.level))
        formatted_earnings.append({
            "id": tx.id,
            "amount": float(tx.amount),
            "level": tx.level,
            "level_emoji": level_emoji,
            "referral_id": tx.referral_user_id,
            "payment_amount": float(tx.payment_amount) if tx.payment_amount else 0,
            "created_at": tx.created_at.strftime("%d.%m.%Y %H:%M") if tx.created_at else "—",
        })
    
    return {
        "earnings": formatted_earnings,
        "count": len(formatted_earnings),
    }


@inject
async def partner_withdraw_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для запроса на вывод средств."""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    settings = await settings_service.get()
    partner_settings = settings.partner
    
    # min_withdrawal_amount в копейках, конвертируем в рубли
    min_withdrawal_rubles = partner_settings.min_withdrawal_amount / 100
    
    if not partner:
        return {
            "balance": 0,
            "min_withdrawal": min_withdrawal_rubles,
            "can_withdraw": False,
        }
    
    return {
        "balance": float(partner.balance),
        "min_withdrawal": min_withdrawal_rubles,
        "can_withdraw": partner.balance >= Decimal(min_withdrawal_rubles),
    }


@inject
async def partner_withdraw_confirm_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для подтверждения вывода средств."""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    settings = await settings_service.get()
    partner_settings = settings.partner
    
    if not partner:
        return {"error": True}
    
    amount = dialog_manager.dialog_data.get("withdraw_amount", partner.balance)
    
    # Рассчитываем комиссии и чистую сумму
    # Налог уже учтен при начислении, поэтому комиссия минимальная или отсутствует
    fee_percent = partner_settings.tax_percent
    fee = Decimal(str(amount)) * (fee_percent / 100)
    net_amount = Decimal(str(amount)) - fee
    
    return {
        "amount": float(amount),
        "fee": float(fee),
        "fee_percent": float(fee_percent),
        "net_amount": float(net_amount),
        "can_withdraw": partner.balance >= Decimal(str(amount)),
    }


@inject
async def partner_history_getter(
    dialog_manager: DialogManager,
    user: UserDto,
    i18n: FromDishka[TranslatorRunner],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для истории выводов."""
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    
    if not partner:
        return {"withdrawals": [], "count": 0}
    
    withdrawals = await partner_service.get_partner_withdrawals(partner.id)
    
    formatted_withdrawals = []
    for w in withdrawals:
        status_emoji = {"PENDING": "🕓", "APPROVED": "✅", "REJECTED": "❌"}.get(w.status.name, "❓")
        formatted_withdrawals.append({
            "id": w.id,
            "amount": float(w.amount),
            "status": w.status.name,
            "status_emoji": status_emoji,
            "created_at": w.created_at.strftime("%d.%m.%Y %H:%M") if w.created_at else "—",
        })
    
    return {
        "withdrawals": formatted_withdrawals,
        "count": len(formatted_withdrawals),
    }