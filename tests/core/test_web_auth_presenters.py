from types import SimpleNamespace

from src.api.presenters.web_auth import (
    _build_web_branding_response,
    _render_webapp_entry_html,
)
from src.infrastructure.database.models.dto.settings import BrandingSettingsDto


def _build_config() -> SimpleNamespace:
    return SimpleNamespace(
        locales=["ru", "en"],
        default_locale="ru",
        bot=SimpleNamespace(support_username=None),
    )


def test_build_web_branding_response_includes_runtime_mini_app_url() -> None:
    response = _build_web_branding_response(
        BrandingSettingsDto(project_name="2GET SHOP", web_title="2GET SHOP - Dashboard"),
        config=_build_config(),
        mini_app_url="https://example.com/miniapp",
        mini_app_launch_url="https://t.me/example_bot/app",
    )

    assert response.project_name == "2GET SHOP"
    assert response.web_title == "2GET SHOP - Dashboard"
    assert response.mini_app_url == "https://example.com/miniapp"
    assert response.mini_app_launch_url == "https://t.me/example_bot/app"


def test_render_webapp_entry_html_uses_branding_meta_and_entry_redirect() -> None:
    html = _render_webapp_entry_html(
        project_name="2GET SHOP",
        web_title="2GET SHOP - Dashboard",
        entry_url="entry?ref=ref_ABC123",
    )

    assert "<title>2GET SHOP - Dashboard</title>" in html
    assert 'meta property="og:title" content="2GET SHOP"' in html
    assert 'meta property="og:description" content="2GET SHOP - Dashboard"' in html
    assert 'window.location.replace("entry?ref=ref_ABC123" + window.location.hash);' in html
