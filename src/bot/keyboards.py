from typing import Final

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_dialog import StartMode
from aiogram_dialog.widgets.kbd import Row, Start, Url, WebApp
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.states import DashboardUser, MainMenu, Subscription
from src.bot.widgets.i18n_format import I18nFormat
from src.core.constants import (
    ALTSHOP_GITHUB_RELEASES_LATEST_URL,
    ALTSHOP_GITHUB_UPGRADE_GUIDE_URL,
    ALTSHOP_GITHUB_URL,
    GOTO_PREFIX,
    PURCHASE_PREFIX,
    T_ME,
)
from src.core.enums import PurchaseType
from src.core.utils.formatters import format_username_to_url

CALLBACK_CHANNEL_CONFIRM: Final[str] = "channel_confirm"
CALLBACK_RULES_ACCEPT: Final[str] = "rules_accept"

goto_buttons = [
    InlineKeyboardButton(
        text="btn-contact-support",
    ),
    InlineKeyboardButton(
        text="btn-goto-subscription",
        callback_data=f"{GOTO_PREFIX}{Subscription.MAIN.state}",
    ),
    InlineKeyboardButton(
        text="btn-goto-promocode",
        callback_data=f"{GOTO_PREFIX}{Subscription.PROMOCODE.state}",
    ),
]

connect_buttons = (
    WebApp(
        text=I18nFormat("btn-menu-connect"),
        url=Format("{url}"),
        id="connect_miniapp",
        when=F["is_app"] & F["connectable"],
    ),
    Url(
        text=I18nFormat("btn-menu-connect"),
        url=Format("{url}"),
        id="connect_sub_page",
        when=~F["is_app"] & F["connectable"],
    ),
)

back_main_menu_button = (
    Row(
        Start(
            text=I18nFormat("btn-back-main-menu"),
            id="back_main_menu",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
)

main_menu_button = (
    Start(
        text=I18nFormat("btn-main-menu"),
        id="back_main_menu",
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
    ),
)


def get_renew_keyboard(
    *,
    web_app_url: str | None = None,
    url: str | None = None,
    use_web_app: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-goto-subscription-renew",
            web_app=WebAppInfo(url=web_app_url) if use_web_app and web_app_url else None,
            url=url if not (use_web_app and web_app_url) and url else None,
            callback_data=(
                None
                if (use_web_app and web_app_url) or url
                else f"{GOTO_PREFIX}{PURCHASE_PREFIX}{PurchaseType.RENEW}"
            ),
        ),
    )
    return builder.as_markup()


def get_channel_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-channel-join",
            url=channel_link,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="btn-channel-confirm",
            callback_data=CALLBACK_CHANNEL_CONFIRM,
        ),
    )
    return builder.as_markup()


def get_rules_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-rules-accept",
            callback_data=CALLBACK_RULES_ACCEPT,
        ),
    )
    return builder.as_markup()


def get_contact_support_keyboard(username: str, text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="btn-contact-support",
            url=format_username_to_url(username, text),
        ),
    )
    return builder.as_markup()


def get_remnashop_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="btn-remnashop-github",
            url=ALTSHOP_GITHUB_URL,
        ),
        InlineKeyboardButton(
            text="btn-remnashop-telegram",
            url=f"{T_ME}remna_shop",
        ),
        # InlineKeyboardButton(
        #     text="btn-remnashop-guide",
        #     url=f"{T_ME}remna_shop",
        # ),
    )

    builder.row(
        InlineKeyboardButton(
            text="btn-remnashop-donate",
            url="https://www.donationalerts.com/r/d1zzable",
        )
    )

    return builder.as_markup()


def get_remnashop_update_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="btn-remnashop-release-latest",
            url=ALTSHOP_GITHUB_RELEASES_LATEST_URL,
        ),
        InlineKeyboardButton(
            text="btn-remnashop-how-upgrade",
            url=ALTSHOP_GITHUB_UPGRADE_GUIDE_URL,
        ),
    )

    return builder.as_markup()


def get_user_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="btn-goto-user-profile",
            callback_data=f"{GOTO_PREFIX}{DashboardUser.MAIN.state}:{telegram_id}",
        ),
    )

    return builder.as_markup()
