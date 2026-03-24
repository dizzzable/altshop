from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.enums import PartnerLevel, WithdrawalStatus
from src.services.partner import PartnerService
from src.services.settings import SettingsService


@inject
async def partner_main_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для главного окна настроек партнерской программы."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    # Получаем статистику партнерской программы
    stats = await partner_service.get_partner_statistics()

    # Получаем количество активных партнеров
    total_partners = stats.get("total_partners", 0)
    total_referrals = stats.get("total_referrals", 0)
    pending_withdrawals = stats.get("pending_withdrawals", 0)
    total_earned = stats.get("total_earned", 0) / 100  # копейки в рубли
    total_withdrawn = stats.get("total_withdrawn", 0) / 100

    # Форматируем строку с комиссиями платежных систем
    gateway_fees_list = [
        f"• YooKassa: {partner_settings.yookassa_commission}%",
        f"• Telegram Stars: {partner_settings.telegram_stars_commission}%",
        f"• CryptoPay: {partner_settings.cryptopay_commission}%",
        f"• Heleket: {partner_settings.heleket_commission}%",
        f"• Pal24: {partner_settings.pal24_commission}%",
        f"• WATA: {partner_settings.wata_commission}%",
        f"• Platega: {partner_settings.platega_commission}%",
    ]
    gateway_fees_list.extend(
        [
            f"YooMoney: {partner_settings.yoomoney_commission}%",
            f"Cryptomus: {partner_settings.cryptomus_commission}%",
            f"Robokassa: {partner_settings.robokassa_commission}%",
            f"Stripe: {partner_settings.stripe_commission}%",
            f"MulenPay: {partner_settings.mulenpay_commission}%",
            f"CloudPayments: {partner_settings.cloudpayments_commission}%",
        ]
    )
    gateway_fees = "\n".join(gateway_fees_list)

    return {
        "is_enabled": partner_settings.enabled,
        "level1_percent": partner_settings.level1_percent,
        "level2_percent": partner_settings.level2_percent,
        "level3_percent": partner_settings.level3_percent,
        "tax_percent": partner_settings.tax_percent,
        "min_withdrawal": partner_settings.min_withdrawal_amount,
        "gateway_fees": gateway_fees,
        "total_partners": total_partners,
        "total_referrals": total_referrals,
        "pending_withdrawals": pending_withdrawals,
        "total_earned": total_earned,
        "total_withdrawn": total_withdrawn,
    }


@inject
async def level_percents_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настройки процентов по уровням."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    return {
        "level1_percent": partner_settings.level1_percent,
        "level2_percent": partner_settings.level2_percent,
        "level3_percent": partner_settings.level3_percent,
        "levels": list(PartnerLevel),
    }


@inject
async def level_percent_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для редактирования процента конкретного уровня."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    level = dialog_manager.dialog_data.get("selected_level", 1)

    current_percent = {
        1: partner_settings.level1_percent,
        2: partner_settings.level2_percent,
        3: partner_settings.level3_percent,
    }.get(level, 0)

    return {
        "level": level,
        "current_percent": current_percent,
    }


@inject
async def tax_settings_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для настроек налогов."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    return {
        "tax_percent": partner_settings.tax_percent,
    }


@inject
async def gateway_fees_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для списка комиссий платежных систем."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    # Use "gateway_id" instead of "key" to avoid i18n key translation semantics.
    gateway_fees = [
        {
            "name": "YooKassa",
            "gateway_id": "yookassa",
            "percent": partner_settings.yookassa_commission,
        },
        {
            "name": "YooMoney",
            "gateway_id": "yoomoney",
            "percent": partner_settings.yoomoney_commission,
        },
        {
            "name": "Telegram Stars",
            "gateway_id": "telegram_stars",
            "percent": partner_settings.telegram_stars_commission,
        },
        {
            "name": "CryptoPay",
            "gateway_id": "cryptopay",
            "percent": partner_settings.cryptopay_commission,
        },
        {
            "name": "Heleket",
            "gateway_id": "heleket",
            "percent": partner_settings.heleket_commission,
        },
        {"name": "Pal24", "gateway_id": "pal24", "percent": partner_settings.pal24_commission},
        {"name": "WATA", "gateway_id": "wata", "percent": partner_settings.wata_commission},
        {
            "name": "Platega",
            "gateway_id": "platega",
            "percent": partner_settings.platega_commission,
        },
    ]

    gateway_fees.extend(
        [
            {
                "name": "Cryptomus",
                "gateway_id": "cryptomus",
                "percent": partner_settings.cryptomus_commission,
            },
            {
                "name": "Robokassa",
                "gateway_id": "robokassa",
                "percent": partner_settings.robokassa_commission,
            },
            {
                "name": "Stripe",
                "gateway_id": "stripe",
                "percent": partner_settings.stripe_commission,
            },
            {
                "name": "MulenPay",
                "gateway_id": "mulenpay",
                "percent": partner_settings.mulenpay_commission,
            },
            {
                "name": "CloudPayments",
                "gateway_id": "cloudpayments",
                "percent": partner_settings.cloudpayments_commission,
            },
        ]
    )

    return {
        "gateway_fees": gateway_fees,
    }


@inject
async def gateway_fee_edit_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для редактирования комиссии ПС."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    gateway_key = dialog_manager.dialog_data.get("selected_gateway", "")

    gateway_percents = {
        "yookassa": partner_settings.yookassa_commission,
        "yoomoney": partner_settings.yoomoney_commission,
        "telegram_stars": partner_settings.telegram_stars_commission,
        "cryptopay": partner_settings.cryptopay_commission,
        "heleket": partner_settings.heleket_commission,
        "pal24": partner_settings.pal24_commission,
        "wata": partner_settings.wata_commission,
        "platega": partner_settings.platega_commission,
    }
    gateway_percents.update(
        {
            "cryptomus": partner_settings.cryptomus_commission,
            "robokassa": partner_settings.robokassa_commission,
            "stripe": partner_settings.stripe_commission,
            "mulenpay": partner_settings.mulenpay_commission,
            "cloudpayments": partner_settings.cloudpayments_commission,
        }
    )

    # gateway_type для Fluent шаблона (верхний регистр как в enum)
    gateway_types = {
        "yookassa": "YOOKASSA",
        "yoomoney": "YOOMONEY",
        "telegram_stars": "TELEGRAM_STARS",
        "cryptopay": "CRYPTOPAY",
        "heleket": "HELEKET",
        "pal24": "PAL24",
        "wata": "WATA",
        "platega": "PLATEGA",
    }
    gateway_types.update(
        {
            "cryptomus": "CRYPTOMUS",
            "robokassa": "ROBOKASSA",
            "stripe": "STRIPE",
            "mulenpay": "MULENPAY",
            "cloudpayments": "CLOUDPAYMENTS",
        }
    )

    return {
        "gateway_key": gateway_key,
        "gateway_type": gateway_types.get(gateway_key, gateway_key.upper()),
        "current_fee": gateway_percents.get(gateway_key, 0),
    }


@inject
async def min_withdrawal_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для минимальной суммы вывода."""
    settings = await settings_service.get()
    partner_settings = settings.partner

    # Конвертируем копейки в рубли для отображения
    return {
        "min_withdrawal": partner_settings.min_withdrawal_amount / 100,
        "min_withdrawal_amount": partner_settings.min_withdrawal_amount,
    }


@inject
async def withdrawals_list_getter(
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для списка запросов на вывод."""
    # Получаем запросы на вывод с фильтрацией по статусу
    status_filter = dialog_manager.dialog_data.get("status_filter")

    withdrawals = await partner_service.get_all_withdrawals(status=status_filter)

    withdrawals_data = [
        {
            "id": str(w.id),
            "partner_id": w.partner_id,
            "amount_rubles": float(w.amount_rub),
            "status": w.status,
            "created_at": w.created_at.strftime("%d.%m.%Y %H:%M") if w.created_at else "",
        }
        for w in withdrawals
    ]

    return {
        "withdrawals": withdrawals_data,
        "has_withdrawals": len(withdrawals_data) > 0,
        "status_filter": status_filter,
        "statuses": list(WithdrawalStatus),
    }


@inject
async def withdrawal_details_getter(
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для деталей запроса на вывод."""
    raw_withdrawal_id = dialog_manager.dialog_data.get("selected_withdrawal_id")

    if raw_withdrawal_id is None:
        return {"error": True}

    try:
        withdrawal_id = int(raw_withdrawal_id)
    except (TypeError, ValueError):
        return {"error": True}

    withdrawal = await partner_service.get_withdrawal(withdrawal_id)

    if not withdrawal:
        return {"error": True}

    partner = await partner_service.get_partner(withdrawal.partner_id)

    return {
        "withdrawal_id": str(withdrawal.id),
        "partner_id": withdrawal.partner_id,
        "partner_telegram_id": partner.user_telegram_id if partner else None,
        "amount_rubles": float(withdrawal.amount_rub),
        "status": withdrawal.status,
        "payment_details": withdrawal.requisites or i18n.get("msg-common-empty-value"),
        "created_at": withdrawal.created_at.strftime("%d.%m.%Y %H:%M")
        if withdrawal.created_at
        else "",
        "processed_at": withdrawal.updated_at.strftime("%d.%m.%Y %H:%M")
        if withdrawal.updated_at and withdrawal.status != WithdrawalStatus.PENDING
        else None,
        "admin_comment": withdrawal.admin_comment or "",
        "is_pending": withdrawal.status == WithdrawalStatus.PENDING,
    }
