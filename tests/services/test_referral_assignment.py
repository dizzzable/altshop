from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.enums import Locale, ReferralInviteSource, ReferralLevel, UserRole
from src.infrastructure.database.models.dto import UserDto
from src.services.referral import ReferralAssignmentError, ReferralService


def run_async(coroutine):
    return asyncio.run(coroutine)


class DummyUow:
    def __init__(self, repository: SimpleNamespace) -> None:
        self.repository = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def make_user(telegram_id: int, *, name: str | None = None) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=f"user_{telegram_id}",
        referral_code=f"ref_{telegram_id}",
        name=name or f"User {telegram_id}",
        role=UserRole.USER,
        language=Locale.EN,
    )


def make_referral_model(
    *,
    referral_id: int,
    referrer: UserDto,
    referred: UserDto,
    level: ReferralLevel,
    invite_source: ReferralInviteSource = ReferralInviteSource.UNKNOWN,
    qualified_at: datetime | None = None,
):
    return SimpleNamespace(
        id=referral_id,
        referrer_telegram_id=referrer.telegram_id,
        referred_telegram_id=referred.telegram_id,
        level=level,
        invite_source=invite_source,
        qualified_at=qualified_at,
        qualified_purchase_channel=None,
        qualified_transaction_id=None,
        referrer=referrer,
        referred=referred,
        created_at=None,
        updated_at=None,
    )


def build_service(referrals_repo: SimpleNamespace) -> tuple[ReferralService, AsyncMock]:
    clear_user_cache = AsyncMock()
    service = ReferralService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=DummyUow(repository=SimpleNamespace(referrals=referrals_repo)),
        user_service=SimpleNamespace(clear_user_cache=clear_user_cache),
        settings_service=SimpleNamespace(),
        notification_service=MagicMock(),
    )
    return service, clear_user_cache


def test_assign_referrer_updates_existing_referral_and_clears_caches() -> None:
    referred = make_user(300)
    old_referrer = make_user(100)
    new_referrer = make_user(200)
    existing_referral = make_referral_model(
        referral_id=7,
        referrer=old_referrer,
        referred=referred,
        level=ReferralLevel.FIRST,
    )
    updated_referral = make_referral_model(
        referral_id=7,
        referrer=new_referrer,
        referred=referred,
        level=ReferralLevel.FIRST,
    )
    referral_by_referred = {
        referred.telegram_id: existing_referral,
        new_referrer.telegram_id: None,
    }
    referrals_repo = SimpleNamespace(
        get_referral_by_referred=AsyncMock(
            side_effect=lambda telegram_id: referral_by_referred.get(telegram_id)
        ),
        get_rewards_by_referral=AsyncMock(return_value=[]),
        update_referral=AsyncMock(return_value=updated_referral),
        create_referral=AsyncMock(),
    )
    service, clear_user_cache = build_service(referrals_repo)

    result = run_async(service.assign_referrer(referred=referred, referrer=new_referrer))

    assert result.referrer.telegram_id == new_referrer.telegram_id
    assert result.referred.telegram_id == referred.telegram_id
    referrals_repo.update_referral.assert_awaited_once_with(
        7,
        referrer_telegram_id=new_referrer.telegram_id,
        level=ReferralLevel.FIRST,
        invite_source=ReferralInviteSource.UNKNOWN,
    )
    assert {
        call.args[0] for call in clear_user_cache.await_args_list
    } == {referred.telegram_id, old_referrer.telegram_id, new_referrer.telegram_id}


def test_assign_referrer_rejects_reassignment_after_reward_history() -> None:
    referred = make_user(300)
    current_referrer = make_user(100)
    candidate_referrer = make_user(200)
    existing_referral = make_referral_model(
        referral_id=7,
        referrer=current_referrer,
        referred=referred,
        level=ReferralLevel.FIRST,
    )
    referral_by_referred = {
        referred.telegram_id: existing_referral,
        candidate_referrer.telegram_id: None,
    }
    referrals_repo = SimpleNamespace(
        get_referral_by_referred=AsyncMock(
            side_effect=lambda telegram_id: referral_by_referred.get(telegram_id)
        ),
        get_rewards_by_referral=AsyncMock(return_value=[SimpleNamespace(id=1)]),
        update_referral=AsyncMock(),
        create_referral=AsyncMock(),
    )
    service, _ = build_service(referrals_repo)

    with pytest.raises(ReferralAssignmentError, match="HAS_HISTORY") as exc_info:
        run_async(service.assign_referrer(referred=referred, referrer=candidate_referrer))

    assert exc_info.value.code == "HAS_HISTORY"
    referrals_repo.update_referral.assert_not_called()
    referrals_repo.create_referral.assert_not_called()


def test_assign_referrer_rejects_cycle() -> None:
    referred = make_user(300)
    candidate_referrer = make_user(200)
    cycle_referral = make_referral_model(
        referral_id=9,
        referrer=referred,
        referred=candidate_referrer,
        level=ReferralLevel.FIRST,
    )
    referrals_repo = SimpleNamespace(
        get_referral_by_referred=AsyncMock(
            side_effect=lambda telegram_id: (
                cycle_referral if telegram_id == candidate_referrer.telegram_id else None
            )
        ),
        get_rewards_by_referral=AsyncMock(),
        update_referral=AsyncMock(),
        create_referral=AsyncMock(),
    )
    service, _ = build_service(referrals_repo)

    with pytest.raises(ReferralAssignmentError, match="REFERRAL_CYCLE") as exc_info:
        run_async(service.assign_referrer(referred=referred, referrer=candidate_referrer))

    assert exc_info.value.code == "REFERRAL_CYCLE"
    referrals_repo.update_referral.assert_not_called()
    referrals_repo.create_referral.assert_not_called()
