from __future__ import annotations

from dataclasses import dataclass

from src.core.config import AppConfig
from src.core.enums import PointsExchangeType
from src.infrastructure.database.models.dto import UserDto

from . import referral as referral_module
from .partner import PartnerService
from .referral import (
    ReferralInviteStateSnapshot,
    ReferralService,
)
from .referral_exchange import (
    ReferralExchangeExecutionResult,
    ReferralExchangeOptions,
    ReferralExchangeService,
)
from .referral_portal_access import (
    _resolve_links_from_invite_state as _resolve_links_from_invite_state_impl,
)
from .referral_portal_access import ensure_api_available as _ensure_api_available_impl
from .referral_portal_access import (
    prepare_user_with_resolved_links as _prepare_user_with_resolved_links_impl,
)
from .referral_portal_access import resolve_referral_links as _resolve_referral_links_impl
from .referral_portal_exchange import build_qr_image as _build_qr_image_impl
from .referral_portal_exchange import execute_exchange as _execute_exchange_impl
from .referral_portal_exchange import get_about as _get_about_impl
from .referral_portal_exchange import get_exchange_options as _get_exchange_options_impl
from .referral_portal_info import _serialize_enum_value as _serialize_enum_value_impl
from .referral_portal_info import get_info as _get_info_impl
from .referral_portal_info import list_referrals as _list_referrals_impl
from .user import UserService

REFERRAL_DISABLED_FOR_ACTIVE_PARTNER = "REFERRAL_DISABLED_FOR_ACTIVE_PARTNER"
REFERRAL_INVITE_UNAVAILABLE = "REFERRAL_INVITE_UNAVAILABLE"
INVITE_BLOCK_REASON_EXPIRED = referral_module.INVITE_BLOCK_REASON_EXPIRED
INVITE_BLOCK_REASON_EXHAUSTED = referral_module.INVITE_BLOCK_REASON_EXHAUSTED


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
    referral_code: str | None
    invite_expires_at: str | None
    remaining_slots: int | None
    total_capacity: int | None
    requires_regeneration: bool
    invite_block_reason: str | None
    refill_step_progress: int | None
    refill_step_target: int | None
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
        return await _ensure_api_available_impl(self, current_user)

    async def prepare_user_with_resolved_links(
        self,
        current_user: UserDto,
    ) -> tuple[UserDto, ResolvedReferralLinks]:
        return await _prepare_user_with_resolved_links_impl(self, current_user)

    async def resolve_referral_links(
        self,
        current_user: UserDto,
    ) -> ResolvedReferralLinks:
        return await _resolve_referral_links_impl(self, current_user)

    async def get_info(self, current_user: UserDto) -> ReferralInfoSnapshot:
        return await _get_info_impl(self, current_user)

    async def build_qr_image(self, *, target: str, current_user: UserDto) -> bytes:
        return await _build_qr_image_impl(self, target=target, current_user=current_user)

    async def list_referrals(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> ReferralListPageSnapshot:
        return await _list_referrals_impl(
            self,
            current_user=current_user,
            page=page,
            limit=limit,
        )

    async def get_exchange_options(self, current_user: UserDto) -> ReferralExchangeOptions:
        return await _get_exchange_options_impl(self, current_user)

    async def execute_exchange(
        self,
        *,
        current_user: UserDto,
        exchange_type: PointsExchangeType,
        subscription_id: int | None,
        gift_plan_id: int | None,
    ) -> ReferralExchangeExecutionResult:
        return await _execute_exchange_impl(
            self,
            current_user=current_user,
            exchange_type=exchange_type,
            subscription_id=subscription_id,
            gift_plan_id=gift_plan_id,
        )

    @staticmethod
    def get_about() -> ReferralAboutSnapshot:
        return _get_about_impl()

    @staticmethod
    def _serialize_enum_value(value: object | None) -> str | None:
        return _serialize_enum_value_impl(value)

    async def _resolve_links_from_invite_state(
        self,
        invite_state: ReferralInviteStateSnapshot,
    ) -> ResolvedReferralLinks:
        return await _resolve_links_from_invite_state_impl(self, invite_state)
