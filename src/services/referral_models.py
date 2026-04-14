from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.infrastructure.database.models.dto import ReferralInviteDto

INVITE_BLOCK_REASON_EXPIRED = "EXPIRED"
INVITE_BLOCK_REASON_EXHAUSTED = "SLOTS_EXHAUSTED"


@dataclass(slots=True, frozen=True)
class ReferralInviteCapacitySnapshot:
    total_capacity: int | None
    remaining_slots: int | None
    qualified_referral_count: int
    used_slots: int
    refill_step_progress: int | None
    refill_step_target: int | None


@dataclass(slots=True, frozen=True)
class ReferralInviteStateSnapshot:
    invite: ReferralInviteDto | None
    invite_expires_at: datetime | None
    total_capacity: int | None
    remaining_slots: int | None
    qualified_referral_count: int
    requires_regeneration: bool
    invite_block_reason: str | None
    refill_step_progress: int | None
    refill_step_target: int | None


@dataclass(slots=True, frozen=True)
class ReferralManualAttachResult:
    historical_payments_processed: int
    partner_chain_attached: bool
