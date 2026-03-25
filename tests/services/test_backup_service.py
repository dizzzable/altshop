from __future__ import annotations

import asyncio
import json
import tarfile
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from remnawave.enums.users import TrafficLimitStrategy

from src.core.enums import (
    ArchivedPlanRenewMode,
    BackupScope,
    BackupSourceKind,
    Currency,
    DeviceType,
    Locale,
    PaymentGatewayType,
    PlanAvailability,
    PlanType,
    PromocodeAvailability,
    PromocodeRewardType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
    UserRole,
)
from src.infrastructure.database.models.sql.plan import Plan, PlanDuration, PlanPrice
from src.infrastructure.database.models.sql.promocode import Promocode
from src.infrastructure.database.models.sql.subscription import Subscription
from src.infrastructure.database.models.sql.transaction import Transaction
from src.infrastructure.database.models.sql.user import User
from src.services.backup import BackupInfo, BackupService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_backup_service(
    tmp_path: Path,
    *,
    assets_dir: Path | None = None,
) -> tuple[BackupService, object]:
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    current_assets_dir = assets_dir or (tmp_path / "assets")
    current_assets_dir.mkdir(parents=True, exist_ok=True)

    backup_config = SimpleNamespace(
        compression=True,
        include_logs=False,
        auto_enabled=False,
        interval_hours=24,
        time="03:00",
        max_keep=7,
        location=backup_dir,
        send_enabled=False,
        send_chat_id=None,
        send_topic_id=None,
        is_send_enabled=lambda: False,
        get_backup_dir=lambda: backup_dir,
    )
    config = SimpleNamespace(
        backup=backup_config,
        assets_dir=current_assets_dir,
    )

    service = BackupService(
        config=config,
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        session_pool=MagicMock(),
        engine=MagicMock(),
    )
    service._send_backup_file_to_chat = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._cleanup_old_backups = AsyncMock()  # type: ignore[method-assign]
    service._list_registered_backup_infos = AsyncMock(return_value=[])  # type: ignore[method-assign]
    service._upsert_backup_record = AsyncMock()  # type: ignore[method-assign]
    service._sync_backup_record_after_local_delete = AsyncMock()  # type: ignore[method-assign]
    service._download_telegram_backup_file = AsyncMock()  # type: ignore[method-assign]
    return service, config


def read_archive_metadata(archive_path: Path) -> tuple[dict[str, object], list[str]]:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        with archive.extractfile("metadata.json") as metadata_file:
            assert metadata_file is not None
            metadata = json.load(metadata_file)
    return metadata, names


async def write_database_dump(staging_dir: Path) -> dict[str, object]:
    dump_path = staging_dir / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-24T10:00:00+00:00"},
                "data": {"users": [{"id": 1}], "plans": [{"id": 10}]},
            }
        ),
        encoding="utf-8",
    )
    return {
        "type": "postgresql",
        "path": dump_path.name,
        "size_bytes": dump_path.stat().st_size,
        "format": "json",
        "tool": "orm",
        "tables_count": 2,
        "total_records": 2,
    }


def test_create_database_backup_contains_db_manifest_only(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 12, "total_records": 345}
    )
    service._dump_database_json = AsyncMock(side_effect=write_database_dump)  # type: ignore[method-assign]

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.DB))

    assert success is True
    assert file_path is not None
    assert "Scope: Database only" in message
    assert "Records: 345" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.DB.value
    assert metadata["includes_database"] is True
    assert metadata["includes_assets"] is False
    assert "database.json" in names
    assert all(not name.startswith("assets/") for name in names)


def test_create_assets_backup_contains_assets_only(tmp_path: Path) -> None:
    assets_dir = tmp_path / "runtime-assets"
    branded_file = assets_dir / "branding" / "logo.txt"
    branded_file.parent.mkdir(parents=True, exist_ok=True)
    branded_file.write_text("custom-logo", encoding="utf-8")
    (assets_dir / ".altshop_assets_version").write_text("1.2.1", encoding="utf-8")
    backup_dir = assets_dir / ".bak"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "assets_backup_20260325.tar.gz").write_text("backup-payload", encoding="utf-8")

    service, _config = build_backup_service(tmp_path, assets_dir=assets_dir)

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.ASSETS))

    assert success is True
    assert file_path is not None
    assert "Scope: Assets only" in message
    assert "Assets files: 1" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.ASSETS.value
    assert metadata["includes_database"] is False
    assert metadata["includes_assets"] is True
    assert "database.json" not in names
    assert "assets/branding/logo.txt" in names
    assert "assets/.altshop_assets_version" not in names
    assert "assets/.bak/assets_backup_20260325.tar.gz" not in names


def test_create_full_backup_contains_database_and_assets(tmp_path: Path) -> None:
    assets_dir = tmp_path / "runtime-assets"
    branded_file = assets_dir / "translations" / "en.ftl"
    branded_file.parent.mkdir(parents=True, exist_ok=True)
    branded_file.write_text("hello = world", encoding="utf-8")

    service, _config = build_backup_service(tmp_path, assets_dir=assets_dir)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 7, "total_records": 99}
    )
    service._dump_database_json = AsyncMock(side_effect=write_database_dump)  # type: ignore[method-assign]

    success, message, file_path = run_async(service.create_backup(scope=BackupScope.FULL))

    assert success is True
    assert file_path is not None
    assert "Scope: Full backup" in message
    assert "Tables: 7" in message
    assert "Assets files: 1" in message

    metadata, names = read_archive_metadata(Path(file_path))
    assert metadata["backup_scope"] == BackupScope.FULL.value
    assert metadata["includes_database"] is True
    assert metadata["includes_assets"] is True
    assert "database.json" in names
    assert "assets/translations/en.ftl" in names


def test_restore_assets_backup_merges_files_without_deleting_unrelated(tmp_path: Path) -> None:
    source_assets_dir = tmp_path / "source-assets"
    backed_up_file = source_assets_dir / "branding" / "banner.txt"
    backed_up_file.parent.mkdir(parents=True, exist_ok=True)
    backed_up_file.write_text("banner-v1", encoding="utf-8")

    service, config = build_backup_service(tmp_path, assets_dir=source_assets_dir)
    success, _message, file_path = run_async(service.create_backup(scope=BackupScope.ASSETS))
    assert success is True
    assert file_path is not None

    target_assets_dir = tmp_path / "target-assets"
    unrelated_file = target_assets_dir / "keep.txt"
    unrelated_file.parent.mkdir(parents=True, exist_ok=True)
    unrelated_file.write_text("keep-me", encoding="utf-8")
    config.assets_dir = target_assets_dir

    restored, restore_message = run_async(service.restore_backup(file_path))

    assert restored is True
    assert "Assets restored successfully!" in restore_message
    restored_banner = (target_assets_dir / "branding" / "banner.txt").read_text(
        encoding="utf-8"
    )

    assert restored_banner == "banner-v1"
    assert unrelated_file.read_text(encoding="utf-8") == "keep-me"


def test_restore_assets_backup_skips_internal_asset_sync_files(tmp_path: Path) -> None:
    source_assets_dir = tmp_path / "source-assets"
    marker_file = source_assets_dir / ".altshop_assets_version"
    backup_archive = source_assets_dir / ".bak" / "assets_backup_20260325.tar.gz"
    actual_file = source_assets_dir / "branding" / "banner.txt"
    backup_archive.parent.mkdir(parents=True, exist_ok=True)
    actual_file.parent.mkdir(parents=True, exist_ok=True)
    marker_file.write_text("1.2.0", encoding="utf-8")
    backup_archive.write_text("old-assets", encoding="utf-8")
    actual_file.write_text("banner-v1", encoding="utf-8")

    service, config = build_backup_service(tmp_path)
    target_assets_dir = tmp_path / "target-assets"
    config.assets_dir = target_assets_dir

    restore_message = run_async(service._restore_assets_from_dir(source_assets_dir))

    assert "Assets restored successfully!" in restore_message
    assert (target_assets_dir / "branding" / "banner.txt").read_text(encoding="utf-8") == (
        "banner-v1"
    )
    assert not (target_assets_dir / ".altshop_assets_version").exists()
    assert not (target_assets_dir / ".bak").exists()


def test_restore_database_backup_leaves_assets_untouched(tmp_path: Path) -> None:
    service, config = build_backup_service(tmp_path)
    service._collect_database_overview = AsyncMock(  # type: ignore[method-assign]
        return_value={"tables_count": 4, "total_records": 10}
    )
    service._dump_database_json = AsyncMock(side_effect=write_database_dump)  # type: ignore[method-assign]
    service._restore_from_json = AsyncMock(return_value=(True, "DB restored"))  # type: ignore[method-assign]

    success, _message, file_path = run_async(service.create_backup(scope=BackupScope.DB))
    assert success is True
    assert file_path is not None

    target_assets_dir = tmp_path / "runtime-assets"
    existing_file = target_assets_dir / "custom.txt"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("do-not-touch", encoding="utf-8")
    config.assets_dir = target_assets_dir

    restored, restore_message = run_async(service.restore_backup(file_path, clear_existing=True))

    assert restored is True
    assert restore_message == "DB restored"
    assert existing_file.read_text(encoding="utf-8") == "do-not-touch"
    service._restore_from_json.assert_awaited_once()


def test_get_backup_list_merges_registry_entries_with_local_fallback(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)

    fallback_file = service.backup_dir / "backup_local_only.tar.gz"
    fallback_file.write_text("broken backup", encoding="utf-8")

    registry_backup = BackupInfo(
        selection_key="registry:1",
        filename="backup_registry.tar.gz",
        filepath=str(service.backup_dir / "backup_registry.tar.gz"),
        timestamp="2026-03-25T11:00:00+00:00",
        tables_count=1,
        total_records=2,
        compressed=True,
        file_size_bytes=1024,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.0",
        source_kind=BackupSourceKind.LOCAL_AND_TELEGRAM,
        has_local_copy=True,
        has_telegram_copy=True,
        telegram_file_id="telegram-file",
    )
    service._list_registered_backup_infos = AsyncMock(return_value=[registry_backup])  # type: ignore[method-assign]

    backups = run_async(service.get_backup_list())

    assert len(backups) == 2
    assert any(backup.selection_key == "registry:1" for backup in backups)
    assert any(backup.selection_key == "local:backup_local_only.tar.gz" for backup in backups)


def test_restore_selected_backup_downloads_telegram_only_backup(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    telegram_backup = BackupInfo(
        selection_key="registry:42",
        filename="backup_remote.tar.gz",
        filepath="",
        timestamp="2026-03-25T11:00:00+00:00",
        tables_count=1,
        total_records=2,
        compressed=True,
        file_size_bytes=1024,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.0",
        source_kind=BackupSourceKind.TELEGRAM,
        has_local_copy=False,
        has_telegram_copy=True,
        telegram_file_id="telegram-file",
    )
    service.get_backup_by_key = AsyncMock(return_value=telegram_backup)  # type: ignore[method-assign]
    service.restore_backup = AsyncMock(return_value=(True, "restored"))  # type: ignore[method-assign]

    success, message = run_async(service.restore_selected_backup("registry:42"))

    assert success is True
    assert message == "restored"
    service._download_telegram_backup_file.assert_awaited_once()
    service.restore_backup.assert_awaited_once()


def test_import_backup_file_registers_local_copy(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    archive_path = tmp_path / "backup_import.tar.gz"
    archive_path.write_text("fake", encoding="utf-8")
    service._read_backup_metadata = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "timestamp": "2026-03-25T10:00:00+00:00",
            "backup_scope": BackupScope.DB.value,
            "includes_database": True,
            "includes_assets": False,
        }
    )

    success, backup_info, error = run_async(
        service.import_backup_file(
            source_file_path=archive_path,
            original_filename="backup_import.tar.gz",
            created_by=7,
        )
    )

    assert success is True
    assert backup_info is not None
    assert error == ""
    service._upsert_backup_record.assert_awaited_once()


def test_delete_selected_backup_removes_local_copy_only(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    local_path = service.backup_dir / "backup_local.tar.gz"
    local_path.write_text("payload", encoding="utf-8")
    local_backup = BackupInfo(
        selection_key="registry:9",
        filename=local_path.name,
        filepath=str(local_path),
        timestamp="2026-03-25T11:00:00+00:00",
        tables_count=1,
        total_records=2,
        compressed=True,
        file_size_bytes=local_path.stat().st_size,
        file_size_mb=0.0,
        created_by=1,
        database_type="postgresql",
        version="3.0",
        source_kind=BackupSourceKind.LOCAL_AND_TELEGRAM,
        has_local_copy=True,
        has_telegram_copy=True,
        telegram_file_id="telegram-file",
    )
    service.get_backup_by_key = AsyncMock(return_value=local_backup)  # type: ignore[method-assign]

    success, _message = run_async(service.delete_selected_backup("registry:9"))

    assert success is True
    assert not local_path.exists()
    service._sync_backup_record_after_local_delete.assert_awaited_once()


def test_model_to_dict_preserves_plan_arrays_and_empty_lists(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    internal_squad_id = uuid4()
    external_squad_id = uuid4()
    plan = Plan(
        id=10,
        order_index=1,
        is_active=True,
        is_archived=False,
        type=PlanType.BOTH,
        availability=PlanAvailability.ALLOWED,
        archived_renew_mode=ArchivedPlanRenewMode.SELF_RENEW,
        name="Starter",
        description="Base plan",
        tag="starter",
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        replacement_plan_ids=[],
        upgrade_to_plan_ids=[11, 12],
        allowed_user_ids=[],
        internal_squads=[internal_squad_id],
        external_squad=[external_squad_id],
    )
    duration = PlanDuration(id=20, plan_id=10, days=30)
    price = PlanPrice(id=30, plan_duration_id=20, currency=Currency.RUB, price=Decimal("99.90"))

    serialized_plan = service._model_to_dict(plan, Plan)
    serialized_duration = service._model_to_dict(duration, PlanDuration)
    serialized_price = service._model_to_dict(price, PlanPrice)

    assert serialized_plan["replacement_plan_ids"] == []
    assert serialized_plan["upgrade_to_plan_ids"] == [11, 12]
    assert serialized_plan["allowed_user_ids"] == []
    assert serialized_plan["internal_squads"] == [str(internal_squad_id)]
    assert serialized_plan["external_squad"] == [str(external_squad_id)]
    assert serialized_duration["days"] == 30
    assert serialized_price["price"] == "99.90"


def test_model_to_dict_preserves_transaction_json_objects(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    transaction = Transaction(
        id=1,
        payment_id=uuid4(),
        user_telegram_id=123,
        status=TransactionStatus.PENDING,
        is_test=False,
        purchase_type=PurchaseType.NEW,
        channel=None,
        gateway_type=PaymentGatewayType.PLATEGA,
        pricing={"amount": "9.99", "currency": "RUB"},
        currency=Currency.RUB,
        payment_asset=None,
        plan={"id": 10, "name": "Starter"},
        renew_subscription_id=None,
        renew_subscription_ids=[1, 2],
        device_types=["ios", "android"],
    )

    serialized = service._model_to_dict(transaction, Transaction)

    assert serialized["pricing"] == {"amount": "9.99", "currency": "RUB"}
    assert serialized["plan"] == {"id": 10, "name": "Starter"}
    assert serialized["renew_subscription_ids"] == [1, 2]
    assert serialized["device_types"] == ["ios", "android"]


def test_process_record_data_restores_legacy_plan_arrays_and_missing_defaults(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())

    processed = service._process_record_data(
        {
            "id": 10,
            "order_index": 1,
            "is_active": True,
            "is_archived": False,
            "type": PlanType.BOTH.value,
            "availability": PlanAvailability.ALLOWED.value,
            "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
            "name": "Starter",
            "description": "Base plan",
            "tag": "starter",
            "traffic_limit": 100,
            "device_limit": 3,
            "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
            "replacement_plan_ids": "[11, 12]",
            "upgrade_to_plan_ids": None,
            "allowed_user_ids": "[]",
            "internal_squads": f'["{squad_id}"]',
            # external_squad intentionally omitted to verify default salvage
        },
        Plan,
        "plans",
    )

    assert processed["replacement_plan_ids"] == [11, 12]
    assert processed["upgrade_to_plan_ids"] == []
    assert processed["allowed_user_ids"] == []
    assert processed["internal_squads"] == [UUID(squad_id)]
    assert "external_squad" not in processed


def test_process_record_data_restores_other_array_backed_models(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())

    promocode_processed = service._process_record_data(
        {
            "id": 1,
            "code": "PROMO",
            "is_active": True,
            "availability": PromocodeAvailability.ALL.value,
            "reward_type": PromocodeRewardType.DURATION.value,
            "reward": 30,
            "plan": '{"id": 10}',
            "lifetime": -1,
            "max_activations": -1,
            "allowed_user_ids": "[1, 2]",
            "allowed_plan_ids": None,
        },
        Promocode,
        "promocodes",
    )
    subscription_processed = service._process_record_data(
        {
            "id": 1,
            "user_remna_id": str(uuid4()),
            "user_telegram_id": 123,
            "status": SubscriptionStatus.ACTIVE.value,
            "is_trial": False,
            "traffic_limit": 100,
            "device_limit": 3,
            "internal_squads": f'["{squad_id}"]',
            "external_squad": str(uuid4()),
            "expire_at": datetime.now(timezone.utc).isoformat(),
            "url": "https://example.com",
            "device_type": DeviceType.IPHONE.value,
            "plan": '{"id": 10, "name": "Starter"}',
        },
        Subscription,
        "subscriptions",
    )
    transaction_processed = service._process_record_data(
        {
            "id": 1,
            "payment_id": str(uuid4()),
            "user_telegram_id": 123,
            "status": TransactionStatus.PENDING.value,
            "is_test": False,
            "purchase_type": PurchaseType.NEW.value,
            "channel": None,
            "gateway_type": PaymentGatewayType.PLATEGA.value,
            "pricing": '{"amount": "9.99"}',
            "currency": Currency.RUB.value,
            "payment_asset": None,
            "plan": '{"id": 10}',
            "renew_subscription_id": None,
            "renew_subscription_ids": "[1, 2]",
            "device_types": '["ios", "android"]',
        },
        Transaction,
        "transactions",
    )

    assert promocode_processed["allowed_user_ids"] == [1, 2]
    assert promocode_processed["allowed_plan_ids"] is None
    assert promocode_processed["plan"] == {"id": 10}
    assert subscription_processed["internal_squads"] == [UUID(squad_id)]
    assert subscription_processed["plan"] == {"id": 10, "name": "Starter"}
    assert transaction_processed["renew_subscription_ids"] == [1, 2]
    assert transaction_processed["device_types"] == ["ios", "android"]
    assert transaction_processed["pricing"] == {"amount": "9.99"}


def test_restore_table_records_builds_plan_instance_with_restored_arrays(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())
    captured_instances: list[Plan] = []
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=lambda instance: captured_instances.append(instance),
        no_autoflush=nullcontext(),
    )

    restored_count = run_async(
        service._restore_table_records(
            session,
            Plan,
            "plans",
            [
                {
                    "id": 10,
                    "order_index": 1,
                    "is_active": True,
                    "is_archived": False,
                    "type": PlanType.BOTH.value,
                    "availability": PlanAvailability.ALLOWED.value,
                    "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
                    "name": "Starter",
                    "description": "Base plan",
                    "tag": "starter",
                    "traffic_limit": 100,
                    "device_limit": 3,
                    "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                    "replacement_plan_ids": "[11, 12]",
                    "upgrade_to_plan_ids": None,
                    "allowed_user_ids": "[]",
                    "internal_squads": f'["{squad_id}"]',
                    "external_squad": "[]",
                }
            ],
            False,
        )
    )

    assert restored_count == 1
    assert len(captured_instances) == 1
    assert captured_instances[0].replacement_plan_ids == [11, 12]
    assert captured_instances[0].upgrade_to_plan_ids == []
    assert captured_instances[0].internal_squads == [UUID(squad_id)]


def test_restore_table_records_merges_existing_user_by_telegram_id(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    existing_user = SimpleNamespace(
        id=999,
        telegram_id=7534150980,
        username="existing_user",
        referral_code="oldCode",
        name="Existing Name",
        role=UserRole.USER,
        language=Locale.RU,
        personal_discount=0,
        purchase_discount=0,
        points=0,
        is_blocked=False,
        is_bot_blocked=False,
        is_rules_accepted=True,
        partner_balance_currency_override=None,
        referral_invite_settings={},
        max_subscriptions=None,
        current_subscription_id=None,
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: None),
                SimpleNamespace(scalar_one_or_none=lambda: existing_user),
            ]
        ),
        add=MagicMock(),
        no_autoflush=nullcontext(),
    )

    restored_count = run_async(
        service._restore_table_records(
            session,
            User,
            "users",
            [
                {
                    "id": 49,
                    "telegram_id": 7534150980,
                    "username": None,
                    "referral_code": "newCode",
                    "name": "Restored Name",
                    "role": UserRole.USER.value,
                    "language": Locale.RU.value,
                    "personal_discount": 0,
                    "purchase_discount": 0,
                    "points": 0,
                    "is_blocked": False,
                    "is_bot_blocked": False,
                    "is_rules_accepted": True,
                    "partner_balance_currency_override": None,
                    "referral_invite_settings": {},
                    "max_subscriptions": None,
                    "current_subscription_id": None,
                }
            ],
            False,
        )
    )

    assert restored_count == 1
    session.add.assert_not_called()
    assert existing_user.id == 999
    assert existing_user.telegram_id == 7534150980
    assert existing_user.referral_code == "newCode"
    assert existing_user.name == "Restored Name"


def test_extract_and_apply_deferred_user_subscription_restore_update(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    existing_user = SimpleNamespace(telegram_id=7534150980, current_subscription_id=None)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: existing_user),
                SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=83)),
            ]
        ),
        no_autoflush=nullcontext(),
    )

    processed_data, deferred_update = service._extract_deferred_restore_fields(
        User,
        {
            "id": 49,
            "telegram_id": 7534150980,
            "current_subscription_id": 83,
        },
    )

    assert processed_data["current_subscription_id"] is None
    assert deferred_update is not None
    assert deferred_update.phase == service.RESTORE_PHASE_POST_SUBSCRIPTIONS

    run_async(
        service._apply_deferred_restore_updates(
            session,
            [deferred_update],
            phase=service.RESTORE_PHASE_POST_SUBSCRIPTIONS,
        )
    )

    assert existing_user.current_subscription_id == 83


def test_apply_deferred_user_subscription_restore_update_skips_missing_subscription(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    existing_user = SimpleNamespace(telegram_id=7534150980, current_subscription_id=None)
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(scalar_one_or_none=lambda: existing_user),
                SimpleNamespace(scalar_one_or_none=lambda: None),
            ]
        ),
        no_autoflush=nullcontext(),
    )

    _, deferred_update = service._extract_deferred_restore_fields(
        User,
        {
            "id": 49,
            "telegram_id": 7534150980,
            "current_subscription_id": 83,
        },
    )

    assert deferred_update is not None

    run_async(
        service._apply_deferred_restore_updates(
            session,
            [deferred_update],
            phase=service.RESTORE_PHASE_POST_SUBSCRIPTIONS,
        )
    )

    assert existing_user.current_subscription_id is None


def test_recover_legacy_missing_plans_from_snapshots_and_durations(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    squad_id = str(uuid4())
    external_squad_id = str(uuid4())

    recovered_data, recovered_count = service._recover_legacy_missing_plans(
        {
            "plans": [],
            "plan_durations": [
                {"id": 1, "plan_id": 1, "days": 30},
                {"id": 2, "plan_id": 2, "days": 90},
            ],
            "transactions": [
                {
                    "id": 10,
                    "plan": {
                        "id": 1,
                        "name": "Starter",
                        "tag": "starter",
                        "type": PlanType.BOTH.value,
                        "traffic_limit": 100,
                        "device_limit": 3,
                        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                        "internal_squads": [squad_id],
                        "external_squad": external_squad_id,
                    },
                }
            ],
            "subscriptions": [
                {
                    "id": 11,
                    "plan": {
                        "id": 2,
                        "name": "Pro",
                        "tag": None,
                        "type": PlanType.TRAFFIC.value,
                        "traffic_limit": 500,
                        "device_limit": 1,
                        "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                        "internal_squads": [],
                        "external_squad": None,
                    },
                }
            ],
        }
    )

    assert recovered_count == 2
    plans = recovered_data["plans"]
    assert len(plans) == 2
    assert plans[0]["name"] == "Starter"
    assert plans[0]["internal_squads"] == [squad_id]
    assert plans[0]["external_squad"] == [external_squad_id]
    assert plans[1]["name"] == "Pro"
    assert plans[1]["availability"] == PlanAvailability.ALL.value
    assert plans[1]["archived_renew_mode"] == ArchivedPlanRenewMode.SELF_RENEW.value


def test_restore_from_json_flushes_each_table_before_children(tmp_path: Path) -> None:
    service, _config = build_backup_service(tmp_path)
    dump_path = tmp_path / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-25T12:00:00+00:00"},
                "data": {
                    "plans": [
                        {
                            "id": 1,
                            "order_index": 1,
                            "is_active": True,
                            "is_archived": False,
                            "type": PlanType.BOTH.value,
                            "availability": PlanAvailability.ALL.value,
                            "archived_renew_mode": ArchivedPlanRenewMode.SELF_RENEW.value,
                            "name": "Starter",
                            "description": None,
                            "tag": None,
                            "traffic_limit": 100,
                            "device_limit": 3,
                            "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                            "replacement_plan_ids": [],
                            "upgrade_to_plan_ids": [],
                            "allowed_user_ids": [],
                            "internal_squads": [],
                            "external_squad": None,
                        }
                    ],
                    "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
            self.flush = AsyncMock()
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.no_autoflush = nullcontext()
            self.instances: list[object] = []

        def add(self, instance: object) -> None:
            self.instances.append(instance)

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    fake_session = FakeSession()
    service.session_pool = lambda: FakeSessionContext(fake_session)  # type: ignore[assignment]

    restored, _message = run_async(service._restore_from_json(dump_path, clear_existing=False))

    assert restored is True
    assert fake_session.flush.await_count == 2
    assert fake_session.commit.await_count == 1
    assert len(fake_session.instances) == 2


def test_restore_from_json_recovers_missing_plans_before_restoring_durations(
    tmp_path: Path,
) -> None:
    service, _config = build_backup_service(tmp_path)
    dump_path = tmp_path / "database.json"
    dump_path.write_text(
        json.dumps(
            {
                "metadata": {"timestamp": "2026-03-25T12:00:00+00:00"},
                "data": {
                    "plans": [],
                    "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
                    "transactions": [
                        {
                            "id": 1,
                            "plan": {
                                "id": 1,
                                "name": "Recovered Starter",
                                "tag": "starter",
                                "type": PlanType.BOTH.value,
                                "traffic_limit": 100,
                                "device_limit": 3,
                                "traffic_limit_strategy": TrafficLimitStrategy.NO_RESET.value,
                                "internal_squads": [],
                                "external_squad": None,
                            },
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self) -> None:
            self.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
            self.flush = AsyncMock()
            self.commit = AsyncMock()
            self.rollback = AsyncMock()
            self.no_autoflush = nullcontext()
            self.instances: list[object] = []

        def add(self, instance: object) -> None:
            self.instances.append(instance)

    class FakeSessionContext:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def __aenter__(self) -> FakeSession:
            return self.session

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    fake_session = FakeSession()
    service.session_pool = lambda: FakeSessionContext(fake_session)  # type: ignore[assignment]

    restored, message = run_async(service._restore_from_json(dump_path, clear_existing=False))

    assert restored is True
    assert "Recovered plans: 1" in message
    assert len(fake_session.instances) == 3
    assert isinstance(fake_session.instances[0], Plan)
    assert isinstance(fake_session.instances[1], PlanDuration)
