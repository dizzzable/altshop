from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

import aiofiles
from loguru import logger
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.enums import Locale
from src.infrastructure.database.models.sql import Subscription, User

from .backup_models import DeferredRestoreUpdate

if TYPE_CHECKING:
    from .backup import BackupService

_aiofiles_open = cast(Any, aiofiles.open)


async def _restore_from_json(
    service: BackupService,
    dump_path: Path,
    clear_existing: bool,
    locale: Locale | None = None,
) -> tuple[bool, str]:
    async with _aiofiles_open(dump_path, "r", encoding="utf-8") as file:
        dump_data = json_lib.loads(await file.read())

    metadata = dump_data.get("metadata", {})
    raw_backup_data = dump_data.get("data", {})
    diagnostics = service._analyze_restore_archive(raw_backup_data)
    service._log_restore_archive_diagnostics(diagnostics)
    backup_data, recovered_legacy_plans = service._recover_legacy_missing_plans(raw_backup_data)

    if not backup_data:
        if locale is not None:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            return False, i18n.get("msg-backup-error-empty")
        return False, "❌ Файл бэкапа не содержит данных"

    logger.info(
        "📉 Загружен дамп: {}",
        metadata.get("timestamp", "неизвестная дата"),
    )

    restored_records = 0
    restored_tables = 0

    async with service.session_pool() as session:
        try:
            deferred_updates: list[DeferredRestoreUpdate] = []
            if clear_existing:
                logger.warning("🗑️ Очищаем существующие данные...")
                await service._clear_database_tables_atomic(session)

            for model in service.BACKUP_MODELS:
                table_name = model.__tablename__
                records = backup_data.get(table_name, [])

                if not records:
                    continue

                logger.info(
                    "🔥 Восстанавливаем таблицу {} ({} записей)",
                    table_name,
                    len(records),
                )

                restored = await service._restore_table_records(
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
                    logger.info("✅ Таблица {} восстановлена", table_name)

            await service._apply_deferred_restore_updates(
                session,
                deferred_updates,
                phase=service.RESTORE_PHASE_POST_SUBSCRIPTIONS,
            )
            if deferred_updates:
                await session.flush()

            await session.commit()

        except Exception as exc:
            await session.rollback()
            logger.error("Ошибка при восстановлении: {}", exc)
            raise

    message = service._build_restore_result_message(
        locale=locale,
        metadata=metadata,
        restored_tables=restored_tables,
        restored_records=restored_records,
        recovered_legacy_plans=recovered_legacy_plans,
    )
    diagnostics = await service._recover_missing_subscriptions_from_panel(diagnostics)
    message = service._append_restore_diagnostics_to_message(
        message=message,
        locale=locale,
        diagnostics=diagnostics,
    )

    logger.info(message)
    return True, message


async def _restore_table_records(  # noqa: C901
    service: BackupService,
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
            processed_data = service._process_record_data(record_data, model, table_name)
            processed_data, deferred_update = service._extract_deferred_restore_fields(
                model,
                processed_data,
            )
            primary_key_col = service._get_primary_key_column(model)

            existing = None
            if not clear_existing and model is User:
                updated = await service._merge_existing_user_record(
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
                existing = await service._find_existing_restore_record(
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

        except Exception as exc:
            logger.error(
                "Ошибка восстановления записи в {}: {}",
                table_name,
                exc,
            )
            logger.error("Проблемные данные: {}", record_data)
            raise

    return restored_count


async def _merge_existing_user_record(
    service: BackupService,
    *,
    session: AsyncSession,
    processed_data: dict[str, Any],
    primary_key_col: Optional[str],
) -> bool:
    restore_target = await service._find_existing_user_restore_target(
        session=session,
        processed_data=processed_data,
        primary_key_col=primary_key_col,
    )
    if restore_target is None:
        return False

    lookup_field, lookup_value = restore_target
    values = {key: value for key, value in processed_data.items() if key != primary_key_col}
    await service._apply_scalar_restore_update(
        session=session,
        model=User,
        lookup_field=lookup_field,
        lookup_value=lookup_value,
        values=values,
    )
    return True


async def _find_existing_user_restore_target(
    _service: BackupService,
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
    service: BackupService,
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

    for lookup_field in service.RESTORE_LOOKUP_FIELDS.get(model.__tablename__, ()):
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
    service: BackupService,
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
        phase=service.RESTORE_PHASE_POST_SUBSCRIPTIONS,
        apply_as_scalar_update=True,
    )


async def _apply_deferred_restore_updates(
    service: BackupService,
    session: AsyncSession,
    deferred_updates: list[DeferredRestoreUpdate],
    *,
    phase: str,
) -> None:
    for deferred_update in deferred_updates:
        if deferred_update.phase != phase:
            continue

        values = await service._filter_deferred_restore_values(session, deferred_update)
        if not values:
            continue

        if deferred_update.apply_as_scalar_update:
            await service._apply_scalar_deferred_restore_update(
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
    service: BackupService,
    session: AsyncSession,
    deferred_update: DeferredRestoreUpdate,
    values: dict[str, Any],
) -> None:
    rows_updated = await service._apply_scalar_restore_update(
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
    _service: BackupService,
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
    _service: BackupService,
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


async def _clear_database_tables(service: BackupService, session: AsyncSession) -> None:
    tables_order = [model.__tablename__ for model in reversed(service.BACKUP_MODELS)]

    for table_name in tables_order:
        try:
            await session.execute(text(f"DELETE FROM {table_name}"))
            logger.info("🗑️ Очищена таблица {}", table_name)
        except Exception as exc:
            logger.warning(
                "⚠️ Не удалось очистить таблицу {}: {}",
                table_name,
                exc,
            )


async def _clear_database_tables_atomic(
    service: BackupService,
    session: AsyncSession,
) -> None:
    table_names = ", ".join(model.__tablename__ for model in service.BACKUP_MODELS)
    await session.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    logger.info("🗑️ Cleared restore-owned tables with TRUNCATE CASCADE")
