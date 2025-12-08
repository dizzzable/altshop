from aiogram.enums import ContentType
from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import (
    Button,
    Column,
    Group,
    Row,
    Select,
    Start,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Format
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.states import DashboardRemnashop, RemnashopBanners
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import (
    banner_confirm_delete_getter,
    banner_select_getter,
    banner_upload_getter,
    banners_getter,
)
from .handlers import (
    on_banner_select,
    on_banner_upload_input,
    on_confirm_delete,
    on_delete_banner,
    on_locale_select,
    on_upload_banner,
)


banners_main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-banners-main"),
    Group(
        Select(
            text=I18nFormat(
                "btn-banner-item",
                name=F["item"]["display_name"],
            ),
            id="banner_select",
            item_id_getter=lambda item: item["name"],
            items="banners",
            on_click=on_banner_select,
        ),
        width=2,
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
    state=RemnashopBanners.MAIN,
    getter=banners_getter,
)

banner_select = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-banner-select"),
    Column(
        Select(
            text=I18nFormat(
                "btn-banner-locale-choice",
                locale=F["item"]["display_name"],
                selected=F["item"]["selected"],
            ),
            id="locale_select",
            item_id_getter=lambda item: item["locale"],
            items="locale_list",
            on_click=on_locale_select,
        ),
    ),
    Row(
        Button(
            text=I18nFormat("btn-banner-upload"),
            id="upload",
            on_click=on_upload_banner,
        ),
        Button(
            text=I18nFormat("btn-banner-delete"),
            id="delete",
            on_click=on_delete_banner,
            when=F["has_banner"],
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBanners.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBanners.SELECT_BANNER,
    getter=banner_select_getter,
)

banner_upload = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-banner-upload"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBanners.SELECT_BANNER,
        ),
    ),
    MessageInput(
        func=on_banner_upload_input,
        content_types=[ContentType.PHOTO, ContentType.ANIMATION, ContentType.DOCUMENT],
    ),
    IgnoreUpdate(),
    state=RemnashopBanners.UPLOAD_BANNER,
    getter=banner_upload_getter,
)

banner_confirm_delete = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-banner-confirm-delete"),
    Row(
        Button(
            text=I18nFormat("btn-banner-confirm-delete"),
            id="confirm_delete",
            on_click=on_confirm_delete,
        ),
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=RemnashopBanners.SELECT_BANNER,
        ),
    ),
    IgnoreUpdate(),
    state=RemnashopBanners.CONFIRM_DELETE,
    getter=banner_confirm_delete_getter,
)

router = Dialog(
    banners_main,
    banner_select,
    banner_upload,
    banner_confirm_delete,
)