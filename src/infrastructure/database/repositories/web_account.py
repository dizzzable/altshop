from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.sql import AuthChallenge, WebAccount

from .base import BaseRepository


class WebAccountRepository(BaseRepository):
    async def create(self, account: WebAccount) -> WebAccount:
        return await self.create_instance(account)

    async def get(self, account_id: int) -> Optional[WebAccount]:
        return await self._get_one(WebAccount, WebAccount.id == account_id)

    async def get_by_username(self, username: str) -> Optional[WebAccount]:
        return await self._get_one(WebAccount, WebAccount.username == username.lower())

    async def get_by_user_telegram_id(self, telegram_id: int) -> Optional[WebAccount]:
        return await self._get_one(WebAccount, WebAccount.user_telegram_id == telegram_id)

    async def get_by_partial_username(self, query: str) -> list[WebAccount]:
        search_pattern = f"%{query.lower()}%"
        return await self._get_many(
            WebAccount,
            func.lower(WebAccount.username).like(search_pattern),
        )

    async def get_by_email(self, email_normalized: str) -> Optional[WebAccount]:
        return await self._get_one(
            WebAccount, WebAccount.email_normalized == email_normalized.lower()
        )

    async def update(self, account_id: int, **data: Any) -> Optional[WebAccount]:
        return await self._update(WebAccount, WebAccount.id == account_id, **data)

    async def delete(self, account_id: int) -> bool:
        return bool(await self._delete(WebAccount, WebAccount.id == account_id))


class AuthChallengeRepository(BaseRepository):
    async def create(self, challenge: AuthChallenge) -> AuthChallenge:
        return await self.create_instance(challenge)

    async def get(self, challenge_id: UUID) -> Optional[AuthChallenge]:
        return await self._get_one(AuthChallenge, AuthChallenge.id == challenge_id)

    async def get_latest_active(
        self,
        *,
        web_account_id: int,
        purpose: str,
        destination: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[AuthChallenge]:
        current_time = now if now is not None else datetime_now()
        conditions = [
            AuthChallenge.web_account_id == web_account_id,
            AuthChallenge.purpose == purpose,
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > current_time,
        ]
        if destination is not None:
            conditions.append(AuthChallenge.destination == destination)

        query = (
            select(AuthChallenge)
            .where(and_(*conditions))
            .order_by(AuthChallenge.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_token_hash(
        self,
        *,
        purpose: str,
        token_hash: str,
        now: Optional[datetime] = None,
    ) -> Optional[AuthChallenge]:
        current_time = now if now is not None else datetime_now()
        return await self._get_one(
            AuthChallenge,
            AuthChallenge.purpose == purpose,
            AuthChallenge.token_hash == token_hash,
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > current_time,
        )

    async def update(self, challenge_id: UUID, **data: Any) -> Optional[AuthChallenge]:
        return await self._update(AuthChallenge, AuthChallenge.id == challenge_id, **data)

    async def invalidate_active(
        self,
        *,
        web_account_id: int,
        purpose: str,
        destination: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> int:
        current_time = now if now is not None else datetime_now()
        conditions = [
            AuthChallenge.web_account_id == web_account_id,
            AuthChallenge.purpose == purpose,
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > current_time,
        ]
        if destination is not None:
            conditions.append(AuthChallenge.destination == destination)

        query = update(AuthChallenge).where(and_(*conditions)).values(consumed_at=current_time)
        result = await self.session.execute(query)
        return self._rowcount(result)
