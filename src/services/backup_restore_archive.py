from __future__ import annotations

import gzip
import json as json_lib
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import aiofiles
from loguru import logger

from src.core.enums import Locale

if TYPE_CHECKING:
    from .backup import BackupService

_aiofiles_open = cast(Any, aiofiles.open)


def _archive_read_mode(backup_path: Path) -> Literal["r", "r:gz"]:
    return "r:gz" if backup_path.suffixes and backup_path.suffixes[-1] == ".gz" else "r"


def _is_archive_backup(_service: BackupService, backup_path: Path) -> bool:
    suffixes = backup_path.suffixes
    if (len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]) or (
        suffixes and suffixes[-1] == ".tar"
    ):
        return True
    try:
        return tarfile.is_tarfile(backup_path)
    except Exception:
        return False


async def _read_backup_metadata(
    service: BackupService,
    backup_path: Path,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    if service._is_archive_backup(backup_path):
        with tarfile.open(str(backup_path), _archive_read_mode(backup_path)) as tar:
            try:
                member = tar.getmember("metadata.json")
                meta_file = tar.extractfile(member)
                if meta_file is not None:
                    with meta_file:
                        metadata = json_lib.load(meta_file)
            except KeyError:
                pass
    else:
        if backup_path.suffix == ".gz":
            with gzip.open(backup_path, "rt", encoding="utf-8") as file:
                backup_structure = json_lib.load(file)
        else:
            with open(backup_path, "r", encoding="utf-8") as file:
                backup_structure = json_lib.load(file)
        metadata = backup_structure.get("metadata", {})

    return metadata


async def _restore_archive_database_part(
    service: BackupService,
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
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            return False, i18n.get(
                "msg-backup-error-db-dump-missing",
                path=str(dump_file),
            )
        return False, f"Database dump file not found: {dump_file}"

    return await service._restore_from_json(
        dump_file,
        clear_existing,
        locale=locale,
    )


async def _restore_archive_assets_part(
    service: BackupService,
    *,
    temp_path: Path,
    metadata: dict[str, Any],
    locale: Locale | None,
) -> tuple[bool, str]:
    assets_info = metadata.get("assets", {})
    assets_dir = temp_path / assets_info.get("path", "assets")
    if not assets_dir.exists():
        if locale is not None:
            i18n = service.translator_hub.get_translator_by_locale(locale=locale)
            return False, i18n.get(
                "msg-backup-error-assets-missing",
                path=str(assets_dir),
            )
        return False, f"Assets directory not found: {assets_dir}"

    return True, await service._restore_assets_from_dir(assets_dir, locale=locale)


async def _restore_from_archive(
    service: BackupService,
    backup_path: Path,
    clear_existing: bool,
    locale: Locale | None = None,
) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        with tarfile.open(str(backup_path), _archive_read_mode(backup_path)) as tar:
            tar.extractall(temp_path, filter="data")

        metadata_path = temp_path / "metadata.json"
        if not metadata_path.exists():
            if locale is not None:
                i18n = service.translator_hub.get_translator_by_locale(locale=locale)
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
            db_success, db_message = await service._restore_archive_database_part(
                temp_path=temp_path,
                metadata=metadata,
                clear_existing=clear_existing,
                locale=locale,
            )
            if not db_success:
                return db_success, db_message
            result_parts.append(db_message)

        if includes_assets:
            assets_success, assets_message = await service._restore_archive_assets_part(
                temp_path=temp_path,
                metadata=metadata,
                locale=locale,
            )
            if not assets_success:
                return False, assets_message
            result_parts.append(assets_message)

        if not result_parts:
            if locale is not None:
                i18n = service.translator_hub.get_translator_by_locale(locale=locale)
                return False, i18n.get("msg-backup-error-empty")
            return False, "Backup does not contain restorable data"

        return True, "\n\n".join(result_parts)


async def _restore_assets_from_dir(
    service: BackupService,
    source_dir: Path,
    *,
    locale: Locale | None = None,
) -> str:
    target_dir = service.config.assets_dir
    restored_files = 0

    target_dir.mkdir(parents=True, exist_ok=True)

    for source_file in source_dir.rglob("*"):
        if not source_file.is_file():
            continue

        relative_path = source_file.relative_to(source_dir)
        if service._should_skip_asset_file(relative_path):
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
        i18n = service.translator_hub.get_translator_by_locale(locale=locale)
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
