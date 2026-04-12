# ruff: noqa: E501
import asyncio
import json as json_lib
import shutil
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import aiofiles  # type: ignore[import-untyped]
from aiogram import Bot
from aiogram.types import FSInputFile, Message
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from remnawave import RemnawaveSDK
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.core.config import AppConfig
from src.core.enums import (
    BackupScope,
    BackupSourceKind,
    Locale,
)
from src.core.utils.assets_sync import ASSETS_BACKUP_DIRNAME, ASSETS_VERSION_MARKER
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

from .backup_formatting import BackupFormattingMixin
from .backup_models import (
    BackupInfo,
)
from .backup_panel_recovery import BackupPanelRecoveryMixin
from .backup_registry import BackupRegistryMixin
from .backup_restore import BackupRestoreMixin
from .backup_values import BackupValueMixin
from .base import BaseService

_aiofiles_open = cast(Callable[..., Any], aiofiles.open)
BACKUP_FORMAT_VERSION = "3.3"


class BackupService(
    BackupRestoreMixin,
    BackupPanelRecoveryMixin,
    BackupRegistryMixin,
    BackupFormattingMixin,
    BackupValueMixin,
    BaseService,
):
    """РЎРµСЂРІРёСЃ РґР»СЏ СЃРѕР·РґР°РЅРёСЏ Рё РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёСЏ Р±СЌРєР°РїРѕРІ Р±Р°Р·С‹ РґР°РЅРЅС‹С…."""

    session_pool: async_sessionmaker[AsyncSession]
    engine: AsyncEngine
    remnawave: RemnawaveSDK

    # РњРѕРґРµР»Рё РґР»СЏ Р±СЌРєР°РїР° РІ РїРѕСЂСЏРґРєРµ Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№
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
        """Р”РёСЂРµРєС‚РѕСЂРёСЏ РґР»СЏ С…СЂР°РЅРµРЅРёСЏ Р±СЌРєР°РїРѕРІ."""
        return self._backup_dir

    def _parse_backup_time(self) -> Tuple[int, int]:
        """РџР°СЂСЃРёС‚ РІСЂРµРјСЏ Р·Р°РїСѓСЃРєР° Р°РІС‚РѕР±СЌРєР°РїР°."""
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
            logger.warning(f"РќРµРєРѕСЂСЂРµРєС‚РЅРѕРµ Р·РЅР°С‡РµРЅРёРµ BACKUP_TIME='{time_str}'. РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ 03:00.")
            return 3, 0

    def _calculate_next_backup_datetime(self, reference: Optional[datetime] = None) -> datetime:
        """Р’С‹С‡РёСЃР»СЏРµС‚ РІСЂРµРјСЏ СЃР»РµРґСѓСЋС‰РµРіРѕ Р°РІС‚РѕР±СЌРєР°РїР°."""
        reference = reference or datetime_now()
        hours, minutes = self._parse_backup_time()

        next_run = reference.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        if next_run <= reference:
            next_run += timedelta(days=1)

        return next_run

    def _get_backup_interval(self) -> timedelta:
        """РџРѕР»СѓС‡Р°РµС‚ РёРЅС‚РµСЂРІР°Р» РјРµР¶РґСѓ Р°РІС‚РѕР±СЌРєР°РїР°РјРё."""
        hours = self.config.backup.interval_hours
        if hours <= 0:
            logger.warning(f"РќРµРєРѕСЂСЂРµРєС‚РЅРѕРµ Р·РЅР°С‡РµРЅРёРµ BACKUP_INTERVAL_HOURS={hours}. РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ 24.")
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
        РЎРѕР·РґР°С‘С‚ Р±СЌРєР°Рї Р±Р°Р·С‹ РґР°РЅРЅС‹С….

        Args:
            created_by: ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ, СЃРѕР·РґР°РІС€РµРіРѕ Р±СЌРєР°Рї
            compress: РЎР¶РёРјР°С‚СЊ Р»Рё Р±СЌРєР°Рї (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РёР· РєРѕРЅС„РёРіР°)
            include_logs: Р’РєР»СЋС‡Р°С‚СЊ Р»Рё Р»РѕРіРё (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РёР· РєРѕРЅС„РёРіР°)

        Returns:
            Tuple[success, message, filepath]
        """
        try:
            logger.info("рџ“„ РќР°С‡РёРЅР°РµРј СЃРѕР·РґР°РЅРёРµ Р±СЌРєР°РїР°...")

            if compress is None:
                compress = self.config.backup.compression
            if include_logs is None:
                include_logs = self.config.backup.include_logs

            includes_database = scope in (BackupScope.DB, BackupScope.FULL)
            includes_assets = scope in (BackupScope.ASSETS, BackupScope.FULL)

            # РЎРѕР±РёСЂР°РµРј СЃС‚Р°С‚РёСЃС‚РёРєСѓ
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

                # Р­РєСЃРїРѕСЂС‚РёСЂСѓРµРј Р‘Р” С‡РµСЂРµР· ORM
                database_info: Optional[Dict[str, Any]] = None
                assets_info: Optional[Dict[str, Any]] = None
                if includes_database:
                    database_info = await self._dump_database_json(staging_dir)
                if includes_assets:
                    assets_info = await self._dump_assets(staging_dir)

                # РњРµС‚Р°РґР°РЅРЅС‹Рµ
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

                # РЎРѕР·РґР°С‘Рј Р°СЂС…РёРІ
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
                f"вњ… Р‘СЌРєР°Рї СѓСЃРїРµС€РЅРѕ СЃРѕР·РґР°РЅ!\n"
                f"рџ“Ѓ Р¤Р°Р№Р»: {filename}\n"
                f"рџ“Љ РўР°Р±Р»РёС†: {overview.get('tables_count', 0)}\n"
                f"рџ“€ Р—Р°РїРёСЃРµР№: {overview.get('total_records', 0):,}\n"
                f"рџ’ѕ Р Р°Р·РјРµСЂ: {size_mb:.2f} MB"
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
            error_msg = f"вќЊ РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ Р±СЌРєР°РїР°: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None

    async def restore_backup(
        self,
        backup_file_path: str,
        clear_existing: bool = False,
        locale: Locale | None = None,
    ) -> Tuple[bool, str]:
        """
        Р’РѕСЃСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ Р±Р°Р·Сѓ РґР°РЅРЅС‹С… РёР· Р±СЌРєР°РїР°.

        Args:
            backup_file_path: РџСѓС‚СЊ Рє С„Р°Р№Р»Сѓ Р±СЌРєР°РїР°
            clear_existing: РћС‡РёСЃС‚РёС‚СЊ Р»Рё СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ РґР°РЅРЅС‹Рµ

        Returns:
            Tuple[success, message]
        """
        try:
            logger.info(f"рџ“„ РќР°С‡РёРЅР°РµРј РІРѕСЃСЃС‚Р°РЅРѕРІР»РµРЅРёРµ РёР· {backup_file_path}")

            backup_path = Path(backup_file_path)
            if not backup_path.exists():
                if locale is not None:
                    return False, self._build_backup_missing_file_message(
                        backup_file_path,
                        locale=locale,
                    )
                return False, f"вќЊ Р¤Р°Р№Р» Р±СЌРєР°РїР° РЅРµ РЅР°Р№РґРµРЅ: {backup_file_path}"

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
        """РџРѕР»СѓС‡Р°РµС‚ СЃРїРёСЃРѕРє РІСЃРµС… Р±СЌРєР°РїРѕРІ."""
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
                    logger.error(f"РћС€РёР±РєР° С‡С‚РµРЅРёСЏ РјРµС‚Р°РґР°РЅРЅС‹С… {backup_file}: {e}")
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
            logger.error(f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° Р±СЌРєР°РїРѕРІ: {e}")

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
        """РЈРґР°Р»СЏРµС‚ С„Р°Р№Р» Р±СЌРєР°РїР°."""
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
        """Р—Р°РїСѓСЃРєР°РµС‚ С†РёРєР» Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёС… Р±СЌРєР°РїРѕРІ."""
        if self._auto_backup_task and not self._auto_backup_task.done():
            self._auto_backup_task.cancel()

        if self.config.backup.auto_enabled:
            next_run = self._calculate_next_backup_datetime()
            interval = self._get_backup_interval()
            self._auto_backup_task = asyncio.create_task(self._auto_backup_loop(next_run))
            logger.info(
                f"рџ“„ РђРІС‚РѕР±СЌРєР°РїС‹ РІРєР»СЋС‡РµРЅС‹, РёРЅС‚РµСЂРІР°Р»: {interval.total_seconds() / 3600:.2f}С‡, "
                f"Р±Р»РёР¶Р°Р№С€РёР№ Р·Р°РїСѓСЃРє: {next_run.strftime('%d.%m.%Y %H:%M:%S')}"
            )

    async def stop_auto_backup(self) -> None:
        """РћСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ С†РёРєР» Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёС… Р±СЌРєР°РїРѕРІ."""
        if self._auto_backup_task and not self._auto_backup_task.done():
            self._auto_backup_task.cancel()
            logger.info("в„№пёЏ РђРІС‚РѕР±СЌРєР°РїС‹ РѕСЃС‚Р°РЅРѕРІР»РµРЅС‹")

    # --- Private methods ---

    async def _auto_backup_loop(self, next_run: Optional[datetime] = None) -> None:
        """Р¦РёРєР» Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРёС… Р±СЌРєР°РїРѕРІ."""
        next_run = next_run or self._calculate_next_backup_datetime()
        interval = self._get_backup_interval()

        while True:
            try:
                now = datetime_now()
                delay = (next_run - now).total_seconds()

                if delay > 0:
                    logger.info(
                        f"вЏ° РЎР»РµРґСѓСЋС‰РёР№ Р°РІС‚РѕР±СЌРєР°Рї: {next_run.strftime('%d.%m.%Y %H:%M:%S')} "
                        f"(С‡РµСЂРµР· {delay / 3600:.2f} С‡)"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.info("вЏ° Р’СЂРµРјСЏ Р°РІС‚РѕР±СЌРєР°РїР° СѓР¶Рµ РЅР°СЃС‚СѓРїРёР»Рѕ, Р·Р°РїСѓСЃРєР°РµРј РЅРµРјРµРґР»РµРЅРЅРѕ")

                logger.info("рџ“„ Р—Р°РїСѓСЃРє Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРіРѕ Р±СЌРєР°РїР°...")
                success, message, _ = await self.create_backup()

                if success:
                    logger.info(f"вњ… РђРІС‚РѕР±СЌРєР°Рї Р·Р°РІРµСЂС€РµРЅ: {message}")
                else:
                    logger.error(f"вќЊ РћС€РёР±РєР° Р°РІС‚РѕР±СЌРєР°РїР°: {message}")

                next_run = next_run + interval

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"РћС€РёР±РєР° РІ С†РёРєР»Рµ Р°РІС‚РѕР±СЌРєР°РїРѕРІ: {e}")
                next_run = datetime_now() + interval

    async def _collect_database_overview(self) -> Dict[str, Any]:
        """РЎРѕР±РёСЂР°РµС‚ СЃС‚Р°С‚РёСЃС‚РёРєСѓ РїРѕ С‚Р°Р±Р»РёС†Р°Рј Р‘Р”."""
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
            logger.warning(f"РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР±СЂР°С‚СЊ СЃС‚Р°С‚РёСЃС‚РёРєСѓ РїРѕ Р‘Р”: {exc}")

        return overview

    async def _dump_database_json(self, staging_dir: Path) -> Dict[str, Any]:
        """Р­РєСЃРїРѕСЂС‚РёСЂСѓРµС‚ Р‘Р” РІ JSON С‡РµСЂРµР· ORM."""
        backup_data: Dict[str, List[Dict[str, Any]]] = {}
        total_records = 0
        export_errors: dict[str, str] = {}

        async with self.session_pool() as session:
            for model in self.BACKUP_MODELS:
                table_name = model.__tablename__
                logger.info(f"рџ“Љ Р­РєСЃРїРѕСЂС‚РёСЂСѓРµРј С‚Р°Р±Р»РёС†Сѓ: {table_name}")

                try:
                    result = await session.execute(select(model))
                    records = result.scalars().all()

                    table_data: List[Dict[str, Any]] = []
                    for record in records:
                        record_dict = self._model_to_dict(record, model)
                        table_data.append(record_dict)

                    backup_data[table_name] = table_data
                    total_records += len(table_data)

                    logger.info(f"вњ… Р­РєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅРѕ {len(table_data)} Р·Р°РїРёСЃРµР№ РёР· {table_name}")

                except Exception as e:
                    logger.error(f"РћС€РёР±РєР° СЌРєСЃРїРѕСЂС‚Р° С‚Р°Р±Р»РёС†С‹ {table_name}: {e}")
                    export_errors[table_name] = str(e)
                    backup_data[table_name] = []

        # РЎРѕС…СЂР°РЅСЏРµРј РІ С„Р°Р№Р»
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

        logger.info(f"вњ… Р‘Р” СЌРєСЃРїРѕСЂС‚РёСЂРѕРІР°РЅР° РІ JSON ({dump_path})")

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

    async def _cleanup_old_backups(self) -> None:
        """РЈРґР°Р»СЏРµС‚ СЃС‚Р°СЂС‹Рµ Р±СЌРєР°РїС‹."""
        try:
            backups = [
                backup
                for backup in await self.get_backup_list()
                if backup.has_local_copy and backup.filepath
            ]

            if len(backups) > self.config.backup.max_keep:
                # РЎРѕСЂС‚РёСЂСѓРµРј РїРѕ РІСЂРµРјРµРЅРё (РЅРѕРІС‹Рµ РїРµСЂРІС‹Рµ)
                backups.sort(
                    key=lambda backup: self._backup_sort_timestamp(backup.timestamp),
                    reverse=True,
                )

                for backup in backups[self.config.backup.max_keep :]:
                    try:
                        await self.delete_backup(backup.filename)
                        logger.info(f"рџ—‘пёЏ РЈРґР°Р»С‘РЅ СЃС‚Р°СЂС‹Р№ Р±СЌРєР°Рї: {backup.filename}")
                    except Exception as e:
                        logger.error(f"РћС€РёР±РєР° СѓРґР°Р»РµРЅРёСЏ СЃС‚Р°СЂРѕРіРѕ Р±СЌРєР°РїР° {backup.filename}: {e}")

        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РѕС‡РёСЃС‚РєРё СЃС‚Р°СЂС‹С… Р±СЌРєР°РїРѕРІ: {e}")

    async def _send_backup_file_to_chat(self, file_path: str) -> Optional[Message]:
        """РћС‚РїСЂР°РІР»СЏРµС‚ С„Р°Р№Р» Р±СЌРєР°РїР° РІ Telegram С‡Р°С‚."""
        try:
            if not self.config.backup.is_send_enabled():
                return None

            chat_id = self.config.backup.send_chat_id
            if not chat_id:
                return None

            document = FSInputFile(file_path)
            caption = (
                f"рџ“¦ <b>Р РµР·РµСЂРІРЅР°СЏ РєРѕРїРёСЏ</b>\n\n"
                f"вЏ° <i>{datetime_now().strftime('%d.%m.%Y %H:%M:%S')}</i>"
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
            logger.info(f"Р‘СЌРєР°Рї РѕС‚РїСЂР°РІР»РµРЅ РІ С‡Р°С‚ {chat_id}")
            return message

        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РѕС‚РїСЂР°РІРєРё Р±СЌРєР°РїР° РІ С‡Р°С‚: {e}")
            return None
