from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    CopyText,
    Group,
    ListGroup,
    Row,
    Select,
    Start,
    SwitchInlineQueryChosenChatButton,
    SwitchTo,
    Url,
    WebApp,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.routers.dashboard.users.handlers import on_user_search
from src.bot.states import Dashboard, MainMenu, Subscription, UserPartner
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.constants import MIDDLEWARE_DATA_KEY, PURCHASE_PREFIX, USER_KEY
from src.core.enums import BannerName, PointsExchangeType

from .getters import (
    connect_device_getter,
    connect_device_url_getter,
    devices_getter,
    exchange_discount_getter,
    exchange_getter,
    exchange_gift_confirm_getter,
    exchange_gift_getter,
    exchange_gift_select_plan_getter,
    exchange_gift_success_getter,
    exchange_points_confirm_getter,
    exchange_points_getter,
    exchange_select_type_getter,
    exchange_traffic_confirm_getter,
    exchange_traffic_getter,
    invite_about_getter,
    invite_getter,
    menu_getter,
)
from .handlers import (
    on_connect_device_selected,
    on_exchange_discount_confirm,
    on_exchange_gift_confirm,
    on_exchange_gift_select_plan,
    on_exchange_points,
    on_exchange_points_confirm,
    on_exchange_points_select_subscription,
    on_exchange_select_type,
    on_exchange_traffic_confirm,
    on_exchange_traffic_select_subscription,
    on_get_trial,
    on_go_to_exchange,
    on_invite,
    on_show_qr,
    on_withdraw_points,
    show_reason,
)

menu = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-main-menu"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu-connect"),
            id="connect_device",
            state=MainMenu.CONNECT_DEVICE,
            when=F["connectable"],
        ),
        Button(
            text=I18nFormat("btn-menu-connect-not-available"),
            id="not_available",
            on_click=show_reason,
            when=~F["connectable"],
        ),
        when=F["has_subscription"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu-trial"),
            id="trial",
            on_click=on_get_trial,
            when=F["trial_available"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu-devices", count=F["count"]),
            id="devices",
            state=MainMenu.DEVICES,
            when=F["has_device_limit"],
        ),
        Start(
            text=I18nFormat("btn-menu-subscription", count=F["subscriptions_count"]),
            id=f"{PURCHASE_PREFIX}subscription",
            state=Subscription.MAIN,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu-exchange"),
            id="exchange",
            state=MainMenu.EXCHANGE,
            when=F["is_referral_enable"],
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-menu-partner"),
            id="partner",
            state=UserPartner.MAIN,
            when=F["is_partner"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu-invite"),
            id="invite",
            on_click=on_invite,
            when=F["is_referral_enable"],
        ),
        SwitchInlineQueryChosenChatButton(
            text=I18nFormat("btn-menu-invite"),
            query=Format("{invite}"),
            allow_user_chats=True,
            allow_group_chats=True,
            allow_channel_chats=True,
            id="send",
            when=~F["is_referral_enable"],
        ),
        Url(
            text=I18nFormat("btn-menu-support"),
            id="support",
            url=Format("{support}"),
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-menu-dashboard"),
            id="dashboard",
            state=Dashboard.MAIN,
            mode=StartMode.RESET_STACK,
            when=F[MIDDLEWARE_DATA_KEY][USER_KEY].is_privileged,
        ),
    ),
    MessageInput(func=on_user_search),
    IgnoreUpdate(),
    state=MainMenu.MAIN,
    getter=menu_getter,
)

devices = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-devices"),
    Row(
        Button(
            text=I18nFormat("btn-menu-devices-empty"),
            id="devices_empty",
            when=F["devices_empty"],
        ),
    ),
    ListGroup(
        CopyText(
            text=Format("{item[device_name]} - {item[plan_name]}"),
            copy_text=Format("{item[subscription_url]}"),
        ),
        id="devices_list",
        item_id_getter=lambda item: item["id"],
        items="devices",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.DEVICES,
    getter=devices_getter,
)


connect_device = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-connect-device"),
    Group(
        Select(
            text=Format("{item[display_name]}"),
            id="connect_device_select",
            item_id_getter=lambda item: str(item["id"]),
            items="subscriptions",
            on_click=on_connect_device_selected,
        ),
        width=1,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.CONNECT_DEVICE,
    getter=connect_device_getter,
)


invite = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-invite"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu-invite-about"),
            id="about",
            state=MainMenu.INVITE_ABOUT,
        ),
    ),
    Row(
        CopyText(
            text=I18nFormat("btn-menu-invite-copy"),
            copy_text=Format("{referral_link}"),
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu-invite-qr"),
            id="qr",
            on_click=on_show_qr,
        ),
        SwitchInlineQueryChosenChatButton(
            text=I18nFormat("btn-menu-invite-send"),
            query=Format("{invite}"),
            allow_user_chats=True,
            allow_group_chats=True,
            allow_channel_chats=True,
            id="send",
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.INVITE,
    getter=invite_getter,
)

invite_about = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-invite-about"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.INVITE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.INVITE_ABOUT,
    getter=invite_about_getter,
)

connect_device_url = Window(
    Banner(BannerName.MENU),
    I18nFormat("msg-menu-connect-device-url"),
    Row(
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
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.CONNECT_DEVICE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.CONNECT_DEVICE_URL,
    getter=connect_device_url_getter,
)

# Экран обмена баллов/дней - показывает баллы и доступные типы обмена
exchange = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange"),
    # Если включено несколько типов обмена - показываем кнопку выбора
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu-exchange-select-type"),
            id="select_type",
            state=MainMenu.EXCHANGE_SELECT_TYPE,
            when=F["has_multiple_types"] & F["has_points"],
        ),
    ),
    # Если включен только один тип - показываем прямые кнопки
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-points"),
            id="exchange_points",
            on_click=on_exchange_points,
            when=~F["has_multiple_types"] & F["subscription_days_available"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-gift"),
            id="exchange_gift",
            on_click=on_exchange_points,
            when=~F["has_multiple_types"] & F["gift_subscription_available"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-discount"),
            id="exchange_discount",
            on_click=on_exchange_points,
            when=~F["has_multiple_types"] & F["discount_available"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-traffic"),
            id="exchange_traffic",
            on_click=on_exchange_points,
            when=~F["has_multiple_types"] & F["traffic_available"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE,
    getter=exchange_getter,
)

# Выбор типа обмена
exchange_select_type = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-select-type"),
    Column(
        Select(
            text=I18nFormat("btn-menu-exchange-type-choice", type=F["item"]["type"], available=F["item"]["available"]),
            id="exchange_type_select",
            item_id_getter=lambda item: item["type"].value,
            items="exchange_types",
            type_factory=str,
            on_click=on_exchange_select_type,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_SELECT_TYPE,
    getter=exchange_select_type_getter,
)

exchange_points = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-points"),
    Column(
        Select(
            text=Format("{item[display_name]}"),
            id="exchange_points_select",
            item_id_getter=lambda item: str(item["id"]),
            items="subscriptions",
            type_factory=int,
            on_click=on_exchange_points_select_subscription,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_POINTS,
    getter=exchange_points_getter,
)

exchange_points_confirm = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-points-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-points-confirm"),
            id="confirm_exchange",
            on_click=on_exchange_points_confirm,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE_POINTS,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_POINTS_CONFIRM,
    getter=exchange_points_confirm_getter,
)

# Обмен на подарочную подписку - информация
exchange_gift = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-gift"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-menu-exchange-gift-select-plan"),
            id="select_plan",
            state=MainMenu.EXCHANGE_GIFT_SELECT_PLAN,
            when=F["can_exchange"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_GIFT,
    getter=exchange_gift_getter,
)

# Выбор плана для подарочной подписки
exchange_gift_select_plan = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-gift-select-plan"),
    Column(
        Select(
            text=Format("{item[display_name]}"),
            id="gift_plan_select",
            item_id_getter=lambda item: str(item["id"]),
            items="plans",
            type_factory=int,
            on_click=on_exchange_gift_select_plan,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE_GIFT,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_GIFT_SELECT_PLAN,
    getter=exchange_gift_select_plan_getter,
)

# Подтверждение обмена на подарочную подписку
exchange_gift_confirm = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-gift-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-gift-confirm"),
            id="confirm_gift",
            on_click=on_exchange_gift_confirm,
            when=F["can_exchange"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE_GIFT_SELECT_PLAN,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_GIFT_CONFIRM,
    getter=exchange_gift_confirm_getter,
)

# Успешный обмен на подарочную подписку - показ промокода
exchange_gift_success = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-gift-success"),
    Row(
        CopyText(
            text=I18nFormat("btn-menu-copy-promocode"),
            copy_text=Format("{promocode}"),
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_GIFT_SUCCESS,
    getter=exchange_gift_success_getter,
)

# Обмен на скидку
exchange_discount = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-discount"),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-discount-confirm"),
            id="confirm_discount",
            on_click=on_exchange_discount_confirm,
            when=F["can_exchange"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_DISCOUNT,
    getter=exchange_discount_getter,
)

# Обмен на трафик - выбор подписки
exchange_traffic = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-traffic"),
    Column(
        Select(
            text=Format("{item[display_name]}"),
            id="traffic_subscription_select",
            item_id_getter=lambda item: str(item["id"]),
            items="subscriptions",
            type_factory=int,
            on_click=on_exchange_traffic_select_subscription,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_TRAFFIC,
    getter=exchange_traffic_getter,
)

# Подтверждение обмена на трафик
exchange_traffic_confirm = Window(
    Banner(BannerName.REFERRAL),
    I18nFormat("msg-menu-exchange-traffic-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-menu-exchange-traffic-confirm"),
            id="confirm_traffic",
            on_click=on_exchange_traffic_confirm,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=MainMenu.EXCHANGE_TRAFFIC,
        ),
    ),
    IgnoreUpdate(),
    state=MainMenu.EXCHANGE_TRAFFIC_CONFIRM,
    getter=exchange_traffic_confirm_getter,
)

router = Dialog(
    menu,
    devices,
    connect_device,
    connect_device_url,
    invite,
    invite_about,
    exchange,
    exchange_select_type,
    exchange_points,
    exchange_points_confirm,
    exchange_gift,
    exchange_gift_select_plan,
    exchange_gift_confirm,
    exchange_gift_success,
    exchange_discount,
    exchange_traffic,
    exchange_traffic_confirm,
)
