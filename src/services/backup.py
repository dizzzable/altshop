import asyncio
import gzip
import json as json_lib
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, field
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
from remnawave import RemnawaveSDK
from remnawave.enums.users import TrafficLimitStrategy
from remnawave.models import TelegramUserResponseDto, UserResponseDto
from sqlalchemy import ARRAY, inspect, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import AppConfig
from src.core.constants import IMPORTED_TAG
from src.core.enums import (
    ArchivedPlanRenewMode,
    BackupScope,
    BackupSourceKind,
    DeviceType,
    Locale,
    PlanAvailability,
    PlanType,
    SubscriptionStatus,
)
from src.core.utils.assets_sync import ASSETS_BACKUP_DIRNAME, ASSETS_VERSION_MARKER
from src.core.utils.formatters import format_limits_to_plan_type
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import PlanSnapshotDto, RemnaSubscriptionDto
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
    ReferralInvite,
    ReferralReward,
    Settings,
    Subscription,
    Transaction,
    User,
    WebAccount,
)
from src.infrastructure.redis import RedisRepository

from .base import BaseService

_aiofiles_open = cast(Callable[..., Any], aiofiles.open)
BACKUP_FORMAT_VERSION = "3.3"


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


@dataclass
class DeferredRestoreUpdate:
    model: Any
    lookup_field: str
    lookup_value: Any
    values: Dict[str, Any]
    phase: str = "default"
    apply_as_scalar_update: bool = False


@dataclass
class RestoreArchiveDiagnostics:
    archive_issue_messages: list[str] = field(default_factory=list)
    current_subscription_refs: list[tuple[int, int]] = field(default_factory=list)
    missing_archive_subscription_refs: list[tuple[int, int]] = field(default_factory=list)
    panel_sync_candidate_ids: list[int] = field(default_factory=list)
    remnawave_users_recovered: int = 0
    remnawave_subscriptions_recovered: int = 0
    unrecovered_user_refs: list[tuple[int, int]] = field(default_factory=list)
    panel_sync_errors: list[tuple[int, str]] = field(default_factory=list)

    @property
    def has_partial_recovery(self) -> bool:
        return bool(
            self.archive_issue_messages
            or self.unrecovered_user_refs
            or self.panel_sync_errors
            or self.remnawave_subscriptions_recovered
        )


class BackupService(BaseService):
    """Сервис для создания и восстановления бэкапов базы данных."""

    session_pool: async_sessionmaker[AsyncSession]
    engine: AsyncEngine
    remnawave: RemnawaveSDK

    # Модели для бэкапа в порядке зависимостей
    BACKUP_MODELS = [
        Settings,
        PaymentGateway,
        Plan,
        PlanDuration,
        PlanPrice,
        User,
        WebAccount,
        ReferralInvite,
        Partner,
        PartnerReferral,
        Promocode,
        Subscription,
        PromocodeActivation,
        Transaction,
        PartnerTransaction,
        PartnerWithdrawal,
        Referral,
        ReferralReward,
        Broadcast,
        BroadcastMessage,
    ]

    RESTORE_LOOKUP_FIELDS: dict[str, tuple[str, ...]] = {
        User.__tablename__: ("telegram_id",),
    }
    RESTORE_PHASE_DEFAULT = "default"
    RESTORE_PHASE_POST_SUBSCRIPTIONS = "post_subscriptions"

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
        remnawave: RemnawaveSDK,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.session_pool = session_pool
        self.engine = engine
        self.remnawave = remnawave
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
                    "integrity": (database_info or {}).get(
                        "integrity",
                        {"degraded": False, "issues": []},
                    ),
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
                overview={**overview, "integrity": (database_info or {}).get("integrity", {})},
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
        export_errors: dict[str, str] = {}

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
                    export_errors[table_name] = str(e)
                    backup_data[table_name] = []

        # Сохраняем в файл
        integrity = self._build_backup_integrity_report(
            backup_data=backup_data,
            export_errors=export_errors,
        )
        dump_path = staging_dir / "database.json"
        dump_structure = {
            "metadata": {
                "timestamp": datetime_now().isoformat(),
                "version": "orm-1.1",
                "database_type": "postgresql",
                "tables_count": len(self.BACKUP_MODELS),
                "total_records": total_records,
                "integrity": integrity,
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
            "integrity": integrity,
        }

    def _build_backup_integrity_report(
        self,
        *,
        backup_data: Dict[str, List[Dict[str, Any]]],
        export_errors: dict[str, str],
    ) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []

        if export_errors:
            issues.append(
                {
                    "code": "export_errors",
                    "message": f"Export failed for {len(export_errors)} table(s)",
                    "tables": sorted(export_errors),
                }
            )

        plan_rows = backup_data.get(Plan.__tablename__) or []
        duration_rows = backup_data.get(PlanDuration.__tablename__) or []
        price_rows = backup_data.get(PlanPrice.__tablename__) or []
        if not plan_rows and (duration_rows or price_rows):
            issues.append(
                {
                    "code": "missing_plan_catalog",
                    "message": "Plan rows are missing while plan durations or prices exist",
                    "durations_count": len(duration_rows),
                    "prices_count": len(price_rows),
                }
            )

        subscription_rows = backup_data.get(Subscription.__tablename__) or []
        subscription_ids = {
            int(row["id"])
            for row in subscription_rows
            if isinstance(row, dict) and row.get("id") is not None
        }
        user_rows = backup_data.get(User.__tablename__) or []
        current_refs = self._extract_current_subscription_refs(user_rows)
        missing_subscription_refs = [
            (telegram_id, subscription_id)
            for telegram_id, subscription_id in current_refs
            if subscription_id not in subscription_ids
        ]
        if missing_subscription_refs:
            issues.append(
                {
                    "code": "missing_subscription_rows",
                    "message": (
                        "Users reference current subscriptions that are absent "
                        "from the export"
                    ),
                    "users_count": len(missing_subscription_refs),
                    "subscription_ids": sorted(
                        {
                            subscription_id
                            for _telegram_id, subscription_id in missing_subscription_refs
                        }
                    ),
                }
            )

        return {
            "degraded": bool(issues),
            "issues": issues,
        }

    def _extract_current_subscription_refs(
        self,
        user_rows: List[Dict[str, Any]],
    ) -> list[tuple[int, int]]:
        refs: list[tuple[int, int]] = []
        for row in user_rows:
            if not isinstance(row, dict):
                continue
            telegram_id = row.get("telegram_id")
            subscription_id = row.get("current_subscription_id")
            if telegram_id is None or subscription_id is None:
                continue
            try:
                refs.append((int(telegram_id), int(subscription_id)))
            except (TypeError, ValueError):
                continue
        return refs

    def _analyze_restore_archive(
        self,
        backup_data: Dict[str, List[Dict[str, Any]]],
    ) -> RestoreArchiveDiagnostics:
        diagnostics = RestoreArchiveDiagnostics()
        plan_rows = backup_data.get(Plan.__tablename__) or []
        duration_rows = backup_data.get(PlanDuration.__tablename__) or []
        price_rows = backup_data.get(PlanPrice.__tablename__) or []
        if not plan_rows and (duration_rows or price_rows):
            diagnostics.archive_issue_messages.append(
                "Archive is missing plan rows and requires legacy plan recovery"
            )

        user_rows = backup_data.get(User.__tablename__) or []
        current_refs = self._extract_current_subscription_refs(user_rows)
        diagnostics.current_subscription_refs = current_refs
        subscription_ids = {
            int(row["id"])
            for row in (backup_data.get(Subscription.__tablename__) or [])
            if isinstance(row, dict) and row.get("id") is not None
        }
        diagnostics.missing_archive_subscription_refs = [
            (telegram_id, subscription_id)
            for telegram_id, subscription_id in current_refs
            if subscription_id not in subscription_ids
        ]
        diagnostics.panel_sync_candidate_ids = sorted(
            {
                telegram_id
                for telegram_id, _subscription_id in diagnostics.missing_archive_subscription_refs
            }
        )
        if diagnostics.missing_archive_subscription_refs:
            diagnostics.archive_issue_messages.append(
                "Archive is missing subscription rows referenced by users.current_subscription_id"
            )

        return diagnostics

    def _collect_plan_snapshots(  # noqa: C901
        self,
        backup_data: Dict[str, List[Dict[str, Any]]],
        *,
        extra_snapshots: Optional[List[Dict[str, Any]]] = None,
    ) -> dict[int, dict[str, Any]]:
        snapshots_by_id: dict[int, dict[str, Any]] = {}
        for table_name in (
            Subscription.__tablename__,
            Transaction.__tablename__,
            Promocode.__tablename__,
        ):
            for record in backup_data.get(table_name) or []:
                if not isinstance(record, dict):
                    continue
                snapshot = self._parse_backup_snapshot(record.get("plan"))
                if not snapshot:
                    continue
                raw_plan_id = snapshot.get("id")
                if not isinstance(raw_plan_id, int | str):
                    continue
                try:
                    plan_id = int(raw_plan_id)
                except (TypeError, ValueError):
                    continue
                if plan_id <= 0:
                    continue
                snapshots_by_id.setdefault(plan_id, snapshot)

        for snapshot in extra_snapshots or []:
            if not isinstance(snapshot, dict):
                continue
            raw_plan_id = snapshot.get("id")
            if not isinstance(raw_plan_id, int | str):
                continue
            try:
                plan_id = int(raw_plan_id)
            except (TypeError, ValueError):
                continue
            if plan_id <= 0:
                continue
            snapshots_by_id.setdefault(plan_id, snapshot)

        return snapshots_by_id

    def _log_restore_archive_diagnostics(self, diagnostics: RestoreArchiveDiagnostics) -> None:
        if not diagnostics.archive_issue_messages:
            return

        logger.warning(
            (
                "Legacy archive diagnostics: issues={}, "
                "users_with_missing_subscriptions={}, "
                "missing_subscription_refs={}"
            ),
            diagnostics.archive_issue_messages,
            len(diagnostics.panel_sync_candidate_ids),
            len(diagnostics.missing_archive_subscription_refs),
        )

    @staticmethod
    def _normalize_squad_values(values: list[UUID]) -> list[str]:
        return sorted(str(value) for value in values)

    def _match_plan_for_panel_subscription(
        self,
        *,
        remna_subscription: RemnaSubscriptionDto,
        plans: list[Plan],
    ) -> Optional[Plan]:
        if remna_subscription.tag:
            exact_tag_matches = [
                plan for plan in plans if plan.tag and plan.tag == remna_subscription.tag
            ]
            if exact_tag_matches:
                exact_tag_matches.sort(key=lambda plan: (plan.order_index, plan.id))
                return exact_tag_matches[0]

        subscription_type = format_limits_to_plan_type(
            remna_subscription.traffic_limit,
            remna_subscription.device_limit,
        )
        matches = [
            plan
            for plan in plans
            if plan.type == subscription_type
            and plan.traffic_limit == remna_subscription.traffic_limit
            and plan.device_limit == remna_subscription.device_limit
            and plan.traffic_limit_strategy == (
                remna_subscription.traffic_limit_strategy or TrafficLimitStrategy.NO_RESET
            )
            and self._normalize_squad_values(plan.internal_squads)
            == self._normalize_squad_values(remna_subscription.internal_squads)
            and plan.external_squad == remna_subscription.external_squad
        ]
        if not matches:
            return None

        matches.sort(key=lambda plan: (plan.order_index, plan.id))
        return matches[0]

    def _build_panel_subscription_snapshot(
        self,
        *,
        remna_subscription: RemnaSubscriptionDto,
        matched_plan: Optional[Plan],
    ) -> dict[str, Any]:
        snapshot = PlanSnapshotDto(
            id=matched_plan.id if matched_plan and matched_plan.id is not None else -1,
            name=matched_plan.name if matched_plan else IMPORTED_TAG,
            tag=matched_plan.tag if matched_plan else remna_subscription.tag,
            type=(
                matched_plan.type
                if matched_plan
                else format_limits_to_plan_type(
                    remna_subscription.traffic_limit,
                    remna_subscription.device_limit,
                )
            ),
            traffic_limit=(
                matched_plan.traffic_limit if matched_plan else remna_subscription.traffic_limit
            ),
            device_limit=(
                matched_plan.device_limit if matched_plan else remna_subscription.device_limit
            ),
            duration=-1,
            traffic_limit_strategy=(
                matched_plan.traffic_limit_strategy
                if matched_plan
                else remna_subscription.traffic_limit_strategy or TrafficLimitStrategy.NO_RESET
            ),
            internal_squads=(
                list(matched_plan.internal_squads)
                if matched_plan
                else list(remna_subscription.internal_squads)
            ),
            external_squad=(
                matched_plan.external_squad if matched_plan else remna_subscription.external_squad
            ),
        )
        return snapshot.model_dump(mode="json")

    async def _fetch_panel_users_by_telegram_id(self, telegram_id: int) -> list[UserResponseDto]:
        users_result = await self.remnawave.users.get_users_by_telegram_id(
            telegram_id=str(telegram_id)
        )
        if not isinstance(users_result, TelegramUserResponseDto):
            raise ValueError(
                "Unexpected Remnawave response for telegram_id "
                f"'{telegram_id}': {users_result!r}"
            )
        return list(users_result.root)

    async def _upsert_missing_plan_rows_from_snapshots(
        self,
        session: AsyncSession,
        *,
        snapshots_by_id: dict[int, dict[str, Any]],
    ) -> int:
        if not snapshots_by_id:
            return 0

        result = await session.execute(select(Plan.id, Plan.order_index))
        existing_rows = list(result.all())
        existing_plan_ids = {int(plan_id) for plan_id, _order_index in existing_rows}
        max_order_index = max(
            (int(order_index) for _plan_id, order_index in existing_rows),
            default=0,
        )
        created = 0

        for plan_id in sorted(snapshots_by_id):
            if plan_id <= 0 or plan_id in existing_plan_ids:
                continue

            max_order_index += 1
            session.add(
                Plan(
                    **self._build_recovered_plan_record(
                        plan_id=plan_id,
                        order_index=max_order_index,
                        snapshot=snapshots_by_id[plan_id],
                        snapshot_only=True,
                    )
                )
            )
            existing_plan_ids.add(plan_id)
            created += 1

        return created

    @staticmethod
    def _resolve_effective_subscription_status(subscription: Subscription) -> SubscriptionStatus:
        if subscription.expire_at < datetime_now():
            return SubscriptionStatus.EXPIRED
        return subscription.status

    def _select_current_subscription_id(
        self,
        subscriptions: list[Subscription],
    ) -> Optional[int]:
        if not subscriptions:
            return None

        status_priority = {
            SubscriptionStatus.ACTIVE: 0,
            SubscriptionStatus.DISABLED: 1,
            SubscriptionStatus.EXPIRED: 2,
        }
        candidates = [
            subscription
            for subscription in subscriptions
            if self._resolve_effective_subscription_status(subscription)
            != SubscriptionStatus.DELETED
        ]
        if not candidates:
            return None

        selected = sorted(
            candidates,
            key=lambda subscription: (
                status_priority.get(self._resolve_effective_subscription_status(subscription), 99),
                -subscription.expire_at.timestamp(),
                -(subscription.id or 0),
            ),
        )[0]
        return selected.id

    async def _sync_panel_profiles_for_restore(
        self,
        *,
        telegram_id: int,
        remna_users: list[UserResponseDto],
    ) -> tuple[int, list[dict[str, Any]]]:
        panel_snapshots: list[dict[str, Any]] = []

        async with self.session_pool() as session:
            existing_user = await session.execute(
                select(User.telegram_id).where(User.telegram_id == telegram_id)
            )
            if existing_user.scalar_one_or_none() is None:
                return 0, panel_snapshots

            plans_result = await session.execute(select(Plan))
            plans = list(plans_result.scalars().all())
            restored_subscriptions = 0

            for remna_user in remna_users:
                remna_payload = remna_user.model_dump()
                remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_payload)
                matched_plan = self._match_plan_for_panel_subscription(
                    remna_subscription=remna_subscription,
                    plans=plans,
                )
                plan_payload = self._build_panel_subscription_snapshot(
                    remna_subscription=remna_subscription,
                    matched_plan=matched_plan,
                )
                panel_snapshots.append(plan_payload)

                status = (
                    SubscriptionStatus.EXPIRED
                    if remna_user.expire_at and remna_user.expire_at < datetime_now()
                    else remna_user.status
                )
                values = {
                    "user_telegram_id": telegram_id,
                    "status": status,
                    "is_trial": False,
                    "traffic_limit": remna_subscription.traffic_limit,
                    "device_limit": remna_subscription.device_limit,
                    "internal_squads": list(remna_subscription.internal_squads),
                    "external_squad": remna_subscription.external_squad,
                    "expire_at": remna_user.expire_at,
                    "url": remna_subscription.url or "",
                    "device_type": DeviceType.OTHER,
                    "plan": plan_payload,
                }

                subscription_result = await session.execute(
                    select(Subscription.id).where(Subscription.user_remna_id == remna_user.uuid)
                )
                existing_subscription_id = subscription_result.scalar_one_or_none()

                if existing_subscription_id is None:
                    session.add(
                        Subscription(
                            user_remna_id=remna_user.uuid,
                            **values,
                        )
                    )
                else:
                    await session.execute(
                        update(Subscription)
                        .where(Subscription.id == existing_subscription_id)
                        .values(**values)
                        .execution_options(synchronize_session=False)
                    )
                restored_subscriptions += 1

            await self._upsert_missing_plan_rows_from_snapshots(
                session,
                snapshots_by_id=self._collect_plan_snapshots({}, extra_snapshots=panel_snapshots),
            )
            await session.flush()
            subscriptions_result = await session.execute(
                select(Subscription).where(Subscription.user_telegram_id == telegram_id)
            )
            subscriptions = list(subscriptions_result.scalars().all())
            current_subscription_id = self._select_current_subscription_id(subscriptions)
            await self._apply_scalar_restore_update(
                session=session,
                model=User,
                lookup_field="telegram_id",
                lookup_value=telegram_id,
                values={"current_subscription_id": current_subscription_id},
            )
            await session.commit()

        return restored_subscriptions, panel_snapshots

    async def _recover_missing_subscriptions_from_panel(
        self,
        diagnostics: RestoreArchiveDiagnostics,
    ) -> RestoreArchiveDiagnostics:
        if not diagnostics.panel_sync_candidate_ids:
            return diagnostics

        for telegram_id, missing_subscription_id in diagnostics.missing_archive_subscription_refs:
            try:
                remna_users = await self._fetch_panel_users_by_telegram_id(telegram_id)
            except Exception as exc:
                logger.warning(
                    "Panel recovery failed for telegram_id '{}': {}",
                    telegram_id,
                    exc,
                )
                diagnostics.panel_sync_errors.append((telegram_id, str(exc)))
                diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
                continue

            if not remna_users:
                diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
                continue

            restored_subscriptions, _panel_snapshots = await self._sync_panel_profiles_for_restore(
                telegram_id=telegram_id,
                remna_users=remna_users,
            )
            if restored_subscriptions == 0:
                diagnostics.unrecovered_user_refs.append((telegram_id, missing_subscription_id))
                continue

            diagnostics.remnawave_users_recovered += 1
            diagnostics.remnawave_subscriptions_recovered += restored_subscriptions

        return diagnostics

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
            integrity = self._get_backup_integrity_from_metadata(overview)
            if integrity.get("degraded"):
                lines.append(i18n.get("msg-backup-result-degraded"))
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
        integrity = self._get_backup_integrity_from_metadata(overview)
        if integrity.get("degraded"):
            lines.append("Warning: backup marked as degraded")
        return "\n".join(lines)

    @staticmethod
    def _get_backup_integrity_from_metadata(metadata: Dict[str, Any]) -> dict[str, Any]:
        integrity = metadata.get("integrity")
        if isinstance(integrity, dict):
            return integrity
        return {"degraded": False, "issues": []}

    def _summarize_backup_integrity(self, metadata: Dict[str, Any]) -> Optional[str]:
        integrity = self._get_backup_integrity_from_metadata(metadata)
        issues = integrity.get("issues")
        if not integrity.get("degraded") or not isinstance(issues, list) or not issues:
            return None

        first_issue = issues[0]
        first_message = (
            first_issue.get("message")
            if isinstance(first_issue, dict)
            else None
        )
        if isinstance(first_message, str) and first_message.strip():
            if len(issues) == 1:
                return f"Degraded backup: {first_message}"
            return f"Degraded backup: {first_message} (+{len(issues) - 1} more)"

        return f"Degraded backup: {len(issues)} issue(s)"

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
        error = self._summarize_backup_restore_error(error)
        if locale is None:
            return f"Restore failed: {error}"
        i18n = self.translator_hub.get_translator_by_locale(locale=locale)
        return i18n.get("msg-backup-error-restore", error=error)

    @staticmethod
    def _summarize_backup_restore_error(error: str) -> str:
        normalized = " ".join(str(error).split())
        if not normalized:
            return "unknown restore error"

        if "Circular dependency detected" in normalized:
            return "users and subscriptions could not be linked automatically"

        if "[SQL:" in normalized:
            normalized = normalized.split("[SQL:", 1)[0].strip()

        max_length = 320
        if len(normalized) <= max_length:
            return normalized

        return f"{normalized[: max_length - 3].rstrip()}..."

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
            error=self._summarize_backup_integrity(metadata),
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
                if backup_info.has_local_copy and backup_info.filepath:
                    metadata = await self._read_backup_metadata(Path(backup_info.filepath))
                    backup_info.error = self._summarize_backup_integrity(metadata)
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

    async def _restore_from_json(  # noqa: C901
        self,
        dump_path: Path,
        clear_existing: bool,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        """Восстановление из JSON-дампа."""
        async with _aiofiles_open(dump_path, "r", encoding="utf-8") as f:
            dump_data = json_lib.loads(await f.read())

        metadata = dump_data.get("metadata", {})
        raw_backup_data = dump_data.get("data", {})
        diagnostics = self._analyze_restore_archive(raw_backup_data)
        self._log_restore_archive_diagnostics(diagnostics)
        backup_data, recovered_legacy_plans = self._recover_legacy_missing_plans(raw_backup_data)

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
                deferred_updates: list[DeferredRestoreUpdate] = []
                if clear_existing:
                    logger.warning("🗑️ Очищаем существующие данные...")
                    await self._clear_database_tables_atomic(session)

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
                        deferred_updates=deferred_updates,
                    )
                    await session.flush()
                    restored_records += restored

                    if restored:
                        restored_tables += 1
                        logger.info(f"✅ Таблица {table_name} восстановлена")

                await self._apply_deferred_restore_updates(
                    session,
                    deferred_updates,
                    phase=self.RESTORE_PHASE_POST_SUBSCRIPTIONS,
                )
                if deferred_updates:
                    await session.flush()

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
            if recovered_legacy_plans:
                message = "\n".join(
                    [
                        message,
                        i18n.get(
                            "msg-backup-result-recovered-plans",
                            count=recovered_legacy_plans,
                        ),
                    ]
                )
        elif recovered_legacy_plans:
            message += f"\nRecovered plans: {recovered_legacy_plans}"

        diagnostics = await self._recover_missing_subscriptions_from_panel(diagnostics)
        message = self._append_restore_diagnostics_to_message(
            message=message,
            locale=locale,
            diagnostics=diagnostics,
        )

        logger.info(message)
        return True, message

    async def _restore_table_records(  # noqa: C901
        self,
        session: AsyncSession,
        model: Any,
        table_name: str,
        records: List[Dict[str, Any]],
        clear_existing: bool,
        deferred_updates: Optional[list[DeferredRestoreUpdate]] = None,
    ) -> int:
        """Восстанавливает записи в таблицу."""
        restored_count = 0

        for record_data in records:
            try:
                processed_data = self._process_record_data(record_data, model, table_name)
                processed_data, deferred_update = self._extract_deferred_restore_fields(
                    model,
                    processed_data,
                )
                primary_key_col = self._get_primary_key_column(model)

                existing = None
                if not clear_existing and model is User:
                    updated = await self._merge_existing_user_record(
                        session=session,
                        processed_data=processed_data,
                        primary_key_col=primary_key_col,
                    )
                    if updated:
                        if deferred_update is not None and deferred_updates is not None:
                            deferred_updates.append(deferred_update)
                        restored_count += 1
                        continue

                if not clear_existing:
                    existing = await self._find_existing_restore_record(
                        session=session,
                        model=model,
                        processed_data=processed_data,
                        primary_key_col=primary_key_col,
                    )

                if existing is not None:
                    for key, value in processed_data.items():
                        if key != primary_key_col:
                            setattr(existing, key, value)
                else:
                    instance = model(**processed_data)
                    session.add(instance)

                if deferred_update is not None and deferred_updates is not None:
                    deferred_updates.append(deferred_update)

                restored_count += 1

            except Exception as e:
                logger.error(f"Ошибка восстановления записи в {table_name}: {e}")
                logger.error(f"Проблемные данные: {record_data}")
                raise e

        return restored_count

    async def _merge_existing_user_record(
        self,
        *,
        session: AsyncSession,
        processed_data: Dict[str, Any],
        primary_key_col: Optional[str],
    ) -> bool:
        restore_target = await self._find_existing_user_restore_target(
            session=session,
            processed_data=processed_data,
            primary_key_col=primary_key_col,
        )
        if restore_target is None:
            return False

        lookup_field, lookup_value = restore_target
        values = {
            key: value for key, value in processed_data.items() if key != primary_key_col
        }
        await self._apply_scalar_restore_update(
            session=session,
            model=User,
            lookup_field=lookup_field,
            lookup_value=lookup_value,
            values=values,
        )
        return True

    async def _find_existing_user_restore_target(
        self,
        *,
        session: AsyncSession,
        processed_data: Dict[str, Any],
        primary_key_col: Optional[str],
    ) -> tuple[str, Any] | None:
        telegram_id = processed_data.get("telegram_id")
        if telegram_id is not None:
            with session.no_autoflush:
                existing_record = await session.execute(
                    select(User.telegram_id).where(User.telegram_id == telegram_id)
                )
            existing_telegram_id = existing_record.scalar_one_or_none()
            if existing_telegram_id is not None:
                return "telegram_id", existing_telegram_id

        if primary_key_col and primary_key_col in processed_data:
            with session.no_autoflush:
                existing_record = await session.execute(
                    select(getattr(User, primary_key_col)).where(
                        getattr(User, primary_key_col) == processed_data[primary_key_col]
                    )
                )
            existing_primary_key = existing_record.scalar_one_or_none()
            if existing_primary_key is not None:
                return primary_key_col, existing_primary_key

        return None

    async def _find_existing_restore_record(
        self,
        *,
        session: AsyncSession,
        model: Any,
        processed_data: Dict[str, Any],
        primary_key_col: Optional[str],
    ) -> Any:
        if primary_key_col and primary_key_col in processed_data:
            with session.no_autoflush:
                existing_record = await session.execute(
                    select(model).where(
                        getattr(model, primary_key_col) == processed_data[primary_key_col]
                    )
                )
            existing = existing_record.scalar_one_or_none()
            if existing is not None:
                return existing

        for lookup_field in self.RESTORE_LOOKUP_FIELDS.get(model.__tablename__, ()):
            lookup_value = processed_data.get(lookup_field)
            if lookup_value is None:
                continue

            with session.no_autoflush:
                existing_record = await session.execute(
                    select(model).where(getattr(model, lookup_field) == lookup_value)
                )
            existing = existing_record.scalar_one_or_none()
            if existing is not None:
                return existing

        return None

    def _extract_deferred_restore_fields(
        self,
        model: Any,
        processed_data: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Optional[DeferredRestoreUpdate]]:
        if model is not User:
            return processed_data, None

        current_subscription_id = processed_data.get("current_subscription_id")
        telegram_id = processed_data.get("telegram_id")
        if current_subscription_id is None or telegram_id is None:
            return processed_data, None

        deferred_data = dict(processed_data)
        deferred_data["current_subscription_id"] = None
        return deferred_data, DeferredRestoreUpdate(
            model=User,
            lookup_field="telegram_id",
            lookup_value=telegram_id,
            values={"current_subscription_id": current_subscription_id},
            phase=self.RESTORE_PHASE_POST_SUBSCRIPTIONS,
            apply_as_scalar_update=True,
        )

    async def _apply_deferred_restore_updates(
        self,
        session: AsyncSession,
        deferred_updates: list[DeferredRestoreUpdate],
        *,
        phase: str,
    ) -> None:
        for deferred_update in deferred_updates:
            if deferred_update.phase != phase:
                continue

            values = await self._filter_deferred_restore_values(session, deferred_update)
            if not values:
                continue

            if deferred_update.apply_as_scalar_update:
                await self._apply_scalar_deferred_restore_update(
                    session,
                    deferred_update,
                    values,
                )
                continue

            with session.no_autoflush:
                existing_record = await session.execute(
                    select(deferred_update.model).where(
                        getattr(deferred_update.model, deferred_update.lookup_field)
                        == deferred_update.lookup_value
                    )
                )
            existing = existing_record.scalar_one_or_none()
            if existing is None:
                logger.warning(
                    "Skipped deferred restore update for {}.{}={}",
                    deferred_update.model.__tablename__,
                    deferred_update.lookup_field,
                    deferred_update.lookup_value,
                )
                continue

            for key, value in values.items():
                setattr(existing, key, value)

    async def _apply_scalar_deferred_restore_update(
        self,
        session: AsyncSession,
        deferred_update: DeferredRestoreUpdate,
        values: Dict[str, Any],
    ) -> None:
        rows_updated = await self._apply_scalar_restore_update(
            session=session,
            model=deferred_update.model,
            lookup_field=deferred_update.lookup_field,
            lookup_value=deferred_update.lookup_value,
            values=values,
        )
        if rows_updated == 0:
            logger.warning(
                "Skipped scalar deferred restore update for {}.{}={}",
                deferred_update.model.__tablename__,
                deferred_update.lookup_field,
                deferred_update.lookup_value,
            )

    async def _apply_scalar_restore_update(
        self,
        *,
        session: AsyncSession,
        model: Any,
        lookup_field: str,
        lookup_value: Any,
        values: Dict[str, Any],
    ) -> int | None:
        result = await session.execute(
            update(model)
            .where(getattr(model, lookup_field) == lookup_value)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        return cast(Optional[int], getattr(result, "rowcount", None))

    async def _filter_deferred_restore_values(
        self,
        session: AsyncSession,
        deferred_update: DeferredRestoreUpdate,
    ) -> Dict[str, Any]:
        values = dict(deferred_update.values)

        if deferred_update.model is User and "current_subscription_id" in values:
            current_subscription_id = values["current_subscription_id"]
            if current_subscription_id is not None:
                with session.no_autoflush:
                    subscription_record = await session.execute(
                        select(Subscription.id).where(Subscription.id == current_subscription_id)
                    )
                subscription = subscription_record.scalar_one_or_none()
                if subscription is None:
                    values.pop("current_subscription_id", None)

        return values

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
    def _parse_backup_snapshot(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value

        if isinstance(value, str) and value.strip():
            try:
                parsed = json_lib.loads(value)
            except (ValueError, TypeError):
                return None
            if isinstance(parsed, dict):
                return parsed

        return None

    @staticmethod
    def _coerce_plan_enum_value(value: Any, enum_cls: Any, fallback: str) -> str:
        if isinstance(value, str) and value in enum_cls._value2member_map_:
            return value
        return fallback

    @staticmethod
    def _coerce_int_value(value: Any, fallback: int) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return fallback
        return fallback

    def _build_recovered_plan_record(
        self,
        *,
        plan_id: int,
        order_index: int,
        snapshot: dict[str, Any] | None,
        snapshot_only: bool = False,
    ) -> dict[str, Any]:
        snapshot = snapshot or {}
        external_squad = snapshot.get("external_squad")
        if external_squad is not None and not isinstance(external_squad, list):
            external_squad = [external_squad]

        return {
            "id": plan_id,
            "order_index": order_index,
            "is_active": not snapshot_only,
            "is_archived": snapshot_only,
            "type": self._coerce_plan_enum_value(
                snapshot.get("type"),
                PlanType,
                PlanType.BOTH.value,
            ),
            "availability": PlanAvailability.ALL.value,
            "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
            "name": snapshot.get("name") or f"Recovered plan #{plan_id}",
            "description": None,
            "tag": snapshot.get("tag"),
            "traffic_limit": self._coerce_int_value(snapshot.get("traffic_limit"), 0),
            "device_limit": self._coerce_int_value(snapshot.get("device_limit"), 1),
            "traffic_limit_strategy": self._coerce_plan_enum_value(
                snapshot.get("traffic_limit_strategy"),
                TrafficLimitStrategy,
                TrafficLimitStrategy.NO_RESET.value,
            ),
            "replacement_plan_ids": [],
            "upgrade_to_plan_ids": [],
            "allowed_user_ids": [],
            "internal_squads": snapshot.get("internal_squads") or [],
            "external_squad": external_squad,
        }

    def _recover_legacy_missing_plans(  # noqa: C901
        self,
        backup_data: Dict[str, List[Dict[str, Any]]],
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], int]:
        plans = list(backup_data.get(Plan.__tablename__) or [])
        durations = backup_data.get(PlanDuration.__tablename__) or []
        if not durations and not self._collect_plan_snapshots(backup_data):
            return backup_data, 0

        existing_plan_ids = {
            int(plan["id"])
            for plan in plans
            if isinstance(plan, dict) and isinstance(plan.get("id"), int | str)
        }
        referenced_plan_ids_set: set[int] = set()
        for duration in durations:
            if not isinstance(duration, dict):
                continue
            raw_plan_id = duration.get("plan_id")
            if not isinstance(raw_plan_id, int | str):
                continue
            try:
                plan_id = int(raw_plan_id)
            except ValueError:
                continue
            if plan_id > 0:
                referenced_plan_ids_set.add(plan_id)

        snapshots_by_id = self._collect_plan_snapshots(backup_data)
        referenced_plan_ids = sorted(referenced_plan_ids_set | set(snapshots_by_id))
        missing_plan_ids = [
            plan_id
            for plan_id in referenced_plan_ids
            if plan_id > 0 and plan_id not in existing_plan_ids
        ]
        if not missing_plan_ids:
            return backup_data, 0

        recovered_plans = [
            self._build_recovered_plan_record(
                plan_id=plan_id,
                order_index=len(plans) + index,
                snapshot=snapshots_by_id.get(plan_id),
                snapshot_only=plan_id not in referenced_plan_ids_set,
            )
            for index, plan_id in enumerate(missing_plan_ids, start=1)
        ]
        backup_data = dict(backup_data)
        backup_data[Plan.__tablename__] = [*plans, *recovered_plans]
        logger.warning(
            "Recovered {} missing plan records from a legacy backup using related snapshots",
            len(recovered_plans),
        )
        return backup_data, len(recovered_plans)

    def _build_restore_result_message(
        self,
        *,
        locale: Locale | None,
        metadata: dict[str, Any],
        restored_tables: int,
        restored_records: int,
        recovered_legacy_plans: int,
    ) -> str:
        message = (
            f"вњ… Р’РѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ Р·Р°РІРµСЂС€РµРЅРѕ!\n"
            f"рџ“Љ РўР°Р±Р»РёС†: {restored_tables}\n"
            f"рџ“€ Р—Р°РїРёСЃРµР№: {restored_records:,}\n"
            f"рџ“… Р”Р°С‚Р° Р±СЌРєР°РїР°: {metadata.get('timestamp', 'РЅРµРёР·РІРµСЃС‚РЅРѕ')}"
        )

        if locale is None:
            if recovered_legacy_plans:
                message += f"\nRecovered plans: {recovered_legacy_plans}"
            return message

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
        if recovered_legacy_plans:
            message = "\n".join(
                [
                    message,
                    i18n.get(
                        "msg-backup-result-recovered-plans",
                        count=recovered_legacy_plans,
                    ),
                ]
            )
        return message

    def _append_restore_diagnostics_to_message(  # noqa: C901
        self,
        *,
        message: str,
        locale: Locale | None,
        diagnostics: RestoreArchiveDiagnostics,
    ) -> str:
        extra_lines: list[str] = []

        if diagnostics.archive_issue_messages:
            issue_count = len(diagnostics.archive_issue_messages)
            if locale is None:
                extra_lines.append(f"Archive issues detected: {issue_count}")
            else:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(i18n.get("msg-backup-result-archive-issues", count=issue_count))

        if diagnostics.remnawave_users_recovered:
            if locale is None:
                extra_lines.append(
                    f"Users synced from Remnawave: {diagnostics.remnawave_users_recovered}"
                )
            else:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(
                    i18n.get(
                        "msg-backup-result-remnawave-users",
                        count=diagnostics.remnawave_users_recovered,
                    )
                )

        if diagnostics.remnawave_subscriptions_recovered:
            if locale is None:
                extra_lines.append(
                    "Subscriptions recovered from Remnawave: "
                    f"{diagnostics.remnawave_subscriptions_recovered}"
                )
            else:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(
                    i18n.get(
                        "msg-backup-result-remnawave-subscriptions",
                        count=diagnostics.remnawave_subscriptions_recovered,
                    )
                )

        unrecovered_count = len(diagnostics.unrecovered_user_refs)
        if unrecovered_count:
            if locale is None:
                extra_lines.append(f"Unrecoverable user subscriptions: {unrecovered_count}")
            else:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(
                    i18n.get(
                        "msg-backup-result-unrecoverable-subscriptions",
                        count=unrecovered_count,
                    )
                )

        if diagnostics.panel_sync_errors:
            if locale is None:
                extra_lines.append(f"Remnawave sync errors: {len(diagnostics.panel_sync_errors)}")
            else:
                i18n = self.translator_hub.get_translator_by_locale(locale=locale)
                extra_lines.append(
                    i18n.get(
                        "msg-backup-result-remnawave-sync-errors",
                        count=len(diagnostics.panel_sync_errors),
                    )
                )

        if not extra_lines:
            return message

        return "\n".join([message, *extra_lines])

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

    async def _clear_database_tables_atomic(self, session: AsyncSession) -> None:
        """Clear restore-owned tables in one atomic TRUNCATE statement."""
        table_names = ", ".join(model.__tablename__ for model in self.BACKUP_MODELS)
        await session.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
        logger.info("🗑️ Cleared restore-owned tables with TRUNCATE CASCADE")

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
