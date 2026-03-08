from __future__ import annotations

import asyncio
from dataclasses import dataclass

from loguru import logger

from src.api.utils.web_app_urls import build_web_referral_link
from src.core.config import AppConfig
from src.core.constants import REFERRAL_PREFIX
from src.core.enums import PointsExchangeType
from src.infrastructure.database.models.dto import UserDto

from .partner import PartnerService
from .referral import ReferralService
from .referral_exchange import (
    ReferralExchangeExecutionResult,
    ReferralExchangeOptions,
    ReferralExchangeService,
)
from .user import UserService

REFERRAL_DISABLED_FOR_ACTIVE_PARTNER = "REFERRAL_DISABLED_FOR_ACTIVE_PARTNER"


class ReferralPortalError(Exception):
    """Base error for referral portal flows."""


class ReferralPortalAccessDeniedError(ReferralPortalError):
    def __init__(self, *, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(slots=True, frozen=True)
class ResolvedReferralLinks:
    referral_link: str
    telegram_referral_link: str
    web_referral_link: str


@dataclass(slots=True, frozen=True)
class ReferralInfoSnapshot:
    referral_count: int
    qualified_referral_count: int
    reward_count: int
    referral_link: str
    telegram_referral_link: str
    web_referral_link: str
    referral_code: str
    points: int


@dataclass(slots=True, frozen=True)
class ReferralEventSnapshot:
    type: str
    at: str
    source: str | None = None
    channel: str | None = None


@dataclass(slots=True, frozen=True)
class ReferralItemSnapshot:
    telegram_id: int
    username: str | None
    name: str | None
    level: int
    invited_at: str
    joined_at: str
    invite_source: str
    is_active: bool
    is_qualified: bool
    qualified_at: str | None
    qualified_purchase_channel: str | None
    rewards_issued: int
    rewards_earned: int
    events: list[ReferralEventSnapshot]


@dataclass(slots=True, frozen=True)
class ReferralListPageSnapshot:
    referrals: list[ReferralItemSnapshot]
    total: int
    page: int
    limit: int


@dataclass(slots=True, frozen=True)
class ReferralAboutSnapshot:
    title: str
    description: str
    how_it_works: list[str]
    rewards: dict[str, str]
    faq: list[dict[str, str]]


class ReferralPortalService:
    def __init__(
        self,
        config: AppConfig,
        referral_service: ReferralService,
        referral_exchange_service: ReferralExchangeService,
        partner_service: PartnerService,
        user_service: UserService,
    ) -> None:
        self.config = config
        self.referral_service = referral_service
        self.referral_exchange_service = referral_exchange_service
        self.partner_service = partner_service
        self.user_service = user_service

    async def ensure_api_available(self, current_user: UserDto) -> None:
        partner = await self.partner_service.get_partner_by_user(current_user.telegram_id)
        if partner and partner.is_active:
            raise ReferralPortalAccessDeniedError(
                code=REFERRAL_DISABLED_FOR_ACTIVE_PARTNER,
                message="Referral program is disabled for active partners",
            )

    async def prepare_user_with_resolved_links(
        self,
        current_user: UserDto,
        *,
        retry_delay_seconds: float = 0.2,
    ) -> tuple[UserDto, ResolvedReferralLinks]:
        ensured_user = await self.user_service.ensure_referral_code(current_user)
        links = await self.resolve_referral_links(
            ensured_user,
            retry_delay_seconds=retry_delay_seconds,
        )
        return ensured_user, links

    async def resolve_referral_links(
        self,
        current_user: UserDto,
        *,
        retry_delay_seconds: float = 0.2,
    ) -> ResolvedReferralLinks:
        referral_code = current_user.referral_code
        web_referral_link = build_web_referral_link(self.config, referral_code)

        last_exception: Exception | None = None
        for attempt in range(2):
            try:
                telegram_referral_link = await self.referral_service.get_ref_link(referral_code)
                return ResolvedReferralLinks(
                    referral_link=telegram_referral_link,
                    telegram_referral_link=telegram_referral_link,
                    web_referral_link=web_referral_link,
                )
            except Exception as exception:  # noqa: BLE001
                last_exception = exception
                if attempt == 0:
                    await asyncio.sleep(retry_delay_seconds)

        error_type = type(last_exception).__name__ if last_exception else "UnknownError"
        error_text = str(last_exception) if last_exception else "unknown"
        logger.warning(
            f"Failed to resolve telegram referral link for user '{current_user.telegram_id}' "
            f"code '{referral_code}' after retry: {error_type}: {error_text}. "
            f"Using web referral link fallback."
        )
        return ResolvedReferralLinks(
            referral_link=web_referral_link,
            telegram_referral_link=web_referral_link,
            web_referral_link=web_referral_link,
        )

    async def get_info(self, current_user: UserDto) -> ReferralInfoSnapshot:
        await self.ensure_api_available(current_user)
        current_user, links = await self.prepare_user_with_resolved_links(current_user)

        referral_count, qualified_referral_count, reward_count, user = await asyncio.gather(
            self.referral_service.get_referral_count(current_user.telegram_id),
            self.referral_service.get_qualified_referral_count(current_user.telegram_id),
            self.referral_service.get_reward_count(current_user.telegram_id),
            self.user_service.get(current_user.telegram_id),
        )

        return ReferralInfoSnapshot(
            referral_count=referral_count,
            qualified_referral_count=qualified_referral_count,
            reward_count=reward_count,
            referral_link=links.referral_link,
            telegram_referral_link=links.telegram_referral_link,
            web_referral_link=links.web_referral_link,
            referral_code=f"{REFERRAL_PREFIX}{current_user.referral_code}",
            points=user.points if user else 0,
        )

    async def build_qr_image(self, *, target: str, current_user: UserDto) -> bytes:
        await self.ensure_api_available(current_user)
        current_user = await self.user_service.ensure_referral_code(current_user)

        if target == "web":
            referral_link = build_web_referral_link(self.config, current_user.referral_code)
        else:
            referral_link = (
                await self.resolve_referral_links(current_user)
            ).telegram_referral_link

        return self.referral_service.generate_ref_qr_bytes(referral_link)

    async def list_referrals(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> ReferralListPageSnapshot:
        await self.ensure_api_available(current_user)

        referrals, total = await self.referral_service.get_referrals_page_by_referrer(
            current_user.telegram_id,
            page=page,
            limit=limit,
        )
        rewards_map = await self.referral_service.get_issued_rewards_map_for_referrer(
            referrals=referrals,
            referrer_telegram_id=current_user.telegram_id,
        )

        referral_items: list[ReferralItemSnapshot] = []
        for ref in referrals:
            referred_user = ref.referred
            invite_source = self._serialize_enum_value(ref.invite_source) or "UNKNOWN"
            qualified_channel = (
                self._serialize_enum_value(ref.qualified_purchase_channel) or "UNKNOWN"
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

    async def get_exchange_options(self, current_user: UserDto) -> ReferralExchangeOptions:
        await self.ensure_api_available(current_user)
        return await self.referral_exchange_service.get_options(
            user_telegram_id=current_user.telegram_id
        )

    async def execute_exchange(
        self,
        *,
        current_user: UserDto,
        exchange_type: PointsExchangeType,
        subscription_id: int | None,
        gift_plan_id: int | None,
    ) -> ReferralExchangeExecutionResult:
        await self.ensure_api_available(current_user)
        return await self.referral_exchange_service.execute(
            user_telegram_id=current_user.telegram_id,
            exchange_type=exchange_type,
            subscription_id=subscription_id,
            gift_plan_id=gift_plan_id,
        )

    @staticmethod
    def get_about() -> ReferralAboutSnapshot:
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

    @staticmethod
    def _serialize_enum_value(value: object | None) -> str | None:
        if value is None:
            return None
        if hasattr(value, "value"):
            return str(getattr(value, "value"))
        return str(value)
