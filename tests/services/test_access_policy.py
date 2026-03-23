from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.enums import AccessMode, Locale
from src.infrastructure.database.models.dto import SettingsDto, UserDto
from src.services.access_policy import AccessModePolicyService


def build_user(*, telegram_id: int, created_at: datetime | None = None) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        name="Guest",
        language=Locale.RU,
        created_at=created_at,
    )


def test_invited_mode_grandfathers_existing_user() -> None:
    started_at = datetime.now(timezone.utc)
    service = AccessModePolicyService()
    policy = service.resolve(
        user=build_user(telegram_id=1, created_at=started_at - timedelta(minutes=5)),
        settings=SettingsDto(
            access_mode=AccessMode.INVITED,
            invite_mode_started_at=started_at,
        ),
    )

    assert policy.invite_locked is False
    assert policy.can_purchase is True
    assert policy.should_redirect_to_access_screen is False


def test_invited_mode_blocks_new_uninvited_user() -> None:
    started_at = datetime.now(timezone.utc)
    service = AccessModePolicyService()
    policy = service.resolve(
        user=build_user(telegram_id=2, created_at=started_at + timedelta(minutes=5)),
        settings=SettingsDto(
            access_mode=AccessMode.INVITED,
            invite_mode_started_at=started_at,
        ),
    )

    assert policy.invite_locked is True
    assert policy.can_view_product_screens is False
    assert policy.can_mutate_product is False
    assert policy.can_purchase is False
    assert policy.should_redirect_to_access_screen is True


def test_purchase_blocked_mode_keeps_product_access_but_disables_purchase() -> None:
    service = AccessModePolicyService()
    policy = service.resolve(
        user=build_user(telegram_id=3),
        settings=SettingsDto(access_mode=AccessMode.PURCHASE_BLOCKED),
    )

    assert policy.can_view_product_screens is True
    assert policy.can_mutate_product is True
    assert policy.can_purchase is False
    assert policy.should_redirect_to_access_screen is False


def test_restricted_mode_blocks_non_privileged_user_everywhere() -> None:
    service = AccessModePolicyService()
    policy = service.resolve(
        user=build_user(telegram_id=4),
        settings=SettingsDto(access_mode=AccessMode.RESTRICTED),
    )

    assert policy.can_view_product_screens is False
    assert policy.can_mutate_product is False
    assert policy.can_purchase is False
    assert policy.should_redirect_to_access_screen is True
