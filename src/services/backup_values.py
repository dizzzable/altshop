# ruff: noqa: E501

from __future__ import annotations

import json as json_lib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import ARRAY

from src.core.utils.time import datetime_now


class BackupValueMixin:
    def _model_to_dict(self, record: Any, model: Any) -> dict[str, Any]:
        record_dict: dict[str, Any] = {}

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
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, list):
            return [self._normalize_backup_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): self._normalize_backup_value(item_value)
                for key, item_value in value.items()
            }
        return value

    def _parse_datetime_value(self, key: str, value: str) -> datetime:
        try:
            if "T" in value:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError) as exception:
            logger.warning(
                f"Не удалось парсить дату {value} для поля {key}: {exception}"
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
        if ("INTEGER" in item_type_str or "INT" in item_type_str or "BIGINT" in item_type_str) and isinstance(item, str):
            return self._parse_integer_value(item)
        if ("FLOAT" in item_type_str or "REAL" in item_type_str or "NUMERIC" in item_type_str) and isinstance(item, str):
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
        record_data: dict[str, Any],
        model: Any,
        table_name: str,
    ) -> dict[str, Any]:
        processed_data: dict[str, Any] = {}

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

        for column in model.__table__.columns:
            if column.name in processed_data:
                continue
            if isinstance(column.type, ARRAY) and not column.nullable:
                processed_data[column.name] = []

        return processed_data

    def _get_primary_key_column(self, model: Any) -> Optional[str]:
        for col in model.__table__.columns:
            if col.primary_key:
                return str(col.name)
        return None
