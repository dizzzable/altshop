from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import Column, Row, Select, Start, SwitchTo
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.states import DashboardRemnashop, RemnashopNotifications
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, SystemNotificationType, UserNotificationType

from .getters import system_types_getter, user_types_getter
from .handlers import on_system_type_select, on_user_type_select

notifications = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-notifications-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-notifications-user"),
            id="users",
            state=RemnashopNotifications.USER,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-notifications-system"),
            id="system",
            state=RemnashopNotifications.SYSTEM,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardRemnashop.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.MAIN,
)

user = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-notifications-user"),
    Column(
        Select(
            text=I18nFormat(
                "btn-notifications-user-choice",
                type=F["item"]["type"],
                enabled=F["item"]["enabled"],
            ),
            id="select_type",
            item_id_getter=lambda item: item["type"],
            items="types",
            type_factory=UserNotificationType,
            on_click=on_user_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopNotifications.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.USER,
    getter=user_types_getter,
)

system = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-notifications-system"),
    Column(
        Select(
            text=I18nFormat(
                "btn-notifications-system-choice",
                type=F["item"]["type"],
                enabled=F["item"]["enabled"],
            ),
            id="select_type",
            item_id_getter=lambda item: item["type"],
            items="types",
            type_factory=SystemNotificationType,
            on_click=on_system_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopNotifications.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopNotifications.SYSTEM,
    getter=system_types_getter,
)

router = Dialog(
    notifications,
    user,
    system,
)
