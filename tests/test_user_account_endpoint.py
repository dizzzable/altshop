from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.contracts.user_account import SetPartnerBalanceCurrencyRequest
from src.api.endpoints.user_account import set_partner_balance_currency
from src.core.enums import Currency
from src.services.user_profile import UserProfileSnapshot

SET_PARTNER_BALANCE_CURRENCY_ENDPOINT = getattr(
    inspect.unwrap(set_partner_balance_currency),
    "__dishka_orig_func__",
    inspect.unwrap(set_partner_balance_currency),
)


def _build_snapshot() -> UserProfileSnapshot:
    return UserProfileSnapshot(
        telegram_id=1001,
        username="tester",
        name="Tester",
        safe_name="Tester",
        role="USER",
        points=0,
        language="ru",
        default_currency=Currency.RUB.value,
        personal_discount=0,
        purchase_discount=0,
        partner_balance_currency_override=Currency.USDT.value,
        effective_partner_balance_currency=Currency.USDT.value,
        is_blocked=False,
        is_bot_blocked=False,
        created_at="2026-03-08T00:00:00+00:00",
        updated_at="2026-03-08T00:00:00+00:00",
        email=None,
        email_verified=False,
        telegram_linked=True,
        linked_telegram_id=1001,
        show_link_prompt=False,
        requires_password_change=False,
        effective_max_subscriptions=1,
        active_subscriptions_count=0,
        is_partner=True,
        is_partner_active=True,
        has_web_account=True,
        needs_web_credentials_bootstrap=False,
    )


def test_set_partner_balance_currency_updates_override_and_returns_profile() -> None:
    current_user = SimpleNamespace(telegram_id=1001)
    refreshed_user = SimpleNamespace(telegram_id=1001)
    user_service = SimpleNamespace(
        set_partner_balance_currency_override=AsyncMock(),
        get=AsyncMock(return_value=refreshed_user),
    )
    user_profile_service = SimpleNamespace(
        build_snapshot=AsyncMock(return_value=_build_snapshot())
    )

    response = asyncio.run(
        SET_PARTNER_BALANCE_CURRENCY_ENDPOINT(
            payload=SetPartnerBalanceCurrencyRequest(currency=Currency.USDT),
            current_user=current_user,
            user_service=user_service,
            user_profile_service=user_profile_service,
        )
    )

    user_service.set_partner_balance_currency_override.assert_awaited_once_with(
        user=current_user,
        currency=Currency.USDT,
    )
    user_service.get.assert_awaited_once_with(current_user.telegram_id)
    user_profile_service.build_snapshot.assert_awaited_once_with(user=refreshed_user)
    assert response.default_currency == Currency.RUB.value
    assert response.partner_balance_currency_override == Currency.USDT.value
    assert response.effective_partner_balance_currency == Currency.USDT.value
