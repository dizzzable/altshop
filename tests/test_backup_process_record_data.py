from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from src.services.backup import BackupService


class _ColumnType:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def __str__(self) -> str:
        return self.raw


def _build_model(**column_types: str) -> object:
    columns = SimpleNamespace(
        **{
            name: SimpleNamespace(type=_ColumnType(type_name))
            for name, type_name in column_types.items()
        }
    )
    return SimpleNamespace(__table__=SimpleNamespace(columns=columns))


def test_process_record_data_converts_scalar_and_json_types() -> None:
    service = object.__new__(BackupService)
    model = _build_model(
        created_at="DATETIME",
        is_active="BOOLEAN",
        retries="INTEGER",
        score="FLOAT",
        payload="JSON",
        title="VARCHAR",
    )

    result = service._process_record_data(
        record_data={
            "created_at": "2026-03-01T12:00:00Z",
            "is_active": "true",
            "retries": "7",
            "score": "12.5",
            "payload": '{"ok": true}',
            "title": "backup-row",
        },
        model=model,
        table_name="dummy_table",
    )

    assert isinstance(result["created_at"], datetime)
    assert result["is_active"] is True
    assert result["retries"] == 7
    assert result["score"] == 12.5
    assert result["payload"] == {"ok": True}
    assert result["title"] == "backup-row"


def test_process_record_data_falls_back_for_invalid_datetime_and_skips_unknown_columns() -> None:
    service = object.__new__(BackupService)
    model = _build_model(created_at="TIMESTAMP", is_active="BOOL")

    result = service._process_record_data(
        record_data={
            "created_at": "not-a-date",
            "is_active": "no",
            "unknown_column": "value",
        },
        model=model,
        table_name="dummy_table",
    )

    assert isinstance(result["created_at"], datetime)
    assert result["is_active"] is False
    assert "unknown_column" not in result
