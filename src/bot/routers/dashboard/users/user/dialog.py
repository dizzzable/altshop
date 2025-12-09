from uuid import UUID

from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    CopyText,
    Group,
    ListGroup,
    Row,
    ScrollingGroup,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import back_main_menu_button
from src.bot.routers.dashboard.broadcast.handlers import on_content_input, on_preview
from src.bot.routers.extra.test import show_dev_popup
from src.bot.states import DashboardUser, DashboardUsers
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, SubscriptionStatus, UserRole

from .getters import (
    device_limit_getter,
    devices_getter,
    discount_getter,
    expire_time_getter,
    external_squads_getter,
    give_access_getter,
    give_subscription_getter,
    internal_squads_getter,
    partner_accrual_strategy_getter,
    partner_balance_getter,
    partner_fixed_getter,
    partner_getter,
    partner_percent_getter,
    partner_reward_type_getter,
    partner_settings_getter,
    points_getter,
    role_getter,
    squads_getter,
    subscription_duration_getter,
    subscription_getter,
    traffic_limit_getter,
    transaction_getter,
    transactions_getter,
    user_getter,
)
from .handlers import (
    on_active_toggle,
    on_block_toggle,
    on_current_subscription,
    on_device_delete,
    on_device_limit_input,
    on_device_limit_select,
    on_devices,
    on_discount_input,
    on_discount_select,
    on_duration_input,
    on_duration_select,
    on_external_squad_select,
    on_give_access,
    on_give_subscription,
    on_internal_squad_select,
    on_partner,
    on_partner_accrual_strategy_select,
    on_partner_balance,
    on_partner_balance_input,
    on_partner_balance_select,
    on_partner_create,
    on_partner_delete,
    on_partner_fixed_input,
    on_partner_fixed_level_select,
    on_partner_percent_input,
    on_partner_percent_level_select,
    on_partner_reward_type_select,
    on_partner_settings,
    on_partner_toggle,
    on_partner_use_global_toggle,
    on_plan_select,
    on_points_input,
    on_points_select,
    on_reset_traffic,
    on_role_select,
    on_send,
    on_subscription_delete,
    on_subscription_duration_select,
    on_subscription_select,
    on_sync,
    on_traffic_limit_input,
    on_traffic_limit_select,
    on_transaction_select,
    on_transactions,
)

user = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-main"),
    Row(
        Button(
            text=I18nFormat("btn-user-current-subscription"),
            id="subscription",
            on_click=on_current_subscription,
        ),
        when=F["has_subscription"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-statistics"),
            id="statistics",
            on_click=show_dev_popup,
        ),
        Button(
            text=I18nFormat("btn-user-transactions"),
            id="transactions",
            on_click=on_transactions,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-sync"),
            id="sync",
            on_click=on_sync,
        ),
        Button(
            text=I18nFormat("btn-user-give-subscription"),
            id="give_subscription",
            on_click=on_give_subscription,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-message"),
            id="message",
            state=DashboardUser.MESSAGE,
        ),
        Button(
            text=I18nFormat("btn-user-give-access"),
            id="give_access",
            on_click=on_give_access,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-discount"),
            id="discount",
            state=DashboardUser.DISCOUNT,
        ),
        SwitchTo(
            text=I18nFormat("btn-user-points"),
            id="points",
            state=DashboardUser.POINTS,
            when=F["show_points"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-role"),
            id="role",
            state=DashboardUser.ROLE,
            when=F["is_not_self"] & F["can_edit"],
        ),
        Button(
            text=I18nFormat("btn-user-block", is_blocked=F["is_blocked"]),
            id="block",
            on_click=on_block_toggle,
            when=F["is_not_self"] & F["can_edit"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-partner", is_partner=F["is_partner"]),
            id="partner",
            on_click=on_partner,
            when=F["can_edit"],
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back-dashboard"),
            id="back",
            state=DashboardUsers.MAIN,
            mode=StartMode.RESET_STACK,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=DashboardUser.MAIN,
    getter=user_getter,
)

subscription = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-info"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-subscription-traffic-limit"),
            id="traffic",
            state=DashboardUser.TRAFFIC_LIMIT,
        ),
        SwitchTo(
            text=I18nFormat("btn-user-subscription-device-limit"),
            id="device",
            state=DashboardUser.DEVICE_LIMIT,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-subscription-traffic-reset"),
            id="reset",
            on_click=on_reset_traffic,
        ),
        Button(
            text=I18nFormat("btn-user-subscription-devices"),
            id="devices",
            on_click=on_devices,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-subscription-expire-time"),
            id="expire_time",
            state=DashboardUser.EXPIRE_TIME,
        ),
        SwitchTo(
            text=I18nFormat("btn-user-subscription-squads"),
            id="squads",
            state=DashboardUser.SQUADS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-subscription-active-toggle", is_active=F["is_active"]),
            id="active_toggle",
            on_click=on_active_toggle,
            when=F["subscription_status"].in_(
                [SubscriptionStatus.ACTIVE, SubscriptionStatus.DISABLED]
            ),
        ),
        Button(
            text=I18nFormat("btn-user-subscription-delete"),
            id="delete",
            on_click=on_subscription_delete,
        ),
    ),
    Row(
        CopyText(
            text=I18nFormat("btn-user-subscription-url"),
            copy_text=Format("{url}"),
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.SUBSCRIPTION,
    getter=subscription_getter,
)

traffic_limit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-traffic-limit"),
    Group(
        Select(
            text=I18nFormat("{item[traffic_limit][0]}", value=F["item"]["traffic"]),
            id="traffic_limit_select",
            item_id_getter=lambda item: item["traffic"],
            items="traffic_count",
            type_factory=int,
            on_click=on_traffic_limit_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    MessageInput(func=on_traffic_limit_input),
    IgnoreUpdate(),
    state=DashboardUser.TRAFFIC_LIMIT,
    getter=traffic_limit_getter,
)

device_limit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-device-limit"),
    Group(
        Select(
            text=I18nFormat("unit-device", value=F["item"]),
            id="device_limit_select",
            item_id_getter=lambda item: item,
            items="devices_count",
            type_factory=int,
            on_click=on_device_limit_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    MessageInput(func=on_device_limit_input),
    IgnoreUpdate(),
    state=DashboardUser.DEVICE_LIMIT,
    getter=device_limit_getter,
)

expire_time = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-expire-time"),
    Group(
        Select(
            text=Format("{item[operation]}{item[duration]}"),
            id="duration_select",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_duration_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    MessageInput(func=on_duration_input),
    IgnoreUpdate(),
    state=DashboardUser.EXPIRE_TIME,
    getter=expire_time_getter,
)

squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-squads"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-subscription-internal-squads"),
            id="internal",
            state=DashboardUser.INTERNAL_SQUADS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-subscription-external-squads"),
            id="external",
            # state=DashboardUser.EXTERNAL_SQUADS,
            on_click=show_dev_popup,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.SQUADS,
    getter=squads_getter,
)

internal_squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-internal-squads"),
    Column(
        Select(
            text=I18nFormat(
                "btn-squad-choice",
                name=F["item"]["name"],
                selected=F["item"]["selected"],
            ),
            id="select_squad",
            item_id_getter=lambda item: item["uuid"],
            items="squads",
            type_factory=UUID,
            on_click=on_internal_squad_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SQUADS,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.INTERNAL_SQUADS,
    getter=internal_squads_getter,
)

external_squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-subscription-external-squads"),
    Column(
        Select(
            text=I18nFormat(
                "btn-squad-choice",
                name=F["item"]["name"],
                selected=F["item"]["selected"],
            ),
            id="select_squad",
            item_id_getter=lambda item: item["uuid"],
            items="squads",
            type_factory=UUID,
            on_click=on_external_squad_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SQUADS,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.EXTERNAL_SQUADS,
    getter=external_squads_getter,
)

devices_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-devices"),
    ListGroup(
        Row(
            CopyText(
                text=Format("{item[platform]} - {item[device_model]}"),
                copy_text=Format("{item[user_agent]}"),
            ),
            Button(
                text=Format("❌"),
                id="delete",
                on_click=on_device_delete,
            ),
        ),
        id="devices_list",
        item_id_getter=lambda item: item["hwid"],
        items="devices",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.SUBSCRIPTION,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.DEVICES_LIST,
    getter=devices_getter,
)

give_subscription = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-give-subscription"),
    Column(
        Select(
            text=Format("{item[plan_name]}"),
            id="plan_select",
            item_id_getter=lambda item: item["plan_id"],
            items="plans",
            type_factory=int,
            on_click=on_subscription_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.GIVE_SUBSCRIPTION,
    getter=give_subscription_getter,
)

subscription_duration = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-give-subscription-duration"),
    Group(
        Select(
            text=I18nFormat(
                "btn-plan-duration",
                value=F["item"]["days"],
            ),
            id="duration_select",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_subscription_duration_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.GIVE_SUBSCRIPTION,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.SUBSCRIPTION_DURATION,
    getter=subscription_duration_getter,
)

transactions_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-transactions"),
    ScrollingGroup(
        Select(
            text=I18nFormat(
                "btn-user-transaction",
                status=F["item"]["status"],
                created_at=F["item"]["created_at"],
            ),
            id="transaction_select",
            item_id_getter=lambda item: item["payment_id"],
            items="transactions",
            type_factory=UUID,
            on_click=on_transaction_select,
        ),
        id="scroll",
        width=1,
        height=7,
        hide_on_single_page=True,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.TRANSACTIONS_LIST,
    getter=transactions_getter,
)

transaction = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-transaction-info"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.TRANSACTIONS_LIST,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.TRANSACTION,
    getter=transaction_getter,
)

message = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-message"),
    Row(
        Button(
            I18nFormat("btn-user-message-preview"),
            id="preview",
            on_click=on_preview,
        ),
    ),
    Row(
        Button(
            I18nFormat("btn-user-message-confirm"),
            id="confirm",
            on_click=on_send,
        ),
    ),
    Row(
        SwitchTo(
            I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    MessageInput(func=on_content_input),
    IgnoreUpdate(),
    state=DashboardUser.MESSAGE,
)

discount = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-discount"),
    Group(
        Select(
            text=Format("{item}%"),
            id="discount_select",
            item_id_getter=lambda item: item,
            items="percentages",
            type_factory=int,
            on_click=on_discount_select,
        ),
        width=3,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    MessageInput(func=on_discount_input),
    IgnoreUpdate(),
    state=DashboardUser.DISCOUNT,
    getter=discount_getter,
)

points = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-points"),
    Group(
        Select(
            text=Format("{item[operation]}{item[points]} 💎"),
            id="points_select",
            item_id_getter=lambda item: item["points"],
            items="points",
            type_factory=int,
            on_click=on_points_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    MessageInput(func=on_points_input),
    IgnoreUpdate(),
    state=DashboardUser.POINTS,
    getter=points_getter,
)

give_access = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-give-access"),
    Column(
        Select(
            text=I18nFormat(
                "btn-user-allowed-plan-choice",
                plan_name=F["item"]["plan_name"],
                selected=F["item"]["selected"],
            ),
            id="plan_select",
            item_id_getter=lambda item: item["plan_id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.GIVE_ACCESS,
    getter=give_access_getter,
)

role = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-role"),
    Column(
        Select(
            text=I18nFormat("role", role=F["item"]),
            id="role_select",
            item_id_getter=lambda item: item.value,
            items="roles",
            type_factory=UserRole,
            on_click=on_role_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.ROLE,
    getter=role_getter,
)

# Партнерская программа пользователя
partner = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner"),
    Row(
        Button(
            text=I18nFormat("btn-user-partner-create"),
            id="partner_create",
            on_click=on_partner_create,
            when=~F["is_partner"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-partner-balance"),
            id="partner_balance",
            on_click=on_partner_balance,
            when=F["is_partner"],
        ),
        Button(
            text=I18nFormat("btn-user-partner-settings"),
            id="partner_settings",
            on_click=on_partner_settings,
            when=F["is_partner"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-user-partner-toggle", is_active=F["is_active"]),
            id="partner_toggle",
            on_click=on_partner_toggle,
            when=F["is_partner"],
        ),
        Button(
            text=I18nFormat("btn-user-partner-delete"),
            id="partner_delete",
            on_click=on_partner_delete,
            when=F["is_partner"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER,
    getter=partner_getter,
)


# Управление балансом партнера
partner_balance = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner-balance"),
    Group(
        Select(
            text=Format("{item[operation]}{item[amount]} ₽"),
            id="balance_select",
            item_id_getter=lambda item: item["amount"],
            items="amounts",
            type_factory=int,
            on_click=on_partner_balance_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.PARTNER,
        ),
    ),
    MessageInput(func=on_partner_balance_input),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER_BALANCE,
    getter=partner_balance_getter,
)

# Индивидуальные настройки партнера
partner_settings = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner-settings"),
    Row(
        Button(
            text=I18nFormat("btn-user-partner-use-global", use_global=F["use_global_settings"]),
            id="use_global_toggle",
            on_click=on_partner_use_global_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-partner-accrual-strategy"),
            id="accrual_strategy",
            state=DashboardUser.PARTNER_SETTINGS_ACCRUAL,
            when=~F["use_global_settings"],
        ),
        SwitchTo(
            text=I18nFormat("btn-user-partner-reward-type"),
            id="reward_type",
            state=DashboardUser.PARTNER_SETTINGS_REWARD,
            when=~F["use_global_settings"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-user-partner-percents"),
            id="percents",
            state=DashboardUser.PARTNER_SETTINGS_PERCENT,
            when=~F["use_global_settings"] & ~F["is_fixed_amount"],
        ),
        SwitchTo(
            text=I18nFormat("btn-user-partner-fixed-amounts"),
            id="fixed_amounts",
            state=DashboardUser.PARTNER_SETTINGS_FIXED,
            when=~F["use_global_settings"] & F["is_fixed_amount"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.PARTNER,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER_SETTINGS,
    getter=partner_settings_getter,
)


# Выбор стратегии начисления
partner_settings_accrual = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner-accrual-strategy"),
    Column(
        Select(
            text=Format("{item[name]}"),
            id="strategy_select",
            item_id_getter=lambda item: item["value"],
            items="strategies",
            type_factory=str,
            on_click=on_partner_accrual_strategy_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.PARTNER_SETTINGS,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER_SETTINGS_ACCRUAL,
    getter=partner_accrual_strategy_getter,
)


# Выбор типа вознаграждения
partner_settings_reward = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner-reward-type"),
    Column(
        Select(
            text=Format("{item[name]}"),
            id="reward_type_select",
            item_id_getter=lambda item: item["value"],
            items="reward_types",
            type_factory=str,
            on_click=on_partner_reward_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.PARTNER_SETTINGS,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER_SETTINGS_REWARD,
    getter=partner_reward_type_getter,
)


# Настройка индивидуальных процентов
partner_settings_percent = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner-percent"),
    I18nFormat("msg-user-partner-percent-level1"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="percent_l1_select",
            item_id_getter=lambda item: f"1:{item['value']}",
            items="percentages",
            type_factory=str,
            on_click=on_partner_percent_level_select,
        ),
        width=5,
    ),
    I18nFormat("msg-user-partner-percent-level2"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="percent_l2_select",
            item_id_getter=lambda item: f"2:{item['value']}",
            items="percentages",
            type_factory=str,
            on_click=on_partner_percent_level_select,
        ),
        width=5,
    ),
    I18nFormat("msg-user-partner-percent-level3"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="percent_l3_select",
            item_id_getter=lambda item: f"3:{item['value']}",
            items="percentages",
            type_factory=str,
            on_click=on_partner_percent_level_select,
        ),
        width=5,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.PARTNER_SETTINGS,
        ),
    ),
    MessageInput(func=on_partner_percent_input),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER_SETTINGS_PERCENT,
    getter=partner_percent_getter,
)


# Настройка фиксированных сумм
partner_settings_fixed = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-user-partner-fixed"),
    I18nFormat("msg-user-partner-fixed-level1"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="fixed_l1_select",
            item_id_getter=lambda item: f"1:{item['value']}",
            items="amounts",
            type_factory=str,
            on_click=on_partner_fixed_level_select,
        ),
        width=4,
    ),
    I18nFormat("msg-user-partner-fixed-level2"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="fixed_l2_select",
            item_id_getter=lambda item: f"2:{item['value']}",
            items="amounts",
            type_factory=str,
            on_click=on_partner_fixed_level_select,
        ),
        width=4,
    ),
    I18nFormat("msg-user-partner-fixed-level3"),
    Group(
        Select(
            text=Format("{item[label]}"),
            id="fixed_l3_select",
            item_id_getter=lambda item: f"3:{item['value']}",
            items="amounts",
            type_factory=str,
            on_click=on_partner_fixed_level_select,
        ),
        width=4,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardUser.PARTNER_SETTINGS,
        ),
    ),
    MessageInput(func=on_partner_fixed_input),
    IgnoreUpdate(),
    state=DashboardUser.PARTNER_SETTINGS_FIXED,
    getter=partner_fixed_getter,
)


router = Dialog(
    user,
    subscription,
    traffic_limit,
    device_limit,
    expire_time,
    squads,
    internal_squads,
    external_squads,
    devices_list,
    give_subscription,
    subscription_duration,
    transactions_list,
    transaction,
    message,
    discount,
    points,
    give_access,
    role,
    partner,
    partner_balance,
    partner_settings,
    partner_settings_accrual,
    partner_settings_reward,
    partner_settings_percent,
    partner_settings_fixed,
)
