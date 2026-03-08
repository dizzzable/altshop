from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from src.api.endpoints.web_auth import get_web_branding
from src.api.presenters.web_auth import (
    WebBrandingResponse,
    _resolve_default_web_locale,
    _resolve_supported_web_locales,
    _resolve_web_request_locale,
)
from src.core.utils.branding import (
    render_template,
    resolve_branding_locale,
    resolve_localized_text,
    validate_template,
)
from src.infrastructure.database.models.dto.settings import (
    BrandingVerificationDto,
    LocalizedTextDto,
)

GET_WEB_BRANDING_ENDPOINT = getattr(
    inspect.unwrap(get_web_branding),
    "__dishka_orig_func__",
    inspect.unwrap(get_web_branding),
)


def test_render_template_with_code_and_project_name() -> None:
    template = "{project_name} verification code\nCode: {code}"

    rendered = render_template(
        template,
        placeholders={"project_name": "Remna", "code": "123456"},
    )

    assert rendered == "Remna verification code\nCode: 123456"


def test_validate_template_rejects_unknown_placeholders() -> None:
    with pytest.raises(ValueError, match="unsupported placeholders"):
        validate_template(
            "Code: {code}. Unknown: {foo}",
            field_name="verification.telegram_template.ru",
            allowed_placeholders=("project_name", "code"),
            required_placeholders=("code",),
        )


def test_telegram_template_without_code_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing required placeholders: code"):
        BrandingVerificationDto(
            telegram_template=LocalizedTextDto(
                ru="{project_name} код верификации",
                en="{project_name} verification code",
            )
        )


def test_branding_verification_allows_empty_ru_overrides() -> None:
    dto = BrandingVerificationDto(
        telegram_template=LocalizedTextDto(
            ru="",
            en="{project_name} verification code\nCode: {code}",
        ),
        web_request_delivered=LocalizedTextDto(
            ru="",
            en="Verification code sent to Telegram",
        ),
        web_request_open_bot=LocalizedTextDto(
            ru="",
            en="Code generated. Open bot chat, press /start and retry",
        ),
        web_confirm_success=LocalizedTextDto(
            ru="",
            en="Telegram account linked successfully",
        ),
    )

    assert dto.telegram_template.ru == ""
    assert dto.telegram_template.en


def test_locale_resolution_and_fallbacks() -> None:
    assert resolve_branding_locale("en") == "en"
    assert resolve_branding_locale("en-US") == "en"
    assert resolve_branding_locale("ru") == "ru"
    assert resolve_branding_locale("de") == "ru"
    assert resolve_branding_locale(None) == "ru"

    text = LocalizedTextDto(ru="Привет", en="Hello")
    assert resolve_localized_text(text, language="en-GB") == "Hello"
    assert resolve_localized_text(text, language="fr") == "Привет"

    only_ru = LocalizedTextDto(ru="Только RU", en="")
    assert resolve_localized_text(only_ru, language="en") == "Только RU"

    only_en = LocalizedTextDto(ru="", en="Only EN")
    assert resolve_localized_text(only_en, language="ru") == "Only EN"


class _StubSettingsService:
    async def get_branding_settings(self) -> SimpleNamespace:
        return SimpleNamespace(
            project_name="MyBrand",
            web_title="MyBrand - Control Panel",
        )


def _build_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {"type": "http", "headers": raw_headers}
    return Request(scope)


def test_get_web_branding_endpoint_returns_settings_values() -> None:
    config = SimpleNamespace(locales=["ru", "en", "de"], default_locale="en")
    response = asyncio.run(
        GET_WEB_BRANDING_ENDPOINT(
            settings_service=_StubSettingsService(),
            config=config,
        )
    )

    assert isinstance(response, WebBrandingResponse)
    assert response.project_name == "MyBrand"
    assert response.web_title == "MyBrand - Control Panel"
    assert response.default_locale == "en"
    assert response.supported_locales == ["ru", "en"]


def test_web_locale_resolution_prefers_header_and_respects_supported_locales() -> None:
    config = SimpleNamespace(locales=["ru"], default_locale="ru")

    assert _resolve_supported_web_locales(config) == ["ru"]
    assert _resolve_default_web_locale(config) == "ru"

    request = _build_request({"X-Web-Locale": "en"})
    resolved = _resolve_web_request_locale(
        request,
        config=config,
        current_user=SimpleNamespace(language="en"),
    )
    assert resolved == "ru"
