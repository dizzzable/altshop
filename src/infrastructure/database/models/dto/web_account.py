from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from .base import TrackableDto


class BaseWebAccountDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)
    user_telegram_id: int
    username: str
    password_hash: str = Field(default="", exclude=True)

    email: Optional[str] = None
    email_normalized: Optional[str] = None
    email_verified_at: Optional[datetime] = None
    credentials_bootstrapped_at: Optional[datetime] = None

    token_version: int = 0
    requires_password_change: bool = False
    temporary_password_expires_at: Optional[datetime] = None
    link_prompt_snooze_until: Optional[datetime] = None

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)


class WebAccountDto(BaseWebAccountDto):
    pass


class AuthChallengeDto(TrackableDto):
    id: UUID
    web_account_id: int
    purpose: str
    channel: str
    destination: str

    code_hash: Optional[str] = None
    token_hash: Optional[str] = None

    expires_at: datetime
    consumed_at: Optional[datetime] = None
    attempts_left: int = 0
    meta: Optional[dict] = None

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)
