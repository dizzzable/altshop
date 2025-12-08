from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import NumberedPager, Row, Start, StubScroll

from src.bot.keyboards import main_menu_button
from src.bot.states import Dashboard, DashboardStatistics
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import statistics_getter

statistics = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-statistics-main"),
    StubScroll(id="statistics", pages="pages"),
    NumberedPager(
        page_text=I18nFormat("btn-statistics-page"),
        current_page_text=I18nFormat("btn-statistics-current-page"),
        scroll="statistics",
    ),
    Row(
        Start(
            text=I18nFormat("btn-back"),
            id="back",
            state=Dashboard.MAIN,
        ),
        *main_menu_button,
    ),
    IgnoreUpdate(),
    state=DashboardStatistics.MAIN,
    getter=statistics_getter,
    preview_data=statistics_getter,
)

router = Dialog(statistics)
