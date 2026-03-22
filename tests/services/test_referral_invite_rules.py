from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    ReferralInviteDto,
    ReferralInviteIndividualSettingsDto,
    ReferralInviteLimitsDto,
    ReferralSettingsDto,
    UserDto,
)
from src.services.referral import (
    INVITE_BLOCK_REASON_EXHAUSTED,
    INVITE_BLOCK_REASON_EXPIRED,
    ReferralService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(
    *,
    telegram_id: int = 100,
    settings: ReferralInviteIndividualSettingsDto | None = None,
) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=f"User {telegram_id}",
        referral_invite_settings=settings or ReferralInviteIndividualSettingsDto(),
    )


def build_service(
    *,
    referral_count: int = 0,
    qualified_referral_count: int = 0,
    latest_invite: ReferralInviteDto | None = None,
    invite_by_token: ReferralInviteDto | None = None,
    referral_settings: ReferralSettingsDto | None = None,
    inviter: UserDto | None = None,
) -> ReferralService:
    referrals_repo = SimpleNamespace(
        count_referrals_by_referrer=AsyncMock(return_value=referral_count),
        count_qualified_referrals_by_referrer=AsyncMock(
            return_value=qualified_referral_count
        ),
    )
    referral_invites_repo = SimpleNamespace(
        get_latest_by_inviter=AsyncMock(return_value=latest_invite),
        get_by_token=AsyncMock(
            side_effect=lambda token: invite_by_token if token == "TOKEN123" else None
        ),
        revoke_unrevoked_by_inviter=AsyncMock(return_value=1),
        create_invite=AsyncMock(side_effect=lambda invite: invite),
    )
    partners_repo = SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None))
    uow = SimpleNamespace(
        repository=SimpleNamespace(
            referrals=referrals_repo,
            referral_invites=referral_invites_repo,
            partners=partners_repo,
        )
    )
    return ReferralService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=uow,
        user_service=SimpleNamespace(
            get=AsyncMock(return_value=inviter),
            clear_user_cache=AsyncMock(),
        ),
        settings_service=SimpleNamespace(
            get_referral_settings=AsyncMock(
                return_value=referral_settings or ReferralSettingsDto()
            ),
            is_referral_enable=AsyncMock(return_value=True),
        ),
        notification_service=MagicMock(),
    )


def test_invite_capacity_refills_multiple_times() -> None:
    inviter = build_user()
    service = build_service(
        referral_count=6,
        qualified_referral_count=8,
        referral_settings=ReferralSettingsDto(
            invite_limits=ReferralInviteLimitsDto(
                slots_enabled=True,
                initial_slots=5,
                refill_threshold_qualified=4,
                refill_amount=5,
            )
        ),
    )

    snapshot = run_async(service.get_invite_capacity_snapshot(inviter))

    assert snapshot.total_capacity == 15
    assert snapshot.remaining_slots == 9
    assert snapshot.qualified_referral_count == 8
    assert snapshot.used_slots == 6
    assert snapshot.refill_step_progress == 0
    assert snapshot.refill_step_target == 4


def test_effective_invite_limits_respect_user_override() -> None:
    inviter = build_user(
        settings=ReferralInviteIndividualSettingsDto(
            use_global_settings=False,
            link_ttl_enabled=True,
            link_ttl_seconds=3600,
            slots_enabled=True,
            initial_slots=3,
            refill_threshold_qualified=2,
            refill_amount=4,
        )
    )
    service = build_service(
        referral_settings=ReferralSettingsDto(
            invite_limits=ReferralInviteLimitsDto(
                link_ttl_enabled=True,
                link_ttl_seconds=900,
                slots_enabled=True,
                initial_slots=1,
                refill_threshold_qualified=10,
                refill_amount=1,
            )
        )
    )

    effective = run_async(service.get_effective_invite_limits(inviter))

    assert effective.link_ttl_enabled is True
    assert effective.link_ttl_seconds == 3600
    assert effective.initial_slots == 3
    assert effective.refill_threshold_qualified == 2
    assert effective.refill_amount == 4


def test_expired_invite_requires_regeneration() -> None:
    inviter = build_user()
    expired_invite = ReferralInviteDto(
        id=7,
        inviter_telegram_id=inviter.telegram_id,
        token="TOKEN123",
        expires_at=datetime_now() - timedelta(minutes=1),
    )
    service = build_service(latest_invite=expired_invite)

    state = run_async(service.get_invite_state(inviter, create_if_missing=False))

    assert state.invite is not None
    assert state.invite_block_reason == INVITE_BLOCK_REASON_EXPIRED
    assert state.requires_regeneration is True


def test_resolve_invite_token_blocks_when_slots_are_exhausted() -> None:
    inviter = build_user(telegram_id=200)
    active_invite = ReferralInviteDto(
        id=8,
        inviter_telegram_id=inviter.telegram_id,
        token="TOKEN123",
        expires_at=datetime_now() + timedelta(hours=1),
    )
    service = build_service(
        referral_count=1,
        qualified_referral_count=0,
        invite_by_token=active_invite,
        referral_settings=ReferralSettingsDto(
            invite_limits=ReferralInviteLimitsDto(
                slots_enabled=True,
                initial_slots=1,
            )
        ),
        inviter=inviter,
    )

    invite, resolved_inviter, block_reason = run_async(
        service.resolve_invite_token("ref_TOKEN123", user_telegram_id=999)
    )

    assert invite is not None
    assert resolved_inviter is None
    assert block_reason == INVITE_BLOCK_REASON_EXHAUSTED
