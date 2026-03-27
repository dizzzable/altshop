from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.enums import Locale, PartnerLevel, UserRole
from src.infrastructure.database.models.dto import PartnerDto, PartnerReferralDto, UserDto
from src.services.partner import PartnerAttributionAssignmentError, PartnerService


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


def make_partner(
    partner_id: int,
    *,
    user_telegram_id: int,
    is_active: bool = True,
) -> PartnerDto:
    return PartnerDto(
        id=partner_id,
        user_telegram_id=user_telegram_id,
        is_active=is_active,
    )


def build_service(partners_repo: SimpleNamespace) -> PartnerService:
    return PartnerService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        uow=DummyUow(repository=SimpleNamespace(partners=partners_repo)),
        user_service=SimpleNamespace(get=AsyncMock()),
        settings_service=SimpleNamespace(),
        notification_service=MagicMock(),
    )


def test_assign_partner_attribution_rejects_non_partner_source() -> None:
    service = build_service(
        SimpleNamespace(
            get_partner_by_user=AsyncMock(return_value=None),
            get_partner_referrals_by_user=AsyncMock(),
            count_transactions_by_referral=AsyncMock(),
            delete_partner_referrals_by_user=AsyncMock(),
        )
    )

    with pytest.raises(
        PartnerAttributionAssignmentError, match="SOURCE_NOT_ACTIVE_PARTNER"
    ) as exc_info:
        run_async(
            service.assign_partner_attribution(
                user=make_user(500),
                source_user=make_user(200),
            )
        )

    assert exc_info.value.code == "SOURCE_NOT_ACTIVE_PARTNER"


def test_assign_partner_attribution_rebuilds_chain_and_recalculates_counters() -> None:
    partners_repo = SimpleNamespace(
        get_partner_referrals_by_user=AsyncMock(
            return_value=[
                SimpleNamespace(
                    partner_id=99,
                    referral_telegram_id=500,
                    level=PartnerLevel.LEVEL_1,
                    parent_partner_id=None,
                )
            ]
        ),
        count_transactions_by_referral=AsyncMock(return_value=0),
        delete_partner_referrals_by_user=AsyncMock(return_value=1),
    )
    service = build_service(partners_repo)
    level1_partner = make_partner(1, user_telegram_id=200)
    level2_partner = make_partner(2, user_telegram_id=150)
    created_level1 = PartnerReferralDto(
        partner_id=1,
        referral_telegram_id=500,
        level=PartnerLevel.LEVEL_1,
    )
    created_level2 = PartnerReferralDto(
        partner_id=2,
        referral_telegram_id=500,
        level=PartnerLevel.LEVEL_2,
        parent_partner_id=1,
    )
    service._build_active_partner_chain = AsyncMock(return_value=[level1_partner, level2_partner])
    service.add_partner_referral = AsyncMock(side_effect=[created_level1, created_level2])
    service._recalculate_partner_counters = AsyncMock()

    result = run_async(
        service.assign_partner_attribution(
            user=make_user(500),
            source_user=make_user(200),
        )
    )

    assert [item.partner_id for item in result] == [1, 2]
    partners_repo.delete_partner_referrals_by_user.assert_awaited_once_with(500)
    assert service.add_partner_referral.await_args_list[0].kwargs == {
        "partner": level1_partner,
        "referral_telegram_id": 500,
        "level": PartnerLevel.LEVEL_1,
        "parent_partner_id": None,
    }
    assert service.add_partner_referral.await_args_list[1].kwargs == {
        "partner": level2_partner,
        "referral_telegram_id": 500,
        "level": PartnerLevel.LEVEL_2,
        "parent_partner_id": 1,
    }
    assert {call.args[0] for call in service._recalculate_partner_counters.await_args_list} == {
        1,
        2,
        99,
    }


def test_assign_partner_attribution_rejects_reassignment_after_history() -> None:
    partners_repo = SimpleNamespace(
        get_partner_referrals_by_user=AsyncMock(return_value=[]),
        count_transactions_by_referral=AsyncMock(return_value=1),
        delete_partner_referrals_by_user=AsyncMock(),
    )
    service = build_service(partners_repo)
    service._build_active_partner_chain = AsyncMock(
        return_value=[make_partner(1, user_telegram_id=200)]
    )
    service.add_partner_referral = AsyncMock()
    service._recalculate_partner_counters = AsyncMock()

    with pytest.raises(PartnerAttributionAssignmentError, match="HAS_HISTORY") as exc_info:
        run_async(
            service.assign_partner_attribution(
                user=make_user(500),
                source_user=make_user(200),
            )
        )

    assert exc_info.value.code == "HAS_HISTORY"
    partners_repo.delete_partner_referrals_by_user.assert_not_called()
    service.add_partner_referral.assert_not_called()


def test_assign_partner_attribution_rejects_cyclic_source_chain() -> None:
    partner_a = make_partner(1, user_telegram_id=200)
    partner_b = make_partner(2, user_telegram_id=150)

    def get_partner_by_id(partner_id: int) -> PartnerDto | None:
        if partner_id == 1:
            return partner_a
        if partner_id == 2:
            return partner_b
        return None

    partners_repo = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=partner_a),
        get_partner_by_id=AsyncMock(side_effect=get_partner_by_id),
        get_partner_referral_by_user=AsyncMock(
            side_effect=lambda telegram_id: (
                SimpleNamespace(partner_id=2)
                if telegram_id == 200
                else SimpleNamespace(partner_id=1)
            )
        ),
        get_partner_referrals_by_user=AsyncMock(return_value=[]),
        count_transactions_by_referral=AsyncMock(return_value=0),
        delete_partner_referrals_by_user=AsyncMock(),
    )
    service = build_service(partners_repo)

    with pytest.raises(PartnerAttributionAssignmentError, match="ATTRIBUTION_CYCLE") as exc_info:
        run_async(
            service.assign_partner_attribution(
                user=make_user(500),
                source_user=make_user(200),
            )
        )

    assert exc_info.value.code == "ATTRIBUTION_CYCLE"
    partners_repo.delete_partner_referrals_by_user.assert_not_called()
