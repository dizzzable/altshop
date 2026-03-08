from __future__ import annotations

from types import SimpleNamespace

from src.api.presenters.web_auth import (
    _build_access_status_response,
    _build_registration_access_requirements_response,
)


def test_build_access_status_response_maps_access_snapshot() -> None:
    response = _build_access_status_response(
        SimpleNamespace(
            access_mode="invite_only",
            rules_required=True,
            channel_required=True,
            requires_telegram_id=True,
            access_level="blocked",
            channel_check_status="required_unverified",
            rules_accepted=False,
            telegram_linked=False,
            channel_verified=False,
            linked_telegram_id=None,
            rules_link="https://example.test/rules",
            channel_link="https://t.me/example",
            tg_id_helper_bot_link="https://t.me/userinfobot",
            verification_bot_link="https://t.me/verify_bot",
            unmet_requirements=["RULES_ACCEPTANCE_REQUIRED", "TELEGRAM_LINK_REQUIRED"],
            can_use_product_features=False,
        )
    )

    assert response.access_mode == "invite_only"
    assert response.access_level == "blocked"
    assert response.channel_check_status == "required_unverified"
    assert response.unmet_requirements == [
        "RULES_ACCEPTANCE_REQUIRED",
        "TELEGRAM_LINK_REQUIRED",
    ]


def test_build_registration_access_requirements_response_uses_settings_flags() -> None:
    response = _build_registration_access_requirements_response(
        SimpleNamespace(
            access_mode=SimpleNamespace(value="invite_only"),
            rules_required=True,
            channel_required=False,
            rules_link=SimpleNamespace(get_secret_value=lambda: "https://example.test/rules"),
            get_url_channel_link="https://t.me/example",
        ),
        verification_bot_link="https://t.me/verify_bot",
    )

    assert response.access_mode == "invite_only"
    assert response.rules_required is True
    assert response.channel_required is False
    assert response.requires_telegram_id is True
    assert response.rules_link == "https://example.test/rules"
    assert response.channel_link is None
    assert response.verification_bot_link == "https://t.me/verify_bot"
