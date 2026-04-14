from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.enums import PointsExchangeType
from src.infrastructure.database.models.dto import UserDto
from src.services.referral_exchange import (
    ReferralExchangeExecutionResult,
    ReferralExchangeOptions,
)

if TYPE_CHECKING:
    from .referral_portal import ReferralAboutSnapshot, ReferralPortalService


async def build_qr_image(
    service: ReferralPortalService,
    *,
    target: str,
    current_user: UserDto,
) -> bytes:
    from .referral_portal import (  # noqa: PLC0415
        REFERRAL_INVITE_UNAVAILABLE,
        ReferralPortalAccessDeniedError,
    )

    await service.ensure_api_available(current_user)
    links = await service.resolve_referral_links(current_user)
    referral_link = links.web_referral_link if target == "web" else links.telegram_referral_link

    if not referral_link:
        raise ReferralPortalAccessDeniedError(
            code=REFERRAL_INVITE_UNAVAILABLE,
            message="Active referral invite link is unavailable",
        )

    return service.referral_service.generate_ref_qr_bytes(referral_link)


async def get_exchange_options(
    service: ReferralPortalService,
    current_user: UserDto,
) -> ReferralExchangeOptions:
    await service.ensure_api_available(current_user)
    return await service.referral_exchange_service.get_options(
        user_telegram_id=current_user.telegram_id
    )


async def execute_exchange(
    service: ReferralPortalService,
    *,
    current_user: UserDto,
    exchange_type: PointsExchangeType,
    subscription_id: int | None,
    gift_plan_id: int | None,
) -> ReferralExchangeExecutionResult:
    await service.ensure_api_available(current_user)
    return await service.referral_exchange_service.execute(
        user_telegram_id=current_user.telegram_id,
        exchange_type=exchange_type,
        subscription_id=subscription_id,
        gift_plan_id=gift_plan_id,
    )


def get_about(_service: ReferralPortalService | None = None) -> ReferralAboutSnapshot:
    from .referral_portal import ReferralAboutSnapshot  # noqa: PLC0415

    return ReferralAboutSnapshot(
        title="Referral Program",
        description="Invite friends and earn rewards!",
        how_it_works=[
            "Share your referral link",
            "Friend registers and makes a purchase",
            "You earn rewards for each level",
        ],
        rewards={
            "1": "Direct referrals - highest reward",
            "2": "Second level - smaller reward",
            "3": "Third level - minimal reward",
        },
        faq=[
            {"question": "How do I get my referral link?", "answer": "It's shown on this page"},
            {
                "question": "When do I receive rewards?",
                "answer": "After your friend's first payment",
            },
        ],
    )
