from uuid import UUID

from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    CopyText,
    ListGroup,
    Row,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F
from remnawave.enums.users import TrafficLimitStrategy

from src.bot.keyboards import main_menu_button
from src.bot.routers.extra.test import show_dev_popup
from src.bot.states import DashboardRemnashop, RemnashopPlans
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import (
    ArchivedPlanRenewMode,
    BannerName,
    Currency,
    PlanAvailability,
    PlanType,
)

from .getters import (
    allowed_users_getter,
    archived_renew_mode_getter,
    availability_getter,
    configurator_getter,
    description_getter,
    devices_getter,
    durations_getter,
    external_squads_getter,
    internal_squads_getter,
    name_getter,
    plans_getter,
    price_getter,
    prices_getter,
    replacement_plans_getter,
    squads_getter,
    tag_getter,
    traffic_getter,
    type_getter,
    upgrade_plans_getter,
)
from .handlers import (
    on_active_toggle,
    on_allowed_user_input,
    on_allowed_user_remove,
    on_archived_renew_mode_select,
    on_archived_toggle,
    on_availability_select,
    on_confirm_plan,
    on_currency_select,
    on_description_delete,
    on_description_input,
    on_devices_input,
    on_duration_input,
    on_duration_remove,
    on_duration_select,
    on_external_squad_select,
    on_internal_squad_select,
    on_name_input,
    on_plan_configurator_back,
    on_plan_create,
    on_plan_delete,
    on_plan_move,
    on_plan_select,
    on_price_input,
    on_replacement_plan_select,
    on_squads,
    on_strategy_select,
    on_tag_delete,
    on_tag_input,
    on_traffic_input,
    on_type_select,
    on_upgrade_target_select,
)

plans = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plans-main"),
    Row(
        Button(
            I18nFormat("btn-plans-create"),
            id="create",
            on_click=on_plan_create,
        ),
    ),
    ListGroup(
        Row(
            Button(
                text=I18nFormat(
                    "btn-plan",
                    name=F["item"]["name"],
                    is_active=F["item"]["is_active"],
                ),
                id="select_plan",
                on_click=on_plan_select,
            ),
            Button(
                text=Format("🔼"),
                id="move_plan",
                on_click=on_plan_move,
            ),
        ),
        id="plans_list",
        item_id_getter=lambda item: item["id"],
        items="plans",
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardRemnashop.MAIN,
            mode=StartMode.RESET_STACK,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.MAIN,
    getter=plans_getter,
)

configurator = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-configurator"),
    Row(
        Button(
            text=I18nFormat("btn-plan-active", is_active=F["is_active"]),
            id="active_toggle",
            on_click=on_active_toggle,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-plan-archived", is_archived=F["is_archived"]),
            id="archived_toggle",
            on_click=on_archived_toggle,
        ),
        SwitchTo(
            text=I18nFormat("btn-plan-renew-mode", renew_mode=F["archived_renew_mode"]),
            id="renew_mode",
            state=RemnashopPlans.ARCHIVED_RENEW_MODE,
            when=F["is_archived"],
        ),
    ),
    I18nFormat(
        "msg-plan-configurator-transitions",
        is_archived=F["is_archived"],
        renew_mode=F["archived_renew_mode"],
        replacement_count=F["replacement_count"],
        upgrade_count=F["upgrade_count"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-name"),
            id="name",
            state=RemnashopPlans.NAME,
        ),
        SwitchTo(
            text=I18nFormat("btn-plan-description"),
            id="description",
            state=RemnashopPlans.DESCRIPTION,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-availability"),
            id="availability",
            state=RemnashopPlans.AVAILABILITY,
        ),
        SwitchTo(
            text=I18nFormat("btn-plan-type"),
            id="type",
            state=RemnashopPlans.TYPE,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-traffic"),
            id="traffic",
            state=RemnashopPlans.TRAFFIC,
            when=~F["is_unlimited_traffic"],
        ),
        SwitchTo(
            text=I18nFormat("btn-plan-devices"),
            id="devices",
            state=RemnashopPlans.DEVICES,
            when=~F["is_unlimited_devices"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-tag"),
            id="tag",
            state=RemnashopPlans.TAG,
        ),
        Button(
            text=I18nFormat("btn-plan-squads"),
            id="squads",
            on_click=on_squads,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-allowed"),
            id="allowed",
            state=RemnashopPlans.ALLOWED,
            when=F["availability"] == PlanAvailability.ALLOWED,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-replacements", count=F["replacement_count"]),
            id="replacement_plans",
            state=RemnashopPlans.REPLACEMENT_PLANS,
            when=F["is_archived"]
            & (F["archived_renew_mode"] == ArchivedPlanRenewMode.REPLACE_ON_RENEW),
        ),
        SwitchTo(
            text=I18nFormat("btn-plan-upgrades", count=F["upgrade_count"]),
            id="upgrade_plans",
            state=RemnashopPlans.UPGRADE_PLANS,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-durations-prices"),
            id="durations_prices",
            state=RemnashopPlans.DURATIONS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-plan-create"),
            id="create",
            on_click=on_confirm_plan,
        ),
        when=~F["is_edit"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-plan-save"),
            id="save",
            on_click=on_confirm_plan,
        ),
        Button(
            text=I18nFormat("btn-plan-delete"),
            id="delete_plan",
            on_click=on_plan_delete,
        ),
        when=F["is_edit"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-back"),
            id="back",
            on_click=on_plan_configurator_back,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.CONFIGURATOR,
    getter=configurator_getter,
)

plan_name = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-name"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_name_input),
    IgnoreUpdate(),
    state=RemnashopPlans.NAME,
    getter=name_getter,
)

plan_description = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-description"),
    Row(
        Button(
            text=I18nFormat("btn-plan-description-remove"),
            id="remove",
            on_click=on_description_delete,
        ),
        when=F["description"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_description_input),
    IgnoreUpdate(),
    state=RemnashopPlans.DESCRIPTION,
    getter=description_getter,
)

plan_tag = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-tag"),
    Row(
        Button(
            text=I18nFormat("btn-plan-tag-remove"),
            id="remove",
            on_click=on_tag_delete,
        ),
        when=F["tag"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_tag_input),
    IgnoreUpdate(),
    state=RemnashopPlans.TAG,
    getter=tag_getter,
)

plan_type = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-type"),
    Column(
        Select(
            text=I18nFormat("btn-plan-type-choice", type=F["item"]),
            id="select_type",
            item_id_getter=lambda item: item.value,
            items="types",
            type_factory=PlanType,
            on_click=on_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.TYPE,
    getter=type_getter,
)

plan_availability = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-availability"),
    Column(
        Select(
            text=I18nFormat("btn-plan-availability-choice", type=F["item"]),
            id="select_availability",
            item_id_getter=lambda item: item.value,
            items="availability",
            type_factory=PlanAvailability,
            on_click=on_availability_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.AVAILABILITY,
    getter=availability_getter,
)

plan_archived_renew_mode = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-archived-renew-mode"),
    Column(
        Select(
            text=I18nFormat("btn-plan-renew-mode-choice", mode=F["item"]),
            id="select_archived_renew_mode",
            item_id_getter=lambda item: item.value,
            items="renew_modes",
            type_factory=ArchivedPlanRenewMode,
            on_click=on_archived_renew_mode_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.ARCHIVED_RENEW_MODE,
    getter=archived_renew_mode_getter,
)

plan_replacement_plans = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-replacement-plans"),
    Column(
        Select(
            text=I18nFormat(
                "btn-plan-transition-choice",
                name=F["item"]["plan_name"],
                selected=F["item"]["selected"],
            ),
            id="select_replacement_plan",
            item_id_getter=lambda item: item["plan_id"],
            items="plans",
            type_factory=int,
            on_click=on_replacement_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.REPLACEMENT_PLANS,
    getter=replacement_plans_getter,
)

plan_upgrade_plans = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-upgrade-plans"),
    Column(
        Select(
            text=I18nFormat(
                "btn-plan-transition-choice",
                name=F["item"]["plan_name"],
                selected=F["item"]["selected"],
            ),
            id="select_upgrade_plan",
            item_id_getter=lambda item: item["plan_id"],
            items="plans",
            type_factory=int,
            on_click=on_upgrade_target_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.UPGRADE_PLANS,
    getter=upgrade_plans_getter,
)

plan_traffic = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-traffic", traffic_limit=F["traffic_limit"]),
    Column(
        Select(
            text=I18nFormat(
                "btn-plan-traffic-strategy-choice",
                strategy_type=F["item"]["strategy"],
                selected=F["item"]["selected"],
            ),
            id="select_strategy",
            item_id_getter=lambda item: item["strategy"].value,
            items="strategys",
            type_factory=TrafficLimitStrategy,
            on_click=on_strategy_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_traffic_input),
    IgnoreUpdate(),
    state=RemnashopPlans.TRAFFIC,
    getter=traffic_getter,
)

plan_devices = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-devices", device_limit=F["device_limit"]),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_devices_input),
    IgnoreUpdate(),
    state=RemnashopPlans.DEVICES,
    getter=devices_getter,
)

plan_durations = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-durations"),
    ListGroup(
        Row(
            Button(
                text=I18nFormat("btn-plan-duration", value=F["item"]["days"]),
                id="select_duration",
                on_click=on_duration_select,
            ),
            Button(
                text=Format("❌"),
                id="remove_duration",
                on_click=on_duration_remove,
                when=F["data"]["deletable"],
            ),
        ),
        id="duration_list",
        item_id_getter=lambda item: item["days"],
        items="durations",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-duration-add"),
            id="duration_add",
            state=RemnashopPlans.DURATION_ADD,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.DURATIONS,
    getter=durations_getter,
)

plan_durations_add = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-duration"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.DURATIONS,
        ),
    ),
    MessageInput(func=on_duration_input),
    IgnoreUpdate(),
    state=RemnashopPlans.DURATION_ADD,
)

plan_prices = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-prices", value=F["duration"]),
    Column(
        Select(
            text=I18nFormat(
                "btn-plan-price-choice",
                price=F["item"]["price"],
                currency=F["item"]["currency"].value,
            ),
            id="select_price",
            item_id_getter=lambda item: item["currency"].value,
            items="prices",
            type_factory=Currency,
            on_click=on_currency_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.DURATIONS,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.PRICES,
    getter=prices_getter,
)

plan_price = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-price", value=F["duration"], currency=F["currency"]),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.PRICES,
        ),
    ),
    MessageInput(func=on_price_input),
    IgnoreUpdate(),
    state=RemnashopPlans.PRICE,
    getter=price_getter,
)

plan_allowed_users = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-allowed-users"),
    ListGroup(
        Row(
            CopyText(
                text=Format("{item}"),
                copy_text=Format("{item}"),
            ),
            Button(
                text=Format("❌"),
                id="remove_allowed_user",
                on_click=on_allowed_user_remove,
            ),
        ),
        id="allowed_users_list",
        item_id_getter=lambda item: item,
        items="allowed_users",
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    MessageInput(func=on_allowed_user_input),
    IgnoreUpdate(),
    state=RemnashopPlans.ALLOWED,
    getter=allowed_users_getter,
)

plan_squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-squads"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-plan-internal-squads"),
            id="internal",
            state=RemnashopPlans.INTERNAL_SQUADS,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-plan-external-squads"),
            id="external",
            # state=RemnashopPlans.EXTERNAL_SQUADS,
            on_click=show_dev_popup,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPlans.CONFIGURATOR,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.SQUADS,
    getter=squads_getter,
)

plan_internal_squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-internal-squads"),
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
            state=RemnashopPlans.SQUADS,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.INTERNAL_SQUADS,
    getter=internal_squads_getter,
)

plan_external_squads = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-plan-external-squads"),
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
            state=RemnashopPlans.SQUADS,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPlans.EXTERNAL_SQUADS,
    getter=external_squads_getter,
)

router = Dialog(
    plans,
    configurator,
    plan_name,
    plan_description,
    plan_tag,
    plan_type,
    plan_availability,
    plan_archived_renew_mode,
    plan_traffic,
    plan_devices,
    plan_durations,
    plan_durations_add,
    plan_prices,
    plan_price,
    plan_allowed_users,
    plan_replacement_plans,
    plan_upgrade_plans,
    plan_squads,
    plan_internal_squads,
    plan_external_squads,
)
