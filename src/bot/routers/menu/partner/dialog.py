from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    CopyText,
    Row,
    ScrollingGroup,
    Select,
    Start,
    SwitchInlineQueryChosenChatButton,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.states import MainMenu, UserPartner
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import (
    partner_getter,
    partner_referrals_getter,
    partner_earnings_getter,
    partner_withdraw_getter,
    partner_withdraw_confirm_getter,
    partner_history_getter,
)
from .handlers import (
    on_withdraw,
    on_withdraw_all,
    on_withdraw_amount_input,
    on_withdraw_confirm,
)


# Главное окно партнерской программы
partner_main = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-partner-main"),
    Row(
        CopyText(
            text=I18nFormat("btn-partner-invite-copy"),
            copy_text=Format("{referral_link}"),
        ),
        when=F["is_partner"] & F["partner_active"],
    ),
    Row(
        SwitchInlineQueryChosenChatButton(
            text=I18nFormat("btn-partner-invite-send"),
            query=Format("{invite}"),
            allow_user_chats=True,
            allow_group_chats=True,
            allow_channel_chats=True,
            id="send",
        ),
        when=F["is_partner"] & F["partner_active"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-partner-referrals", count=F["count"]),
            id="referrals",
            state=UserPartner.REFERRALS,
        ),
        when=F["is_partner"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-partner-earnings"),
            id="earnings",
            state=UserPartner.EARNINGS,
        ),
        when=F["is_partner"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-partner-withdraw"),
            id="withdraw",
            on_click=on_withdraw,
        ),
        SwitchTo(
            text=I18nFormat("btn-partner-history"),
            id="history",
            state=UserPartner.WITHDRAW_HISTORY,
        ),
        when=F["is_partner"],
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-main-menu"),
            id="back",
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=UserPartner.MAIN,
    getter=partner_getter,
)

# Список рефералов
partner_referrals = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-partner-referrals"),
    ScrollingGroup(
        Select(
            text=I18nFormat(
                "btn-partner-referral-item",
                level=F["item"]["level"],
                username=F["item"]["referral_user_id"],
                total_earned=F["item"]["total_earned"],
            ),
            id="referral_select",
            item_id_getter=lambda item: item["id"],
            items="referrals",
        ),
        id="referrals_scroll",
        width=1,
        height=7,
        hide_on_single_page=True,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=UserPartner.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=UserPartner.REFERRALS,
    getter=partner_referrals_getter,
)

# История начислений
partner_earnings = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-partner-earnings"),
    ScrollingGroup(
        Column(
            Select(
                text=Format("{item[level_emoji]} +{item[amount]} | {item[created_at]}"),
                id="earning_select",
                item_id_getter=lambda item: item["id"],
                items="earnings",
            ),
        ),
        id="earnings_scroll",
        width=1,
        height=7,
        hide_on_single_page=True,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=UserPartner.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=UserPartner.EARNINGS,
    getter=partner_earnings_getter,
)

# Запрос на вывод средств
partner_withdraw = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-partner-withdraw"),
    Row(
        Button(
            text=I18nFormat("btn-partner-withdraw"),
            id="withdraw_all",
            on_click=on_withdraw_all,
            when=F["can_withdraw"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=UserPartner.MAIN,
        ),
    ),
    MessageInput(func=on_withdraw_amount_input),
    IgnoreUpdate(),
    state=UserPartner.WITHDRAW,
    getter=partner_withdraw_getter,
)

# Подтверждение вывода
partner_withdraw_confirm = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-partner-withdraw-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-partner-withdraw-confirm"),
            id="confirm",
            on_click=on_withdraw_confirm,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=UserPartner.WITHDRAW,
        ),
    ),
    IgnoreUpdate(),
    state=UserPartner.WITHDRAW_CONFIRM,
    getter=partner_withdraw_confirm_getter,
)

# История выводов
partner_history = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-partner-history"),
    ScrollingGroup(
        Column(
            Select(
                text=Format("{item[status_emoji]} {item[amount]} | {item[created_at]}"),
                id="withdrawal_select",
                item_id_getter=lambda item: item["id"],
                items="withdrawals",
            ),
        ),
        id="history_scroll",
        width=1,
        height=7,
        hide_on_single_page=True,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=UserPartner.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=UserPartner.WITHDRAW_HISTORY,
    getter=partner_history_getter,
)

router = Dialog(
    partner_main,
    partner_referrals,
    partner_earnings,
    partner_withdraw,
    partner_withdraw_confirm,
    partner_history,
)