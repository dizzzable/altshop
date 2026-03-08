from __future__ import annotations

import re
from typing import Any, Iterable

SUPPORTED_BRANDING_LOCALES: tuple[str, str] = ("ru", "en")
BRANDING_PLACEHOLDER_RE = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")
ANY_PLACEHOLDER_RE = re.compile(r"{([^{}]+)}")


def normalize_text(value: Any) -> str:
    normalized = str(value or "").replace("\r\n", "\n").strip()
    return normalized


def ensure_text_length(
    value: str,
    *,
    field_name: str,
    min_length: int,
    max_length: int,
) -> str:
    normalized = normalize_text(value)
    if len(normalized) < min_length or len(normalized) > max_length:
        raise ValueError(
            f"Field '{field_name}' must be between {min_length} and {max_length} characters."
        )
    return normalized


def extract_placeholders(template: str) -> set[str]:
    return set(BRANDING_PLACEHOLDER_RE.findall(template))


def validate_template(
    template: str,
    *,
    field_name: str,
    allowed_placeholders: Iterable[str],
    required_placeholders: Iterable[str] | None = None,
    min_length: int = 1,
    max_length: int = 1000,
) -> str:
    normalized = ensure_text_length(
        template,
        field_name=field_name,
        min_length=min_length,
        max_length=max_length,
    )

    allowed = set(allowed_placeholders)
    required = set(required_placeholders or ())
    found = extract_placeholders(normalized)
    raw_found = {name.strip() for name in ANY_PLACEHOLDER_RE.findall(normalized)}

    unknown = sorted(raw_found - allowed)
    if unknown:
        raise ValueError(f"Field '{field_name}' has unsupported placeholders: {', '.join(unknown)}")

    missing = sorted(required - found)
    if missing:
        raise ValueError(
            f"Field '{field_name}' is missing required placeholders: {', '.join(missing)}"
        )

    return normalized


def render_template(template: str, placeholders: dict[str, Any]) -> str:
    normalized = normalize_text(template)

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = placeholders.get(key, "")
        return str(value)

    return BRANDING_PLACEHOLDER_RE.sub(_replace, normalized)


def resolve_branding_locale(language: Any) -> str:
    if language is None:
        return "ru"

    raw = str(getattr(language, "value", language)).strip().lower()
    if raw.startswith("en"):
        return "en"

    return "ru"


def resolve_localized_text(localized_text: Any, *, language: Any) -> str:
    locale = resolve_branding_locale(language)

    ru_value = normalize_text(getattr(localized_text, "ru", ""))
    en_value = normalize_text(getattr(localized_text, "en", ""))

    if locale == "en":
        return en_value or ru_value or ""

    return ru_value or en_value or ""
