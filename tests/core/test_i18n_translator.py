from __future__ import annotations

from fluentogram.exceptions import KeyNotFoundError

from src.core.i18n.translator import build_i18n_fallback, humanize_i18n_key, safe_i18n_get


class FakeTranslator:
    def get(self, key: str, **kwargs: object) -> str:
        if key == "known-key":
            return f"Known {kwargs.get('value', '')}".strip()
        raise KeyNotFoundError(key)


def test_humanize_i18n_key_strips_known_prefix() -> None:
    assert humanize_i18n_key("btn-plan-archived") == "Plan Archived"
    assert humanize_i18n_key("ntf-plan-delete-blocked") == "Plan Delete Blocked"


def test_safe_i18n_get_returns_real_translation_when_key_exists() -> None:
    translator = FakeTranslator()

    assert safe_i18n_get(translator, "known-key", value="value") == "Known value"


def test_safe_i18n_get_returns_humanized_fallback_when_key_missing() -> None:
    translator = FakeTranslator()

    assert safe_i18n_get(translator, "msg-plan-archived-renew-mode") == (
        "📝 Plan Archived Renew Mode"
    )


def test_build_i18n_fallback_adds_prefix_emoji() -> None:
    assert build_i18n_fallback("btn-plan-archived") == "🔘 Plan Archived"
    assert build_i18n_fallback("ntf-user-subscription-empty") == "⚠️ User Subscription Empty"
