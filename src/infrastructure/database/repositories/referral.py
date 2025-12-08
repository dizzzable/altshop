from typing import Any, List, Optional

from sqlalchemy import func, select

from src.core.enums import ReferralRewardType
from src.infrastructure.database.models.sql import Referral, ReferralReward

from .base import BaseRepository


class ReferralRepository(BaseRepository):
    async def create_referral(self, referral: Referral) -> Referral:
        return await self.create_instance(referral)

    async def get_referral_by_id(self, referral_id: int) -> Optional[Referral]:
        return await self._get_one(Referral, Referral.id == referral_id)

    async def get_referral_by_referred(self, telegram_id: int) -> Optional[Referral]:
        return await self._get_one(Referral, Referral.referred_telegram_id == telegram_id)

    async def get_referrals_by_referrer(self, telegram_id: int) -> List[Referral]:
        return await self._get_many(Referral, Referral.referrer_telegram_id == telegram_id)

    async def update_referral(self, referral_id: int, **data: Any) -> Optional[Referral]:
        return await self._update(Referral, Referral.id == referral_id, **data)

    async def count_referrals(self) -> int:
        return await self._count(Referral, Referral.id)

    async def create_reward(self, reward: ReferralReward) -> ReferralReward:
        return await self.create_instance(reward)

    async def get_rewards_by_user(self, telegram_id: int) -> List[ReferralReward]:
        return await self._get_many(ReferralReward, ReferralReward.user_telegram_id == telegram_id)

    async def get_rewards_by_referral(self, referral_id: int) -> List[ReferralReward]:
        return await self._get_many(ReferralReward, ReferralReward.referral_id == referral_id)

    async def count_referrals_by_referrer(self, telegram_id: int) -> int:
        return await self._count(Referral, Referral.referrer_telegram_id == telegram_id)

    async def count_rewards_by_referrer(self, telegram_id: int) -> int:
        subquery = (
            select(Referral.id).where(Referral.referrer_telegram_id == telegram_id).subquery()
        )
        return await self._count(ReferralReward, ReferralReward.referral_id.in_(select(subquery)))

    async def sum_rewards_by_user(self, telegram_id: int, reward_type: ReferralRewardType) -> int:
        conditions = [
            ReferralReward.user_telegram_id == telegram_id,
            ReferralReward.type == reward_type,
        ]

        query = select(func.sum(ReferralReward.amount)).where(*conditions)

        result = await self.session.scalar(query)
        return result or 0

    async def update_reward(self, reward_id: int, **data: Any) -> Optional[ReferralReward]:
        return await self._update(ReferralReward, ReferralReward.id == reward_id, **data)
