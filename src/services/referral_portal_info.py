from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.infrastructure.database.models.dto import UserDto

if TYPE_CHECKING:
    from .referral_portal import (
        ReferralInfoSnapshot,
        ReferralItemSnapshot,
        ReferralListPageSnapshot,
        ReferralPortalService,
    )


async def get_info(service: ReferralPortalService, current_user: UserDto) -> ReferralInfoSnapshot:
    from .referral_portal import ReferralInfoSnapshot  # noqa: PLC0415

    await service.ensure_api_available(current_user)
    invite_state = await service.referral_service.get_invite_state(
        current_user,
        create_if_missing=True,
    )
    _, links = await service.prepare_user_with_resolved_links(current_user)

    referral_count, qualified_referral_count, reward_count, user = await asyncio.gather(
        service.referral_service.get_referral_count(current_user.telegram_id),
        service.referral_service.get_qualified_referral_count(current_user.telegram_id),
        service.referral_service.get_reward_count(current_user.telegram_id),
        service.user_service.get(current_user.telegram_id),
    )

    return ReferralInfoSnapshot(
        referral_count=referral_count,
        qualified_referral_count=qualified_referral_count,
        reward_count=reward_count,
        referral_link=links.referral_link,
        telegram_referral_link=links.telegram_referral_link,
        web_referral_link=links.web_referral_link,
        referral_code=(
            f"ref_{invite_state.invite.token}"
            if invite_state.invite and invite_state.invite_block_reason is None
            else None
        ),
        invite_expires_at=(
            invite_state.invite_expires_at.isoformat() if invite_state.invite_expires_at else None
        ),
        remaining_slots=invite_state.remaining_slots,
        total_capacity=invite_state.total_capacity,
        requires_regeneration=invite_state.requires_regeneration,
        invite_block_reason=invite_state.invite_block_reason,
        refill_step_progress=invite_state.refill_step_progress,
        refill_step_target=invite_state.refill_step_target,
        points=user.points if user else 0,
    )


async def list_referrals(
    service: ReferralPortalService,
    *,
    current_user: UserDto,
    page: int,
    limit: int,
) -> ReferralListPageSnapshot:
    from .referral_portal import (  # noqa: PLC0415
        ReferralEventSnapshot,
        ReferralItemSnapshot,
        ReferralListPageSnapshot,
    )

    await service.ensure_api_available(current_user)

    referrals, total = await service.referral_service.get_referrals_page_by_referrer(
        current_user.telegram_id,
        page=page,
        limit=limit,
    )
    rewards_map = await service.referral_service.get_issued_rewards_map_for_referrer(
        referrals=referrals,
        referrer_telegram_id=current_user.telegram_id,
    )

    referral_items: list[ReferralItemSnapshot] = []
    for ref in referrals:
        referred_user = ref.referred
        invite_source = service._serialize_enum_value(ref.invite_source) or "UNKNOWN"
        qualified_channel = (
            service._serialize_enum_value(ref.qualified_purchase_channel) or "UNKNOWN"
            if ref.qualified_at
            else None
        )
        invited_at = ref.created_at.isoformat() if ref.created_at else ""
        qualified_at = ref.qualified_at.isoformat() if ref.qualified_at else None
        rewards_issued = rewards_map.get(ref.id or 0, 0)

        events = [
            ReferralEventSnapshot(
                type="INVITED",
                at=invited_at,
                source=invite_source,
            )
        ]
        if qualified_at:
            events.append(
                ReferralEventSnapshot(
                    type="QUALIFIED",
                    at=qualified_at,
                    channel=qualified_channel or "UNKNOWN",
                )
            )

        referral_items.append(
            ReferralItemSnapshot(
                telegram_id=referred_user.telegram_id,
                username=referred_user.username,
                name=referred_user.name,
                level=ref.level.value if hasattr(ref.level, "value") else int(ref.level),
                invited_at=invited_at,
                joined_at=invited_at,
                invite_source=invite_source,
                is_active=not referred_user.is_blocked,
                is_qualified=ref.is_qualified,
                qualified_at=qualified_at,
                qualified_purchase_channel=qualified_channel,
                rewards_issued=rewards_issued,
                rewards_earned=rewards_issued,
                events=events,
            )
        )

    return ReferralListPageSnapshot(
        referrals=referral_items,
        total=total,
        page=page,
        limit=limit,
    )


def _serialize_enum_value(value: object | None) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)
