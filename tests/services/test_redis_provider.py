from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.infrastructure.di.providers import redis as redis_provider_module


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_provider_await_redis_ping_accepts_non_awaitable_response() -> None:
    redis_client = SimpleNamespace(ping=lambda: True)

    result = run_async(redis_provider_module._await_redis_ping(redis_client))

    assert result is True


def test_provider_await_redis_ping_accepts_awaitable_response() -> None:
    redis_client = SimpleNamespace(ping=AsyncMock(return_value=True))

    result = run_async(redis_provider_module._await_redis_ping(redis_client))

    assert result is True
