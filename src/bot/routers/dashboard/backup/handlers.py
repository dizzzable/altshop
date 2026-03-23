from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.bot.states import DashboardBackup, DashboardRemnashop
from src.core.constants import USER_KEY
from src.core.enums import BackupScope
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.backup import BackupService
from src.services.notification import NotificationService


def _scope_label(scope: BackupScope) -> str:
    labels = {
        BackupScope.DB: "Database only",
        BackupScope.ASSETS: "Assets only",
        BackupScope.FULL: "Full backup",
    }
    return labels[scope]


@inject
async def on_create_backup(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Open backup scope selection."""
    del callback, button
    await manager.switch_to(DashboardBackup.CREATE_SCOPE)


@inject
async def on_create_backup_scope(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
    backup_service: FromDishka[BackupService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Create a backup for the selected scope."""
    del widget
    await callback.answer("Backup creation started...")

    user: UserDto = manager.middleware_data.get(USER_KEY)
    created_by = user.telegram_id if user else None
    scope = BackupScope(item_id.upper())

    progress_notification = await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-backup-creating",
            i18n_kwargs={"scope": _scope_label(scope)},
        ),
    )

    success, message, _file_path = await backup_service.create_backup(
        created_by=created_by,
        scope=scope,
    )

    if progress_notification:
        await progress_notification.delete()

    if success:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-backup-created-success",
                i18n_kwargs={"message": message},
            ),
        )
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-backup-created-failed",
                i18n_kwargs={"message": message},
            ),
        )

    await manager.switch_to(DashboardBackup.MAIN, show_mode=ShowMode.SEND)


@inject
async def on_backup_select(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    """Handle selecting a backup from the list."""
    del callback, widget
    manager.dialog_data["backup_filename"] = item_id
    await manager.switch_to(DashboardBackup.MANAGE)


@inject
async def on_restore_backup(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Start restore without clearing database."""
    del callback, button
    manager.dialog_data["clear_existing"] = False
    await manager.switch_to(DashboardBackup.RESTORE_CONFIRM)


@inject
async def on_restore_backup_clear(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Start restore with database cleanup."""
    del callback, button
    manager.dialog_data["clear_existing"] = True
    await manager.switch_to(DashboardBackup.RESTORE_CONFIRM)


@inject
async def on_restore_confirm(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
    backup_service: FromDishka[BackupService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Confirm backup restore."""
    del button
    user: UserDto = manager.middleware_data.get(USER_KEY)
    filename = manager.dialog_data.get("backup_filename", "")
    clear_existing = manager.dialog_data.get("clear_existing", False)
    backup_scope = manager.dialog_data.get("backup_scope_label", "Unknown")

    await callback.answer("Restore started...")

    progress_notification = await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-backup-restoring",
            i18n_kwargs={
                "filename": filename,
                "clear_existing": clear_existing,
                "scope": backup_scope,
            },
        ),
    )

    backup_path = backup_service.backup_dir / filename
    success, message = await backup_service.restore_backup(
        str(backup_path),
        clear_existing=clear_existing,
    )

    if progress_notification:
        await progress_notification.delete()

    if success:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-backup-restored-success",
                i18n_kwargs={"message": message},
            ),
        )
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-backup-restored-failed",
                i18n_kwargs={"message": message},
            ),
        )

    await manager.switch_to(DashboardBackup.MAIN, show_mode=ShowMode.SEND)


@inject
async def on_delete_backup(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Open backup delete confirmation."""
    del callback, button
    await manager.switch_to(DashboardBackup.DELETE_CONFIRM)


@inject
async def on_delete_confirm(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
    backup_service: FromDishka[BackupService],
) -> None:
    """Delete selected backup."""
    del button
    filename = manager.dialog_data.get("backup_filename", "")

    success, message = await backup_service.delete_backup(filename)

    if success:
        await callback.answer("Backup deleted", show_alert=True)
    else:
        await callback.answer(message, show_alert=True)

    await manager.switch_to(DashboardBackup.LIST)


async def on_back_to_remnashop(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Return to RemnaShop menu."""
    del callback, button
    await manager.start(DashboardRemnashop.MAIN)
