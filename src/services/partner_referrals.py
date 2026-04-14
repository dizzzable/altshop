from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from loguru import logger

from src.core.enums import PartnerLevel, UserNotificationType
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PartnerDto, PartnerReferralDto, UserDto
from src.infrastructure.database.models.sql import PartnerReferral

if TYPE_CHECKING:
    from .partner import PartnerService


async def add_partner_referral(
    service: PartnerService,
    partner: PartnerDto,
    referral_telegram_id: int,
    level: PartnerLevel = PartnerLevel.LEVEL_1,
    parent_partner_id: Optional[int] = None,
) -> PartnerReferralDto:
    assert partner.id is not None, "Partner ID is required for referral creation"
    existing_referral = await service.uow.repository.partners.get_partner_referral(
        partner_id=partner.id,
        referral_telegram_id=referral_telegram_id,
        level=level,
    )
    if existing_referral:
        logger.info(
            "Partner referral already exists: partner '{}' -> referral '{}' (level {})",
            partner.id,
            referral_telegram_id,
            level,
        )
        return PartnerReferralDto.from_model(existing_referral)  # type: ignore[return-value]

    referral = await service.uow.repository.partners.create_partner_referral(
        PartnerReferral(
            partner_id=partner.id,
            referral_telegram_id=referral_telegram_id,
            level=level,
            parent_partner_id=parent_partner_id,
        )
    )

    update_data: dict[str, int] = {}
    if level == PartnerLevel.LEVEL_1:
        update_data["referrals_count"] = partner.referrals_count + 1
    elif level == PartnerLevel.LEVEL_2:
        update_data["level2_referrals_count"] = partner.level2_referrals_count + 1
    elif level == PartnerLevel.LEVEL_3:
        update_data["level3_referrals_count"] = partner.level3_referrals_count + 1

    if update_data:
        await service.uow.repository.partners.update_partner(partner.id, **update_data)

    logger.info(
        f"Partner referral added: partner '{partner.id}' -> "
        f"referral '{referral_telegram_id}' (level {level})"
    )
    return PartnerReferralDto.from_model(referral)  # type: ignore[return-value]


async def attach_partner_referral_chain(
    service: PartnerService,
    *,
    user: UserDto,
    referrer: UserDto,
) -> bool:
    referrer_partner = await service.get_partner_by_user(referrer.telegram_id)
    if not referrer_partner or not referrer_partner.is_active:
        logger.debug(f"Referrer '{referrer.telegram_id}' is not an active partner")
        return False

    await service.add_partner_referral(
        partner=referrer_partner,
        referral_telegram_id=user.telegram_id,
        level=PartnerLevel.LEVEL_1,
    )

    referrer_referral = await service.uow.repository.partners.get_partner_referral_by_user(
        referrer.telegram_id
    )
    if referrer_referral:
        level2_partner = await service.get_partner(referrer_referral.partner_id)
        if level2_partner and level2_partner.is_active:
            await service.add_partner_referral(
                partner=level2_partner,
                referral_telegram_id=user.telegram_id,
                level=PartnerLevel.LEVEL_2,
                parent_partner_id=referrer_partner.id,
            )

            level2_user = await service.user_service.get(
                telegram_id=level2_partner.user_telegram_id
            )
            if level2_user:
                level2_user_referral = (
                    await service.uow.repository.partners.get_partner_referral_by_user(
                        level2_user.telegram_id
                    )
                )
                if level2_user_referral:
                    level3_partner = await service.get_partner(level2_user_referral.partner_id)
                    if level3_partner and level3_partner.is_active:
                        await service.add_partner_referral(
                            partner=level3_partner,
                            referral_telegram_id=user.telegram_id,
                            level=PartnerLevel.LEVEL_3,
                            parent_partner_id=level2_partner.id,
                        )

    return True


async def handle_new_user_referral(
    service: PartnerService,
    user: UserDto,
    referrer_code: str,
) -> None:
    referrer = await service.user_service.get_by_referral_code(referrer_code)
    if not referrer:
        logger.warning(f"Referrer with code '{referrer_code}' not found")
        return

    attached = await service.attach_partner_referral_chain(user=user, referrer=referrer)
    if not attached:
        return

    logger.info(
        f"User '{user.telegram_id}' registered via partner referral "
        f"from '{referrer.telegram_id}'"
    )
    try:
        await service.notification_service.notify_user(
            user=referrer,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-partner-referral-registered",
                i18n_kwargs={"name": user.name or str(user.telegram_id)},
            ),
            ntf_type=UserNotificationType.PARTNER_REFERRAL_REGISTERED,
        )
    except Exception as exception:
        logger.warning(
            f"Failed to send partner referral registration notification "
            f"to '{referrer.telegram_id}': {exception}"
        )


async def get_partner_referrals(
    service: PartnerService,
    partner_id: int,
    level: Optional[PartnerLevel] = None,
) -> List[PartnerReferralDto]:
    referrals = await service.uow.repository.partners.get_referrals_by_partner(
        partner_id,
        level,
    )
    return PartnerReferralDto.from_model_list(referrals)


async def get_partner_referral_transaction_stats(
    service: PartnerService,
    *,
    partner_id: int,
    referral_telegram_ids: List[int],
) -> dict[int, dict[str, Any]]:
    return await service.uow.repository.partners.get_partner_referral_transaction_stats(
        partner_id=partner_id,
        referral_telegram_ids=referral_telegram_ids,
    )


async def get_referral_invite_sources(
    service: PartnerService,
    *,
    referral_telegram_ids: List[int],
) -> dict[int, str]:
    return await service.uow.repository.referrals.get_invite_sources_by_referred_ids(
        referral_telegram_ids
    )
