from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.infrastructure.database.models.dto import PartnerDto, PartnerIndividualSettingsDto, UserDto
from src.infrastructure.database.models.sql import Partner

if TYPE_CHECKING:
    from .partner import PartnerService


async def create_partner(service: PartnerService, user: UserDto) -> PartnerDto:
    existing = await service.get_partner_by_user(user.telegram_id)
    if existing:
        logger.warning("Partner for user '{}' already exists", user.telegram_id)
        return existing

    partner = await service.uow.repository.partners.create_partner(
        Partner(
            user_telegram_id=user.telegram_id,
            balance=0,
            total_earned=0,
            total_withdrawn=0,
            referrals_count=0,
            level2_referrals_count=0,
            level3_referrals_count=0,
            is_active=True,
        )
    )

    logger.info("Partner created for user '{}'", user.telegram_id)
    return PartnerDto.from_model(partner)  # type: ignore[return-value]


async def get_partner(service: PartnerService, partner_id: int) -> PartnerDto | None:
    partner = await service.uow.repository.partners.get_partner_by_id(partner_id)
    return PartnerDto.from_model(partner) if partner else None


async def get_partner_by_user(service: PartnerService, telegram_id: int) -> PartnerDto | None:
    partner = await service.uow.repository.partners.get_partner_by_user(telegram_id)
    return PartnerDto.from_model(partner) if partner else None


async def has_partner_attribution(service: PartnerService, telegram_id: int) -> bool:
    referral = await service.uow.repository.partners.get_partner_referral_by_user(telegram_id)
    return referral is not None


async def is_partner(service: PartnerService, telegram_id: int) -> bool:
    partner = await service.get_partner_by_user(telegram_id)
    return partner is not None and partner.is_active


async def get_all_partners(service: PartnerService) -> list[PartnerDto]:
    partners = await service.uow.repository.partners.get_all_partners()
    return PartnerDto.from_model_list(partners)


async def toggle_partner_status(service: PartnerService, partner_id: int) -> PartnerDto | None:
    partner = await service.get_partner(partner_id)
    if not partner:
        return None

    updated = await service.uow.repository.partners.update_partner(
        partner_id,
        is_active=not partner.is_active,
    )
    logger.info("Partner '{}' status changed to {}", partner_id, not partner.is_active)
    return PartnerDto.from_model(updated) if updated else None


async def deactivate_partner(service: PartnerService, partner_id: int) -> PartnerDto | None:
    updated = await service.uow.repository.partners.update_partner(
        partner_id,
        is_active=False,
    )
    logger.info("Partner '{}' deactivated", partner_id)
    return PartnerDto.from_model(updated) if updated else None


async def update_partner_individual_settings(
    service: PartnerService,
    partner_id: int,
    settings: PartnerIndividualSettingsDto,
) -> PartnerDto | None:
    partner = await service.get_partner(partner_id)
    if not partner:
        logger.warning("Partner '{}' not found for settings update", partner_id)
        return None

    settings_dict = {
        "use_global_settings": settings.use_global_settings,
        "accrual_strategy": settings.accrual_strategy.value,
        "reward_type": settings.reward_type.value,
        "level1_percent": str(settings.level1_percent)
        if settings.level1_percent is not None
        else None,
        "level2_percent": str(settings.level2_percent)
        if settings.level2_percent is not None
        else None,
        "level3_percent": str(settings.level3_percent)
        if settings.level3_percent is not None
        else None,
        "level1_fixed_amount": settings.level1_fixed_amount,
        "level2_fixed_amount": settings.level2_fixed_amount,
        "level3_fixed_amount": settings.level3_fixed_amount,
    }

    updated = await service.uow.repository.partners.update_partner(
        partner_id,
        individual_settings=settings_dict,
    )

    if updated:
        logger.info(
            "Partner '{}' individual settings updated: use_global={}, strategy={}, type={}",
            partner_id,
            settings.use_global_settings,
            settings.accrual_strategy.value,
            settings.reward_type.value,
        )
        return PartnerDto.from_model(updated)

    return None


async def adjust_partner_balance(
    service: PartnerService,
    partner_id: int,
    amount: int,
    admin_telegram_id: int,
    reason: str | None = None,
) -> PartnerDto | None:
    partner = await service.get_partner(partner_id)
    if not partner:
        logger.warning("Partner '{}' not found for balance adjustment", partner_id)
        return None

    new_balance = partner.balance + amount
    if new_balance < 0:
        logger.warning(
            "Cannot adjust partner '{}' balance by {}: resulting balance {} would be negative",
            partner_id,
            amount,
            new_balance,
        )
        return None

    updated = await service.uow.repository.partners.update_partner(
        partner_id,
        balance=new_balance,
    )

    if updated:
        operation = "added" if amount > 0 else "subtracted"
        logger.info(
            "Admin '{}' {} {} kopecks to partner '{}' balance. New balance: {}. Reason: {}",
            admin_telegram_id,
            operation,
            abs(amount),
            partner_id,
            new_balance,
            reason or "Not specified",
        )
        return PartnerDto.from_model(updated)

    return None
