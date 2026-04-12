from src.core.constants import MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import Currency
from src.infrastructure.database.models.dto import SettingsDto, UserDto
from src.services.settings_helpers import (
    normalize_settings_for_update,
    resolve_effective_max_subscriptions,
    resolve_partner_balance_currency,
)


def test_normalize_settings_for_update_preserves_nested_dto_payloads() -> None:
    settings = SettingsDto()
    settings.branding.project_name = "AltShop"
    settings.bot_menu.mini_app_url = "https://example.test/app"

    normalized = normalize_settings_for_update(settings)
    changed_data = normalized.prepare_changed_data()

    assert changed_data["branding"]["project_name"] == "AltShop"
    assert changed_data["bot_menu"]["mini_app_url"] == "https://example.test/app"


def test_resolve_effective_max_subscriptions_clamps_unlimited_user_override() -> None:
    user = UserDto(telegram_id=77, name="Tester", max_subscriptions=-1)

    effective_limit = resolve_effective_max_subscriptions(
        user=user,
        multi_subscription_enabled=True,
        default_max_subscriptions=3,
    )

    assert effective_limit == MAX_SUBSCRIPTIONS_PER_USER


def test_resolve_effective_max_subscriptions_returns_one_when_global_setting_disabled() -> None:
    user = UserDto(telegram_id=77, name="Tester")

    effective_limit = resolve_effective_max_subscriptions(
        user=user,
        multi_subscription_enabled=False,
        default_max_subscriptions=9,
    )

    assert effective_limit == 1


def test_resolve_partner_balance_currency_maps_xtr_to_rub() -> None:
    user = UserDto(telegram_id=77, name="Tester", partner_balance_currency_override=Currency.XTR)

    resolved = resolve_partner_balance_currency(Currency.USD, user)

    assert resolved == Currency.RUB
