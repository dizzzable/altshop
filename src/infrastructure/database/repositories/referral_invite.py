from typing import Any, Optional

from sqlalchemy import select, update

from src.infrastructure.database.models.sql import ReferralInvite

from .base import BaseRepository


class ReferralInviteRepository(BaseRepository):
    async def create_invite(self, invite: ReferralInvite) -> ReferralInvite:
        return await self.create_instance(invite)

    async def get_by_token(self, token: str) -> Optional[ReferralInvite]:
        return await self._get_one(ReferralInvite, ReferralInvite.token == token)

    async def get_latest_by_inviter(self, inviter_telegram_id: int) -> Optional[ReferralInvite]:
        query = (
            select(ReferralInvite)
            .where(ReferralInvite.inviter_telegram_id == inviter_telegram_id)
            .order_by(ReferralInvite.created_at.desc(), ReferralInvite.id.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_unrevoked_by_inviter(
        self,
        inviter_telegram_id: int,
    ) -> list[ReferralInvite]:
        return await self._get_many(
            ReferralInvite,
            ReferralInvite.inviter_telegram_id == inviter_telegram_id,
            ReferralInvite.revoked_at.is_(None),
            order_by=[ReferralInvite.created_at.desc(), ReferralInvite.id.desc()],
        )

    async def revoke_unrevoked_by_inviter(
        self,
        inviter_telegram_id: int,
        *,
        revoked_at: Any,
    ) -> int:
        result = await self.session.execute(
            update(ReferralInvite)
            .where(
                ReferralInvite.inviter_telegram_id == inviter_telegram_id,
                ReferralInvite.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return self._rowcount(result)

    async def update_invite(self, invite_id: int, **data: Any) -> Optional[ReferralInvite]:
        return await self._update(ReferralInvite, ReferralInvite.id == invite_id, **data)
