from pathlib import Path

from src.core.utils.branding import resolve_bot_menu_button_text, resolve_project_name


def test_branding_helpers_prefer_configured_values() -> None:
    assert resolve_project_name("2GET SHOP") == "2GET SHOP"
    assert (
        resolve_bot_menu_button_text(
            "Control Panel",
            project_name="2GET SHOP",
        )
        == "Control Panel"
    )


def test_branding_helpers_fallback_to_safe_defaults() -> None:
    assert resolve_project_name("") == "AltShop"
    assert resolve_bot_menu_button_text("", project_name="") == "Shop"
    assert resolve_bot_menu_button_text("", project_name="2GET SHOP") == "2GET SHOP"


def test_client_facing_branding_targets_are_runtime_driven() -> None:
    landing_source = Path("web-app/src/pages/landing/LandingPage.tsx").read_text(encoding="utf-8")
    miniapp_source = Path("web-app/src/pages/landing/MiniAppLandingPage.tsx").read_text(
        encoding="utf-8"
    )
    en_buttons = Path("assets/translations/en/buttons.ftl").read_text(encoding="utf-8")
    ru_buttons = Path("assets/translations/ru/buttons.ftl").read_text(encoding="utf-8")
    en_messages = Path("assets/translations/en/messages.ftl").read_text(encoding="utf-8")
    ru_messages = Path("assets/translations/ru/messages.ftl").read_text(encoding="utf-8")
    email_recovery_source = Path("src/services/email_recovery.py").read_text(encoding="utf-8")

    assert "projectName" in landing_source
    assert "projectName" in miniapp_source
    assert "{ $shop_label }" in en_buttons
    assert "{ $shop_label }" in ru_buttons
    assert "{ $project_name }" in en_messages
    assert "{ $project_name }" in ru_messages
    assert 'subject = "AltShop email verification"' not in email_recovery_source
    assert 'subject = "AltShop password reset"' not in email_recovery_source
    assert "Your AltShop password reset code" not in email_recovery_source


def test_client_facing_branding_targets_do_not_hardcode_altshop_literals() -> None:
    guarded_paths = [
        Path("web-app/src/pages/landing/LandingPage.tsx"),
        Path("web-app/src/pages/landing/MiniAppLandingPage.tsx"),
        Path("assets/translations/en/buttons.ftl"),
        Path("assets/translations/ru/buttons.ftl"),
        Path("assets/translations/en/messages.ftl"),
        Path("assets/translations/ru/messages.ftl"),
        Path("src/services/email_recovery.py"),
    ]

    hits: list[str] = []
    for path in guarded_paths:
        text = path.read_text(encoding="utf-8")
        if "AltShop" in text or "ALTSHOP" in text:
            hits.append(str(path))

    assert hits == []
