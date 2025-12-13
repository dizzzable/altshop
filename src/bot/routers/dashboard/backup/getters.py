from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.config import AppConfig
from src.services.backup import BackupService


@inject
async def backup_main_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    config: AppConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для главного окна системы бэкапов."""
    backup_config = config.backup
    backups = await backup_service.get_backup_list()
    
    return {
        "auto_enabled": backup_config.auto_enabled,
        "interval_hours": backup_config.interval_hours,
        "backup_time": backup_config.time,
        "max_keep": backup_config.max_keep,
        "compression": backup_config.compression,
        "send_enabled": backup_config.send_enabled,
        "backups_count": len(backups),
        "backup_location": str(backup_config.location),
    }


@inject
async def backup_list_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для списка бэкапов."""
    backups = await backup_service.get_backup_list()
    
    # Преобразуем BackupInfo в словари для отображения
    backups_list = []
    for backup in backups:
        backups_list.append({
            "filename": backup.filename,
            "timestamp": backup.timestamp[:16].replace("T", " ") if backup.timestamp else "?",
            "file_size_mb": backup.file_size_mb,
            "total_records": backup.total_records,
        })
    
    return {
        "backups": backups_list,
        "has_backups": len(backups_list) > 0,
        "total_backups": len(backups_list),
    }


@inject
async def backup_manage_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для управления конкретным бэкапом."""
    filename = dialog_manager.dialog_data.get("backup_filename", "")
    
    backups = await backup_service.get_backup_list()
    backup_info = None
    
    for backup in backups:
        if backup.filename == filename:
            backup_info = backup
            break
    
    if not backup_info:
        return {
            "found": False,
            "filename": filename,
            "content_details": "",
        }
    
    # Форматирование даты
    try:
        timestamp_str = backup_info.timestamp[:19].replace("T", " ")
    except Exception:
        timestamp_str = "Неизвестно"
    
    # Формируем content_details с базовой информацией
    content_details = f"• Таблиц: {backup_info.tables_count}\n• Записей: {backup_info.total_records}"
    
    return {
        "found": True,
        "filename": backup_info.filename,
        "timestamp": timestamp_str,
        "file_size_mb": backup_info.file_size_mb,
        "tables_count": backup_info.tables_count,
        "total_records": backup_info.total_records,
        "compressed": backup_info.compressed,
        "database_type": backup_info.database_type,
        "version": backup_info.version,
        "created_by": backup_info.created_by or "Система",
        "error": backup_info.error,
        "content_details": content_details,
    }


@inject
async def backup_settings_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для настроек бэкапов."""
    backup_config = config.backup
    
    return {
        "auto_enabled": backup_config.auto_enabled,
        "interval_hours": backup_config.interval_hours,
        "backup_time": backup_config.time,
        "max_keep": backup_config.max_keep,
        "compression": backup_config.compression,
        "include_logs": backup_config.include_logs,
        "send_enabled": backup_config.send_enabled,
        "send_chat_id": backup_config.send_chat_id or "Не указан",
        "send_topic_id": backup_config.send_topic_id or "Не указан",
        "backup_location": str(backup_config.location),
    }


@inject
async def backup_restore_confirm_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для подтверждения восстановления."""
    filename = dialog_manager.dialog_data.get("backup_filename", "")
    clear_before = dialog_manager.dialog_data.get("clear_existing", False)
    
    # Получаем информацию о бэкапе для отображения timestamp и total_records
    backups = await backup_service.get_backup_list()
    backup_info = None
    for backup in backups:
        if backup.filename == filename:
            backup_info = backup
            break
    
    timestamp = "Неизвестно"
    total_records = 0
    if backup_info:
        try:
            timestamp = backup_info.timestamp[:19].replace("T", " ")
        except Exception:
            pass
        total_records = backup_info.total_records
    
    return {
        "filename": filename,
        "clear_before": 1 if clear_before else 0,
        "timestamp": timestamp,
        "total_records": total_records,
    }


@inject
async def backup_delete_confirm_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для подтверждения удаления."""
    filename = dialog_manager.dialog_data.get("backup_filename", "")
    
    # Получаем информацию о бэкапе для отображения timestamp
    backups = await backup_service.get_backup_list()
    backup_info = None
    for backup in backups:
        if backup.filename == filename:
            backup_info = backup
            break
    
    timestamp = "Неизвестно"
    if backup_info:
        try:
            timestamp = backup_info.timestamp[:19].replace("T", " ")
        except Exception:
            pass
    
    return {
        "filename": filename,
        "timestamp": timestamp,
    }