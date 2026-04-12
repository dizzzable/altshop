# mypy: ignore-errors

from __future__ import annotations

import gzip
import json as json_lib
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Optional, cast

import aiofiles  # type: ignore[import-untyped]
from loguru import logger
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import Locale
from src.infrastructure.database.models.sql import Subscription, User

from .backup_models import DeferredRestoreUpdate

_aiofiles_open = cast(Any, aiofiles.open)


class BackupRestoreMixin:
    def _is_archive_backup(self, backup_path: Path) -> bool:
        suffixes = backup_path.suffixes
        if (len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]) or (
            suffixes and suffixes[-1] == ".tar"
        ):
            return True
        try:
            return tarfile.is_tarfile(backup_path)
        except Exception:
            return False

    async def _read_backup_metadata(self, backup_path: Path) -> dict[str, Any]:
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
        metadata: dict[str, Any],
        clear_existing: bool,
        locale: Locale | None,
    ) -> tuple[bool, str]:
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
        metadata: dict[str, Any],
        locale: Locale | None,
    ) -> tuple[bool, str]:
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
    ) -> tuple[bool, str]:
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
    ) -> tuple[bool, str]:
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

        message = self._build_restore_result_message(
            locale=locale,
            metadata=metadata,
            restored_tables=restored_tables,
            restored_records=restored_records,
            recovered_legacy_plans=recovered_legacy_plans,
        )
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
        records: list[dict[str, Any]],
        clear_existing: bool,
        deferred_updates: Optional[list[DeferredRestoreUpdate]] = None,
    ) -> int:
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
        processed_data: dict[str, Any],
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
        values = {key: value for key, value in processed_data.items() if key != primary_key_col}
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
        processed_data: dict[str, Any],
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
        processed_data: dict[str, Any],
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
        processed_data: dict[str, Any],
    ) -> tuple[dict[str, Any], Optional[DeferredRestoreUpdate]]:
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
        values: dict[str, Any],
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
        values: dict[str, Any],
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
    ) -> dict[str, Any]:
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

    async def _clear_database_tables(self, session: AsyncSession) -> None:
        tables_order = [model.__tablename__ for model in reversed(self.BACKUP_MODELS)]

        for table_name in tables_order:
            try:
                await session.execute(text(f"DELETE FROM {table_name}"))
                logger.info(f"🗑️ Очищена таблица {table_name}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось очистить таблицу {table_name}: {e}")

    async def _clear_database_tables_atomic(self, session: AsyncSession) -> None:
        table_names = ", ".join(model.__tablename__ for model in self.BACKUP_MODELS)
        await session.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
        logger.info("🗑️ Cleared restore-owned tables with TRUNCATE CASCADE")
