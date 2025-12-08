from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Column, CopyText, Group, Row, Select, SwitchTo, Url
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import back_main_menu_button, connect_buttons
from src.bot.states import Subscription
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.constants import PURCHASE_PREFIX
from src.core.enums import BannerName, DeviceType, PaymentGatewayType, PurchaseType

from .getters import (
    confirm_delete_getter,
    confirm_getter,
    confirm_renew_selection_getter,
    device_type_getter,
    duration_getter,
    getter_connect,
    my_subscriptions_getter,
    payment_method_getter,
    plans_getter,
    promocode_confirm_new_getter,
    promocode_select_subscription_getter,
    select_subscription_for_renew_getter,
    subscription_details_getter,
    subscription_getter,
    success_payment_getter,
)
from .handlers import (
    on_cancel_delete_subscription,
    on_confirm_delete_subscription,
    on_confirm_renew_selection,
    on_delete_subscription,
    on_device_type_select,
    on_duration_select,
    on_get_subscription,
    on_payment_method_select,
    on_plan_select,
    on_promocode_create_new_subscription,
    on_promocode_input,
    on_promocode_select_subscription,
    on_renew_selected_subscription,
    on_subscription_for_renew_select,
    on_subscription_for_renew_toggle,
    on_subscription_plans,
    on_subscription_select,
)

subscription = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-main"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-my-subscriptions", count=F["subscriptions_count"]),
            id=f"{PURCHASE_PREFIX}my_subscriptions",
            state=Subscription.MY_SUBSCRIPTIONS,
            when=F["has_subscriptions"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-subscription-new"),
            id=f"{PURCHASE_PREFIX}{PurchaseType.NEW}",
            on_click=on_subscription_plans,
            when=~F["has_active_subscription"],
        ),
        Button(
            text=I18nFormat("btn-subscription-renew"),
            id=f"{PURCHASE_PREFIX}{PurchaseType.RENEW}",
            on_click=on_subscription_plans,
            when=F["has_active_subscription"] & F["is_not_unlimited"],
        ),
        Button(
            text=I18nFormat("btn-subscription-additional"),
            id=f"{PURCHASE_PREFIX}{PurchaseType.ADDITIONAL}",
            on_click=on_subscription_plans,
            when=F["has_active_subscription"] & F["can_add_subscription"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-promocode"),
            id=f"{PURCHASE_PREFIX}promocode",
            state=Subscription.PROMOCODE,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.MAIN,
    getter=subscription_getter,
)

my_subscriptions = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-my-subscriptions"),
    Column(
        Select(
            text=I18nFormat(
                "btn-subscription-item",
                status=F["item"]["status"],
                device_name=F["item"]["device_name"],
                expire_time=F["item"]["expire_time"],
            ),
            id=f"{PURCHASE_PREFIX}select_subscription",
            item_id_getter=lambda item: item["id"],
            items="subscriptions",
            type_factory=int,
            on_click=on_subscription_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.MAIN,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.MY_SUBSCRIPTIONS,
    getter=my_subscriptions_getter,
)

subscription_details = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-details-view"),
    Row(
        Url(
            text=I18nFormat("btn-subscription-connect-url"),
            url=Format("{url}"),
            when=F["connectable"] & F["is_app"],
        ),
        CopyText(
            text=I18nFormat("btn-subscription-copy-url"),
            copy_text=Format("{url}"),
            when=F["connectable"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-subscription-renew"),
            id=f"{PURCHASE_PREFIX}renew_selected",
            on_click=on_renew_selected_subscription,
            when=F["can_renew"],
        ),
        Button(
            text=I18nFormat("btn-subscription-delete"),
            id=f"{PURCHASE_PREFIX}delete_subscription",
            on_click=on_delete_subscription,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.MY_SUBSCRIPTIONS,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.SUBSCRIPTION_DETAILS,
    getter=subscription_details_getter,
)

confirm_delete = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-confirm-delete"),
    Row(
        Button(
            text=I18nFormat("btn-subscription-confirm-delete"),
            id=f"{PURCHASE_PREFIX}confirm_delete",
            on_click=on_confirm_delete_subscription,
        ),
        Button(
            text=I18nFormat("btn-subscription-cancel-delete"),
            id=f"{PURCHASE_PREFIX}cancel_delete",
            on_click=on_cancel_delete_subscription,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.CONFIRM_DELETE,
    getter=confirm_delete_getter,
)

promocode_input = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat("msg-subscription-promocode"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.MAIN,
        ),
    ),
    MessageInput(func=on_promocode_input),
    IgnoreUpdate(),
    state=Subscription.PROMOCODE,
)

promocode_select_subscription = Window(
    Banner(BannerName.PROMOCODE),
    # Показываем разные сообщения в зависимости от типа промокода
    I18nFormat(
        "msg-subscription-promocode-select-duration",
        promocode_days=F["promocode_days"],
        when=F["is_duration_promocode"],
    ),
    I18nFormat(
        "msg-subscription-promocode-select",
        promocode_days=F["promocode_days"],
        when=~F["is_duration_promocode"],
    ),
    Column(
        Select(
            text=I18nFormat(
                "btn-subscription-item",
                status=F["item"]["status"],
                device_name=F["item"]["device_name"],
                expire_time=F["item"]["expire_time"],
            ),
            id=f"{PURCHASE_PREFIX}promocode_select_subscription",
            item_id_getter=lambda item: item["id"],
            items="subscriptions",
            type_factory=int,
            on_click=on_promocode_select_subscription,
        ),
    ),
    Row(
        # Кнопка создания новой подписки только для промокодов типа SUBSCRIPTION
        Button(
            text=I18nFormat("btn-subscription-promocode-create-new"),
            id=f"{PURCHASE_PREFIX}promocode_create_new",
            on_click=on_promocode_create_new_subscription,
            when=~F["is_duration_promocode"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.PROMOCODE,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.PROMOCODE_SELECT_SUBSCRIPTION,
    getter=promocode_select_subscription_getter,
)

promocode_confirm_new = Window(
    Banner(BannerName.PROMOCODE),
    I18nFormat(
        "msg-subscription-promocode-confirm-new",
        plan_name=F["plan_name"],
        days_formatted=F["days_formatted"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-subscription-promocode-confirm-create"),
            id=f"{PURCHASE_PREFIX}promocode_confirm_create",
            on_click=on_promocode_create_new_subscription,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.PROMOCODE,
        ),
    ),
    IgnoreUpdate(),
    state=Subscription.PROMOCODE_CONFIRM_NEW,
    getter=promocode_confirm_new_getter,
)

select_subscription_for_renew = Window(
    Banner(BannerName.SUBSCRIPTION),
    # Показываем разные сообщения в зависимости от режима выбора
    I18nFormat(
        "msg-subscription-select-for-renew-single",
        when=F["single_select_mode"],
    ),
    I18nFormat(
        "msg-subscription-select-for-renew-multi",
        selected_count=F["selected_count"],
        when=~F["single_select_mode"],
    ),
    Column(
        Select(
            text=I18nFormat(
                "btn-subscription-item-selectable",
                status=F["item"]["status"],
                plan_name=F["item"]["plan_name"],
                expire_time=F["item"]["expire_time"],
                is_selected=F["item"]["is_selected"],
            ),
            id=f"{PURCHASE_PREFIX}toggle_subscription_for_renew",
            item_id_getter=lambda item: item["id"],
            items="subscriptions",
            type_factory=int,
            on_click=on_subscription_for_renew_toggle,
        ),
    ),
    Row(
        # Кнопка подтверждения только в режиме множественного выбора
        Button(
            text=I18nFormat("btn-subscription-confirm-selection", count=F["selected_count"]),
            id=f"{PURCHASE_PREFIX}confirm_renew_selection",
            on_click=on_confirm_renew_selection,
            when=F["has_selection"] & ~F["single_select_mode"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.MAIN,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.SELECT_SUBSCRIPTION_FOR_RENEW,
    getter=select_subscription_for_renew_getter,
)

confirm_renew_selection = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-confirm-renew-selection", selected_count=F["selected_count"]),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-continue-to-duration"),
            id=f"{PURCHASE_PREFIX}continue_to_duration",
            state=Subscription.DURATION,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=Subscription.SELECT_SUBSCRIPTION_FOR_RENEW,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.CONFIRM_RENEW_SELECTION,
    getter=confirm_renew_selection_getter,
)

plans = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-plans"),
    Column(
        Select(
            text=Format("{item[name]}"),
            id=f"{PURCHASE_PREFIX}select_plan",
            item_id_getter=lambda item: item["id"],
            items="plans",
            type_factory=int,
            on_click=on_plan_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id=f"{PURCHASE_PREFIX}back",
            state=Subscription.MAIN,
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.PLANS,
    getter=plans_getter,
)

duration = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-duration"),
    Group(
        Select(
            text=I18nFormat(
                "btn-subscription-duration",
                period=F["item"]["period"],
                final_amount=F["item"]["final_amount"],
                discount_percent=F["item"]["discount_percent"],
                original_amount=F["item"]["original_amount"],
                currency=F["item"]["currency"],
            ),
            id=f"{PURCHASE_PREFIX}select_duration",
            item_id_getter=lambda item: item["days"],
            items="durations",
            type_factory=int,
            on_click=on_duration_select,
        ),
        width=2,
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-plans"),
            id=f"{PURCHASE_PREFIX}back_plans",
            state=Subscription.PLANS,
            when=~F["only_single_plan"],
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.DURATION,
    getter=duration_getter,
)

payment_method = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-payment-method"),
    Column(
        Select(
            text=I18nFormat(
                "btn-subscription-payment-method",
                gateway_type=F["item"]["gateway_type"],
                price=F["item"]["price"],
                currency=F["item"]["currency"],
            ),
            id=f"{PURCHASE_PREFIX}select_payment_method",
            item_id_getter=lambda item: item["gateway_type"],
            items="payment_methods",
            type_factory=PaymentGatewayType,
            on_click=on_payment_method_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-device-type"),
            id=f"{PURCHASE_PREFIX}back_device",
            state=Subscription.DEVICE_TYPE,
            when=F["is_new_purchase"],
        ),
        SwitchTo(
            text=I18nFormat("btn-subscription-back-duration"),
            id=f"{PURCHASE_PREFIX}back",
            state=Subscription.DURATION,
            when=~F["only_single_duration"] & ~F["is_new_purchase"],
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.PAYMENT_METHOD,
    getter=payment_method_getter,
)

device_type = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat(
        "msg-subscription-device-type",
        is_multiple=F["is_multiple"],
        current_index=F["current_index"],
        total_count=F["total_count"],
    ),
    Column(
        Select(
            text=I18nFormat(
                "btn-subscription-device-type",
                type=F["item"]["type"],
            ),
            id=f"{PURCHASE_PREFIX}select_device_type",
            item_id_getter=lambda item: item["type"],
            items="device_types",
            type_factory=DeviceType,
            on_click=on_device_type_select,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-duration"),
            id=f"{PURCHASE_PREFIX}back_duration",
            state=Subscription.DURATION,
            when=~F["only_single_duration"],
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.DEVICE_TYPE,
    getter=device_type_getter,
)

confirm = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-confirm"),
    Row(
        Url(
            text=I18nFormat("btn-subscription-pay"),
            url=Format("{url}"),
            when=F["url"],
        ),
        Button(
            text=I18nFormat("btn-subscription-get"),
            id=f"{PURCHASE_PREFIX}get",
            on_click=on_get_subscription,
            when=~F["url"],
        ),
    ),
    Row(
        Url(
            text=I18nFormat("btn-subscription-privacy-policy"),
            url=Format("https://telegra.ph/Politika-konfidencialnosti-12-08-51"),
        ),
        Url(
            text=I18nFormat("btn-subscription-terms-of-service"),
            url=Format("https://telegra.ph/Polzovatelskoe-soglashenie-12-08-39"),
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-subscription-back-payment-method"),
            id=f"{PURCHASE_PREFIX}back_payment_method",
            state=Subscription.PAYMENT_METHOD,
            when=~F["only_single_gateway"] & ~F["is_free"],
        ),
        SwitchTo(
            text=I18nFormat("btn-subscription-back-duration"),
            id=f"{PURCHASE_PREFIX}back_duration",
            state=Subscription.DURATION,
            when=F["only_single_gateway"] & ~F["only_single_duration"] | F["is_free"],
        ),
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.CONFIRM,
    getter=confirm_getter,
)

success_payment = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-success"),
    Row(
        *connect_buttons,
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.SUCCESS,
    getter=success_payment_getter,
)

success_trial = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-trial"),
    Row(
        *connect_buttons,
    ),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.TRIAL,
    getter=getter_connect,
)

failed = Window(
    Banner(BannerName.SUBSCRIPTION),
    I18nFormat("msg-subscription-failed"),
    *back_main_menu_button,
    IgnoreUpdate(),
    state=Subscription.FAILED,
)

router = Dialog(
    subscription,
    my_subscriptions,
    subscription_details,
    confirm_delete,
    promocode_input,
    promocode_select_subscription,
    promocode_confirm_new,
    select_subscription_for_renew,
    confirm_renew_selection,
    plans,
    duration,
    payment_method,
    device_type,
    confirm,
    success_payment,
    success_trial,
    failed,
)
