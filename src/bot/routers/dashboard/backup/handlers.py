from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.bot.states import DashboardBackup, DashboardRemnashop
from src.core.constants import USER_KEY
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.backup import BackupService
from src.services.notification import NotificationService


@inject
async def on_create_backup(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
    backup_service: FromDishka[BackupService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Обработчик создания бэкапа."""
    await callback.answer("🔄 Создание бэкапа запущено...")

    user: UserDto = manager.middleware_data.get(USER_KEY)
    created_by = user.telegram_id if user else None

    # Показываем прогресс через уведомление
    progress_notification = await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-backup-creating",
        ),
    )

    # Создаём бэкап
    success, message, file_path = await backup_service.create_backup(created_by=created_by)

    # Удаляем уведомление о прогрессе
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

    # Возвращаемся на главный экран бэкапов
    await manager.switch_to(DashboardBackup.MAIN, show_mode=ShowMode.SEND)


@inject
async def on_backup_select(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    """Обработчик выбора бэкапа из списка."""
    manager.dialog_data["backup_filename"] = item_id
    await manager.switch_to(DashboardBackup.MANAGE)


@inject
async def on_restore_backup(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Обработчик начала восстановления бэкапа."""
    manager.dialog_data["clear_existing"] = False
    await manager.switch_to(DashboardBackup.RESTORE_CONFIRM)


@inject
async def on_restore_backup_clear(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Обработчик восстановления с очисткой данных."""
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
    """Обработчик подтверждения восстановления."""
    user: UserDto = manager.middleware_data.get(USER_KEY)
    filename = manager.dialog_data.get("backup_filename", "")
    clear_existing = manager.dialog_data.get("clear_existing", False)

    await callback.answer("🔄 Восстановление запущено...")

    # Показываем прогресс через уведомление
    progress_notification = await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-backup-restoring",
            i18n_kwargs={
                "filename": filename,
                "clear_existing": clear_existing,
            },
        ),
    )

    backup_path = backup_service.backup_dir / filename
    success, message = await backup_service.restore_backup(
        str(backup_path),
        clear_existing=clear_existing,
    )

    # Удаляем уведомление о прогрессе
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
    """Обработчик начала удаления бэкапа."""
    await manager.switch_to(DashboardBackup.DELETE_CONFIRM)


@inject
async def on_delete_confirm(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
    backup_service: FromDishka[BackupService],
) -> None:
    """Обработчик подтверждения удаления."""
    filename = manager.dialog_data.get("backup_filename", "")

    success, message = await backup_service.delete_backup(filename)

    if success:
        await callback.answer("✅ Бэкап удалён", show_alert=True)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

    await manager.switch_to(DashboardBackup.LIST)


async def on_back_to_remnashop(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Возврат в меню RemnaShop."""
    await manager.start(DashboardRemnashop.MAIN)
