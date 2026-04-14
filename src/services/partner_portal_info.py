from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.api.utils.web_app_urls import build_web_referral_link
from src.core.enums import PartnerAccrualStrategy, PartnerLevel, PartnerRewardType
from src.infrastructure.database.models.dto import (
    PartnerIndividualSettingsDto,
    PartnerSettingsDto,
    UserDto,
)
from src.services.partner_portal_models import PartnerInfoSnapshot, PartnerLevelSettingSnapshot

if TYPE_CHECKING:
    from .partner_portal import PartnerPortalService


async def get_info(service: PartnerPortalService, current_user: UserDto) -> PartnerInfoSnapshot:
    settings = await service.partner_service.settings_service.get()
    partner_settings = settings.partner
    min_withdrawal_rub = float(Decimal(partner_settings.min_withdrawal_amount) / Decimal(100))
    effective_currency = (
        await service.partner_service.settings_service.resolve_partner_balance_currency(
            current_user
        )
    )
    min_withdrawal_display = await service._convert_kopecks_to_display(
        partner_settings.min_withdrawal_amount,
        effective_currency,
    )
    support_username = service.config.bot.support_username.get_secret_value().strip().lstrip("@")
    apply_support_url = f"https://t.me/{support_username}" if support_username else None

    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if not partner:
        return PartnerInfoSnapshot(
            is_partner=False,
            is_active=False,
            can_withdraw=False,
            apply_support_url=apply_support_url,
            effective_currency=effective_currency.value,
            min_withdrawal_rub=min_withdrawal_rub,
            min_withdrawal_display=float(min_withdrawal_display),
            balance=0,
            balance_display=0,
            total_earned=0,
            total_earned_display=0,
            total_withdrawn=0,
            total_withdrawn_display=0,
            referrals_count=0,
            level2_referrals_count=0,
            level3_referrals_count=0,
            referral_link=None,
            telegram_referral_link=None,
            web_referral_link=None,
            use_global_settings=True,
            effective_reward_type=PartnerRewardType.PERCENT.value,
            effective_accrual_strategy=PartnerAccrualStrategy.ON_EACH_PAYMENT.value,
            level_settings=[],
        )

    partner_stats = await service.partner_service.get_partner_statistics(partner=partner)
    current_user = await service.referral_portal_service.user_service.ensure_referral_code(
        current_user
    )
    telegram_referral_link = await service.referral_portal_service.referral_service.get_ref_link(
        current_user.referral_code
    )
    web_referral_link = build_web_referral_link(service.config, current_user.referral_code)

    individual_settings = partner.individual_settings
    use_global_settings = bool(individual_settings.use_global_settings)

    effective_reward_type = (
        PartnerRewardType.PERCENT if use_global_settings else individual_settings.reward_type
    )
    effective_accrual_strategy = (
        PartnerAccrualStrategy.ON_EACH_PAYMENT
        if use_global_settings
        else individual_settings.accrual_strategy
    )
    (
        balance_display,
        total_earned_display,
        total_withdrawn_display,
    ) = await service._convert_display_bundle(
        effective_currency=effective_currency,
        amounts_kopecks=(partner.balance, partner.total_earned, partner.total_withdrawn),
    )

    level_settings = [
        service._build_level_setting(
            level=level,
            referrals_count=referrals_count,
            earned_amount=earned_amount,
            partner_settings=partner_settings,
            use_global_settings=use_global_settings,
            individual_settings=individual_settings,
            effective_reward_type=effective_reward_type,
        )
        for level, referrals_count, earned_amount in [
            (
                PartnerLevel.LEVEL_1,
                partner.referrals_count,
                int(partner_stats.get("level1_earnings", 0) or 0),
            ),
            (
                PartnerLevel.LEVEL_2,
                partner.level2_referrals_count,
                int(partner_stats.get("level2_earnings", 0) or 0),
            ),
            (
                PartnerLevel.LEVEL_3,
                partner.level3_referrals_count,
                int(partner_stats.get("level3_earnings", 0) or 0),
            ),
        ]
    ]

    return PartnerInfoSnapshot(
        is_partner=True,
        is_active=partner.is_active,
        can_withdraw=bool(
            partner.is_active and partner.balance >= partner_settings.min_withdrawal_amount
        ),
        apply_support_url=apply_support_url,
        effective_currency=effective_currency.value,
        min_withdrawal_rub=min_withdrawal_rub,
        min_withdrawal_display=float(min_withdrawal_display),
        balance=partner.balance,
        balance_display=float(balance_display),
        total_earned=partner.total_earned,
        total_earned_display=float(total_earned_display),
        total_withdrawn=partner.total_withdrawn,
        total_withdrawn_display=float(total_withdrawn_display),
        referrals_count=partner.referrals_count,
        level2_referrals_count=partner.level2_referrals_count,
        level3_referrals_count=partner.level3_referrals_count,
        referral_link=telegram_referral_link,
        telegram_referral_link=telegram_referral_link,
        web_referral_link=web_referral_link,
        use_global_settings=use_global_settings,
        effective_reward_type=effective_reward_type.value,
        effective_accrual_strategy=effective_accrual_strategy.value,
        level_settings=level_settings,
    )


def _build_level_setting(
    _service: PartnerPortalService,
    *,
    level: PartnerLevel,
    referrals_count: int,
    earned_amount: int,
    partner_settings: PartnerSettingsDto,
    use_global_settings: bool,
    individual_settings: PartnerIndividualSettingsDto,
    effective_reward_type: PartnerRewardType,
) -> PartnerLevelSettingSnapshot:
    global_percent = partner_settings.get_level_percent(level)
    individual_percent = (
        None if use_global_settings else individual_settings.get_level_percent(level)
    )
    raw_individual_fixed_amount = (
        None if use_global_settings else individual_settings.get_level_fixed_amount(level)
    )
    individual_fixed_amount = (
        raw_individual_fixed_amount
        if raw_individual_fixed_amount and raw_individual_fixed_amount > 0
        else None
    )

    effective_percent: Decimal | None = None
    effective_fixed_amount: int | None = None
    uses_global_value = use_global_settings

    if effective_reward_type == PartnerRewardType.FIXED_AMOUNT and individual_fixed_amount:
        effective_fixed_amount = individual_fixed_amount
        uses_global_value = False
    else:
        if use_global_settings:
            effective_percent = global_percent
        elif (
            effective_reward_type == PartnerRewardType.PERCENT
            and individual_percent is not None
        ):
            effective_percent = individual_percent
            uses_global_value = False
        else:
            effective_percent = global_percent
            uses_global_value = True

    return PartnerLevelSettingSnapshot(
        level=int(level.value),
        referrals_count=referrals_count,
        earned_amount=earned_amount,
        global_percent=float(global_percent),
        individual_percent=(float(individual_percent) if individual_percent is not None else None),
        individual_fixed_amount=individual_fixed_amount,
        effective_percent=float(effective_percent) if effective_percent is not None else None,
        effective_fixed_amount=effective_fixed_amount,
        uses_global_value=uses_global_value,
    )
