from __future__ import annotations

from types import SimpleNamespace

from src.core.enums import PurchaseChannel
from src.services.payment_redirect_policy import sanitize_payment_redirect_urls_for_channel


def build_config(*, web_app_url: str = "https://example.test/webapp") -> SimpleNamespace:
    return SimpleNamespace(
        web_app=SimpleNamespace(url_str=web_app_url),
        domain=SimpleNamespace(get_secret_value=lambda: "example.test"),
        bot=SimpleNamespace(mini_app_url=False),
    )


def test_sanitize_payment_redirect_urls_for_web_keeps_configured_targets() -> None:
    success_redirect_url, fail_redirect_url = sanitize_payment_redirect_urls_for_channel(
        channel=PurchaseChannel.WEB,
        config=build_config(),
        success_redirect_url="https://EXAMPLE.TEST/webapp/dashboard/subscription?payment=success",
        fail_redirect_url=(
            "https://example.test/webapp/dashboard/subscription/purchase?payment=failed"
        ),
    )

    assert success_redirect_url == "https://example.test/webapp/dashboard/subscription?payment=success"
    assert (
        fail_redirect_url
        == "https://example.test/webapp/dashboard/subscription/purchase?payment=failed"
    )


def test_sanitize_payment_redirect_urls_for_telegram_keeps_approved_bot_targets() -> None:
    success_redirect_url, fail_redirect_url = sanitize_payment_redirect_urls_for_channel(
        channel=PurchaseChannel.TELEGRAM,
        config=build_config(),
        success_redirect_url="https://telegram.me/example_bot?startapp=payment-success",
        fail_redirect_url="https://t.me/example_bot?startapp=payment-failed",
        bot_username="example_bot",
    )

    assert success_redirect_url == "https://t.me/example_bot?startapp=payment-success"
    assert fail_redirect_url == "https://t.me/example_bot?startapp=payment-failed"
