from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.api.utils.web_app_urls import build_web_referral_link
from src.core.enums import Locale, PointsExchangeType, ReferralInviteSource, ReferralLevel
from src.infrastructure.database.models.dto import ReferralDto, ReferralInviteDto, UserDto
from src.services.referral import (
    INVITE_BLOCK_REASON_EXPIRED,
    ReferralInviteStateSnapshot,
)
from src.services.referral_portal import (
    REFERRAL_DISABLED_FOR_ACTIVE_PARTNER,
    REFERRAL_INVITE_UNAVAILABLE,
    ReferralAboutSnapshot,
    ReferralPortalAccessDeniedError,
    ReferralPortalService,
    ResolvedReferralLinks,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_user(*, telegram_id: int = 100, points: int = 0) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name=f"User {telegram_id}",
        username=f"user{telegram_id}",
        language=Locale.EN,
        referral_code=f"code-{telegram_id}",
        points=points,
    )


def build_invite_state(
    *,
    token: str | None = "TOKEN123",
    block_reason: str | None = None,
    requires_regeneration: bool = False,
    invite_expires_at: datetime | None = None,
    remaining_slots: int | None = 3,
    total_capacity: int | None = 5,
    refill_step_progress: int | None = 1,
    refill_step_target: int | None = 4,
) -> ReferralInviteStateSnapshot:
    invite = (
        ReferralInviteDto(
            id=7,
            inviter_telegram_id=100,
            token=token,
            expires_at=invite_expires_at,
        )
        if token is not None
        else None
    )
    return ReferralInviteStateSnapshot(
        invite=invite,
        invite_expires_at=invite_expires_at,
        total_capacity=total_capacity,
        remaining_slots=remaining_slots,
        qualified_referral_count=2,
        requires_regeneration=requires_regeneration,
        invite_block_reason=block_reason,
        refill_step_progress=refill_step_progress,
        refill_step_target=refill_step_target,
    )


def build_referral(*, referrer: UserDto, referred: UserDto) -> ReferralDto:
    return ReferralDto(
        id=11,
        level=ReferralLevel.FIRST,
        invite_source=ReferralInviteSource.WEB,
        referrer=referrer,
        referred=referred,
        created_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        qualified_at=datetime(2025, 1, 4, 5, 6, 7, tzinfo=timezone.utc),
    )


def build_service(
    *,
    referral_service: SimpleNamespace | None = None,
    referral_exchange_service: SimpleNamespace | None = None,
    partner_service: SimpleNamespace | None = None,
    user_service: SimpleNamespace | None = None,
) -> ReferralPortalService:
    config = SimpleNamespace(web_app=SimpleNamespace(url_str="https://app.example.test"))
    return ReferralPortalService(
        config=config,
        referral_service=referral_service or SimpleNamespace(),
        referral_exchange_service=referral_exchange_service or SimpleNamespace(),
        partner_service=partner_service or SimpleNamespace(),
        user_service=user_service or SimpleNamespace(),
    )


def test_ensure_api_available_denies_active_partner() -> None:
    user = build_user(telegram_id=201)
    service = build_service(
        partner_service=SimpleNamespace(
            get_partner_by_user=AsyncMock(return_value=SimpleNamespace(is_active=True))
        )
    )

    try:
        run_async(service.ensure_api_available(user))
    except ReferralPortalAccessDeniedError as error:
        assert error.code == REFERRAL_DISABLED_FOR_ACTIVE_PARTNER
        assert str(error) == "Referral program is disabled for active partners"
    else:
        raise AssertionError("Expected ReferralPortalAccessDeniedError")


def test_resolve_referral_links_returns_empty_when_invite_is_blocked() -> None:
    user = build_user(telegram_id=202)
    invite_state = build_invite_state(block_reason=INVITE_BLOCK_REASON_EXPIRED)
    referral_service = SimpleNamespace(
        get_invite_state=AsyncMock(return_value=invite_state),
        get_ref_link=AsyncMock(),
    )
    service = build_service(
        referral_service=referral_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    links = run_async(service.resolve_referral_links(user))

    assert links == ResolvedReferralLinks(
        referral_link="",
        telegram_referral_link="",
        web_referral_link="",
    )
    referral_service.get_ref_link.assert_not_awaited()


def test_get_info_preserves_counts_points_links_and_referral_code() -> None:
    user = build_user(telegram_id=203, points=77)
    invite_state = build_invite_state(token="ABC123")
    referral_service = SimpleNamespace(
        get_invite_state=AsyncMock(side_effect=[invite_state, invite_state]),
        get_ref_link=AsyncMock(return_value="https://t.me/bot?start=ref_ABC123"),
        get_referral_count=AsyncMock(return_value=5),
        get_qualified_referral_count=AsyncMock(return_value=3),
        get_reward_count=AsyncMock(return_value=2),
    )
    service = build_service(
        referral_service=referral_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
        user_service=SimpleNamespace(get=AsyncMock(return_value=user)),
    )

    snapshot = run_async(service.get_info(user))

    assert snapshot.referral_count == 5
    assert snapshot.qualified_referral_count == 3
    assert snapshot.reward_count == 2
    assert snapshot.points == 77
    assert snapshot.referral_code == "ref_ABC123"
    assert snapshot.telegram_referral_link == "https://t.me/bot?start=ref_ABC123"
    assert snapshot.web_referral_link == build_web_referral_link(
        service.config,
        "ABC123",
    )


def test_build_qr_image_uses_requested_target_link() -> None:
    user = build_user(telegram_id=204)
    referral_service = SimpleNamespace(
        get_invite_state=AsyncMock(return_value=build_invite_state(token="ABC123")),
        get_ref_link=AsyncMock(return_value="https://t.me/bot?start=ref_ABC123"),
        generate_ref_qr_bytes=MagicMock(return_value=b"qr"),
    )
    service = build_service(
        referral_service=referral_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    qr_bytes = run_async(service.build_qr_image(target="web", current_user=user))

    assert qr_bytes == b"qr"
    referral_service.generate_ref_qr_bytes.assert_called_once_with(
        build_web_referral_link(service.config, "ABC123")
    )


def test_build_qr_image_raises_when_invite_link_is_unavailable() -> None:
    user = build_user(telegram_id=205)
    referral_service = SimpleNamespace(
        get_invite_state=AsyncMock(
            return_value=build_invite_state(block_reason=INVITE_BLOCK_REASON_EXPIRED)
        ),
        get_ref_link=AsyncMock(),
        generate_ref_qr_bytes=AsyncMock(),
    )
    service = build_service(
        referral_service=referral_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    try:
        run_async(service.build_qr_image(target="telegram", current_user=user))
    except ReferralPortalAccessDeniedError as error:
        assert error.code == REFERRAL_INVITE_UNAVAILABLE
        assert str(error) == "Active referral invite link is unavailable"
    else:
        raise AssertionError("Expected ReferralPortalAccessDeniedError")


def test_list_referrals_preserves_event_serialization_and_rewards_map() -> None:
    current_user = build_user(telegram_id=206)
    referred_user = build_user(telegram_id=301)
    referral = build_referral(referrer=current_user, referred=referred_user)
    referral_service = SimpleNamespace(
        get_referrals_page_by_referrer=AsyncMock(return_value=([referral], 1)),
        get_issued_rewards_map_for_referrer=AsyncMock(return_value={11: 9}),
    )
    service = build_service(
        referral_service=referral_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    snapshot = run_async(service.list_referrals(current_user=current_user, page=1, limit=20))

    assert snapshot.total == 1
    assert snapshot.referrals[0].telegram_id == referred_user.telegram_id
    assert snapshot.referrals[0].rewards_issued == 9
    assert snapshot.referrals[0].rewards_earned == 9
    assert [event.type for event in snapshot.referrals[0].events] == ["INVITED", "QUALIFIED"]


def test_get_exchange_options_is_access_guarded_and_passthrough() -> None:
    current_user = build_user(telegram_id=207)
    expected = SimpleNamespace(kind="options")
    exchange_service = SimpleNamespace(get_options=AsyncMock(return_value=expected))
    service = build_service(
        referral_exchange_service=exchange_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    result = run_async(service.get_exchange_options(current_user))

    assert result is expected
    exchange_service.get_options.assert_awaited_once_with(user_telegram_id=current_user.telegram_id)


def test_execute_exchange_is_access_guarded_and_passthrough() -> None:
    current_user = build_user(telegram_id=208)
    expected = SimpleNamespace(kind="execution")
    exchange_service = SimpleNamespace(execute=AsyncMock(return_value=expected))
    service = build_service(
        referral_exchange_service=exchange_service,
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    result = run_async(
        service.execute_exchange(
            current_user=current_user,
            exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
            subscription_id=12,
            gift_plan_id=None,
        )
    )

    assert result is expected
    exchange_service.execute.assert_awaited_once_with(
        user_telegram_id=current_user.telegram_id,
        exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
        subscription_id=12,
        gift_plan_id=None,
    )


def test_get_about_preserves_static_payload_shape() -> None:
    snapshot = ReferralPortalService.get_about()

    assert isinstance(snapshot, ReferralAboutSnapshot)
    assert snapshot.title == "Referral Program"
    assert len(snapshot.how_it_works) == 3
    assert {"question", "answer"} <= set(snapshot.faq[0].keys())
