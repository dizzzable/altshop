from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.endpoints.user_account import get_user_profile
from src.api.endpoints.user_portal import (
    PartnerWithdrawalRequest,
    request_withdrawal,
)
from src.api.presenters.web_auth import _build_auth_me_response
from src.api.utils.user_identity import resolve_public_username
from src.core.enums import Currency, Locale, UserRole
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.partner_portal import PartnerPortalService
from src.services.user_profile import UserProfileService, UserProfileSnapshot

GET_USER_PROFILE_ENDPOINT = getattr(
    inspect.unwrap(get_user_profile),
    "__dishka_orig_func__",
    inspect.unwrap(get_user_profile),
)
REQUEST_WITHDRAWAL_ENDPOINT = getattr(
    inspect.unwrap(request_withdrawal),
    "__dishka_orig_func__",
    inspect.unwrap(request_withdrawal),
)


def _build_user(
    *,
    telegram_id: int,
    username: str | None,
    name: str | None = None,
) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=username,
        referral_code=f"code{telegram_id}",
        name=name if name is not None else f"User {telegram_id}",
        role=UserRole.USER,
        language=Locale.EN,
    )


def _build_web_account(
    *,
    user_telegram_id: int,
    username: str,
    email: str | None = None,
    email_verified_at: datetime | None = None,
    credentials_bootstrapped_at: datetime | None = None,
    requires_password_change: bool = False,
    link_prompt_snooze_until: datetime | None = None,
) -> WebAccountDto:
    return WebAccountDto(
        id=1,
        user_telegram_id=user_telegram_id,
        username=username,
        password_hash="hashed",
        email=email,
        email_verified_at=email_verified_at,
        credentials_bootstrapped_at=credentials_bootstrapped_at,
        token_version=0,
        requires_password_change=requires_password_change,
        link_prompt_snooze_until=link_prompt_snooze_until,
    )


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        bot=SimpleNamespace(
            support_username=SimpleNamespace(get_secret_value=lambda: "support_helper")
        )
    )


def test_resolve_public_username_prefers_user_username_over_web_account() -> None:
    user = _build_user(telegram_id=101, username="telegram_user")
    web_account = _build_web_account(user_telegram_id=user.telegram_id, username="web_user")

    resolved = resolve_public_username(user, web_account=web_account)

    assert resolved == "telegram_user"


def test_resolve_public_username_uses_web_account_when_user_username_missing() -> None:
    user = _build_user(telegram_id=202, username=None)
    web_account = _build_web_account(user_telegram_id=user.telegram_id, username="web_user")

    resolved = resolve_public_username(user, web_account=web_account)

    assert resolved == "web_user"


def test_build_auth_me_response_maps_profile_snapshot() -> None:
    response = _build_auth_me_response(
        UserProfileSnapshot(
            telegram_id=303,
            username="web_user",
            name=None,
            safe_name="web_user",
            role="user",
            points=0,
            language="en",
            default_currency=Currency.RUB.value,
            personal_discount=0,
            purchase_discount=0,
            partner_balance_currency_override=None,
            effective_partner_balance_currency=Currency.RUB.value,
            is_blocked=False,
            is_bot_blocked=False,
            created_at="",
            updated_at="",
            email="user@example.com",
            email_verified=True,
            telegram_linked=False,
            linked_telegram_id=None,
            show_link_prompt=True,
            requires_password_change=True,
            effective_max_subscriptions=1,
            active_subscriptions_count=0,
            is_partner=False,
            is_partner_active=False,
            has_web_account=True,
            needs_web_credentials_bootstrap=False,
        )
    )

    assert response.username == "web_user"
    assert response.email_verified is True
    assert response.show_link_prompt is True
    assert response.default_currency == Currency.RUB.value


def test_user_profile_service_uses_supplied_web_account_and_respects_link_prompt_snooze() -> None:
    current_user = _build_user(telegram_id=353, username=None, name="")
    web_account = _build_web_account(
        user_telegram_id=0,
        username="web_user",
        link_prompt_snooze_until=datetime_now() + timedelta(days=1),
    )
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(return_value=web_account)
    )
    service = UserProfileService(
        web_account_service=web_account_service,
        subscription_service=SimpleNamespace(get_all_by_user=AsyncMock(return_value=[])),
        settings_service=SimpleNamespace(
            get_max_subscriptions_for_user=AsyncMock(return_value=1),
            get_default_currency=AsyncMock(return_value=Currency.RUB),
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        ),
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    snapshot = asyncio.run(service.build_snapshot(user=current_user, web_account=web_account))

    assert snapshot.username == "web_user"
    assert snapshot.safe_name == "web_user"
    assert snapshot.show_link_prompt is False
    assert snapshot.default_currency == Currency.RUB.value
    assert web_account_service.get_by_user_telegram_id.await_count == 0


def test_get_user_profile_maps_snapshot_from_user_profile_service() -> None:
    current_user = _build_user(telegram_id=404, username=None)
    profile = UserProfileSnapshot(
        telegram_id=current_user.telegram_id,
        username="web_user",
        name=current_user.name,
        safe_name=current_user.name,
        role="user",
        points=current_user.points,
        language="en",
        default_currency=Currency.RUB.value,
        personal_discount=current_user.personal_discount,
        purchase_discount=current_user.purchase_discount,
        partner_balance_currency_override=None,
        effective_partner_balance_currency=Currency.RUB.value,
        is_blocked=current_user.is_blocked,
        is_bot_blocked=current_user.is_bot_blocked,
        created_at="",
        updated_at="",
        email="user@example.com",
        email_verified=False,
        telegram_linked=True,
        linked_telegram_id=current_user.telegram_id,
        show_link_prompt=False,
        requires_password_change=False,
        effective_max_subscriptions=1,
        active_subscriptions_count=0,
        is_partner=False,
        is_partner_active=False,
        has_web_account=True,
        needs_web_credentials_bootstrap=False,
    )
    user_profile_service = SimpleNamespace(build_snapshot=AsyncMock(return_value=profile))

    response = asyncio.run(
        GET_USER_PROFILE_ENDPOINT(
            current_user=current_user,
            user_profile_service=user_profile_service,
        )
    )

    assert response.username == "web_user"
    assert response.email == "user@example.com"
    assert response.default_currency == Currency.RUB.value
    assert user_profile_service.build_snapshot.await_count == 1


def test_user_profile_service_marks_shell_web_account_for_credentials_bootstrap() -> None:
    current_user = _build_user(telegram_id=454, username=None, name="")
    web_account = _build_web_account(
        user_telegram_id=current_user.telegram_id,
        username="tg_shell",
        credentials_bootstrapped_at=None,
    )
    service = UserProfileService(
        web_account_service=SimpleNamespace(get_by_user_telegram_id=AsyncMock(return_value=web_account)),
        subscription_service=SimpleNamespace(get_all_by_user=AsyncMock(return_value=[])),
        settings_service=SimpleNamespace(
            get_max_subscriptions_for_user=AsyncMock(return_value=1),
            get_default_currency=AsyncMock(return_value=Currency.RUB),
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB),
        ),
        partner_service=SimpleNamespace(get_partner_by_user=AsyncMock(return_value=None)),
    )

    snapshot = asyncio.run(service.build_snapshot(user=current_user, web_account=web_account))

    assert snapshot.has_web_account is True
    assert snapshot.needs_web_credentials_bootstrap is True
    assert snapshot.default_currency == Currency.RUB.value


def test_request_withdrawal_notification_uses_web_account_username_when_needed() -> None:
    current_user = _build_user(telegram_id=505, username=None)
    web_account = _build_web_account(user_telegram_id=current_user.telegram_id, username="web_user")
    withdrawal = SimpleNamespace(
        id=10,
        amount=12345,
        requested_amount=Decimal("123.45"),
        requested_currency=Currency.RUB,
        quote_rate=Decimal("1"),
        quote_source="STATIC",
        status="pending",
        method="sbp",
        requisites="+79990000000",
        admin_comment=None,
        created_at=datetime(2026, 3, 6, 12, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 6, 12, 0, 0, tzinfo=UTC),
    )
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(
            return_value=SimpleNamespace(id=99, is_active=True, balance=20000)
        ),
        create_withdrawal_request=AsyncMock(return_value=withdrawal),
        settings_service=SimpleNamespace(
            resolve_partner_balance_currency=AsyncMock(return_value=Currency.RUB)
        ),
    )
    notification_service = SimpleNamespace(notify_super_dev=AsyncMock())
    partner_portal_service = PartnerPortalService(
        config=_build_config(),
        partner_service=partner_service,
        referral_portal_service=SimpleNamespace(),
        notification_service=notification_service,
        web_account_service=SimpleNamespace(
            get_by_user_telegram_id=AsyncMock(return_value=web_account)
        ),
        market_quote_service=SimpleNamespace(),
    )

    response = asyncio.run(
        REQUEST_WITHDRAWAL_ENDPOINT(
            request=PartnerWithdrawalRequest(
                amount=Decimal("123.45"),
                method="sbp",
                requisites="+79990000000",
            ),
            current_user=current_user,
            partner_portal_service=partner_portal_service,
        )
    )

    payload = notification_service.notify_super_dev.await_args.args[0]

    assert payload.i18n_kwargs["username"] == "web_user"
    assert response.id == 10
