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
            text=Format("Project Name"),
            id="project_name",
            on_click=on_select_edit_field,
        ),
        Button(
            text=Format("Web Title"),
            id="web_title",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("TG Template"),
            id="telegram_template",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("TG Password Reset Template"),
            id="password_reset_telegram_template",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("Web Request Delivered"),
            id="web_request_delivered",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("Web Request Open Bot"),
            id="web_request_open_bot",
            on_click=on_select_edit_field,
        ),
    ),
    Row(
        Button(
            text=Format("Web Confirm Success"),
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
            text=Format("Edit EN (Base)"),
            id="edit_locale_en",
            on_click=on_select_edit_locale,
            when=F["is_localized"],
        ),
        Button(
            text=Format("Edit RU (Override)"),
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
