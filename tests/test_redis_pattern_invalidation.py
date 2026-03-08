from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.infrastructure.redis import RedisRepository
from src.services.user import UserService
from src.services.webhook import WebhookService


def test_redis_repository_delete_pattern_uses_scan_batches() -> None:
    async def scan_iter(*, match: str, count: int):  # type: ignore[no-untyped-def]
        assert match == "cache:get_user:*"
        assert count == 2
        for key in (b"cache:get_user:1", b"cache:get_user:2", b"cache:get_user:3"):
            yield key

    client = SimpleNamespace(
        scan_iter=scan_iter,
        delete=AsyncMock(side_effect=[2, 1]),
    )
    repository = RedisRepository(config=SimpleNamespace(), client=client)

    deleted = asyncio.run(repository.delete_pattern("cache:get_user:*", count=2))

    assert deleted == 3
    assert client.delete.await_count == 2


def test_user_rules_reset_invalidates_cache_via_delete_pattern() -> None:
    repository = SimpleNamespace(
        users=SimpleNamespace(
            set_rules_accepted_for_non_privileged=AsyncMock(return_value=4),
        )
    )
    service = UserService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(delete=AsyncMock()),
        redis_repository=SimpleNamespace(delete_pattern=AsyncMock(return_value=7)),
        translator_hub=SimpleNamespace(),
        uow=SimpleNamespace(repository=repository, commit=AsyncMock()),
    )
    service._clear_list_caches = AsyncMock()  # type: ignore[method-assign]

    updated = asyncio.run(service.reset_rules_acceptance_for_non_privileged(True))

    assert updated == 4
    service.redis_repository.delete_pattern.assert_awaited_once_with("cache:get_user:*")


def test_webhook_clear_uses_delete_pattern() -> None:
    service = WebhookService(
        config=SimpleNamespace(bot=SimpleNamespace(reset_webhook=True)),
        bot=SimpleNamespace(id=88),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(delete_pattern=AsyncMock(return_value=2)),
        translator_hub=SimpleNamespace(),
    )

    asyncio.run(service._clear(bot_id=88))

    service.redis_repository.delete_pattern.assert_awaited_once_with("webhook_lock:88:*")
