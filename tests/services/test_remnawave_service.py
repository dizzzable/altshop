from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pydantic import ValidationError

from src.services.remnawave import RemnawaveService


def run_async(coroutine):
    return asyncio.run(coroutine)


def _build_validation_error() -> ValidationError:
    return ValidationError.from_exception_data(
        "GetStatsResponseDto",
        [
            {
                "type": "missing",
                "loc": ("cpu", "physicalCores"),
                "input": {"cores": 1},
            }
        ],
    )


def test_try_connection_falls_back_to_raw_health_check_on_validation_error() -> None:
    remnawave = SimpleNamespace(
        system=SimpleNamespace(
            get_stats=AsyncMock(side_effect=_build_validation_error())
        )
    )
    service = RemnawaveService(
        config=MagicMock(),
        bot=MagicMock(),
        redis_client=MagicMock(),
        redis_repository=MagicMock(),
        translator_hub=MagicMock(),
        remnawave=remnawave,
        user_service=MagicMock(),
        subscription_service=MagicMock(),
        plan_service=MagicMock(),
        settings_service=MagicMock(),
    )
    service._try_connection_raw = AsyncMock()  # type: ignore[method-assign]

    run_async(service.try_connection())

    service._try_connection_raw.assert_awaited_once()
