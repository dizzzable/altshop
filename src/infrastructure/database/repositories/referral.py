from typing import Any, List, Optional

from sqlalchemy import and_, func, select

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
        return await self._get_many(
            Referral,
            Referral.referrer_telegram_id == telegram_id,
            order_by=[Referral.created_at.desc(), Referral.id.desc()],
        )

    async def get_referrals_page_by_referrer(
        self,
        telegram_id: int,
        *,
        limit: int,
        offset: int,
    ) -> List[Referral]:
        return await self._get_many(
            Referral,
            Referral.referrer_telegram_id == telegram_id,
            order_by=[Referral.created_at.desc(), Referral.id.desc()],
            limit=limit,
            offset=offset,
        )

    async def get_referrals_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> List[Referral]:
        return await self._get_many(
            Referral,
            order_by=[Referral.created_at.desc(), Referral.id.desc()],
            limit=limit,
            offset=offset,
        )

    async def update_referral(self, referral_id: int, **data: Any) -> Optional[Referral]:
        return await self._update(Referral, Referral.id == referral_id, **data)

    async def count_referrals(self) -> int:
        return await self._count(Referral)

    async def count_qualified_referrals_by_referrer(self, telegram_id: int) -> int:
        return await self._count(
            Referral,
            and_(
                Referral.referrer_telegram_id == telegram_id,
                Referral.qualified_at.is_not(None),
            ),
        )

    async def get_invite_sources_by_referred_ids(
        self,
        referred_telegram_ids: list[int],
    ) -> dict[int, str]:
        if not referred_telegram_ids:
            return {}

        query = select(Referral.referred_telegram_id, Referral.invite_source).where(
            Referral.referred_telegram_id.in_(referred_telegram_ids)
        )
        rows = (await self.session.execute(query)).all()

        invite_sources: dict[int, str] = {}
        for referred_telegram_id, invite_source in rows:
            invite_sources[int(referred_telegram_id)] = (
                invite_source.value if hasattr(invite_source, "value") else str(invite_source)
            )
        return invite_sources

    async def create_reward(self, reward: ReferralReward) -> ReferralReward:
        return await self.create_instance(reward)

    async def get_reward_by_id(self, reward_id: int) -> Optional[ReferralReward]:
        return await self._get_one(ReferralReward, ReferralReward.id == reward_id)

    async def get_reward_by_source_transaction(
        self,
        *,
        referral_id: int,
        user_telegram_id: int,
        source_transaction_id: int,
    ) -> Optional[ReferralReward]:
        return await self._get_one(
            ReferralReward,
            ReferralReward.referral_id == referral_id,
            ReferralReward.user_telegram_id == user_telegram_id,
            ReferralReward.source_transaction_id == source_transaction_id,
        )

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

    async def sum_issued_rewards_by_referral_ids_for_user(
        self,
        referral_ids: list[int],
        user_telegram_id: int,
    ) -> dict[int, int]:
        if not referral_ids:
            return {}

        query = (
            select(
                ReferralReward.referral_id,
                func.coalesce(func.sum(ReferralReward.amount), 0),
            )
            .where(
                ReferralReward.referral_id.in_(referral_ids),
                ReferralReward.user_telegram_id == user_telegram_id,
                ReferralReward.is_issued.is_(True),
            )
            .group_by(ReferralReward.referral_id)
        )
        rows = (await self.session.execute(query)).all()
        return {int(referral_id): int(total) for referral_id, total in rows}
