from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.routers.dashboard.remnashop.referral.getters import (
    accrual_strategy_getter,
    eligible_plans_getter,
    exchange_gift_plan_getter,
    exchange_type_settings_getter,
    exchange_types_getter,
    level_getter,
    max_exchange_points_getter,
    min_exchange_points_getter,
    points_exchange_getter,
    points_per_day_getter,
    referral_getter,
    reward_getter,
    reward_strategy_getter,
    reward_type_getter,
)
from src.bot.routers.dashboard.remnashop.referral.handlers import (
    on_accrual_strategy_select,
    on_clear_eligible_plans,
    on_discount_max_input,
    on_eligible_plan_select,
    on_enable_toggle,
    on_exchange_toggle,
    on_exchange_type_cost_input,
    on_exchange_type_max_input,
    on_exchange_type_min_input,
    on_exchange_type_select,
    on_exchange_type_toggle,
    on_gift_duration_input,
    on_gift_plan_select,
    on_level_select,
    on_max_exchange_points_input,
    on_min_exchange_points_input,
    on_points_per_day_input,
    on_reward_input,
    on_reward_select,
    on_reward_strategy_select,
    on_traffic_max_input,
)
from src.bot.states import DashboardRemnashop, RemnashopReferral
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import (
    BannerName,
    PointsExchangeType,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)

referral = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-main"),
    Row(
        Button(
            text=I18nFormat("btn-referral-enable"),
            id="enable",
            on_click=on_enable_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-level"),
            id="level",
            state=RemnashopReferral.LEVEL,
        ),
        SwitchTo(
            text=I18nFormat("btn-referral-reward-type"),
            id="reward_type",
            state=RemnashopReferral.REWARD_TYPE,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-accrual-strategy"),
            id="accrual_strategy",
            state=RemnashopReferral.ACCRUAL_STRATEGY,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-reward-strategy"),
            id="reward_strategy",
            state=RemnashopReferral.REWARD_STRATEGY,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-reward"),
            id="reward",
            state=RemnashopReferral.REWARD,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-eligible-plans"),
            id="eligible_plans",
            state=RemnashopReferral.ELIGIBLE_PLANS,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-points-exchange"),
            id="points_exchange",
            state=RemnashopReferral.POINTS_EXCHANGE,
            when=F["is_enable"],
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
    state=RemnashopReferral.MAIN,
    getter=referral_getter,
)

level = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-level"),
    Row(
        Select(
            text=I18nFormat("btn-referral-level-choice", type=F["item"]),
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
            state=RemnashopReferral.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.LEVEL,
    getter=level_getter,
)

reward_type = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-reward-type"),
    Column(
        Select(
            text=I18nFormat("btn-referral-reward-choice", type=F["item"]),
            id="select_reward",
            item_id_getter=lambda item: item.value,
            items="rewards",
            type_factory=ReferralRewardType,
            on_click=on_reward_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.REWARD_TYPE,
    getter=reward_type_getter,
)

reward = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-reward"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.MAIN,
        ),
    ),
    MessageInput(func=on_reward_input),
    IgnoreUpdate(),
    state=RemnashopReferral.REWARD,
    getter=reward_getter,
)

accrual_strategy = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-accrual-strategy"),
    Column(
        Select(
            text=I18nFormat("btn-referral-accrual-strategy-choice", type=F["item"]),
            id="select_strategy",
            item_id_getter=lambda item: item.value,
            items="strategys",
            type_factory=ReferralAccrualStrategy,
            on_click=on_accrual_strategy_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.ACCRUAL_STRATEGY,
    getter=accrual_strategy_getter,
)

reward_strategy = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-reward-strategy"),
    Column(
        Select(
            text=I18nFormat("btn-referral-reward-strategy-choice", type=F["item"]),
            id="select_strategy",
            item_id_getter=lambda item: item.value,
            items="strategys",
            type_factory=ReferralRewardStrategy,
            on_click=on_reward_strategy_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.REWARD_STRATEGY,
    getter=reward_strategy_getter,
)

eligible_plans = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-eligible-plans"),
    Column(
        Select(
            text=I18nFormat(
                "btn-referral-eligible-plan-choice",
                selected=F["item"]["selected"],
                is_active=F["item"]["is_active"],
                plan_name=F["item"]["name"],
            ),
            id="select_plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_eligible_plan_select,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-referral-clear-filter"),
            id="clear_filter",
            on_click=on_clear_eligible_plans,
            when=F["has_filter"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.ELIGIBLE_PLANS,
    getter=eligible_plans_getter,
)

# Настройки обмена баллов
points_exchange = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-points-exchange"),
    Row(
        Button(
            text=I18nFormat("btn-referral-exchange-enable"),
            id="exchange_toggle",
            on_click=on_exchange_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-exchange-types"),
            id="exchange_types",
            state=RemnashopReferral.EXCHANGE_TYPES,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-points-per-day"),
            id="points_per_day",
            state=RemnashopReferral.POINTS_PER_DAY,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-min-exchange"),
            id="min_exchange",
            state=RemnashopReferral.MIN_EXCHANGE_POINTS,
        ),
        SwitchTo(
            text=I18nFormat("btn-referral-max-exchange"),
            id="max_exchange",
            state=RemnashopReferral.MAX_EXCHANGE_POINTS,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.POINTS_EXCHANGE,
    getter=points_exchange_getter,
)

# Список типов обмена
exchange_types = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-exchange-types"),
    Column(
        Select(
            text=I18nFormat("btn-referral-exchange-type-choice", type=F["item"]["type"], enabled=F["item"]["enabled"]),
            id="select_exchange_type",
            item_id_getter=lambda item: item["type"].value,
            items="exchange_types",
            type_factory=str,
            on_click=on_exchange_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.POINTS_EXCHANGE,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_TYPES,
    getter=exchange_types_getter,
)

# Настройки конкретного типа обмена
exchange_type_settings = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-exchange-type-settings"),
    Row(
        Button(
            text=I18nFormat("btn-referral-exchange-type-enable"),
            id="type_toggle",
            on_click=on_exchange_type_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-exchange-type-cost"),
            id="type_cost",
            state=RemnashopReferral.EXCHANGE_TYPE_COST,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-exchange-type-min"),
            id="type_min",
            state=RemnashopReferral.EXCHANGE_TYPE_MIN,
        ),
        SwitchTo(
            text=I18nFormat("btn-referral-exchange-type-max"),
            id="type_max",
            state=RemnashopReferral.EXCHANGE_TYPE_MAX,
        ),
    ),
    # Дополнительные настройки для подарочной подписки
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-gift-plan"),
            id="gift_plan",
            state=RemnashopReferral.EXCHANGE_GIFT_PLAN,
            when=F["exchange_type"] == PointsExchangeType.GIFT_SUBSCRIPTION,
        ),
        SwitchTo(
            text=I18nFormat("btn-referral-gift-duration"),
            id="gift_duration",
            state=RemnashopReferral.EXCHANGE_GIFT_DURATION,
            when=F["exchange_type"] == PointsExchangeType.GIFT_SUBSCRIPTION,
        ),
    ),
    # Дополнительные настройки для скидки
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-discount-max"),
            id="discount_max",
            state=RemnashopReferral.EXCHANGE_DISCOUNT_MAX,
            when=F["exchange_type"] == PointsExchangeType.DISCOUNT,
        ),
    ),
    # Дополнительные настройки для трафика
    Row(
        SwitchTo(
            text=I18nFormat("btn-referral-traffic-max"),
            id="traffic_max",
            state=RemnashopReferral.EXCHANGE_TRAFFIC_MAX,
            when=F["exchange_type"] == PointsExchangeType.TRAFFIC,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPES,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
    getter=exchange_type_settings_getter,
)

# Ввод стоимости в баллах
exchange_type_cost = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-exchange-type-cost"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    MessageInput(func=on_exchange_type_cost_input),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_TYPE_COST,
    getter=exchange_type_settings_getter,
)

# Ввод минимума баллов
exchange_type_min = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-exchange-type-min"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    MessageInput(func=on_exchange_type_min_input),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_TYPE_MIN,
    getter=exchange_type_settings_getter,
)

# Ввод максимума баллов
exchange_type_max = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-exchange-type-max"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    MessageInput(func=on_exchange_type_max_input),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_TYPE_MAX,
    getter=exchange_type_settings_getter,
)

# Выбор плана для подарочной подписки
exchange_gift_plan = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-gift-plan"),
    Column(
        Select(
            text=I18nFormat(
                "btn-referral-gift-plan-choice",
                selected=F["item"]["selected"],
                is_active=F["item"]["is_active"],
                plan_name=F["item"]["name"],
            ),
            id="select_gift_plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_gift_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_GIFT_PLAN,
    getter=exchange_gift_plan_getter,
)

# Ввод длительности подарочной подписки
exchange_gift_duration = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-gift-duration"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    MessageInput(func=on_gift_duration_input),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_GIFT_DURATION,
    getter=exchange_type_settings_getter,
)

# Ввод максимального процента скидки
exchange_discount_max = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-discount-max"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    MessageInput(func=on_discount_max_input),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_DISCOUNT_MAX,
    getter=exchange_type_settings_getter,
)

# Ввод максимального количества ГБ трафика
exchange_traffic_max = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-traffic-max"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS,
        ),
    ),
    MessageInput(func=on_traffic_max_input),
    IgnoreUpdate(),
    state=RemnashopReferral.EXCHANGE_TRAFFIC_MAX,
    getter=exchange_type_settings_getter,
)

points_per_day = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-points-per-day"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.POINTS_EXCHANGE,
        ),
    ),
    MessageInput(func=on_points_per_day_input),
    IgnoreUpdate(),
    state=RemnashopReferral.POINTS_PER_DAY,
    getter=points_per_day_getter,
)

min_exchange_points = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-min-exchange-points"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.POINTS_EXCHANGE,
        ),
    ),
    MessageInput(func=on_min_exchange_points_input),
    IgnoreUpdate(),
    state=RemnashopReferral.MIN_EXCHANGE_POINTS,
    getter=min_exchange_points_getter,
)

max_exchange_points = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-referral-max-exchange-points"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopReferral.POINTS_EXCHANGE,
        ),
    ),
    MessageInput(func=on_max_exchange_points_input),
    IgnoreUpdate(),
    state=RemnashopReferral.MAX_EXCHANGE_POINTS,
    getter=max_exchange_points_getter,
)

router = Dialog(
    referral,
    level,
    reward_type,
    accrual_strategy,
    reward_strategy,
    reward,
    eligible_plans,
    points_exchange,
    points_per_day,
    min_exchange_points,
    max_exchange_points,
    # Новые окна для типов обмена
    exchange_types,
    exchange_type_settings,
    exchange_type_cost,
    exchange_type_min,
    exchange_type_max,
    exchange_gift_plan,
    exchange_gift_duration,
    exchange_discount_max,
    exchange_traffic_max,
)
