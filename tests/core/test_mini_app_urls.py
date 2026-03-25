from src.core.utils.mini_app_urls import (
    PAYMENT_RETURN_STATUS_QUERY_KEY,
    build_telegram_payment_return_url,
)


def test_build_telegram_payment_return_url_prefers_mini_app_url() -> None:
    resolved = build_telegram_payment_return_url(
        status="success",
        mini_app_url="https://example.com/webapp/miniapp",
        bot_username="example_bot",
    )

    assert resolved == (
        f"https://example.com/webapp/miniapp?{PAYMENT_RETURN_STATUS_QUERY_KEY}=success&tg_open=1"
    )


def test_build_telegram_payment_return_url_updates_existing_t_me_startapp() -> None:
    resolved = build_telegram_payment_return_url(
        status="failed",
        mini_app_url="https://t.me/example_bot/app?startapp=old",
        bot_username="example_bot",
    )

    assert resolved == "https://t.me/example_bot/app?startapp=payment-failed"


def test_build_telegram_payment_return_url_falls_back_to_bot_username() -> None:
    resolved = build_telegram_payment_return_url(
        status="success",
        mini_app_url=None,
        bot_username="@example_bot",
    )

    assert resolved == "https://t.me/example_bot?startapp=payment-success"
