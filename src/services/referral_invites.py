from __future__ import annotations

import secrets
import string
from datetime import timedelta
from typing import TYPE_CHECKING

from src.core.constants import REFERRAL_PREFIX
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    ReferralInviteDto,
    ReferralInviteLimitsDto,
    UserDto,
)
from src.infrastructure.database.models.sql import ReferralInvite
from src.services.referral_models import (
    INVITE_BLOCK_REASON_EXHAUSTED,
    INVITE_BLOCK_REASON_EXPIRED,
    ReferralInviteCapacitySnapshot,
    ReferralInviteStateSnapshot,
)

if TYPE_CHECKING:
    from .referral import ReferralService


async def get_effective_invite_limits(
    service: ReferralService,
    inviter: UserDto,
) -> ReferralInviteLimitsDto:
    settings = await service.settings_service.get_referral_settings()
    global_limits = settings.invite_limits
    individual = inviter.referral_invite_settings

    if individual.use_global_settings:
        return ReferralInviteLimitsDto.model_validate(global_limits.model_dump())

    return ReferralInviteLimitsDto.model_validate(
        individual.model_dump(exclude={"use_global_settings"})
    )


async def get_invite_capacity_snapshot(
    service: ReferralService,
    inviter: UserDto,
    *,
    limits: ReferralInviteLimitsDto | None = None,
) -> ReferralInviteCapacitySnapshot:
    effective_limits = limits or await service.get_effective_invite_limits(inviter)
    qualified_referral_count, used_slots = await service._get_capacity_counters(
        inviter.telegram_id
    )

    if not effective_limits.slots_enabled:
        return ReferralInviteCapacitySnapshot(
            total_capacity=None,
            remaining_slots=None,
            qualified_referral_count=qualified_referral_count,
            used_slots=used_slots,
            refill_step_progress=None,
            refill_step_target=None,
        )

    initial_slots = effective_limits.effective_initial_slots or 0
    refill_threshold = effective_limits.effective_refill_threshold
    refill_amount = effective_limits.effective_refill_amount

    bonus_capacity = 0
    refill_step_progress: int | None = None
    refill_step_target: int | None = None

    if refill_threshold and refill_amount > 0:
        bonus_capacity = (qualified_referral_count // refill_threshold) * refill_amount
        refill_step_progress = qualified_referral_count % refill_threshold
        refill_step_target = refill_threshold

    total_capacity = max(initial_slots + bonus_capacity, 0)
    remaining_slots = max(total_capacity - used_slots, 0)

    return ReferralInviteCapacitySnapshot(
        total_capacity=total_capacity,
        remaining_slots=remaining_slots,
        qualified_referral_count=qualified_referral_count,
        used_slots=used_slots,
        refill_step_progress=refill_step_progress,
        refill_step_target=refill_step_target,
    )


async def get_latest_invite(
    service: ReferralService,
    inviter_telegram_id: int,
) -> ReferralInviteDto | None:
    invite = await service.uow.repository.referral_invites.get_latest_by_inviter(
        inviter_telegram_id
    )
    return ReferralInviteDto.from_model(invite)


async def get_invite_state(
    service: ReferralService,
    inviter: UserDto,
    *,
    create_if_missing: bool = False,
    regenerate: bool = False,
) -> ReferralInviteStateSnapshot:
    limits = await service.get_effective_invite_limits(inviter)
    capacity = await service.get_invite_capacity_snapshot(inviter, limits=limits)
    invite = await service.get_latest_invite(inviter.telegram_id)

    if regenerate:
        if capacity.remaining_slots is not None and capacity.remaining_slots <= 0:
            return service._build_invite_state_snapshot(invite=invite, capacity=capacity)
        invite = await service._create_new_referral_invite(inviter, limits=limits)
    elif create_if_missing and invite is None:
        if capacity.remaining_slots is None or capacity.remaining_slots > 0:
            invite = await service._create_new_referral_invite(inviter, limits=limits)

    return service._build_invite_state_snapshot(invite=invite, capacity=capacity)


async def regenerate_invite(
    service: ReferralService,
    inviter: UserDto,
) -> ReferralInviteStateSnapshot:
    return await service.get_invite_state(
        inviter,
        create_if_missing=True,
        regenerate=True,
    )


async def resolve_invite_token(
    service: ReferralService,
    code: str,
    *,
    user_telegram_id: int,
) -> tuple[ReferralInviteDto | None, UserDto | None, str | None]:
    token = service._normalize_referral_payload(code)
    if not token:
        return None, None, None

    invite = await service.uow.repository.referral_invites.get_by_token(token)
    invite_dto = ReferralInviteDto.from_model(invite)
    if not invite_dto:
        return None, None, None

    inviter = await service.user_service.get(invite_dto.inviter_telegram_id)
    if not inviter or inviter.telegram_id == user_telegram_id:
        return invite_dto, None, INVITE_BLOCK_REASON_EXPIRED

    capacity = await service.get_invite_capacity_snapshot(inviter)
    block_reason = service._resolve_invite_block_reason(invite_dto, capacity)
    if block_reason:
        return invite_dto, None, block_reason

    return invite_dto, inviter, None


async def get_partner_referrer_by_code(
    service: ReferralService,
    code: str,
    *,
    user_telegram_id: int,
) -> UserDto | None:
    normalized = service._normalize_referral_payload(code)
    if not normalized:
        return None

    referrer = await service.user_service.get_by_referral_code(normalized)
    if not referrer or referrer.telegram_id == user_telegram_id:
        return None

    partner = await service.uow.repository.partners.get_partner_by_user(referrer.telegram_id)
    if not partner or not partner.is_active:
        return None

    return referrer


async def is_valid_invite_or_partner_code(
    service: ReferralService,
    code: str,
    *,
    user_telegram_id: int,
) -> bool:
    _, inviter, block_reason = await service.resolve_invite_token(
        code,
        user_telegram_id=user_telegram_id,
    )
    if inviter and block_reason is None:
        return True

    partner_referrer = await service.get_partner_referrer_by_code(
        code,
        user_telegram_id=user_telegram_id,
    )
    return partner_referrer is not None


async def _get_capacity_counters(
    service: ReferralService,
    inviter_telegram_id: int,
) -> tuple[int, int]:
    qualified_referral_count = await service.get_qualified_referral_count(inviter_telegram_id)
    used_slots = await service.get_referral_count(inviter_telegram_id)
    return qualified_referral_count, used_slots


async def _create_new_referral_invite(
    service: ReferralService,
    inviter: UserDto,
    *,
    limits: ReferralInviteLimitsDto,
) -> ReferralInviteDto:
    revoked_at = datetime_now()
    await service.uow.repository.referral_invites.revoke_unrevoked_by_inviter(
        inviter.telegram_id,
        revoked_at=revoked_at,
    )

    expires_at = None
    ttl_seconds = limits.effective_link_ttl_seconds
    if ttl_seconds is not None:
        expires_at = revoked_at + timedelta(seconds=ttl_seconds)

    invite = await service.uow.repository.referral_invites.create_invite(
        ReferralInvite(
            inviter_telegram_id=inviter.telegram_id,
            token=await service._generate_unique_invite_token(),
            expires_at=expires_at,
            revoked_at=None,
        )
    )
    return ReferralInviteDto.from_model(invite)  # type: ignore[return-value]


async def _generate_unique_invite_token(
    service: ReferralService,
    *,
    length: int = 16,
) -> str:
    alphabet = string.ascii_uppercase + string.digits

    for _ in range(10):
        token = "".join(secrets.choice(alphabet) for _ in range(length))
        existing = await service.uow.repository.referral_invites.get_by_token(token)
        if not existing:
            return token

    raise ValueError("Failed to generate unique referral invite token")


def _build_invite_state_snapshot(
    service: ReferralService,
    *,
    invite: ReferralInviteDto | None,
    capacity: ReferralInviteCapacitySnapshot,
) -> ReferralInviteStateSnapshot:
    block_reason = service._resolve_invite_block_reason(invite, capacity)
    requires_regeneration = (
        block_reason == INVITE_BLOCK_REASON_EXPIRED
        or (invite is None and block_reason != INVITE_BLOCK_REASON_EXHAUSTED)
    )

    return ReferralInviteStateSnapshot(
        invite=invite,
        invite_expires_at=invite.expires_at if invite else None,
        total_capacity=capacity.total_capacity,
        remaining_slots=capacity.remaining_slots,
        qualified_referral_count=capacity.qualified_referral_count,
        requires_regeneration=requires_regeneration,
        invite_block_reason=block_reason,
        refill_step_progress=capacity.refill_step_progress,
        refill_step_target=capacity.refill_step_target,
    )


def _resolve_invite_block_reason(
    service: ReferralService,
    invite: ReferralInviteDto | None,
    capacity: ReferralInviteCapacitySnapshot,
) -> str | None:
    del service
    if capacity.remaining_slots is not None and capacity.remaining_slots <= 0:
        if invite is None:
            return INVITE_BLOCK_REASON_EXHAUSTED

    if invite is None:
        return None

    if invite.is_revoked or _is_invite_expired(None, invite):
        return INVITE_BLOCK_REASON_EXPIRED

    if capacity.remaining_slots is not None and capacity.remaining_slots <= 0:
        return INVITE_BLOCK_REASON_EXHAUSTED

    return None


def _normalize_referral_payload(
    service: ReferralService | None,
    code: str,
) -> str:
    del service
    normalized = code.strip()
    if normalized.startswith(REFERRAL_PREFIX):
        normalized = normalized[len(REFERRAL_PREFIX) :]
    return normalized.strip()


def _is_invite_expired(
    _service: ReferralService | None,
    invite: ReferralInviteDto,
) -> bool:
    if invite.expires_at is None:
        return False
    return invite.expires_at <= datetime_now()
