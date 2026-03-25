import asyncio
import gzip
import json as json_lib
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from uuid import UUID

import aiofiles  # type: ignore[import-untyped]
from aiogram import Bot
from aiogram.types import FSInputFile, Message
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import ARRAY, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import AppConfig
from src.core.enums import BackupScope, BackupSourceKind, Locale
from src.core.utils.assets_sync import ASSETS_BACKUP_DIRNAME, ASSETS_VERSION_MARKER
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.sql import (
    BackupRecord,
    Broadcast,
    BroadcastMessage,
    Partner,
    PartnerReferral,
    PartnerTransaction,
    PartnerWithdrawal,
    PaymentGateway,
    Plan,
    PlanDuration,
    PlanPrice,
    Promocode,
    PromocodeActivation,
    Referral,
    ReferralReward,
    Settings,
    Subscription,
    Transaction,
    User,
)
from src.infrastructure.redis import RedisRepository

from .base import BaseService

_aiofiles_open = cast(Callable[..., Any], aiofiles.open)
BACKUP_FORMAT_VERSION = "3.1"


@dataclass
class BackupMetadata:
    """Метаданные бэкапа."""

    timestamp: str
    version: str = BACKUP_FORMAT_VERSION
    database_type: str = "postgresql"
    backup_scope: BackupScope = BackupScope.FULL
    includes_database: bool = True
    includes_assets: bool = False
    assets_root: Optional[str] = None
    tables_count: int = 0
    total_records: int = 0
    compressed: bool = True
    file_size_bytes: int = 0
    created_by: Optional[int] = None


@dataclass
class BackupInfo:
    """Информация о файле бэкапа."""

    selection_key: str
    filename: str
    filepath: str
    timestamp: str
    tables_count: int
    total_records: int
    compressed: bool
    file_size_bytes: int
    file_size_mb: float
    created_by: Optional[int]
    database_type: str
    version: str
    backup_scope: BackupScope = BackupScope.FULL
    includes_database: bool = True
    includes_assets: bool = False
    assets_root: Optional[str] = None
    assets_files_count: int = 0
    assets_size_bytes: int = 0
    source_kind: BackupSourceKind = BackupSourceKind.LOCAL
    has_local_copy: bool = True
    has_telegram_copy: bool = False
    telegram_file_id: Optional[str] = None
    error: Optional[str] = None


class BackupService(BaseService):
    """Сервис для создания и восстановления бэкапов базы данных."""

    session_pool: async_sessionmaker[AsyncSession]
    engine: AsyncEngine

    # Модели для бэкапа в порядке зависимостей
    BACKUP_MODELS = [
        Settings,
        PaymentGateway,
        Plan,
        PlanDuration,
        PlanPrice,
        User,
        Partner,
        PartnerReferral,
        Promocode,
        PromocodeActivation,
        Subscription,
        Transaction,
        PartnerTransaction,
        PartnerWithdrawal,
        Referral,
        ReferralReward,
        Broadcast,
        BroadcastMessage,
    ]

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        session_pool: async_sessionmaker[AsyncSession],
        engine: AsyncEngine,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.session_pool = session_pool
        self.engine = engine
        self._auto_backup_task: Optional[asyncio.Task] = None
        self._backup_dir = self.config.backup.get_backup_dir()

    @property
    def backup_dir(self) -> Path:
        """Директория для хранения бэкапов."""
        return self._backup_dir

    def _parse_backup_time(self) -> Tuple[int, int]:
        """Парсит время запуска автобэкапа."""
        time_str = (self.config.backup.time or "").strip()
        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                raise ValueError("Invalid time format")

            hours, minutes = map(int, parts)
            if not (0 <= hours < 24 and 0 <= minutes < 60):
                raise ValueError("Hours or minutes out of range")

            return hours, minutes
        except ValueError:
            logger.warning(f"Некорректное значение BACKUP_TIME='{time_str}'. Используется 03:00.")
            return 3, 0

    def _calculate_next_backup_datetime(self, reference: Optional[datetime] = None) -> datetime:
        """Вычисляет время следующего автобэкапа."""
        reference = reference or datetime_now()
        hours, minutes = self._parse_backup_time()

        next_run = reference.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if next_run <= reference:
            next_run += timedelta(days=1)

        return next_run

    def _get_backup_interval(self) -> timedelta:
        """Получает интервал между автобэкапами."""
        hours = self.config.backup.interval_hours
        if hours <= 0:
            logger.warning(f"Некорректное значение BACKUP_INTERVAL_HOURS={hours}. Используется 24.")
            hours = 24
        return timedelta(hours=hours)

    async def create_backup(
        self,
        created_by: Optional[int] = None,
        compress: Optional[bool] = None,
        include_logs: Optional[bool] = None,
        scope: BackupScope = BackupScope.FULL,
        locale: Locale | None = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Создаёт бэкап базы данных.

        Args:
            created_by: ID пользователя, создавшего бэкап
            compress: Сжимать ли бэкап (по умолчанию из конфига)
            include_logs: Включать ли логи (по умолчанию из конфига)

        Returns:
            Tuple[success, message, filepath]
        """
        try:
            logger.info("📄 Начинаем создание бэкапа...")

            if compress is None:
                compress = self.config.backup.compression
            if include_logs is None:
                include_logs = self.config.backup.include_logs

            includes_database = scope in (BackupScope.DB, BackupScope.FULL)
            includes_assets = scope in (BackupScope.ASSETS, BackupScope.FULL)

            # Собираем статистику
            overview: Dict[str, Any] = {"tables_count": 0, "total_records": 0}
            if includes_database:
                overview = await self._collect_database_overview()

            timestamp = datetime_now().strftime("%Y%m%d_%H%M%S")
            archive_suffix = ".tar.gz" if compress else ".tar"
            filename = f"backup_{scope.lower()}_{timestamp}{archive_suffix}"
            backup_path = self.backup_dir / filename

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                staging_dir = temp_path / "backup"
                staging_dir.mkdir(parents=True, exist_ok=True)

                # Экспортируем БД через ORM
                database_info: Optional[Dict[str, Any]] = None
                assets_info: Optional[Dict[str, Any]] = None
                if includes_database:
                    database_info = await self._dump_database_json(staging_dir)
                if includes_assets:
                    assets_info = await self._dump_assets(staging_dir)

                # Метаданные
                metadata = {
                    "format_version": BACKUP_FORMAT_VERSION,
                    "timestamp": datetime_now().isoformat(),
                    "database_type": "postgresql",
                    "backup_scope": scope.value,
                    "backup_type": scope.value,
                    "includes_database": includes_database,
                    "includes_assets": includes_assets,
                    "assets_root": str(self.config.assets_dir) if includes_assets else None,
                    "tables_count": overview.get("tables_count", 0),
                    "total_records": overview.get("total_records", 0),
                    "compressed": compress,
                    "created_by": created_by,
                    "database": database_info,
                    "assets": assets_info,
                    "include_logs": include_logs,
                }

                metadata_path = staging_dir / "metadata.json"
                async with _aiofiles_open(metadata_path, "w", encoding="utf-8") as meta_file:
                    await meta_file.write(json_lib.dumps(metadata, ensure_ascii=False, indent=2))

                # Создаём архив
                mode = "w:gz" if compress else "w"
                with tarfile.open(str(backup_path), mode) as tar:
                    for item in staging_dir.iterdir():
                        tar.add(item, arcname=item.name)

            file_size = backup_path.stat().st_size
            backup_info = self._metadata_to_backup_info(
                backup_path,
                backup_path.stat(),
                metadata,
            )
            await self._upsert_backup_record(
                backup_info=backup_info,
                local_path=backup_path,
            )

            sent_message = await self._send_backup_file_to_chat(str(backup_path))
            if sent_message is not None:
                await self._upsert_backup_record(
                    backup_info=backup_info,
                    local_path=backup_path,
                    telegram_message=sent_message,
                )

            await self._cleanup_old_backups()

            size_mb = file_size / 1024 / 1024
            message = (
                f"✅ Бэкап успешно создан!\n"
                f"📁 Файл: {filename}\n"
                f"📊 Таблиц: {overview.get('tables_count', 0)}\n"
                f"📈 Записей: {overview.get('total_records', 0):,}\n"
                f"💾 Размер: {size_mb:.2f} MB"
            )

            message = self._build_backup_result_message(
                scope=scope,
                filename=filename,
                size_mb=size_mb,
                overview=overview,
                includes_database=includes_database,
                assets_info=assets_info,
                locale=locale,
            )
            logger.info(message)

            return True, message, str(backup_path)

        except Exception as e:
            if locale is not None:
                error_msg = self._build_backup_create_error_message(str(e), locale=locale)
                logger.error(error_msg, exc_info=True)
                return False, error_msg, None
            error_msg = f"❌ Ошибка создания бэкапа: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None

    async def restore_backup(
        self,
        backup_file_path: str,
        clear_existing: bool = False,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        """
        Восстанавливает базу данных из бэкапа.

        Args:
            backup_file_path: Путь к файлу бэкапа
            clear_existing: Очистить ли существующие данные

        Returns:
            Tuple[success, message]
        """
        try:
            logger.info(f"📄 Начинаем восстановление из {backup_file_path}")

            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                if locale is not None:
                    return False, self._build_backup_missing_file_message(
                        backup_file_path,
                        locale=locale,
                    )
                return False, f"❌ Файл бэкапа не найден: {backup_file_path}"

            if self._is_archive_backup(backup_path):
                success, message = await self._restore_from_archive(
                    backup_path,
                    clear_existing,
                    locale=locale,
                )
            else:
                success, message = await self._restore_from_json(
                    backup_path,
                    clear_existing,
                    locale=locale,
                )

            return success, message

        except Exception as e:
            if locale is not None:
                error_msg = self._build_backup_restore_error_message(str(e), locale=locale)
                logger.error(error_msg, exc_info=True)
                return False, error_msg
            error_msg = f"Restore failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def get_backup_list(self) -> List[BackupInfo]:
        """Получает список всех бэкапов."""
        backups: List[BackupInfo] = []
        known_local_paths: set[Path] = set()
        known_filenames: set[str] = set()

        try:
            registered_backups = await self._list_registered_backup_infos()
            backups.extend(registered_backups)
            for backup in registered_backups:
                known_filenames.add(backup.filename)
                if backup.has_local_copy and backup.filepath:
                    known_local_paths.add(Path(backup.filepath))

            for backup_file in sorted(self.backup_dir.glob("backup_*"), reverse=True):
                if (
                    not backup_file.is_file()
                    or backup_file in known_local_paths
                    or backup_file.name in known_filenames
                ):
                    continue

                try:
                    metadata = await self._read_backup_metadata(backup_file)
                    file_stats = backup_file.stat()
                    backups.append(self._metadata_to_backup_info(backup_file, file_stats, metadata))
                except Exception as e:
                    logger.error(f"Ошибка чтения метаданных {backup_file}: {e}")
                    file_stats = backup_file.stat()
                    backups.append(
                        BackupInfo(
                            selection_key=f"local:{backup_file.name}",
                            filename=backup_file.name,
                            filepath=str(backup_file),
                            timestamp=datetime.fromtimestamp(
                                file_stats.st_mtime, tz=timezone.utc
                            ).isoformat(),
                            tables_count=0,
                            total_records=0,
                            compressed=self._is_archive_backup(backup_file),
                            file_size_bytes=file_stats.st_size,
                            file_size_mb=round(file_stats.st_size / 1024 / 1024, 2),
                            created_by=None,
                            database_type="unknown",
                            version="unknown",
                            backup_scope=BackupScope.FULL,
                            includes_database=True,
                            includes_assets=False,
                            source_kind=BackupSourceKind.LOCAL,
                            has_local_copy=True,
                            has_telegram_copy=False,
                            error=str(e),
                        )
                    )

            backups.sort(
                key=lambda item: self._backup_sort_timestamp(item.timestamp),
                reverse=True,
            )
        except Exception as e:
            logger.error(f"Ошибка получения списка бэкапов: {e}")

        return backups

    async def get_backup_by_key(self, selection_key: str) -> Optional[BackupInfo]:
        backups = await self.get_backup_list()
        return next((backup for backup in backups if backup.selection_key == selection_key), None)

    async def restore_selected_backup(
        self,
        selection_key: str,
        *,
        clear_existing: bool = False,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        backup_info = await self.get_backup_by_key(selection_key)
        if backup_info is None:
            if locale is not None:
                return False, self._build_backup_missing_file_message(selection_key, locale=locale)
            return False, f"Backup not found: {selection_key}"

        if backup_info.has_local_copy and backup_info.filepath:
            return await self.restore_backup(
                backup_info.filepath,
                clear_existing=clear_existing,
                locale=locale,
            )

        if backup_info.has_telegram_copy and backup_info.telegram_file_id:
            suffixes = "".join(Path(backup_info.filename).suffixes)
            if not suffixes:
                suffixes = ".tar.gz"
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"telegram_restore{suffixes}"
                try:
                    await self._download_telegram_backup_file(
                        telegram_file_id=backup_info.telegram_file_id,
                        destination=temp_path,
                    )
                except Exception as exc:
                    if locale is not None:
                        return (
                            False,
                            self._build_backup_restore_error_message(
                                str(exc),
                                locale=locale,
                            ),
                        )
                    return False, f"Restore failed: {exc}"

                return await self.restore_backup(
                    str(temp_path),
                    clear_existing=clear_existing,
                    locale=locale,
                )

        if locale is not None:
            return (
                False,
                self._build_backup_missing_file_message(
                    backup_info.filename,
                    locale=locale,
                ),
            )
        return False, f"Backup source is unavailable: {backup_info.filename}"

    async def delete_selected_backup(
        self,
        selection_key: str,
        *,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        backup_info = await self.get_backup_by_key(selection_key)
        if backup_info is None:
            if locale is not None:
                return False, self._build_backup_missing_file_message(selection_key, locale=locale)
            return False, f"Backup not found: {selection_key}"

        if not backup_info.has_local_copy or not backup_info.filepath:
            if locale is not None:
                return False, self._build_backup_delete_error_message(
                    self.translator_hub.get_translator_by_locale(locale=locale).get(
                        "msg-backup-error-telegram-only-delete"
                    ),
                    locale=locale,
                )
            return False, "Telegram-only backup cannot delete a local copy"

        return await self.delete_backup(backup_info.filename, locale=locale)

    async def delete_backup(
        self,
        backup_filename: str,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        """Удаляет файл бэкапа."""
        try:
            backup_path = self.backup_dir / backup_filename

            if not backup_path.exists():
                if locale is not None:
                    return False, self._build_backup_missing_file_message(
                        backup_filename,
                        locale=locale,
                    )
                return False, f"Backup file not found: {backup_filename}"

            backup_path.unlink()
            await self._sync_backup_record_after_local_delete(
                backup_filename=backup_filename,
                deleted_path=backup_path,
            )
            if locale is not None:
                message = self._build_backup_deleted_message(backup_filename, locale=locale)
                logger.info(message)
                return True, message
            message = f"Backup {backup_filename} deleted"
            logger.info(message)

            return True, message

        except Exception as e:
            if locale is not None:
                error_msg = self._build_backup_delete_error_message(str(e), locale=locale)
                logger.error(error_msg)
                return False, error_msg
            error_msg = f"Backup deletion failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def start_auto_backup(self) -> None:
        """Запускает цикл автоматических бэкапов."""
        if self._auto_backup_task and not self._auto_backup_task.done():
            self._auto_backup_task.cancel()

        if self.config.backup.auto_enabled:
            next_run = self._calculate_next_backup_datetime()
            interval = self._get_backup_interval()
            self._auto_backup_task = asyncio.create_task(self._auto_backup_loop(next_run))
            logger.info(
                f"📄 Автобэкапы включены, интервал: {interval.total_seconds() / 3600:.2f}ч, "
                f"ближайший запуск: {next_run.strftime('%d.%m.%Y %H:%M:%S')}"
            )

    async def stop_auto_backup(self) -> None:
        """Останавливает цикл автоматических бэкапов."""
        if self._auto_backup_task and not self._auto_backup_task.done():
            self._auto_backup_task.cancel()
            logger.info("ℹ️ Автобэкапы остановлены")

    # --- Private methods ---

    async def _auto_backup_loop(self, next_run: Optional[datetime] = None) -> None:
        """Цикл автоматических бэкапов."""
        next_run = next_run or self._calculate_next_backup_datetime()
        interval = self._get_backup_interval()

        while True:
            try:
                now = datetime_now()
                delay = (next_run - now).total_seconds()

                if delay > 0:
                    logger.info(
                        f"⏰ Следующий автобэкап: {next_run.strftime('%d.%m.%Y %H:%M:%S')} "
                        f"(через {delay / 3600:.2f} ч)"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.info("⏰ Время автобэкапа уже наступило, запускаем немедленно")

                logger.info("📄 Запуск автоматического бэкапа...")
                success, message, _ = await self.create_backup()

                if success:
                    logger.info(f"✅ Автобэкап завершен: {message}")
                else:
                    logger.error(f"❌ Ошибка автобэкапа: {message}")

                next_run = next_run + interval

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле автобэкапов: {e}")
                next_run = datetime_now() + interval

    async def _collect_database_overview(self) -> Dict[str, Any]:
        """Собирает статистику по таблицам БД."""
        overview: Dict[str, Any] = {
            "tables_count": 0,
            "total_records": 0,
            "tables": [],
        }

        try:
            async with self.engine.begin() as conn:
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

    async def _dump_database_json(self, staging_dir: Path) -> Dict[str, Any]:
        """Экспортирует БД в JSON через ORM."""
        backup_data: Dict[str, List[Dict[str, Any]]] = {}
        total_records = 0

        async with self.session_pool() as session:
            for model in self.BACKUP_MODELS:
                table_name = model.__tablename__
                logger.info(f"📊 Экспортируем таблицу: {table_name}")

                try:
                    result = await session.execute(select(model))
                    records = result.scalars().all()

                    table_data: List[Dict[str, Any]] = []
                    for record in records:
                        record_dict = self._model_to_dict(record, model)
                        table_data.append(record_dict)

                    backup_data[table_name] = table_data
                    total_records += len(table_data)

                    logger.info(f"✅ Экспортировано {len(table_data)} записей из {table_name}")

                except Exception as e:
                    logger.error(f"Ошибка экспорта таблицы {table_name}: {e}")
                    backup_data[table_name] = []

        # Сохраняем в файл
        dump_path = staging_dir / "database.json"
        dump_structure = {
            "metadata": {
                "timestamp": datetime_now().isoformat(),
                "version": "orm-1.0",
                "database_type": "postgresql",
                "tables_count": len(self.BACKUP_MODELS),
                "total_records": total_records,
            },
            "data": backup_data,
        }

        async with _aiofiles_open(dump_path, "w", encoding="utf-8") as f:
            await f.write(json_lib.dumps(dump_structure, ensure_ascii=False, indent=2, default=str))

        size = dump_path.stat().st_size if dump_path.exists() else 0

        logger.info(f"✅ БД экспортирована в JSON ({dump_path})")

        return {
            "type": "postgresql",
            "path": dump_path.name,
            "size_bytes": size,
            "format": "json",
            "tool": "orm",
            "tables_count": len(self.BACKUP_MODELS),
            "total_records": total_records,
        }

    @staticmethod
    def _should_skip_asset_file(relative_path: Path) -> bool:
        return ASSETS_BACKUP_DIRNAME in relative_path.parts or relative_path.name == (
            ASSETS_VERSION_MARKER
        )

    async def _dump_assets(self, staging_dir: Path) -> Dict[str, Any]:
        """Copy mutable runtime assets into the backup staging directory."""
        source_dir = self.config.assets_dir
        assets_dir = staging_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        files_count = 0
        total_size = 0

        if source_dir.exists():
            for source_file in source_dir.rglob("*"):
                if not source_file.is_file():
                    continue

                relative_path = source_file.relative_to(source_dir)
                if self._should_skip_asset_file(relative_path):
                    continue
                target_file = assets_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_file)
                files_count += 1
                total_size += source_file.stat().st_size

        logger.info(
            "Backed up assets from '{}' ({} files)",
            source_dir,
            files_count,
        )

        return {
            "path": assets_dir.name,
            "root": str(source_dir),
            "files_count": files_count,
            "size_bytes": total_size,
        }

    @staticmethod
    def _format_scope_label(scope: BackupScope) -> str:
        mapping = {
            BackupScope.DB: "Database only",
            BackupScope.ASSETS: "Assets only",
            BackupScope.FULL: "Full backup",
        }
        return mapping[scope]

    def _format_scope_label_localized(self, scope: BackupScope, locale: Locale | None) -> str:
        if locale is None:
            return self._format_scope_label(scope)

        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        mapping = {
            BackupScope.DB: i18n.get("msg-backup-scope-db-label"),
            BackupScope.ASSETS: i18n.get("msg-backup-scope-assets-label"),
            BackupScope.FULL: i18n.get("msg-backup-scope-full-label"),
        }
        return mapping[scope]

    def _build_backup_result_message(
        self,
        *,
        scope: BackupScope,
        filename: str,
        size_mb: float,
        overview: Dict[str, Any],
        includes_database: bool,
        assets_info: Optional[Dict[str, Any]],
        locale: Locale | None = None,
    ) -> str:
        if locale is not None:
            i18n = self.translator_hub.get_translator_by_locale(locale=locale)
            lines = [
                i18n.get("msg-backup-result-created-title"),
                i18n.get(
                    "msg-backup-result-scope",
                    scope=self._format_scope_label_localized(scope, locale),
                ),
                i18n.get("msg-backup-result-file", value=filename),
                i18n.get("msg-backup-result-size", value=f"{size_mb:.2f} MB"),
            ]
            if includes_database:
                lines.append(
                    i18n.get("msg-backup-result-tables", count=overview.get("tables_count", 0))
                )
                lines.append(
                    i18n.get(
                        "msg-backup-result-records",
                        count=f"{overview.get('total_records', 0):,}",
                    )
                )
            if assets_info is not None:
                lines.append(
                    i18n.get(
                        "msg-backup-content-assets-files",
                        count=int(assets_info.get("files_count", 0) or 0),
                    )
                )
            return "\n".join(lines)

        lines = [
            "Backup created successfully!",
            f"Scope: {self._format_scope_label(scope)}",
            f"File: {filename}",
            f"Size: {size_mb:.2f} MB",
        ]
        if includes_database:
            lines.append(f"Tables: {overview.get('tables_count', 0)}")
            lines.append(f"Records: {overview.get('total_records', 0):,}")
        if assets_info is not None:
            lines.append(f"Assets files: {assets_info.get('files_count', 0)}")
        return "\n".join(lines)

    def _build_backup_create_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup creation failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-create", error=error)

    def _build_backup_restore_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Restore failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-restore", error=error)

    def _build_backup_missing_file_message(
        self,
        path: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup file not found: {path}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-file-missing", path=path)

    def _build_backup_deleted_message(
        self,
        backup_filename: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup {backup_filename} deleted"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-result-deleted", filename=backup_filename)

    def _build_backup_delete_error_message(
        self,
        error: str,
        *,
        locale: Locale | None = None,
    ) -> str:
        if locale is None:
            return f"Backup deletion failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-delete", error=error)

    def _normalize_backup_scope(self, metadata: Dict[str, Any]) -> BackupScope:
        scope_value = str(
            metadata.get("backup_scope") or metadata.get("backup_type") or BackupScope.FULL
        ).upper()
        try:
            scope = BackupScope(scope_value)
        except ValueError:
            scope = BackupScope.FULL

        if not metadata.get("includes_database") and metadata.get("database"):
            return BackupScope.DB if not metadata.get("includes_assets") else BackupScope.FULL
        return scope

    def _metadata_to_backup_info(
        self,
        backup_file: Path,
        file_stats: Any,
        metadata: Dict[str, Any],
    ) -> BackupInfo:
        scope = self._normalize_backup_scope(metadata)
        includes_database = bool(metadata.get("includes_database", metadata.get("database")))
        includes_assets = bool(metadata.get("includes_assets", metadata.get("assets")))
        assets_info = metadata.get("assets") or {}

        return BackupInfo(
            selection_key=f"local:{backup_file.name}",
            filename=backup_file.name,
            filepath=str(backup_file),
            timestamp=metadata.get(
                "timestamp",
                datetime.fromtimestamp(file_stats.st_mtime, tz=timezone.utc).isoformat(),
            ),
            tables_count=metadata.get("tables_count", 0),
            total_records=metadata.get("total_records", 0),
            compressed=self._is_archive_backup(backup_file),
            file_size_bytes=file_stats.st_size,
            file_size_mb=round(file_stats.st_size / 1024 / 1024, 2),
            created_by=metadata.get("created_by"),
            database_type=metadata.get("database_type", "unknown"),
            version=metadata.get("format_version", "1.0"),
            backup_scope=scope,
            includes_database=includes_database,
            includes_assets=includes_assets,
            assets_root=metadata.get("assets_root") or assets_info.get("root"),
            assets_files_count=int(assets_info.get("files_count", 0) or 0),
            assets_size_bytes=int(assets_info.get("size_bytes", 0) or 0),
            source_kind=BackupSourceKind.LOCAL,
            has_local_copy=True,
            has_telegram_copy=False,
        )

    def _parse_backup_timestamp(self, value: object) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _backup_sort_timestamp(self, value: object) -> float:
        parsed = self._parse_backup_timestamp(value)
        if parsed is None:
            return 0.0
        return parsed.timestamp()

    def _resolve_backup_source_kind(
        self,
        *,
        has_local_copy: bool,
        has_telegram_copy: bool,
    ) -> BackupSourceKind:
        if has_local_copy and has_telegram_copy:
            return BackupSourceKind.LOCAL_AND_TELEGRAM
        if has_telegram_copy:
            return BackupSourceKind.TELEGRAM
        return BackupSourceKind.LOCAL

    def _resolve_registry_local_path(self, record: BackupRecord) -> Optional[Path]:
        if record.local_path:
            candidate = Path(record.local_path)
            if candidate.exists():
                return candidate

        fallback = self.backup_dir / record.filename
        if fallback.exists():
            return fallback

        return None

    def _record_to_backup_info(self, record: BackupRecord) -> Optional[BackupInfo]:
        local_path = self._resolve_registry_local_path(record)
        has_local_copy = local_path is not None
        has_telegram_copy = bool(record.telegram_file_id)
        if not has_local_copy and not has_telegram_copy:
            return None

        scope_value = (record.backup_scope or BackupScope.FULL.value).upper()
        try:
            backup_scope = BackupScope(scope_value)
        except ValueError:
            backup_scope = BackupScope.FULL

        timestamp = (
            record.backup_timestamp.isoformat()
            if record.backup_timestamp
            else record.created_at.isoformat()
        )

        return BackupInfo(
            selection_key=f"registry:{record.id}",
            filename=record.filename,
            filepath=str(local_path) if local_path else "",
            timestamp=timestamp,
            tables_count=record.tables_count,
            total_records=record.total_records,
            compressed=record.compressed,
            file_size_bytes=record.file_size_bytes,
            file_size_mb=round(record.file_size_bytes / 1024 / 1024, 2),
            created_by=record.created_by,
            database_type=record.database_type,
            version=record.version,
            backup_scope=backup_scope,
            includes_database=record.includes_database,
            includes_assets=record.includes_assets,
            assets_root=record.assets_root,
            assets_files_count=record.assets_files_count,
            assets_size_bytes=record.assets_size_bytes,
            source_kind=self._resolve_backup_source_kind(
                has_local_copy=has_local_copy,
                has_telegram_copy=has_telegram_copy,
            ),
            has_local_copy=has_local_copy,
            has_telegram_copy=has_telegram_copy,
            telegram_file_id=record.telegram_file_id,
        )

    async def _list_registered_backup_infos(self) -> List[BackupInfo]:
        async with self.session_pool() as session:
            result = await session.execute(
                select(BackupRecord).order_by(
                    BackupRecord.backup_timestamp.desc().nullslast(),
                    BackupRecord.created_at.desc(),
                    BackupRecord.id.desc(),
                )
            )
            records = list(result.scalars().all())

        backups: List[BackupInfo] = []
        for record in records:
            backup_info = self._record_to_backup_info(record)
            if backup_info is not None:
                backups.append(backup_info)
        return backups

    async def _upsert_backup_record(
        self,
        *,
        backup_info: BackupInfo,
        local_path: Optional[Path],
        telegram_message: Optional[Message] = None,
    ) -> None:
        async with self.session_pool() as session:
            result = await session.execute(
                select(BackupRecord)
                .where(BackupRecord.filename == backup_info.filename)
                .order_by(BackupRecord.id.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()

            if record is None:
                record = BackupRecord(
                    filename=backup_info.filename,
                    backup_timestamp=self._parse_backup_timestamp(backup_info.timestamp),
                    created_by=backup_info.created_by,
                    backup_scope=backup_info.backup_scope.value,
                    includes_database=backup_info.includes_database,
                    includes_assets=backup_info.includes_assets,
                    assets_root=backup_info.assets_root,
                    tables_count=backup_info.tables_count,
                    total_records=backup_info.total_records,
                    compressed=backup_info.compressed,
                    file_size_bytes=backup_info.file_size_bytes,
                    database_type=backup_info.database_type,
                    version=backup_info.version,
                    assets_files_count=backup_info.assets_files_count,
                    assets_size_bytes=backup_info.assets_size_bytes,
                    local_path=str(local_path) if local_path else None,
                )
                session.add(record)
            else:
                record.backup_timestamp = self._parse_backup_timestamp(backup_info.timestamp)
                record.created_by = backup_info.created_by
                record.backup_scope = backup_info.backup_scope.value
                record.includes_database = backup_info.includes_database
                record.includes_assets = backup_info.includes_assets
                record.assets_root = backup_info.assets_root
                record.tables_count = backup_info.tables_count
                record.total_records = backup_info.total_records
                record.compressed = backup_info.compressed
                record.file_size_bytes = backup_info.file_size_bytes
                record.database_type = backup_info.database_type
                record.version = backup_info.version
                record.assets_files_count = backup_info.assets_files_count
                record.assets_size_bytes = backup_info.assets_size_bytes
                if local_path is not None:
                    record.local_path = str(local_path)

            if telegram_message and telegram_message.document:
                record.telegram_chat_id = telegram_message.chat.id
                record.telegram_thread_id = telegram_message.message_thread_id
                record.telegram_message_id = telegram_message.message_id
                record.telegram_file_id = telegram_message.document.file_id
                record.telegram_file_unique_id = telegram_message.document.file_unique_id

            await session.commit()

    async def _sync_backup_record_after_local_delete(
        self,
        *,
        backup_filename: str,
        deleted_path: Optional[Path],
    ) -> None:
        async with self.session_pool() as session:
            result = await session.execute(
                select(BackupRecord).where(BackupRecord.filename == backup_filename)
            )
            records = list(result.scalars().all())
            changed = False

            for record in records:
                matches_deleted_path = (
                    deleted_path is not None and record.local_path == str(deleted_path)
                )
                matches_fallback_path = (
                    deleted_path is not None
                    and deleted_path == (self.backup_dir / record.filename)
                )
                if record.local_path is None and not matches_fallback_path:
                    continue
                if (
                    deleted_path is not None
                    and not matches_deleted_path
                    and not matches_fallback_path
                ):
                    continue

                record.local_path = None
                changed = True
                if not record.telegram_file_id:
                    await session.delete(record)

            if changed:
                await session.commit()

    async def _download_telegram_backup_file(
        self,
        *,
        telegram_file_id: str,
        destination: Path,
    ) -> None:
        file = await self.bot.get_file(telegram_file_id)
        if not file.file_path:
            raise ValueError(f"File path not found for telegram backup '{telegram_file_id}'")

        await self.bot.download_file(file.file_path, destination=destination)

    async def import_backup_file(
        self,
        *,
        source_file_path: Path,
        original_filename: Optional[str],
        created_by: Optional[int],
    ) -> Tuple[bool, Optional[BackupInfo], str]:
        filename = self._build_imported_backup_filename(original_filename or source_file_path.name)
        target_path = self.backup_dir / filename

        shutil.copy2(source_file_path, target_path)

        try:
            metadata = await self._read_backup_metadata(target_path)
            if not metadata:
                raise ValueError("Backup metadata file is missing.")

            scope = self._normalize_backup_scope(metadata)
            includes_database = bool(metadata.get("includes_database", metadata.get("database")))
            includes_assets = bool(metadata.get("includes_assets", metadata.get("assets")))
            if not includes_database and not includes_assets:
                raise ValueError("Backup does not contain restorable data.")

            file_stats = target_path.stat()
            backup_info = self._metadata_to_backup_info(target_path, file_stats, metadata)
            backup_info.backup_scope = scope
            backup_info.includes_database = includes_database
            backup_info.includes_assets = includes_assets
            backup_info.created_by = (
                created_by if created_by is not None else backup_info.created_by
            )
            await self._upsert_backup_record(backup_info=backup_info, local_path=target_path)
            await self._cleanup_old_backups()
            return True, backup_info, ""
        except Exception as exc:
            if target_path.exists():
                target_path.unlink()
            return False, None, str(exc)

    def _build_imported_backup_filename(self, original_filename: str) -> str:
        candidate = (
            Path(original_filename or "backup_import.tar.gz").name.strip()
            or "backup_import.tar.gz"
        )
        base_name = candidate.replace(" ", "_")
        timestamp = datetime_now().strftime("%Y%m%d_%H%M%S")
        target_name = f"backup_import_{timestamp}_{base_name}"
        target_path = self.backup_dir / target_name
        suffix = 1
        while target_path.exists():
            target_name = f"backup_import_{timestamp}_{suffix}_{base_name}"
            target_path = self.backup_dir / target_name
            suffix += 1
        return target_name

    def _model_to_dict(self, record: Any, model: Any) -> Dict[str, Any]:
        """Конвертирует ORM модель в словарь."""
        record_dict: Dict[str, Any] = {}

        for column in model.__table__.columns:
            value = getattr(record, column.name)
            record_dict[column.name] = self._normalize_backup_value(value)

        return record_dict

    def _normalize_backup_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        if hasattr(value, "value"):  # Enum
            return value.value
        if hasattr(value, "model_dump"):
            return self._normalize_backup_value(value.model_dump(mode="json"))
        if isinstance(value, list):
            return [self._normalize_backup_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._normalize_backup_value(item) for key, item in value.items()}
        if hasattr(value, "__dict__"):
            return str(value)
        return value

    def _is_archive_backup(self, backup_path: Path) -> bool:
        """Проверяет, является ли файл архивом."""
        suffixes = backup_path.suffixes
        if (len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]) or (
            suffixes and suffixes[-1] == ".tar"
        ):
            return True
        try:
            return tarfile.is_tarfile(backup_path)
        except Exception:
            return False

    async def _read_backup_metadata(self, backup_path: Path) -> Dict[str, Any]:
        """Читает метаданные из файла бэкапа."""
        metadata = {}

        if self._is_archive_backup(backup_path):
            mode = "r:gz" if backup_path.suffixes and backup_path.suffixes[-1] == ".gz" else "r"
            with tarfile.open(str(backup_path), mode) as tar:
                try:
                    member = tar.getmember("metadata.json")
                    with tar.extractfile(member) as meta_file:
                        if meta_file:
                            metadata = json_lib.load(meta_file)
                except KeyError:
                    pass
        else:
            if backup_path.suffix == ".gz":
                with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                    backup_structure = json_lib.load(f)
            else:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_structure = json_lib.load(f)
            metadata = backup_structure.get("metadata", {})

        return metadata

    async def _restore_archive_database_part(
        self,
        *,
        temp_path: Path,
        metadata: Dict[str, Any],
        clear_existing: bool,
        locale: Locale | None,
    ) -> Tuple[bool, str]:
        database_info = metadata.get("database", {})
        dump_file = temp_path / database_info.get("path", "database.json")
        if not dump_file.exists():
            if locale is not None:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                return False, i18n.get(
                    "msg-backup-error-db-dump-missing",
                    path=str(dump_file),
                )
            return False, f"Database dump file not found: {dump_file}"

        return await self._restore_from_json(
            dump_file,
            clear_existing,
            locale=locale,
        )

    async def _restore_archive_assets_part(
        self,
        *,
        temp_path: Path,
        metadata: Dict[str, Any],
        locale: Locale | None,
    ) -> Tuple[bool, str]:
        assets_info = metadata.get("assets", {})
        assets_dir = temp_path / assets_info.get("path", "assets")
        if not assets_dir.exists():
            if locale is not None:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                return False, i18n.get(
                    "msg-backup-error-assets-missing",
                    path=str(assets_dir),
                )
            return False, f"Assets directory not found: {assets_dir}"

        return True, await self._restore_assets_from_dir(assets_dir, locale=locale)

    async def _restore_from_archive(
        self,
        backup_path: Path,
        clear_existing: bool,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        """Restore a selective backup archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            mode = "r:gz" if backup_path.suffixes and backup_path.suffixes[-1] == ".gz" else "r"
            with tarfile.open(str(backup_path), mode) as tar:
                tar.extractall(temp_path, filter="data")

            metadata_path = temp_path / "metadata.json"
            if not metadata_path.exists():
                if locale is not None:
                    i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                    return False, i18n.get("msg-backup-error-metadata-missing")
                return False, "Backup metadata file is missing"

            async with _aiofiles_open(metadata_path, "r", encoding="utf-8") as meta_file:
                metadata = json_lib.loads(await meta_file.read())

            logger.info(
                "Loaded archive backup format {}",
                metadata.get("format_version", "unknown"),
            )

            includes_database = bool(metadata.get("includes_database", metadata.get("database")))
            includes_assets = bool(metadata.get("includes_assets", metadata.get("assets")))
            result_parts: list[str] = []

            if includes_database:
                db_success, db_message = await self._restore_archive_database_part(
                    temp_path=temp_path,
                    metadata=metadata,
                    clear_existing=clear_existing,
                    locale=locale,
                )
                if not db_success:
                    return db_success, db_message
                result_parts.append(db_message)

            if includes_assets:
                assets_success, assets_message = await self._restore_archive_assets_part(
                    temp_path=temp_path,
                    metadata=metadata,
                    locale=locale,
                )
                if not assets_success:
                    return False, assets_message
                result_parts.append(assets_message)

            if not result_parts:
                if locale is not None:
                    i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                    return False, i18n.get("msg-backup-error-empty")
                return False, "Backup does not contain restorable data"

            return True, "\n\n".join(result_parts)


    async def _restore_assets_from_dir(
        self,
        source_dir: Path,
        *,
        locale: Locale | None = None,
    ) -> str:
        """Restore bundled runtime assets without wiping unrelated files."""
        target_dir = self.config.assets_dir
        restored_files = 0

        target_dir.mkdir(parents=True, exist_ok=True)

        for source_file in source_dir.rglob("*"):
            if not source_file.is_file():
                continue

            relative_path = source_file.relative_to(source_dir)
            if self._should_skip_asset_file(relative_path):
                continue
            target_file = target_dir / relative_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            restored_files += 1

        logger.info(
            "Restored {} asset file(s) into '{}'",
            restored_files,
            target_dir,
        )
        if locale is not None:
            i18n = self.translator_hub.get_translator_by_locale(locale=locale)
            return "\n".join(
                [
                    i18n.get("msg-backup-result-assets-restored-title"),
                    i18n.get("msg-backup-content-assets-files", count=restored_files),
                    i18n.get("msg-backup-result-target", value=str(target_dir)),
                ]
            )
        return (
            "Assets restored successfully!\n"
            f"Files: {restored_files}\n"
            f"Target: {target_dir}"
        )

    async def _restore_from_json(
        self,
        dump_path: Path,
        clear_existing: bool,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        """Восстановление из JSON-дампа."""
        async with _aiofiles_open(dump_path, "r", encoding="utf-8") as f:
            dump_data = json_lib.loads(await f.read())

        metadata = dump_data.get("metadata", {})
        backup_data = dump_data.get("data", {})

        if not backup_data:
            if locale is not None:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                return False, i18n.get("msg-backup-error-empty")
            return False, "❌ Файл бэкапа не содержит данных"

        logger.info(f"📊 Загружен дамп: {metadata.get('timestamp', 'неизвестная дата')}")

        restored_records = 0
        restored_tables = 0

        async with self.session_pool() as session:
            try:
                if clear_existing:
                    logger.warning("🗑️ Очищаем существующие данные...")
                    await self._clear_database_tables(session)

                # Восстанавливаем таблицы в порядке зависимостей
                for model in self.BACKUP_MODELS:
                    table_name = model.__tablename__
                    records = backup_data.get(table_name, [])

                    if not records:
                        continue

                    logger.info(f"🔥 Восстанавливаем таблицу {table_name} ({len(records)} записей)")

                    restored = await self._restore_table_records(
                        session,
                        model,
                        table_name,
                        records,
                        clear_existing,
                    )
                    await session.flush()
                    restored_records += restored

                    if restored:
                        restored_tables += 1
                        logger.info(f"✅ Таблица {table_name} восстановлена")

                await session.commit()

            except Exception as exc:
                await session.rollback()
                logger.error(f"Ошибка при восстановлении: {exc}")
                raise exc

        message = (
            f"✅ Восстановление завершено!\n"
            f"📊 Таблиц: {restored_tables}\n"
            f"📈 Записей: {restored_records:,}\n"
            f"📅 Дата бэкапа: {metadata.get('timestamp', 'неизвестно')}"
        )

        if locale is not None:
            i18n = self.translator_hub.get_translator_by_locale(locale=locale)
            message = "\n".join(
                [
                    i18n.get("msg-backup-result-db-restored-title"),
                    i18n.get("msg-backup-result-tables", count=restored_tables),
                    i18n.get("msg-backup-result-records", count=f"{restored_records:,}"),
                    i18n.get(
                        "msg-backup-result-backup-date",
                        value=metadata.get("timestamp", i18n.get("msg-backup-value-unknown")),
                    ),
                ]
            )

        logger.info(message)
        return True, message

    async def _restore_table_records(
        self,
        session: AsyncSession,
        model: Any,
        table_name: str,
        records: List[Dict[str, Any]],
        clear_existing: bool,
    ) -> int:
        """Восстанавливает записи в таблицу."""
        restored_count = 0

        for record_data in records:
            try:
                processed_data = self._process_record_data(record_data, model, table_name)
                primary_key_col = self._get_primary_key_column(model)

                if primary_key_col and primary_key_col in processed_data:
                    with session.no_autoflush:
                        existing_record = await session.execute(
                            select(model).where(
                                getattr(model, primary_key_col) == processed_data[primary_key_col]
                            )
                        )
                    existing = existing_record.scalar_one_or_none()

                    if existing and not clear_existing:
                        for key, value in processed_data.items():
                            if key != primary_key_col:
                                setattr(existing, key, value)
                    else:
                        instance = model(**processed_data)
                        session.add(instance)
                else:
                    instance = model(**processed_data)
                    session.add(instance)

                restored_count += 1

            except Exception as e:
                logger.error(f"Ошибка восстановления записи в {table_name}: {e}")
                logger.error(f"Проблемные данные: {record_data}")
                raise e

        return restored_count

    def _parse_datetime_value(self, key: str, value: str) -> datetime:
        try:
            if "T" in value:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as exception:
            logger.warning(
                f"РќРµ СѓРґР°Р»РѕСЃСЊ РїР°СЂСЃРёС‚СЊ РґР°С‚Сѓ {value} "
                f"РґР»СЏ РїРѕР»СЏ {key}: {exception}"
            )
            return datetime_now()

    @staticmethod
    def _parse_boolean_value(value: str) -> bool:
        return value.lower() in ("true", "1", "yes", "on")

    @staticmethod
    def _parse_integer_value(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return 0

    @staticmethod
    def _parse_float_value(value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_json_value(value: Any) -> Any:
        if isinstance(value, str) and value.strip():
            try:
                return json_lib.loads(value)
            except (ValueError, TypeError):
                return value

        if isinstance(value, (list, dict)):
            return value

        return None

    @staticmethod
    def _parse_decimal_value(value: str) -> Decimal:
        try:
            return Decimal(value)
        except Exception:
            return Decimal("0")

    @staticmethod
    def _parse_uuid_value(value: str) -> UUID | str:
        try:
            return UUID(value)
        except (ValueError, TypeError, AttributeError):
            return value

    def _parse_array_item(self, item: Any, item_type_str: str) -> Any:
        if item is None:
            return None
        if "UUID" in item_type_str and isinstance(item, str):
            return self._parse_uuid_value(item)
        if (
            "INTEGER" in item_type_str
            or "INT" in item_type_str
            or "BIGINT" in item_type_str
        ) and isinstance(item, str):
            return self._parse_integer_value(item)
        if (
            "FLOAT" in item_type_str
            or "REAL" in item_type_str
            or "NUMERIC" in item_type_str
        ) and isinstance(item, str):
            return self._parse_decimal_value(item)
        if ("BOOLEAN" in item_type_str or "BOOL" in item_type_str) and isinstance(item, str):
            return self._parse_boolean_value(item)
        return item

    def _parse_array_value(self, value: Any, column: Any) -> Any:
        if value is None:
            return [] if not column.nullable else None

        items = value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return [] if not column.nullable else None
            try:
                items = json_lib.loads(stripped)
            except (ValueError, TypeError):
                items = value

        if items is None:
            return [] if not column.nullable else None

        if not isinstance(items, list):
            return items

        item_type_str = str(column.type.item_type).upper()
        return [self._parse_array_item(item, item_type_str) for item in items]

    def _process_column_value(self, key: str, value: Any, column: Any) -> Any:
        column_type_str = str(column.type).upper()

        if isinstance(column.type, ARRAY):
            return self._parse_array_value(value, column)

        if ("DATETIME" in column_type_str or "TIMESTAMP" in column_type_str) and isinstance(
            value, str
        ):
            return self._parse_datetime_value(key, value)

        if ("BOOLEAN" in column_type_str or "BOOL" in column_type_str) and isinstance(value, str):
            return self._parse_boolean_value(value)

        if (
            "INTEGER" in column_type_str
            or "INT" in column_type_str
            or "BIGINT" in column_type_str
        ) and isinstance(value, str):
            return self._parse_integer_value(value)

        if (
            "FLOAT" in column_type_str
            or "REAL" in column_type_str
            or "NUMERIC" in column_type_str
        ) and isinstance(value, str):
            return self._parse_decimal_value(value)

        if "JSON" in column_type_str:
            return self._parse_json_value(value)

        if "UUID" in column_type_str and isinstance(value, str):
            return self._parse_uuid_value(value)

        return value

    def _process_record_data(
        self,
        record_data: Dict[str, Any],
        model: Any,
        table_name: str,
    ) -> Dict[str, Any]:
        """Обрабатывает данные записи для восстановления."""
        processed_data: Dict[str, Any] = {}

        for key, value in record_data.items():
            column = getattr(model.__table__.columns, key, None)
            if column is None:
                logger.warning(f"Колонка {key} не найдена в модели {table_name}")
                continue

            if value is None and isinstance(column.type, ARRAY) and not column.nullable:
                processed_data[key] = []
                continue
            if value is None:
                processed_data[key] = None
                continue

            processed_data[key] = self._process_column_value(key, value, column)
            """

            if ("DATETIME" in column_type_str or "TIMESTAMP" in column_type_str) and isinstance(
                value, str
            ):
                try:
                    if "T" in value:
                        processed_data[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    else:
                        processed_data[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
                            tzinfo=timezone.utc
                        )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Не удалось парсить дату {value} для поля {key}: {e}")
                    processed_data[key] = datetime_now()
            elif ("BOOLEAN" in column_type_str or "BOOL" in column_type_str) and isinstance(
                value, str
            ):
                processed_data[key] = value.lower() in ("true", "1", "yes", "on")
            elif (
                "INTEGER" in column_type_str
                or "INT" in column_type_str
                or "BIGINT" in column_type_str
            ) and isinstance(value, str):
                try:
                    processed_data[key] = int(value)
                except ValueError:
                    processed_data[key] = 0
            elif (
                "FLOAT" in column_type_str
                or "REAL" in column_type_str
                or "NUMERIC" in column_type_str
            ) and isinstance(value, str):
                try:
                    processed_data[key] = float(value)
                except ValueError:
                    processed_data[key] = 0.0
            elif "JSON" in column_type_str:
                if isinstance(value, str) and value.strip():
                    try:
                        processed_data[key] = json_lib.loads(value)
                    except (ValueError, TypeError):
                        processed_data[key] = value
                elif isinstance(value, (list, dict)):
                    processed_data[key] = value
                else:
                    processed_data[key] = None
            else:
                processed_data[key] = value
            """

        for column in model.__table__.columns:
            if column.name in processed_data:
                continue
            if isinstance(column.type, ARRAY) and not column.nullable:
                processed_data[column.name] = []

        return processed_data

    def _get_primary_key_column(self, model: Any) -> Optional[str]:
        """Получает имя первичного ключа модели."""
        for col in model.__table__.columns:
            if col.primary_key:
                return str(col.name)
        return None

    async def _clear_database_tables(self, session: AsyncSession) -> None:
        """Очищает все таблицы БД в обратном порядке зависимостей."""
        tables_order = [model.__tablename__ for model in reversed(self.BACKUP_MODELS)]

        for table_name in tables_order:
            try:
                await session.execute(text(f"DELETE FROM {table_name}"))
                logger.info(f"🗑️ Очищена таблица {table_name}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось очистить таблицу {table_name}: {e}")

    async def _cleanup_old_backups(self) -> None:
        """Удаляет старые бэкапы."""
        try:
            backups = [
                backup
                for backup in await self.get_backup_list()
                if backup.has_local_copy and backup.filepath
            ]

            if len(backups) > self.config.backup.max_keep:
                # Сортируем по времени (новые первые)
                backups.sort(
                    key=lambda backup: self._backup_sort_timestamp(backup.timestamp),
                    reverse=True,
                )

                for backup in backups[self.config.backup.max_keep :]:
                    try:
                        await self.delete_backup(backup.filename)
                        logger.info(f"🗑️ Удалён старый бэкап: {backup.filename}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления старого бэкапа {backup.filename}: {e}")

        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")

    async def _send_backup_file_to_chat(self, file_path: str) -> Optional[Message]:
        """Отправляет файл бэкапа в Telegram чат."""
        try:
            if not self.config.backup.is_send_enabled():
                return None

            chat_id = self.config.backup.send_chat_id
            if not chat_id:
                return None

            document = FSInputFile(file_path)
            caption = (
                f"📦 <b>Резервная копия</b>\n\n"
                f"⏰ <i>{datetime_now().strftime('%d.%m.%Y %H:%M:%S')}</i>"
            )

            if self.config.backup.send_topic_id:
                message = await self.bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    caption=caption,
                    parse_mode="HTML",
                    message_thread_id=self.config.backup.send_topic_id,
                )
            else:
                message = await self.bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    caption=caption,
                    parse_mode="HTML",
                )
            logger.info(f"Бэкап отправлен в чат {chat_id}")
            return message

        except Exception as e:
            logger.error(f"Ошибка отправки бэкапа в чат: {e}")
            return None
