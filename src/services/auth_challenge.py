from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import AuthChallengeDto
from src.infrastructure.database.models.sql import AuthChallenge
from src.infrastructure.database.uow import UnitOfWork


class ChallengePurpose:
    TG_LINK = "TG_LINK"
    EMAIL_VERIFY = "EMAIL_VERIFY"
    PASSWORD_RESET = "PASSWORD_RESET"


class ChallengeChannel:
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"


class ChallengeErrorReason:
    INVALID_OR_EXPIRED = "INVALID_OR_EXPIRED"
    INVALID_CODE = "INVALID_CODE"
    TOO_MANY_ATTEMPTS = "TOO_MANY_ATTEMPTS"


@dataclass
class ChallengeCreateResult:
    challenge: AuthChallengeDto
    code: Optional[str]
    token: Optional[str]


@dataclass
class ChallengeVerifyResult:
    ok: bool
    reason: Optional[str] = None
    challenge: Optional[AuthChallengeDto] = None


class AuthChallengeService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    @staticmethod
    def _hash_secret(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_code(length: int = 6) -> str:
        alphabet = string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _generate_token() -> str:
        return secrets.token_urlsafe(32)

    async def create(
        self,
        *,
        web_account_id: int,
        purpose: str,
        channel: str,
        destination: str,
        ttl_seconds: int,
        attempts: int,
        include_code: bool = False,
        include_token: bool = False,
        meta: Optional[dict] = None,
    ) -> ChallengeCreateResult:
        now = datetime_now()
        code = self._generate_code() if include_code else None
        token = self._generate_token() if include_token else None

        async with self.uow:
            await self.uow.repository.auth_challenges.invalidate_active(
                web_account_id=web_account_id,
                purpose=purpose,
                destination=destination,
                now=now,
            )

            challenge = AuthChallenge(
                id=uuid4(),
                web_account_id=web_account_id,
                purpose=purpose,
                channel=channel,
                destination=destination,
                code_hash=self._hash_secret(code) if code else None,
                token_hash=self._hash_secret(token) if token else None,
                expires_at=now + timedelta(seconds=ttl_seconds),
                attempts_left=attempts,
                meta=meta,
            )
            created = await self.uow.repository.auth_challenges.create(challenge)
            await self.uow.commit()

        challenge_dto = AuthChallengeDto.from_model(created)
        if challenge_dto is None:
            raise ValueError("Failed to create auth challenge")

        return ChallengeCreateResult(challenge=challenge_dto, code=code, token=token)

    async def verify_code(
        self,
        *,
        web_account_id: int,
        purpose: str,
        destination: str,
        code: str,
    ) -> ChallengeVerifyResult:
        now = datetime_now()

        async with self.uow:
            challenge = await self.uow.repository.auth_challenges.get_latest_active(
                web_account_id=web_account_id,
                purpose=purpose,
                destination=destination,
                now=now,
            )
            if not challenge:
                return ChallengeVerifyResult(
                    ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED
                )

            if challenge.expires_at <= now:
                await self.uow.repository.auth_challenges.update(
                    challenge.id,
                    consumed_at=now,
                )
                await self.uow.commit()
                return ChallengeVerifyResult(
                    ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED
                )

            if not challenge.code_hash or self._hash_secret(code) != challenge.code_hash:
                attempts_left = max(challenge.attempts_left - 1, 0)
                consumed_at = now if attempts_left <= 0 else None
                await self.uow.repository.auth_challenges.update(
                    challenge.id,
                    attempts_left=attempts_left,
                    consumed_at=consumed_at,
                )
                await self.uow.commit()

                reason = (
                    ChallengeErrorReason.TOO_MANY_ATTEMPTS
                    if attempts_left <= 0
                    else ChallengeErrorReason.INVALID_CODE
                )
                return ChallengeVerifyResult(ok=False, reason=reason)

            updated = await self.uow.repository.auth_challenges.update(
                challenge.id,
                consumed_at=now,
            )
            await self.uow.commit()

        challenge_dto = AuthChallengeDto.from_model(updated)
        if challenge_dto is None:
            return ChallengeVerifyResult(ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED)

        return ChallengeVerifyResult(ok=True, challenge=challenge_dto)

    async def verify_token(
        self,
        *,
        purpose: str,
        token: str,
        web_account_id: Optional[int] = None,
        destination: Optional[str] = None,
    ) -> ChallengeVerifyResult:
        now = datetime_now()
        token_hash = self._hash_secret(token)

        async with self.uow:
            challenge = await self.uow.repository.auth_challenges.get_by_token_hash(
                purpose=purpose,
                token_hash=token_hash,
                now=now,
            )
            if not challenge:
                return ChallengeVerifyResult(
                    ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED
                )

            if web_account_id is not None and challenge.web_account_id != web_account_id:
                return ChallengeVerifyResult(
                    ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED
                )

            if destination is not None and challenge.destination != destination:
                return ChallengeVerifyResult(
                    ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED
                )

            updated = await self.uow.repository.auth_challenges.update(
                challenge.id,
                consumed_at=now,
            )
            await self.uow.commit()

        challenge_dto = AuthChallengeDto.from_model(updated)
        if challenge_dto is None:
            return ChallengeVerifyResult(ok=False, reason=ChallengeErrorReason.INVALID_OR_EXPIRED)

        return ChallengeVerifyResult(ok=True, challenge=challenge_dto)
