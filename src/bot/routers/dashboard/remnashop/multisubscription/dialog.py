from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Group, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.states import DashboardRemnashop, RemnashopMultiSubscription
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import max_subscriptions_getter, multi_subscription_main_getter
from .handlers import (
    on_max_subscriptions_input,
    on_max_subscriptions_select,
    on_multi_subscription_toggle,
)

# Главное окно настроек мультиподписок
multi_subscription_main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-multi-subscription-main"),
    Row(
        Button(
            text=I18nFormat("btn-multi-subscription-toggle", enabled=F["enabled"]),
            id="toggle",
            on_click=on_multi_subscription_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-multi-subscription-max"),
            id="max_subscriptions",
            state=RemnashopMultiSubscription.MAX_SUBSCRIPTIONS,
            when=F["enabled"],
        ),
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
    state=RemnashopMultiSubscription.MAIN,
    getter=multi_subscription_main_getter,
)

# Окно выбора максимального количества подписок
max_subscriptions = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-multi-subscription-max"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="max_subscriptions_select",
            item_id_getter=lambda item: item["value"],
            items="subscription_options",
            type_factory=int,
            on_click=on_max_subscriptions_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopMultiSubscription.MAIN,
        ),
    ),
    MessageInput(func=on_max_subscriptions_input),
    IgnoreUpdate(),
    state=RemnashopMultiSubscription.MAX_SUBSCRIPTIONS,
    getter=max_subscriptions_getter,
)

router = Dialog(
    multi_subscription_main,
    max_subscriptions,
)