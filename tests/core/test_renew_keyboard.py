from src.bot.keyboards import get_renew_keyboard
from src.core.constants import GOTO_PREFIX, PURCHASE_PREFIX
from src.core.enums import PurchaseType


def test_get_renew_keyboard_uses_bot_callback_by_default() -> None:
    keyboard = get_renew_keyboard()
    button = keyboard.inline_keyboard[0][0]

    assert button.callback_data == f"{GOTO_PREFIX}{PURCHASE_PREFIX}{PurchaseType.RENEW}"
    assert button.web_app is None


def test_get_renew_keyboard_uses_web_app_when_requested() -> None:
    keyboard = get_renew_keyboard(
        web_app_url="https://example.com/webapp/dashboard/subscription",
        use_web_app=True,
    )
    button = keyboard.inline_keyboard[0][0]

    assert button.callback_data is None
    assert button.web_app is not None
    assert button.web_app.url == "https://example.com/webapp/dashboard/subscription"


def test_get_renew_keyboard_uses_plain_url_when_webapp_is_not_safe() -> None:
    keyboard = get_renew_keyboard(
        url="https://t.me/example_bot/app?startapp=miniapp",
        use_web_app=False,
    )
    button = keyboard.inline_keyboard[0][0]

    assert button.callback_data is None
    assert button.web_app is None
    assert button.url == "https://t.me/example_bot/app?startapp=miniapp"
