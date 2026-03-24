from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Row, Start, SwitchTo
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.states import DashboardRemnashop, RemnashopBranding
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import branding_edit_getter, branding_main_getter
from .handlers import on_branding_input, on_select_edit_field, on_select_edit_locale

main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-branding-main"),
    Row(
        Button(
            text=Format("{project_name_label}"),
            id="project_name",
            on_click=on_select_edit_field,
        ),
        Button(
            text=Format("{web_title_label}"),
            id="web_title",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("{bot_menu_button_text_label}"),
            id="bot_menu_button_text",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("{telegram_template_label}"),
            id="telegram_template",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("{password_reset_telegram_template_label}"),
            id="password_reset_telegram_template",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("{web_request_delivered_label}"),
            id="web_request_delivered",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("{web_request_open_bot_label}"),
            id="web_request_open_bot",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("{web_confirm_success_label}"),
            id="web_confirm_success",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardRemnashop.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBranding.MAIN,
    getter=branding_main_getter,
)

edit = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-branding-edit"),
    Row(
        Button(
            text=Format("{edit_locale_en_label}"),
            id="edit_locale_en",
            on_click=on_select_edit_locale,
            when=F["is_localized"],
        ),
        Button(
            text=Format("{edit_locale_ru_label}"),
            id="edit_locale_ru",
            on_click=on_select_edit_locale,
            when=F["is_localized"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBranding.MAIN,
        ),
    ),
    MessageInput(func=on_branding_input),
    IgnoreUpdate(),
    state=RemnashopBranding.EDIT,
    getter=branding_edit_getter,
)

router = Dialog(
    main,
    edit,
)
