from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.config import AppConfig
from src.services.backup import BackupService


def _scope_label(scope_value: str) -> str:
    mapping = {
        "DB": "Database only",
        "ASSETS": "Assets only",
        "FULL": "Full backup",
    }
    return mapping.get(scope_value, scope_value.title())


@inject
async def backup_main_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    config: AppConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    del dialog_manager, kwargs
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


async def backup_scope_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    del dialog_manager, kwargs
    return {
        "scopes": [
            {
                "id": "db",
                "label": "Database only",
                "description": "Plans, subscriptions, users, settings",
            },
            {
                "id": "assets",
                "label": "Assets only",
                "description": "Banners, translations, logo and runtime assets",
            },
            {"id": "full", "label": "Full backup", "description": "Database + assets together"},
        ]
    }


@inject
async def backup_list_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    del dialog_manager, kwargs
    backups = await backup_service.get_backup_list()

    backups_list = []
    for backup in backups:
        backups_list.append(
            {
                "filename": backup.filename,
                "timestamp": backup.timestamp[:16].replace("T", " ") if backup.timestamp else "?",
                "file_size_mb": backup.file_size_mb,
                "total_records": backup.total_records,
                "scope_label": _scope_label(backup.backup_scope.value),
            }
        )

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
    del kwargs
    filename = dialog_manager.dialog_data.get("backup_filename", "")

    backups = await backup_service.get_backup_list()
    backup_info = next((backup for backup in backups if backup.filename == filename), None)

    if not backup_info:
        return {
            "found": False,
            "filename": filename,
            "content_details": "",
        }

    try:
        timestamp_str = backup_info.timestamp[:19].replace("T", " ")
    except Exception:
        timestamp_str = "Unknown"

    content_lines = []
    if backup_info.includes_database:
        content_lines.append(f"• Database tables: {backup_info.tables_count}")
        content_lines.append(f"• Database records: {backup_info.total_records}")
        content_lines.append("• Includes plans, prices, subscriptions, users and settings")
    if backup_info.includes_assets:
        content_lines.append(f"• Assets files: {backup_info.assets_files_count}")
        if backup_info.assets_root:
            content_lines.append(f"• Assets root: {backup_info.assets_root}")

    scope_label = _scope_label(backup_info.backup_scope.value)
    dialog_manager.dialog_data["backup_scope_label"] = scope_label

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
        "created_by": backup_info.created_by or "System",
        "error": backup_info.error,
        "content_details": "\n".join(content_lines),
        "scope_label": scope_label,
        "includes_database": backup_info.includes_database,
        "includes_assets": backup_info.includes_assets,
    }


@inject
async def backup_settings_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    **kwargs: Any,
) -> dict[str, Any]:
    del dialog_manager, kwargs
    backup_config = config.backup

    return {
        "auto_enabled": backup_config.auto_enabled,
        "interval_hours": backup_config.interval_hours,
        "backup_time": backup_config.time,
        "max_keep": backup_config.max_keep,
        "compression": backup_config.compression,
        "include_logs": backup_config.include_logs,
        "send_enabled": backup_config.send_enabled,
        "send_chat_id": backup_config.send_chat_id or "Not set",
        "send_topic_id": backup_config.send_topic_id or "Not set",
        "backup_location": str(backup_config.location),
    }


@inject
async def backup_restore_confirm_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    filename = dialog_manager.dialog_data.get("backup_filename", "")
    clear_before = dialog_manager.dialog_data.get("clear_existing", False)

    backups = await backup_service.get_backup_list()
    backup_info = next((backup for backup in backups if backup.filename == filename), None)

    timestamp = "Unknown"
    total_records = 0
    scope_label = "Unknown"
    if backup_info:
        try:
            timestamp = backup_info.timestamp[:19].replace("T", " ")
        except Exception:
            pass
        total_records = backup_info.total_records
        scope_label = _scope_label(backup_info.backup_scope.value)

    return {
        "filename": filename,
        "clear_before": 1 if clear_before else 0,
        "timestamp": timestamp,
        "total_records": total_records,
        "scope_label": scope_label,
    }


@inject
async def backup_delete_confirm_getter(
    dialog_manager: DialogManager,
    backup_service: FromDishka[BackupService],
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    filename = dialog_manager.dialog_data.get("backup_filename", "")

    backups = await backup_service.get_backup_list()
    backup_info = next((backup for backup in backups if backup.filename == filename), None)

    timestamp = "Unknown"
    if backup_info:
        try:
            timestamp = backup_info.timestamp[:19].replace("T", " ")
        except Exception:
            pass

    return {
        "filename": filename,
        "timestamp": timestamp,
    }
