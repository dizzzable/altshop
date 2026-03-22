"""Access-mode parity guards for web API/auth endpoints."""

from __future__ import annotations

import re

from fastapi import HTTPException, status

from src.core.constants import REFERRAL_PREFIX
from src.core.enums import AccessMode
from src.infrastructure.database.models.dto import UserDto
from src.services.referral import ReferralService

ACCESS_DENIED_SERVICE_RESTRICTED = "Access denied: service is currently restricted"
ACCESS_DENIED_REGISTRATION_DISABLED = "Access denied: registration is currently disabled"
ACCESS_DENIED_INVITE_ONLY = "Access denied: invite-only registration"
ACCESS_DENIED_VALID_INVITE_REQUIRED = "Access denied: valid invite code is required"
ACCESS_DENIED_PURCHASES_DISABLED = "Access denied: purchases are currently disabled"

_REFERRAL_CODE_RE = re.compile(rf"^(?:{re.escape(REFERRAL_PREFIX)})?[A-Za-z0-9]{{4,64}}$")


def normalize_web_referral_code(
    raw_code: str | None,
    *,
    require_prefix: bool = False,
) -> str | None:
    if not raw_code:
        return None

    code = raw_code.strip()
    if not code or not _REFERRAL_CODE_RE.fullmatch(code):
        return None
    if require_prefix and not code.startswith(REFERRAL_PREFIX):
        return None

    if code.startswith(REFERRAL_PREFIX):
        return code

    return f"{REFERRAL_PREFIX}{code}"


async def validate_web_invite_code(
    *,
    raw_code: str | None,
    referral_service: ReferralService,
    new_user_telegram_id: int,
) -> bool | None:
    normalized_code = normalize_web_referral_code(raw_code)
    if not normalized_code:
        return None

    return await referral_service.is_valid_invite_or_partner_code(
        normalized_code,
        user_telegram_id=new_user_telegram_id,
    )


def assert_web_general_access(user: UserDto, mode: AccessMode) -> None:
    if user.is_privileged:
        return

    if mode == AccessMode.RESTRICTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED_SERVICE_RESTRICTED,
        )


def assert_web_purchase_access(user: UserDto, mode: AccessMode) -> None:
    if user.is_privileged:
        return

    if mode == AccessMode.RESTRICTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED_SERVICE_RESTRICTED,
        )

    if mode == AccessMode.PURCHASE_BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED_PURCHASES_DISABLED,
        )


def assert_web_registration_access(
    *,
    mode: AccessMode,
    existing_user: UserDto | None,
    is_valid_invite: bool | None,
) -> None:
    if existing_user:
        return

    if mode == AccessMode.REG_BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED_REGISTRATION_DISABLED,
        )

    if mode == AccessMode.RESTRICTED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED_SERVICE_RESTRICTED,
        )

    if mode != AccessMode.INVITED:
        return

    if is_valid_invite is True:
        return

    detail = (
        ACCESS_DENIED_INVITE_ONLY
        if is_valid_invite is None
        else ACCESS_DENIED_VALID_INVITE_REQUIRED
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )
