from __future__ import annotations

import json as json_lib
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

import aiofiles
from loguru import logger
from sqlalchemy import inspect, select, text

from src.core.enums import BackupScope, Locale
from src.core.utils.assets_sync import ASSETS_BACKUP_DIRNAME, ASSETS_VERSION_MARKER
from src.core.utils.time import datetime_now

if TYPE_CHECKING:
    from .backup import BackupService

_aiofiles_open = aiofiles.open


async def _build_backup_archive(
    service: BackupService,
    *,
    backup_path: Path,
    compress: bool,
    include_logs: bool,
    scope: BackupScope,
    created_by: Optional[int],
    overview: Dict[str, Any],
    includes_database: bool,
    includes_assets: bool,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        staging_dir = temp_path / "backup"
        staging_dir.mkdir(parents=True, exist_ok=True)

        database_info: Optional[Dict[str, Any]] = None
        assets_info: Optional[Dict[str, Any]] = None
        if includes_database:
            database_info = await service._dump_database_json(staging_dir)
        if includes_assets:
            assets_info = await service._dump_assets(staging_dir)

        metadata = {
            "format_version": service.BACKUP_FORMAT_VERSION,
            "timestamp": datetime_now().isoformat(),
            "database_type": "postgresql",
            "backup_scope": scope.value,
            "backup_type": scope.value,
            "includes_database": includes_database,
            "includes_assets": includes_assets,
            "assets_root": str(service.config.assets_dir) if includes_assets else None,
            "tables_count": overview.get("tables_count", 0),
            "total_records": overview.get("total_records", 0),
            "compressed": compress,
            "created_by": created_by,
            "database": database_info,
            "integrity": (database_info or {}).get(
                "integrity",
                {"degraded": False, "issues": []},
            ),
            "assets": assets_info,
            "include_logs": include_logs,
        }

        metadata_path = staging_dir / "metadata.json"
        async with cast(Any, _aiofiles_open)(metadata_path, "w", encoding="utf-8") as meta_file:
            await meta_file.write(json_lib.dumps(metadata, ensure_ascii=False, indent=2))

        if compress:
            with tarfile.open(str(backup_path), "w:gz") as tar:
                for item in staging_dir.iterdir():
                    tar.add(item, arcname=item.name)
        else:
            with tarfile.open(str(backup_path), "w") as tar:
                for item in staging_dir.iterdir():
                    tar.add(item, arcname=item.name)

    return metadata


async def create_backup(
    service: BackupService,
    created_by: Optional[int] = None,
    compress: Optional[bool] = None,
    include_logs: Optional[bool] = None,
    scope: BackupScope = BackupScope.FULL,
    locale: Locale | None = None,
) -> Tuple[bool, str, Optional[str]]:
    try:
        logger.info("📄 Начинаем создание бэкапа...")

        if compress is None:
            compress = service.config.backup.compression
        if include_logs is None:
            include_logs = service.config.backup.include_logs

        includes_database = scope in (BackupScope.DB, BackupScope.FULL)
        includes_assets = scope in (BackupScope.ASSETS, BackupScope.FULL)

        overview: Dict[str, Any] = {"tables_count": 0, "total_records": 0}
        if includes_database:
            overview = await service._collect_database_overview()

        archive_timestamp = datetime_now().strftime("%Y%m%d_%H%M%S")
        archive_suffix = ".tar.gz" if compress else ".tar"
        filename = f"backup_{scope.lower()}_{archive_timestamp}{archive_suffix}"
        backup_path = service.backup_dir / filename

        metadata = await _build_backup_archive(
            service,
            backup_path=backup_path,
            compress=compress,
            include_logs=include_logs,
            scope=scope,
            created_by=created_by,
            overview=overview,
            includes_database=includes_database,
            includes_assets=includes_assets,
        )
        backup_info = service._metadata_to_backup_info(
            backup_path,
            backup_path.stat(),
            metadata,
        )
        await service._upsert_backup_record(
            backup_info=backup_info,
            local_path=backup_path,
        )

        sent_message = await service._send_backup_file_to_chat(
            str(backup_path),
            backup_info=backup_info,
            locale=locale,
        )
        if sent_message is not None:
            await service._upsert_backup_record(
                backup_info=backup_info,
                local_path=backup_path,
                telegram_message=sent_message,
            )

        await service._cleanup_old_backups()

        message = service._build_backup_result_message(
            backup_info=backup_info,
            locale=locale,
        )
        logger.info(message)

        return True, message, str(backup_path)

    except Exception as exception:
        if locale is not None:
            error_msg = service._build_backup_create_error_message(str(exception), locale=locale)
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None
        error_msg = f"❌ Ошибка создания бэкапа: {str(exception)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg, None


async def _collect_database_overview(service: BackupService) -> Dict[str, Any]:
    overview: Dict[str, Any] = {
        "tables_count": 0,
        "total_records": 0,
        "tables": [],
    }

    try:
        async with service.engine.begin() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

            for table_name in table_names:
                try:
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    count = result.scalar_one()
                except Exception:
                    count = 0

                overview["tables"].append({"name": table_name, "rows": count})
                overview["total_records"] += count

            overview["tables_count"] = len(table_names)
    except Exception as exc:
        logger.warning(f"Не удалось собрать статистику по БД: {exc}")

    return overview


async def _dump_database_json(service: BackupService, staging_dir: Path) -> Dict[str, Any]:
    backup_data: Dict[str, List[Dict[str, Any]]] = {}
    total_records = 0
    export_errors: dict[str, str] = {}

    async with service.session_pool() as session:
        for model in service.BACKUP_MODELS:
            table_name = model.__tablename__
            logger.info(f"📊 Экспортируем таблицу: {table_name}")

            try:
                result = await session.execute(select(model))
                records = result.scalars().all()

                table_data: List[Dict[str, Any]] = []
                for record in records:
                    record_dict = service._model_to_dict(record, model)
                    table_data.append(record_dict)

                backup_data[table_name] = table_data
                total_records += len(table_data)

                logger.info(f"✅ Экспортировано {len(table_data)} записей из {table_name}")

            except Exception as exc:
                logger.error(f"Ошибка экспорта таблицы {table_name}: {exc}")
                export_errors[table_name] = str(exc)
                backup_data[table_name] = []

    integrity = service._build_backup_integrity_report(
        backup_data=backup_data,
        export_errors=export_errors,
    )
    dump_path = staging_dir / "database.json"
    dump_structure = {
        "metadata": {
            "timestamp": datetime_now().isoformat(),
            "version": "orm-1.1",
            "database_type": "postgresql",
            "tables_count": len(service.BACKUP_MODELS),
            "total_records": total_records,
            "integrity": integrity,
        },
        "data": backup_data,
    }

    async with cast(Any, _aiofiles_open)(dump_path, "w", encoding="utf-8") as f:
        await f.write(json_lib.dumps(dump_structure, ensure_ascii=False, indent=2, default=str))

    size = dump_path.stat().st_size if dump_path.exists() else 0

    logger.info(f"✅ БД экспортирована в JSON ({dump_path})")

    return {
        "type": "postgresql",
        "path": dump_path.name,
        "size_bytes": size,
        "format": "json",
        "tool": "orm",
        "tables_count": len(service.BACKUP_MODELS),
        "total_records": total_records,
        "integrity": integrity,
    }


def _should_skip_asset_file(_service: BackupService | None, relative_path: Path) -> bool:
    return ASSETS_BACKUP_DIRNAME in relative_path.parts or relative_path.name == (
        ASSETS_VERSION_MARKER
    )


async def _dump_assets(service: BackupService, staging_dir: Path) -> Dict[str, Any]:
    source_dir = service.config.assets_dir
    assets_dir = staging_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    files_count = 0
    total_size = 0

    if source_dir.exists():
        for source_file in source_dir.rglob("*"):
            if not source_file.is_file():
                continue

            relative_path = source_file.relative_to(source_dir)
            if service._should_skip_asset_file(relative_path):
                continue

            target_path = assets_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_path)
            files_count += 1
            total_size += source_file.stat().st_size

    logger.info(f"Backed up assets from '{source_dir}' ({files_count} files)")

    return {
        "path": assets_dir.name,
        "root": str(source_dir),
        "files_count": files_count,
        "size_bytes": total_size,
    }


async def _cleanup_old_backups(service: BackupService) -> None:
    try:
        backups = await service.get_backup_list()
        if len(backups) > service.config.backup.max_keep:
            for backup in backups[service.config.backup.max_keep :]:
                try:
                    await service.delete_backup(backup.filename)
                    logger.info(f"🗑️ Удалён старый бэкап: {backup.filename}")
                except Exception as exc:
                    logger.error(f"Ошибка удаления старого бэкапа {backup.filename}: {exc}")
    except Exception as exc:
        logger.error(f"Ошибка очистки старых бэкапов: {exc}")
