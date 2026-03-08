from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from src.api.endpoints.user_portal import (
    get_partner_info,
    get_referral_info,
    get_referral_qr,
)
from src.api.utils.web_app_urls import build_web_referral_link
from src.core.enums import PartnerAccrualStrategy, PartnerRewardType
from src.services.partner_portal import PartnerPortalService
from src.services.referral_portal import ReferralPortalService


def _unwrap_callable(func):
    closure = getattr(func, "__closure__", None) or ()
    for cell in closure:
        cell_value = getattr(cell, "cell_contents", None)
        if callable(cell_value) and getattr(cell_value, "__name__", "") == func.__name__:
            return _unwrap_callable(cell_value)

    target = func
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__  # type: ignore[attr-defined]
    return target


_GET_REFERRAL_INFO_IMPL = _unwrap_callable(get_referral_info)
_GET_REFERRAL_QR_IMPL = _unwrap_callable(get_referral_qr)
_GET_PARTNER_INFO_IMPL = _unwrap_callable(get_partner_info)


class _Secret:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        web_app=SimpleNamespace(url_str="https://example.com/webapp"),
        domain=_Secret("example.com"),
        bot=SimpleNamespace(support_username=_Secret("support_helper")),
    )


def _build_current_user() -> SimpleNamespace:
    return SimpleNamespace(telegram_id=813364774, referral_code="Es4tEy")


def _build_referral_service(get_ref_link_side_effect: object) -> SimpleNamespace:
    return SimpleNamespace(
        get_ref_link=AsyncMock(side_effect=get_ref_link_side_effect),
        get_referral_count=AsyncMock(return_value=12),
        get_qualified_referral_count=AsyncMock(return_value=5),
        get_reward_count=AsyncMock(return_value=4),
        generate_ref_qr_bytes=Mock(return_value=b"qr-image-bytes"),
    )


def _build_user_service(current_user: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(ensure_referral_code=AsyncMock(return_value=current_user))


def _build_referral_partner_service() -> SimpleNamespace:
    return SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None))


def _build_partner_info_service() -> SimpleNamespace:
    settings = SimpleNamespace(
        partner=SimpleNamespace(
            min_withdrawal_amount=100,
            get_level_percent=lambda _level: Decimal("10"),
        )
    )
    individual_settings = SimpleNamespace(
        use_global_settings=True,
        reward_type=PartnerRewardType.PERCENT,
        accrual_strategy=PartnerAccrualStrategy.ON_EACH_PAYMENT,
        get_level_percent=lambda _level: None,
        get_level_fixed_amount=lambda _level: None,
    )
    partner = SimpleNamespace(
        id=1,
        is_active=True,
        balance=700,
        total_earned=2500,
        total_withdrawn=400,
        referrals_count=7,
        level2_referrals_count=3,
        level3_referrals_count=1,
        individual_settings=individual_settings,
    )
    return SimpleNamespace(
        settings_service=SimpleNamespace(get=AsyncMock(return_value=settings)),
        get_partner_by_user=AsyncMock(return_value=partner),
        get_partner_statistics=AsyncMock(
            return_value={
                "level1_earnings": 100,
                "level2_earnings": 50,
                "level3_earnings": 25,
            }
        ),
    )


def _build_referral_portal_service(
    *,
    config: SimpleNamespace,
    referral_service: SimpleNamespace,
    partner_service: SimpleNamespace,
    user_service: SimpleNamespace,
) -> ReferralPortalService:
    return ReferralPortalService(
        config=config,
        referral_service=referral_service,
        referral_exchange_service=SimpleNamespace(),
        partner_service=partner_service,
        user_service=user_service,
    )


def _build_partner_portal_service(
    *,
    config: SimpleNamespace,
    partner_service: SimpleNamespace,
    referral_portal_service: ReferralPortalService,
) -> PartnerPortalService:
    return PartnerPortalService(
        config=config,
        partner_service=partner_service,
        referral_portal_service=referral_portal_service,
        notification_service=SimpleNamespace(notify_super_dev=AsyncMock()),
        web_account_service=SimpleNamespace(get_by_user_telegram_id=AsyncMock(return_value=None)),
    )


def test_get_referral_info_retries_and_returns_telegram_link() -> None:
    current_user = _build_current_user()
    config = _build_config()
    expected_telegram_link = "https://t.me/remna_shop?start=ref_Es4tEy"
    referral_service = _build_referral_service(
        [RuntimeError("network down"), expected_telegram_link]
    )
    partner_service = _build_referral_partner_service()
    user_service = _build_user_service(current_user)
    user_service.get = AsyncMock(return_value=SimpleNamespace(points=99))
    referral_portal_service = _build_referral_portal_service(
        config=config,
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=user_service,
    )

    response = asyncio.run(
        _GET_REFERRAL_INFO_IMPL(
            current_user=current_user,
            referral_portal_service=referral_portal_service,
        )
    )

    assert response.telegram_referral_link == expected_telegram_link
    assert response.referral_link == expected_telegram_link
    assert referral_service.get_ref_link.await_count == 2


def test_get_referral_info_falls_back_to_web_link_after_retry_failure() -> None:
    current_user = _build_current_user()
    config = _build_config()
    expected_web_link = build_web_referral_link(config, current_user.referral_code)
    referral_service = _build_referral_service(
        [RuntimeError("connection reset"), RuntimeError("connection reset again")]
    )
    partner_service = _build_referral_partner_service()
    user_service = _build_user_service(current_user)
    user_service.get = AsyncMock(return_value=SimpleNamespace(points=99))
    referral_portal_service = _build_referral_portal_service(
        config=config,
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=user_service,
    )

    response = asyncio.run(
        _GET_REFERRAL_INFO_IMPL(
            current_user=current_user,
            referral_portal_service=referral_portal_service,
        )
    )

    assert response.telegram_referral_link == expected_web_link
    assert response.referral_link == expected_web_link
    assert response.web_referral_link == expected_web_link
    assert referral_service.get_ref_link.await_count == 2


def test_get_referral_qr_target_telegram_uses_fallback_when_telegram_unavailable() -> None:
    current_user = _build_current_user()
    config = _build_config()
    expected_web_link = build_web_referral_link(config, current_user.referral_code)
    referral_service = _build_referral_service(
        [RuntimeError("connection reset"), RuntimeError("connection reset again")]
    )
    partner_service = _build_referral_partner_service()
    user_service = _build_user_service(current_user)
    referral_portal_service = _build_referral_portal_service(
        config=config,
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=user_service,
    )

    response = asyncio.run(
        _GET_REFERRAL_QR_IMPL(
            target="telegram",
            current_user=current_user,
            referral_portal_service=referral_portal_service,
        )
    )

    assert response.status_code == 200
    assert response.media_type == "image/png"
    assert response.body == b"qr-image-bytes"
    referral_service.generate_ref_qr_bytes.assert_called_once_with(expected_web_link)
    assert referral_service.get_ref_link.await_count == 2


def test_get_referral_qr_target_web_skips_telegram_lookup() -> None:
    current_user = _build_current_user()
    config = _build_config()
    expected_web_link = build_web_referral_link(config, current_user.referral_code)
    referral_service = _build_referral_service("https://t.me/remna_shop?start=ref_Es4tEy")
    partner_service = _build_referral_partner_service()
    user_service = _build_user_service(current_user)
    referral_portal_service = _build_referral_portal_service(
        config=config,
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=user_service,
    )

    response = asyncio.run(
        _GET_REFERRAL_QR_IMPL(
            target="web",
            current_user=current_user,
            referral_portal_service=referral_portal_service,
        )
    )

    assert response.status_code == 200
    assert response.media_type == "image/png"
    assert response.body == b"qr-image-bytes"
    referral_service.generate_ref_qr_bytes.assert_called_once_with(expected_web_link)
    referral_service.get_ref_link.assert_not_awaited()


def test_get_partner_info_falls_back_to_web_link_after_retry_failure() -> None:
    current_user = _build_current_user()
    config = _build_config()
    expected_web_link = build_web_referral_link(config, current_user.referral_code)
    referral_service = _build_referral_service(
        [RuntimeError("connection reset"), RuntimeError("connection reset again")]
    )
    partner_service = _build_partner_info_service()
    user_service = _build_user_service(current_user)
    referral_portal_service = _build_referral_portal_service(
        config=config,
        referral_service=referral_service,
        partner_service=partner_service,
        user_service=user_service,
    )
    partner_portal_service = _build_partner_portal_service(
        config=config,
        partner_service=partner_service,
        referral_portal_service=referral_portal_service,
    )

    response = asyncio.run(
        _GET_PARTNER_INFO_IMPL(
            current_user=current_user,
            partner_portal_service=partner_portal_service,
        )
    )

    assert response.telegram_referral_link == expected_web_link
    assert response.referral_link == expected_web_link
    assert response.web_referral_link == expected_web_link
    assert referral_service.get_ref_link.await_count == 2
