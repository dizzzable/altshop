from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.states import Dashboard, DashboardPromocodes
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, PromocodeAvailability, PromocodeRewardType

from .getters import (
    configurator_getter,
    duration_getter,
    list_getter,
    plan_getter,
    reward_getter,
    type_getter,
    availability_getter,
)
from .handlers import (
    on_active_toggle,
    on_availability_select,
    on_code_input,
    on_confirm_promocode,
    on_delete_promocode,
    on_duration_select,
    on_generate_code,
    on_lifetime_input,
    on_max_activations_input,
    on_plan_select,
    on_promocode_select,
    on_reward_input,
    on_search_promocode,
    on_type_select,
)

promocodes = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocodes-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocodes-create"),
            id="create",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocodes-list"),
            id="list",
            state=DashboardPromocodes.LIST,
        ),
        SwitchTo(
            text=I18nFormat("btn-promocodes-search"),
            id="search",
            state=DashboardPromocodes.CODE,
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
    state=DashboardPromocodes.MAIN,
)

promocodes_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocodes-list"),
    Column(
        Select(
            text=Format("{item[display_name]}"),
            id="select_promocode",
            item_id_getter=lambda item: item["id"],
            items="promocodes",
            type_factory=int,
            on_click=on_promocode_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.LIST,
    getter=list_getter,
)

configurator = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-configurator"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode-code"),
            id="code",
            state=DashboardPromocodes.CODE,
        ),
        SwitchTo(
            text=I18nFormat("btn-promocode-type"),
            id="type",
            state=DashboardPromocodes.TYPE,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode-availability"),
            id="availability",
            state=DashboardPromocodes.AVAILABILITY,
        ),
        Button(
            text=I18nFormat("btn-promocode-active", is_active=F["is_active"]),
            id="active_toggle",
            on_click=on_active_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode-reward"),
            id="reward",
            state=DashboardPromocodes.REWARD,
            when=F["reward_type"] != PromocodeRewardType.SUBSCRIPTION,
        ),
        SwitchTo(
            text=I18nFormat("btn-plan-name"),
            id="plan",
            state=DashboardPromocodes.PLAN,
            when=F["reward_type"] == PromocodeRewardType.SUBSCRIPTION,
        ),
        SwitchTo(
            text=I18nFormat("btn-promocode-lifetime"),
            id="lifetime",
            state=DashboardPromocodes.LIFETIME,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-promocode-allowed"),
            id="allowed",
            state=DashboardPromocodes.ALLOWED,
            when=F["availability"] == PromocodeAvailability.ALLOWED,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-promocode-confirm"),
            id="confirm",
            on_click=on_confirm_promocode,
        ),
        Button(
            text=I18nFormat("btn-promocodes-delete"),
            id="delete",
            on_click=on_delete_promocode,
            when=F["id"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.CONFIGURATOR,
    getter=configurator_getter,
)

code_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-code"),
    Row(
        Button(
            text=I18nFormat("btn-promocode-generate"),
            id="generate",
            on_click=on_generate_code,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_code_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.CODE,
)

type_select = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-type"),
    Column(
        Select(
            text=I18nFormat("btn-promocode-type-choice", type=F["item"]["type"]),
            id="select_type",
            item_id_getter=lambda item: item["type"],
            items="types",
            type_factory=str,
            on_click=on_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.TYPE,
    getter=type_getter,
)

availability_select = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-availability"),
    Column(
        Select(
            text=I18nFormat("btn-promocode-availability-choice", type=F["item"]["type"]),
            id="select_availability",
            item_id_getter=lambda item: item["type"],
            items="availabilities",
            type_factory=str,
            on_click=on_availability_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.AVAILABILITY,
    getter=availability_getter,
)

reward_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-reward"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_reward_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.REWARD,
    getter=reward_getter,
)

lifetime_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-lifetime"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_lifetime_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.LIFETIME,
)

allowed_input = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-allowed"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_max_activations_input),
    IgnoreUpdate(),
    state=DashboardPromocodes.ALLOWED,
)

plan_select = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-plan"),
    Column(
        Select(
            text=Format("{item[display_name]}"),
            id="select_plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.PLAN,
    getter=plan_getter,
)

duration_select = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-promocode-duration"),
    Column(
        Select(
            text=Format("{item[display_name]}"),
            id="select_duration",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_duration_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardPromocodes.PLAN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardPromocodes.DURATION,
    getter=duration_getter,
)

router = Dialog(
    promocodes,
    promocodes_list,
    configurator,
    code_input,
    type_select,
    availability_select,
    reward_input,
    lifetime_input,
    allowed_input,
    plan_select,
    duration_select,
)
