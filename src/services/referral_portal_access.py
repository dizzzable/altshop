from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.api.utils.web_app_urls import build_web_referral_link
from src.infrastructure.database.models.dto import UserDto
from src.services.referral import (
    INVITE_BLOCK_REASON_EXHAUSTED,
    INVITE_BLOCK_REASON_EXPIRED,
    ReferralInviteStateSnapshot,
)

if TYPE_CHECKING:
    from .referral_portal import ReferralPortalService, ResolvedReferralLinks


async def ensure_api_available(service: ReferralPortalService, current_user: UserDto) -> None:
    from .referral_portal import (  # noqa: PLC0415
        REFERRAL_DISABLED_FOR_ACTIVE_PARTNER,
        ReferralPortalAccessDeniedError,
    )

    partner = await service.partner_service.get_partner_by_user(current_user.telegram_id)
    if partner and partner.is_active:
        raise ReferralPortalAccessDeniedError(
            code=REFERRAL_DISABLED_FOR_ACTIVE_PARTNER,
            message="Referral program is disabled for active partners",
        )


async def prepare_user_with_resolved_links(
    service: ReferralPortalService,
    current_user: UserDto,
) -> tuple[UserDto, ResolvedReferralLinks]:
    links = await service.resolve_referral_links(current_user)
    return current_user, links


async def resolve_referral_links(
    service: ReferralPortalService,
    current_user: UserDto,
) -> ResolvedReferralLinks:
    invite_state = await service.referral_service.get_invite_state(
        current_user,
        create_if_missing=True,
    )
    return await service._resolve_links_from_invite_state(invite_state)


async def _resolve_links_from_invite_state(
    service: ReferralPortalService,
    invite_state: ReferralInviteStateSnapshot,
) -> ResolvedReferralLinks:
    from .referral_portal import ResolvedReferralLinks  # noqa: PLC0415

    invite = invite_state.invite
    if not invite or invite_state.invite_block_reason is not None:
        if invite and invite_state.invite_block_reason not in {
            INVITE_BLOCK_REASON_EXPIRED,
            INVITE_BLOCK_REASON_EXHAUSTED,
        }:
            logger.warning(
                "Referral invite '{}' for user '{}' is unavailable: {}",
                invite.token,
                invite.inviter_telegram_id,
                invite_state.invite_block_reason,
            )

        return ResolvedReferralLinks(
            referral_link="",
            telegram_referral_link="",
            web_referral_link="",
        )

    telegram_referral_link = await service.referral_service.get_ref_link(invite.token)
    web_referral_link = build_web_referral_link(service.config, invite.token)
    return ResolvedReferralLinks(
        referral_link=telegram_referral_link,
        telegram_referral_link=telegram_referral_link,
        web_referral_link=web_referral_link,
    )
