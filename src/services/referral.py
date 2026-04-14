from __future__ import annotations

from typing import Any, List, Optional

from aiogram import Bot
from aiogram.types import BufferedInputFile, TelegramObject
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import (
    ReferralInviteSource,
    ReferralLevel,
    ReferralRewardType,
)
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    ReferralDto,
    ReferralInviteDto,
    ReferralInviteLimitsDto,
    ReferralRewardDto,
    ReferralSettingsDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.database.models.sql import Referral
from src.infrastructure.redis import RedisRepository
from src.services.settings import SettingsService
from src.services.user import UserService

from . import referral_invites, referral_links, referral_models, referral_rewards
from .base import BaseService
from .notification import NotificationService
from .referral_models import (
    ReferralInviteCapacitySnapshot,
    ReferralInviteStateSnapshot,
    ReferralManualAttachResult,
)

INVITE_BLOCK_REASON_EXPIRED = referral_models.INVITE_BLOCK_REASON_EXPIRED
INVITE_BLOCK_REASON_EXHAUSTED = referral_models.INVITE_BLOCK_REASON_EXHAUSTED

__all__ = [
    "INVITE_BLOCK_REASON_EXHAUSTED",
    "INVITE_BLOCK_REASON_EXPIRED",
    "ReferralInviteCapacitySnapshot",
    "ReferralInviteStateSnapshot",
    "ReferralManualAttachResult",
    "ReferralService",
]


class ReferralService(BaseService):
    uow: UnitOfWork
    user_service: UserService
    settings_service: SettingsService
    notification_service: NotificationService
    _bot_username: Optional[str]

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        uow: UnitOfWork,
        user_service: UserService,
        settings_service: SettingsService,
        notification_service: NotificationService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.user_service = user_service
        self.settings_service = settings_service
        self.notification_service = notification_service
        self._bot_username = None

    async def create_referral(
        self,
        referrer: UserDto,
        referred: UserDto,
        level: ReferralLevel,
        invite_source: ReferralInviteSource = ReferralInviteSource.UNKNOWN,
    ) -> ReferralDto:
        referral = await self.uow.repository.referrals.create_referral(
            Referral(
                referrer_telegram_id=referrer.telegram_id,
                referred_telegram_id=referred.telegram_id,
                level=level,
                invite_source=invite_source,
            )
        )

        await self.user_service.clear_user_cache(referrer.telegram_id)
        await self.user_service.clear_user_cache(referred.telegram_id)
        logger.info(f"Referral created: {referrer.telegram_id} -> {referred.telegram_id}")
        return ReferralDto.from_model(referral)  # type: ignore[return-value]

    async def get_referral_by_referred(self, telegram_id: int) -> Optional[ReferralDto]:
        referral = await self.uow.repository.referrals.get_referral_by_referred(telegram_id)
        return ReferralDto.from_model(referral) if referral else None

    async def has_referral_attribution(self, telegram_id: int) -> bool:
        return await self.get_referral_by_referred(telegram_id) is not None

    async def get_referrals_by_referrer(self, telegram_id: int) -> List[ReferralDto]:
        referrals = await self.uow.repository.referrals.get_referrals_by_referrer(telegram_id)
        return ReferralDto.from_model_list(referrals)

    async def get_referrals_page_by_referrer(
        self,
        telegram_id: int,
        *,
        page: int,
        limit: int,
    ) -> tuple[List[ReferralDto], int]:
        safe_page = max(page, 1)
        safe_limit = min(max(limit, 1), 100)
        offset = (safe_page - 1) * safe_limit

        total = await self.uow.repository.referrals.count_referrals_by_referrer(telegram_id)
        if total == 0:
            return [], 0

        referrals = await self.uow.repository.referrals.get_referrals_page_by_referrer(
            telegram_id,
            limit=safe_limit,
            offset=offset,
        )
        return ReferralDto.from_model_list(referrals), total

    async def get_referrals_page(
        self,
        *,
        page: int,
        limit: int,
    ) -> tuple[List[ReferralDto], int]:
        safe_page = max(page, 1)
        safe_limit = min(max(limit, 1), 100)
        offset = (safe_page - 1) * safe_limit

        total = await self.uow.repository.referrals.count_referrals()
        if total == 0:
            return [], 0

        referrals = await self.uow.repository.referrals.get_referrals_page(
            limit=safe_limit,
            offset=offset,
        )
        return ReferralDto.from_model_list(referrals), total

    async def get_referral_count(self, telegram_id: int) -> int:
        count = await self.uow.repository.referrals.count_referrals_by_referrer(telegram_id)
        logger.debug(f"Retrieved counted '{count}' referrals for user '{telegram_id}'")
        return count

    async def get_qualified_referral_count(self, telegram_id: int) -> int:
        count = await self.uow.repository.referrals.count_qualified_referrals_by_referrer(
            telegram_id
        )
        logger.debug(f"Retrieved qualified referrals '{count}' for user '{telegram_id}'")
        return count

    async def get_reward_count(self, telegram_id: int) -> int:
        count = await self.uow.repository.referrals.count_rewards_by_referrer(telegram_id)
        logger.debug(f"Retrieved counted '{count}' rewards for user '{telegram_id}'")
        return count

    async def get_total_rewards_amount(
        self,
        telegram_id: int,
        reward_type: ReferralRewardType,
    ) -> int:
        total_amount = await self.uow.repository.referrals.sum_rewards_by_user(
            telegram_id,
            reward_type,
        )
        logger.debug(
            f"Retrieved calculated total rewards amount as '{total_amount}' "
            f"for user 'user_telegram_id' for type '{reward_type.name}'"
        )
        return total_amount

    async def get_effective_invite_limits(
        self,
        inviter: UserDto,
    ) -> ReferralInviteLimitsDto:
        return await referral_invites.get_effective_invite_limits(self, inviter)

    async def get_invite_capacity_snapshot(
        self,
        inviter: UserDto,
        *,
        limits: ReferralInviteLimitsDto | None = None,
    ) -> ReferralInviteCapacitySnapshot:
        return await referral_invites.get_invite_capacity_snapshot(
            self,
            inviter,
            limits=limits,
        )

    async def get_latest_invite(self, inviter_telegram_id: int) -> ReferralInviteDto | None:
        return await referral_invites.get_latest_invite(self, inviter_telegram_id)

    async def get_invite_state(
        self,
        inviter: UserDto,
        *,
        create_if_missing: bool = False,
        regenerate: bool = False,
    ) -> ReferralInviteStateSnapshot:
        return await referral_invites.get_invite_state(
            self,
            inviter,
            create_if_missing=create_if_missing,
            regenerate=regenerate,
        )

    async def regenerate_invite(self, inviter: UserDto) -> ReferralInviteStateSnapshot:
        return await referral_invites.regenerate_invite(self, inviter)

    async def resolve_invite_token(
        self,
        code: str,
        *,
        user_telegram_id: int,
    ) -> tuple[ReferralInviteDto | None, UserDto | None, str | None]:
        return await referral_invites.resolve_invite_token(
            self,
            code,
            user_telegram_id=user_telegram_id,
        )

    async def get_partner_referrer_by_code(
        self,
        code: str,
        *,
        user_telegram_id: int,
    ) -> UserDto | None:
        return await referral_invites.get_partner_referrer_by_code(
            self,
            code,
            user_telegram_id=user_telegram_id,
        )

    async def is_valid_invite_or_partner_code(
        self,
        code: str,
        *,
        user_telegram_id: int,
    ) -> bool:
        return await referral_invites.is_valid_invite_or_partner_code(
            self,
            code,
            user_telegram_id=user_telegram_id,
        )

    async def _get_capacity_counters(self, inviter_telegram_id: int) -> tuple[int, int]:
        return await referral_invites._get_capacity_counters(self, inviter_telegram_id)

    async def _create_new_referral_invite(
        self,
        inviter: UserDto,
        *,
        limits: ReferralInviteLimitsDto,
    ) -> ReferralInviteDto:
        return await referral_invites._create_new_referral_invite(
            self,
            inviter,
            limits=limits,
        )

    async def _generate_unique_invite_token(self, *, length: int = 16) -> str:
        return await referral_invites._generate_unique_invite_token(self, length=length)

    def _build_invite_state_snapshot(
        self,
        *,
        invite: ReferralInviteDto | None,
        capacity: ReferralInviteCapacitySnapshot,
    ) -> ReferralInviteStateSnapshot:
        return referral_invites._build_invite_state_snapshot(
            self,
            invite=invite,
            capacity=capacity,
        )

    def _resolve_invite_block_reason(
        self,
        invite: ReferralInviteDto | None,
        capacity: ReferralInviteCapacitySnapshot,
    ) -> str | None:
        return referral_invites._resolve_invite_block_reason(self, invite, capacity)

    def _normalize_referral_payload(self, code: str) -> str:
        return referral_invites._normalize_referral_payload(self, code)

    def _is_invite_expired(self, invite: ReferralInviteDto) -> bool:
        return referral_invites._is_invite_expired(self, invite)

    async def create_reward(
        self,
        referral_id: int,
        user_telegram_id: int,
        type: ReferralRewardType,
        amount: int,
    ) -> ReferralRewardDto:
        return await referral_rewards.create_reward(
            self,
            referral_id,
            user_telegram_id,
            type,
            amount,
        )

    async def get_rewards_by_user(self, telegram_id: int) -> List[ReferralRewardDto]:
        return await referral_rewards.get_rewards_by_user(self, telegram_id)

    async def get_rewards_by_referral(self, referral_id: int) -> List[ReferralRewardDto]:
        return await referral_rewards.get_rewards_by_referral(self, referral_id)

    async def mark_reward_as_issued(self, reward_id: int) -> None:
        return await referral_rewards.mark_reward_as_issued(self, reward_id)

    async def handle_referral(
        self,
        user: UserDto,
        code: str,
        source: ReferralInviteSource = ReferralInviteSource.UNKNOWN,
    ) -> None:
        return await referral_rewards.handle_referral(self, user, code, source)

    async def _attach_referral(
        self,
        *,
        user: UserDto,
        referrer: UserDto,
        source: ReferralInviteSource,
        enforce_slot_capacity: bool,
    ) -> None:
        return await referral_rewards._attach_referral(
            self,
            user=user,
            referrer=referrer,
            source=source,
            enforce_slot_capacity=enforce_slot_capacity,
        )

    async def attach_referrer_manually(
        self,
        *,
        user: UserDto,
        referrer: UserDto,
        partner_service: Any,
        transaction_service: Any,
    ) -> ReferralManualAttachResult:
        return await referral_rewards.attach_referrer_manually(
            self,
            user=user,
            referrer=referrer,
            partner_service=partner_service,
            transaction_service=transaction_service,
        )

    async def assign_referral_rewards(self, transaction: TransactionDto) -> None:
        return await referral_rewards.assign_referral_rewards(self, transaction)

    def _should_skip_reward_assignment(
        self,
        *,
        settings: ReferralSettingsDto,
        transaction: TransactionDto,
    ) -> bool:
        return referral_rewards._should_skip_reward_assignment(
            self,
            settings=settings,
            transaction=transaction,
        )

    async def _build_reward_chain(
        self,
        current_referrer: BaseUserDto,
    ) -> dict[ReferralLevel, BaseUserDto]:
        return await referral_rewards._build_reward_chain(self, current_referrer)

    async def _issue_referral_reward_for_level(
        self,
        *,
        settings: ReferralSettingsDto,
        transaction: TransactionDto,
        referral: ReferralDto,
        referred_user: BaseUserDto,
        level: ReferralLevel,
        referrer: BaseUserDto,
        task: Any,
    ) -> None:
        return await referral_rewards._issue_referral_reward_for_level(
            self,
            settings=settings,
            transaction=transaction,
            referral=referral,
            referred_user=referred_user,
            level=level,
            referrer=referrer,
            task=task,
        )

    async def get_issued_rewards_map_for_referrer(
        self,
        referrals: list[ReferralDto],
        referrer_telegram_id: int,
    ) -> dict[int, int]:
        referral_ids = [referral.id for referral in referrals if referral.id is not None]
        if not referral_ids:
            return {}

        return await self.uow.repository.referrals.sum_issued_rewards_by_referral_ids_for_user(
            referral_ids=[int(referral_id) for referral_id in referral_ids],
            user_telegram_id=referrer_telegram_id,
        )

    async def get_ref_link(self, referral_payload: str) -> str:
        return await referral_links.get_ref_link(self, referral_payload)

    def generate_ref_qr_bytes(self, url: str) -> bytes:
        return referral_links.generate_ref_qr_bytes(self, url)

    def get_ref_qr(self, url: str) -> BufferedInputFile:
        return referral_links.get_ref_qr(self, url)

    async def get_referrer_by_event(
        self,
        event: TelegramObject,
        user_telegram_id: int,
    ) -> Optional[UserDto]:
        return await referral_links.get_referrer_by_event(self, event, user_telegram_id)

    async def get_partner_referrer_by_event(
        self,
        event: TelegramObject,
        user_telegram_id: int,
    ) -> Optional[UserDto]:
        return await referral_links.get_partner_referrer_by_event(
            self,
            event,
            user_telegram_id,
        )

    async def is_referral_event(self, event: TelegramObject, user_telegram_id: int) -> bool:
        return await referral_links.is_referral_event(self, event, user_telegram_id)

    def _extract_referral_payload_from_event(self, event: TelegramObject) -> str | None:
        return referral_links._extract_referral_payload_from_event(self, event)

    def _define_referral_level(self, parent_level: Optional[ReferralLevel]) -> ReferralLevel:
        return referral_links._define_referral_level(self, parent_level)

    async def _get_bot_redirect_url(self) -> str:
        return await referral_links._get_bot_redirect_url(self)

    def _calculate_reward_amount(
        self,
        settings: ReferralSettingsDto,
        transaction: TransactionDto,
        config_value: int,
    ) -> Optional[int]:
        return referral_rewards._calculate_reward_amount(
            self,
            settings,
            transaction,
            config_value,
        )

    async def _mark_referral_as_qualified(
        self,
        *,
        referral: ReferralDto,
        transaction: TransactionDto,
    ) -> None:
        return await referral_rewards._mark_referral_as_qualified(
            self,
            referral=referral,
            transaction=transaction,
        )
