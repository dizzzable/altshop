from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, ListGroup, Row, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.routers.extra.test import show_dev_popup
from src.bot.states import (
    Dashboard,
    DashboardRemnashop,
    RemnashopBanners,
    RemnashopGateways,
    RemnashopNotifications,
    RemnashopPlans,
    RemnashopReferral,
)
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import admins_getter
from .handlers import on_logs_request, on_user_role_remove, on_user_select

remnashop = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-remnashop-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-remnashop-admins"),
            id="admins",
            state=DashboardRemnashop.ADMINS,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-remnashop-gateways"),
            id="gateways",
            state=RemnashopGateways.MAIN,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-remnashop-referral"),
            id="referral",
            state=RemnashopReferral.MAIN,
        ),
        Button(
            text=I18nFormat("btn-remnashop-advertising"),
            id="advertising",
            # state=DashboardRemnashop.ADVERTISING,
            on_click=show_dev_popup,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-remnashop-plans"),
            id="plans",
            state=RemnashopPlans.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        Start(
            text=I18nFormat("btn-remnashop-notifications"),
            id="notifications",
            state=RemnashopNotifications.MAIN,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-remnashop-banners"),
            id="banners",
            state=RemnashopBanners.MAIN,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-remnashop-logs"),
            id="logs",
            on_click=on_logs_request,
        ),
        Button(
            text=I18nFormat("btn-remnashop-audit"),
            id="audit",
            on_click=show_dev_popup,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardRemnashop.MAIN,
)

admins = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-admins-main"),
    ListGroup(
        Row(
            Button(
                text=Format("{item[user_id]} ({item[user_name]})"),
                id="select_user",
                on_click=on_user_select,
            ),
            Button(
                text=Format("❌"),
                id="remove_role",
                on_click=on_user_role_remove,
                when=F["item"]["deletable"],
            ),
        ),
        id="admins_list",
        item_id_getter=lambda item: item["user_id"],
        items="admins",
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardRemnashop.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardRemnashop.ADMINS,
    getter=admins_getter,
)

router = Dialog(
    remnashop,
    admins,
)
