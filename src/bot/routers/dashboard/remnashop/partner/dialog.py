from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, Row, ScrollingGroup, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.routers.dashboard.remnashop.partner.getters import (
    gateway_fee_edit_getter,
    gateway_fees_getter,
    level_percent_getter,
    level_percents_getter,
    min_withdrawal_getter,
    partner_main_getter,
    tax_settings_getter,
    withdrawal_details_getter,
    withdrawals_list_getter,
)
from src.bot.routers.dashboard.remnashop.partner.handlers import (
    on_admin_comment_input,
    on_enable_toggle,
    on_gateway_fee_input,
    on_gateway_fee_select,
    on_level_percent_input,
    on_level_select,
    on_min_withdrawal_input,
    on_tax_percent_input,
    on_withdrawal_approve,
    on_withdrawal_pending,
    on_withdrawal_reject,
    on_withdrawal_select,
)
from src.bot.states import DashboardRemnashop, RemnashopPartner
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName, PartnerLevel

# Главное окно настроек партнерской программы
partner_main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-admin-main"),
    Row(
        Button(
            text=I18nFormat("btn-partner-enable"),
            id="enable",
            on_click=on_enable_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-partner-level-percents"),
            id="level_percents",
            state=RemnashopPartner.LEVEL_PERCENTS,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-partner-tax-settings"),
            id="tax_settings",
            state=RemnashopPartner.TAX_SETTINGS,
        ),
        SwitchTo(
            text=I18nFormat("btn-partner-gateway-fees"),
            id="gateway_fees",
            state=RemnashopPartner.GATEWAY_FEES,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-partner-min-withdrawal"),
            id="min_withdrawal",
            state=RemnashopPartner.MIN_WITHDRAWAL,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-partner-withdrawals", count=F["pending_withdrawals"]),
            id="withdrawals",
            state=RemnashopPartner.WITHDRAWALS_LIST,
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
    state=RemnashopPartner.MAIN,
    getter=partner_main_getter,
)

# Настройка процентов по уровням
level_percents = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-level-percents"),
    Column(
        Select(
            text=I18nFormat("btn-partner-level-choice", level=F["item"]),
            id="select_level",
            item_id_getter=lambda item: item.value,
            items="levels",
            type_factory=int,
            on_click=on_level_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPartner.LEVEL_PERCENTS,
    getter=level_percents_getter,
)

# Редактирование процента уровня 1
level_1_percent = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-level-percent-edit"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.LEVEL_PERCENTS,
        ),
    ),
    MessageInput(func=on_level_percent_input),
    IgnoreUpdate(),
    state=RemnashopPartner.LEVEL_1_PERCENT,
    getter=level_percent_getter,
)

# Редактирование процента уровня 2
level_2_percent = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-level-percent-edit"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.LEVEL_PERCENTS,
        ),
    ),
    MessageInput(func=on_level_percent_input),
    IgnoreUpdate(),
    state=RemnashopPartner.LEVEL_2_PERCENT,
    getter=level_percent_getter,
)

# Редактирование процента уровня 3
level_3_percent = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-level-percent-edit"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.LEVEL_PERCENTS,
        ),
    ),
    MessageInput(func=on_level_percent_input),
    IgnoreUpdate(),
    state=RemnashopPartner.LEVEL_3_PERCENT,
    getter=level_percent_getter,
)

# Настройки налогов
tax_settings = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-tax-settings"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.MAIN,
        ),
    ),
    MessageInput(func=on_tax_percent_input),
    IgnoreUpdate(),
    state=RemnashopPartner.TAX_SETTINGS,
    getter=tax_settings_getter,
)

# Список комиссий платежных систем
gateway_fees = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-gateway-fees"),
    Column(
        Select(
            text=Format("{item[name]}: {item[percent]}%"),
            id="select_gateway",
            item_id_getter=lambda item: item["gateway_id"],
            items="gateway_fees",
            type_factory=str,
            on_click=on_gateway_fee_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPartner.GATEWAY_FEES,
    getter=gateway_fees_getter,
)

# Редактирование комиссии платежной системы
gateway_fee_edit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-gateway-fee-edit"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.GATEWAY_FEES,
        ),
    ),
    MessageInput(func=on_gateway_fee_input),
    IgnoreUpdate(),
    state=RemnashopPartner.GATEWAY_FEE_EDIT,
    getter=gateway_fee_edit_getter,
)

# Минимальная сумма вывода
min_withdrawal = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-min-withdrawal"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.MAIN,
        ),
    ),
    MessageInput(func=on_min_withdrawal_input),
    IgnoreUpdate(),
    state=RemnashopPartner.MIN_WITHDRAWAL,
    getter=min_withdrawal_getter,
)

# Список запросов на вывод
withdrawals_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-withdrawals-list"),
    ScrollingGroup(
        Select(
            text=I18nFormat(
                "btn-partner-withdrawal-item",
                amount=F["item"]["amount_rubles"],
                status=F["item"]["status"],
                created_at=F["item"]["created_at"],
            ),
            id="withdrawal_select",
            item_id_getter=lambda item: item["id"],
            items="withdrawals",
            type_factory=str,
            on_click=on_withdrawal_select,
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
            state=RemnashopPartner.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopPartner.WITHDRAWALS_LIST,
    getter=withdrawals_list_getter,
)

# Детали запроса на вывод
withdrawal_details = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-partner-withdrawal-details"),
    Row(
        Button(
            text=I18nFormat("btn-partner-withdrawal-approve"),
            id="approve",
            on_click=on_withdrawal_approve,
        ),
        Button(
            text=I18nFormat("btn-partner-withdrawal-pending"),
            id="pending",
            on_click=on_withdrawal_pending,
        ),
        Button(
            text=I18nFormat("btn-partner-withdrawal-reject"),
            id="reject",
            on_click=on_withdrawal_reject,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopPartner.WITHDRAWALS_LIST,
        ),
    ),
    MessageInput(func=on_admin_comment_input),
    IgnoreUpdate(),
    state=RemnashopPartner.WITHDRAWAL_DETAILS,
    getter=withdrawal_details_getter,
)

router = Dialog(
    partner_main,
    level_percents,
    level_1_percent,
    level_2_percent,
    level_3_percent,
    tax_settings,
    gateway_fees,
    gateway_fee_edit,
    min_withdrawal,
    withdrawals_list,
    withdrawal_details,
)