from src.core.utils.mini_app_urls import (
    PAYMENT_RETURN_STATUS_QUERY_KEY,
    build_telegram_payment_return_url,
    resolve_telegram_mini_app_launch_url,
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


def test_resolve_telegram_mini_app_launch_url_prefers_telegram_links() -> None:
    resolved = resolve_telegram_mini_app_launch_url(
        "https://example.com/webapp/miniapp",
        "https://t.me/example_bot/app?startapp=launch",
    )

    assert resolved == "https://t.me/example_bot/app?startapp=launch"


def test_resolve_telegram_mini_app_launch_url_returns_none_without_tg_link() -> None:
    resolved = resolve_telegram_mini_app_launch_url(
        "https://example.com/webapp/miniapp",
        None,
        False,
    )

    assert resolved is None
