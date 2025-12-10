from aiogram_dialog import Dialog, StartMode, Window
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, Start, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from magic_filter import F

from src.bot.keyboards import main_menu_button
from src.bot.states import DashboardBackup, DashboardRemnashop
from src.bot.widgets import Banner, I18nFormat, IgnoreUpdate
from src.core.enums import BannerName

from .getters import (
    backup_delete_confirm_getter,
    backup_list_getter,
    backup_main_getter,
    backup_manage_getter,
    backup_restore_confirm_getter,
    backup_settings_getter,
)
from .handlers import (
    on_back_to_remnashop,
    on_backup_select,
    on_create_backup,
    on_delete_backup,
    on_delete_confirm,
    on_restore_backup,
    on_restore_backup_clear,
    on_restore_confirm,
)


# Главное окно системы бэкапов
backup_main = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-main"),
    Row(
        Button(
            text=I18nFormat("btn-backup-create"),
            id="create_backup",
            on_click=on_create_backup,
        ),
        SwitchTo(
            text=I18nFormat("btn-backup-list"),
            id="backup_list",
            state=DashboardBackup.LIST,
        ),
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-backup-settings"),
            id="backup_settings",
            state=DashboardBackup.SETTINGS,
        ),
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
    state=DashboardBackup.MAIN,
    getter=backup_main_getter,
)

# Список бэкапов
backup_list = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-list"),
    Column(
        Select(
            Format("📦 {item[timestamp]} • {item[file_size_mb]}MB • {item[total_records]} зап."),
            id="backup_select",
            item_id_getter=lambda item: item["filename"],
            items="backups",
            on_click=on_backup_select,
        ),
        when=F["has_backups"],
    ),
    Const(
        "📭 Бэкапы отсутствуют",
        when=~F["has_backups"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardBackup.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBackup.LIST,
    getter=backup_list_getter,
)

# Управление конкретным бэкапом
backup_manage = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-manage"),
    Row(
        Button(
            text=I18nFormat("btn-backup-restore"),
            id="restore_backup",
            on_click=on_restore_backup,
        ),
        when=F["found"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-backup-restore-clear"),
            id="restore_backup_clear",
            on_click=on_restore_backup_clear,
        ),
        when=F["found"],
    ),
    Row(
        Button(
            text=I18nFormat("btn-backup-delete"),
            id="delete_backup",
            on_click=on_delete_backup,
        ),
        when=F["found"],
    ),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardBackup.LIST,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBackup.MANAGE,
    getter=backup_manage_getter,
)

# Настройки бэкапов
backup_settings = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-settings"),
    Row(
        SwitchTo(
            text=I18nFormat("btn-back"),
            id="back",
            state=DashboardBackup.MAIN,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBackup.SETTINGS,
    getter=backup_settings_getter,
)

# Подтверждение восстановления
backup_restore_confirm = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-restore-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-backup-restore-confirm"),
            id="confirm_restore",
            on_click=on_restore_confirm,
        ),
        SwitchTo(
            text=I18nFormat("btn-cancel"),
            id="cancel_restore",
            state=DashboardBackup.MANAGE,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBackup.RESTORE_CONFIRM,
    getter=backup_restore_confirm_getter,
)

# Подтверждение удаления
backup_delete_confirm = Window(
    Banner(BannerName.DASHBOARD),
    I18nFormat("msg-backup-delete-confirm"),
    Row(
        Button(
            text=I18nFormat("btn-backup-delete-confirm"),
            id="confirm_delete",
            on_click=on_delete_confirm,
        ),
        SwitchTo(
            text=I18nFormat("btn-cancel"),
            id="cancel_delete",
            state=DashboardBackup.MANAGE,
        ),
    ),
    IgnoreUpdate(),
    state=DashboardBackup.DELETE_CONFIRM,
    getter=backup_delete_confirm_getter,
)


router = Dialog(
    backup_main,
    backup_list,
    backup_manage,
    backup_settings,
    backup_restore_confirm,
    backup_delete_confirm,
)