from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, ListGroup, Row, Start, SwitchTo
from magic_filter import F

from src.bot.states import DashboardRemnashop, RemnashopBotMenu
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import (
    bot_menu_button_getter,
    bot_menu_button_label_getter,
    bot_menu_button_url_getter,
    bot_menu_main_getter,
    bot_menu_url_getter,
)
from .handlers import (
    on_bot_menu_mode_toggle,
    on_custom_button_add,
    on_custom_button_delete,
    on_custom_button_kind_toggle,
    on_custom_button_label_input,
    on_custom_button_move_down,
    on_custom_button_move_up,
    on_custom_button_select,
    on_custom_button_toggle_enabled,
    on_custom_button_url_input,
    on_mini_app_url_input,
)

main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-bot-menu-main"),
    Row(
        Button(
            text=I18nFormat("btn-bot-menu-mode-toggle", enabled=F["miniapp_only_enabled"]),
            id="toggle_mode",
            on_click=on_bot_menu_mode_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-bot-menu-mini-app-url"),
            id="edit_mini_app_url",
            state=RemnashopBotMenu.MINI_APP_URL,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-bot-menu-add-button"),
            id="add_button",
            on_click=on_custom_button_add,
        ),
    ),
    ListGroup(
        Row(
            Button(
                text=I18nFormat(
                    "btn-bot-menu-button-item",
                    label=F["item"]["label"],
                    kind=F["item"]["kind"],
                    enabled=F["item"]["enabled"],
                ),
                id="select_custom_button",
                on_click=on_custom_button_select,
            ),
        ),
        id="custom_button_list",
        item_id_getter=lambda item: item["id"],
        items="custom_buttons",
        when=F["has_custom_buttons"],
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardRemnashop.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBotMenu.MAIN,
    getter=bot_menu_main_getter,
)

mini_app_url = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-bot-menu-url-input"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBotMenu.MAIN,
        ),
    ),
    MessageInput(func=on_mini_app_url_input),
    IgnoreUpdate(),
    state=RemnashopBotMenu.MINI_APP_URL,
    getter=bot_menu_url_getter,
)

button = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-bot-menu-button-edit"),
    Row(
        Button(
            text=I18nFormat("btn-bot-menu-button-enabled", enabled=F["button_enabled"]),
            id="toggle_enabled",
            on_click=on_custom_button_toggle_enabled,
        ),
        Button(
            text=I18nFormat("btn-bot-menu-button-kind", kind=F["button_kind"]),
            id="toggle_kind",
            on_click=on_custom_button_kind_toggle,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-bot-menu-button-edit-label"),
            id="edit_label",
            state=RemnashopBotMenu.BUTTON_LABEL,
        ),
        SwitchTo(
            text=I18nFormat("btn-bot-menu-button-edit-url"),
            id="edit_url",
            state=RemnashopBotMenu.BUTTON_URL,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-bot-menu-button-move-up"),
            id="move_up",
            on_click=on_custom_button_move_up,
            when=F["can_move_up"],
        ),
        Button(
            text=I18nFormat("btn-bot-menu-button-move-down"),
            id="move_down",
            on_click=on_custom_button_move_down,
            when=F["can_move_down"],
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-bot-menu-button-delete"),
            id="delete_button",
            on_click=on_custom_button_delete,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBotMenu.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBotMenu.BUTTON,
    getter=bot_menu_button_getter,
)

button_label = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-bot-menu-button-label-input"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBotMenu.BUTTON,
        ),
    ),
    MessageInput(func=on_custom_button_label_input),
    IgnoreUpdate(),
    state=RemnashopBotMenu.BUTTON_LABEL,
    getter=bot_menu_button_label_getter,
)

button_url = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-bot-menu-button-url-input"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBotMenu.BUTTON,
        ),
    ),
    MessageInput(func=on_custom_button_url_input),
    IgnoreUpdate(),
    state=RemnashopBotMenu.BUTTON_URL,
    getter=bot_menu_button_url_getter,
)

router = Dialog(
    main,
    mini_app_url,
    button,
    button_label,
    button_url,
)
