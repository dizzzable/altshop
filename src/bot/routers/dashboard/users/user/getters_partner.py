from __future__ import annotations

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.enums import PartnerAccrualStrategy, PartnerRewardType
from src.services.partner import PartnerService
from src.services.settings import SettingsService
from src.services.user import UserService


@inject
async def partner_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_partner_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        partner_service=partner_service,
        settings_service=settings_service,
    )


async def _build_partner_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    partner_service: PartnerService,
    settings_service: SettingsService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    partner = await partner_service.get_partner_by_user(target_telegram_id)
    settings = await settings_service.get()
    partner_settings = settings.partner

    if partner and partner.id:
        statistics = await partner_service.get_partner_statistics(partner)
        await partner_service.get_partner_referrals(partner.id)

        return {
            "is_partner": True,
            "is_active": partner.is_active,
            "balance": partner.balance_rub,
            "total_earned": partner.total_earned_rub,
            "total_withdrawn_rubles": partner.total_withdrawn_rub,
            "referrals_count": partner.referrals_count,
            "level1_count": partner.referrals_count,
            "level2_count": partner.level2_referrals_count,
            "level3_count": partner.level3_referrals_count,
            "total_referrals": partner.total_referrals,
            "level1_earned": statistics.get("level1_earnings", 0) / 100,
            "level2_earned": statistics.get("level2_earnings", 0) / 100,
            "level3_earned": statistics.get("level3_earnings", 0) / 100,
            "level_1_percent": partner_settings.level1_percent,
            "level_2_percent": partner_settings.level2_percent,
            "level_3_percent": partner_settings.level3_percent,
            "created_at": partner.created_at.strftime("%d.%m.%Y %H:%M")
            if partner.created_at
            else "",
        }

    return {
        "is_partner": False,
        "is_active": False,
        "balance": 0,
        "total_earned": 0,
        "total_withdrawn_rubles": 0,
        "referrals_count": 0,
        "level1_count": 0,
        "level2_count": 0,
        "level3_count": 0,
        "total_referrals": 0,
        "level1_earned": 0,
        "level2_earned": 0,
        "level3_earned": 0,
        "level_1_percent": partner_settings.level1_percent,
        "level_2_percent": partner_settings.level2_percent,
        "level_3_percent": partner_settings.level3_percent,
        "created_at": "",
    }


@inject
async def partner_balance_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_partner_balance_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        partner_service=partner_service,
    )


async def _build_partner_balance_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    partner_service: PartnerService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    partner = await partner_service.get_partner_by_user(target_telegram_id)
    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    formatted_amounts = [
        {
            "operation": "+" if value > 0 else "",
            "amount": value,
        }
        for value in [100, -100, 500, -500, 1000, -1000, 5000, -5000]
    ]

    return {
        "current_balance": partner.balance_rub,
        "total_earned": partner.total_earned_rub,
        "total_withdrawn": partner.total_withdrawn_rub,
        "amounts": formatted_amounts,
    }


@inject
async def partner_settings_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_partner_settings_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        partner_service=partner_service,
        settings_service=settings_service,
    )


async def _build_partner_settings_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    partner_service: PartnerService,
    settings_service: SettingsService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    partner = await partner_service.get_partner_by_user(target_telegram_id)
    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    settings = await settings_service.get()
    partner_settings = settings.partner
    ind = partner.individual_settings

    if ind.use_global_settings:
        current_l1_percent = partner_settings.level1_percent
        current_l2_percent = partner_settings.level2_percent
        current_l3_percent = partner_settings.level3_percent
        current_strategy = "global"
        current_reward_type = "global"
    else:
        current_l1_percent = (
            ind.level1_percent
            if ind.level1_percent is not None
            else partner_settings.level1_percent
        )
        current_l2_percent = (
            ind.level2_percent
            if ind.level2_percent is not None
            else partner_settings.level2_percent
        )
        current_l3_percent = (
            ind.level3_percent
            if ind.level3_percent is not None
            else partner_settings.level3_percent
        )
        current_strategy = ind.accrual_strategy.value
        current_reward_type = ind.reward_type.value

    return {
        "use_global_settings": ind.use_global_settings,
        "use_global": ind.use_global_settings,
        "accrual_strategy": current_strategy,
        "reward_type": current_reward_type,
        "level1_percent": current_l1_percent,
        "level2_percent": current_l2_percent,
        "level3_percent": current_l3_percent,
        "ind_level1_percent": ind.level1_percent,
        "ind_level2_percent": ind.level2_percent,
        "ind_level3_percent": ind.level3_percent,
        "level1_fixed": ind.level1_fixed_amount / 100 if ind.level1_fixed_amount else 0,
        "level2_fixed": ind.level2_fixed_amount / 100 if ind.level2_fixed_amount else 0,
        "level3_fixed": ind.level3_fixed_amount / 100 if ind.level3_fixed_amount else 0,
        "global_level1_percent": partner_settings.level1_percent,
        "global_level2_percent": partner_settings.level2_percent,
        "global_level3_percent": partner_settings.level3_percent,
        "is_first_payment_only": not ind.use_global_settings
        and ind.accrual_strategy == PartnerAccrualStrategy.ON_FIRST_PAYMENT,
        "is_fixed_amount": not ind.use_global_settings
        and ind.reward_type == PartnerRewardType.FIXED_AMOUNT,
    }


async def partner_accrual_strategy_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "strategies": [
            {
                "value": PartnerAccrualStrategy.ON_EACH_PAYMENT.value,
                "name": "С каждой оплаты реферала",
            },
            {
                "value": PartnerAccrualStrategy.ON_FIRST_PAYMENT.value,
                "name": "Только при первой оплате реферала",
            },
        ]
    }


async def partner_reward_type_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {
        "reward_types": [
            {
                "value": PartnerRewardType.PERCENT.value,
                "name": "Процент от суммы оплаты",
            },
            {
                "value": PartnerRewardType.FIXED_AMOUNT.value,
                "name": "Фиксированная сумма",
            },
        ]
    }


@inject
async def partner_percent_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_partner_percent_getter_payload(
        dialog_manager=dialog_manager,
        partner_service=partner_service,
        settings_service=settings_service,
    )


async def _build_partner_percent_getter_payload(
    *,
    dialog_manager: DialogManager,
    partner_service: PartnerService,
    settings_service: SettingsService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    settings = await settings_service.get()
    partner_settings = settings.partner
    ind = partner.individual_settings

    percentages = [{"value": p, "label": f"{p}%"} for p in [1, 2, 3, 5, 7, 10, 15, 20, 25, 30]]

    return {
        "percentages": percentages,
        "current_level1": ind.level1_percent
        if ind.level1_percent is not None
        else partner_settings.level1_percent,
        "current_level2": ind.level2_percent
        if ind.level2_percent is not None
        else partner_settings.level2_percent,
        "current_level3": ind.level3_percent
        if ind.level3_percent is not None
        else partner_settings.level3_percent,
        "global_level1": partner_settings.level1_percent,
        "global_level2": partner_settings.level2_percent,
        "global_level3": partner_settings.level3_percent,
    }


@inject
async def partner_fixed_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_partner_fixed_getter_payload(
        dialog_manager=dialog_manager,
        partner_service=partner_service,
    )


async def _build_partner_fixed_getter_payload(
    *,
    dialog_manager: DialogManager,
    partner_service: PartnerService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        raise ValueError(f"Partner for user '{target_telegram_id}' not found")

    ind = partner.individual_settings
    amounts = [{"value": a, "label": f"{a} ₽"} for a in [10, 25, 50, 100, 150, 200, 300, 500]]

    return {
        "amounts": amounts,
        "current_level1": ind.level1_fixed_amount / 100 if ind.level1_fixed_amount else 0,
        "current_level2": ind.level2_fixed_amount / 100 if ind.level2_fixed_amount else 0,
        "current_level3": ind.level3_fixed_amount / 100 if ind.level3_fixed_amount else 0,
    }


@inject
async def max_subscriptions_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_max_subscriptions_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        settings_service=settings_service,
    )


async def _build_max_subscriptions_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    settings_service: SettingsService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    settings = await settings_service.get()
    multi_sub = settings.multi_subscription

    if target_user.max_subscriptions is not None:
        current_max = target_user.max_subscriptions
        use_global = False
    else:
        current_max = multi_sub.default_max_subscriptions
        use_global = True

    limits = [
        {"value": 1, "label": "1"},
        {"value": 2, "label": "2"},
        {"value": 3, "label": "3"},
        {"value": 5, "label": "5"},
        {"value": 10, "label": "10"},
        {"value": -1, "label": "∞"},
    ]

    return {
        "use_global": use_global,
        "current_max": current_max,
        "global_max": multi_sub.default_max_subscriptions,
        "multi_subscription_enabled": multi_sub.enabled,
        "limits": limits,
        "is_unlimited": current_max == -1,
    }
