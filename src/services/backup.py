# ruff: noqa: E501
import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Bot
from aiogram.types import Message
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from remnawave import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import AppConfig
from src.core.enums import (
    BackupScope,
    BackupSourceKind,
    Locale,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.sql import (
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

from .backup_creation import (
    _cleanup_old_backups as _cleanup_old_backups_impl,
)
from .backup_creation import (
    _collect_database_overview as _collect_database_overview_impl,
)
from .backup_creation import _dump_assets as _dump_assets_impl
from .backup_creation import _dump_database_json as _dump_database_json_impl
from .backup_creation import _should_skip_asset_file as _should_skip_asset_file_impl
from .backup_creation import create_backup as _create_backup_impl
from .backup_delivery import _send_backup_file_to_chat as _send_backup_file_to_chat_impl
from .backup_formatting import BackupFormattingMixin
from .backup_models import BackupInfo
from .backup_panel_recovery import BackupPanelRecoveryMixin
from .backup_registry import BackupRegistryMixin
from .backup_restore import BackupRestoreMixin
from .backup_values import BackupValueMixin
from .base import BaseService

BACKUP_FORMAT_VERSION = "3.3"


class BackupService(
    BackupRestoreMixin,
    BackupPanelRecoveryMixin,
    BackupRegistryMixin,
    BackupFormattingMixin,
    BackupValueMixin,
    BaseService,
):
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
    BACKUP_FORMAT_VERSION = BACKUP_FORMAT_VERSION

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
            logger.warning(
                f"Некорректное значение BACKUP_TIME='{time_str}'. Используется 03:00."
            )
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
            logger.warning(
                f"Некорректное значение BACKUP_INTERVAL_HOURS={hours}. Используется 24."
            )
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
        return await _create_backup_impl(
            self,
            created_by=created_by,
            compress=compress,
            include_logs=include_logs,
            scope=scope,
            locale=locale,
        )

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
                "📄 Автобэкапы включены, интервал: "
                f"{interval.total_seconds() / 3600:.2f}ч, "
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
        return await _collect_database_overview_impl(self)

    async def _dump_database_json(self, staging_dir: Path) -> Dict[str, Any]:
        return await _dump_database_json_impl(self, staging_dir)

    @staticmethod
    def _should_skip_asset_file(relative_path: Path) -> bool:
        return _should_skip_asset_file_impl(None, relative_path)

    async def _dump_assets(self, staging_dir: Path) -> Dict[str, Any]:
        return await _dump_assets_impl(self, staging_dir)

    async def _cleanup_old_backups(self) -> None:
        return await _cleanup_old_backups_impl(self)

    async def _send_backup_file_to_chat(
        self,
        file_path: str,
        *,
        backup_info: BackupInfo,
        locale: Locale | None = None,
    ) -> Optional[Message]:
        return await _send_backup_file_to_chat_impl(
            self,
            file_path,
            backup_info=backup_info,
            locale=locale,
        )
