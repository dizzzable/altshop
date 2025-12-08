from typing import Any, Awaitable, Final, Optional, Set, TypeVar, cast

from pydantic import BaseModel, TypeAdapter
from redis.asyncio import Redis
from redis.typing import ExpiryT

from src.core.config import AppConfig
from src.core.storage.key_builder import StorageKey
from src.core.utils import json_utils

T = TypeVar("T", bound=Any)

TX_QUEUE_KEY: Final[str] = "tx_queue"


class RedisRepository:
    config: AppConfig
    client: Redis

    def __init__(self, config: AppConfig, client: Redis) -> None:
        self.config = config
        self.client = client

    async def get(
        self,
        key: StorageKey,
        validator: type[T],
        default: Optional[T] = None,
    ) -> Optional[T]:
        value: Optional[Any] = await self.client.get(key.pack())
        if value is None:
            return default
        value = json_utils.decode(value)
        return TypeAdapter[T](validator).validate_python(value)

    async def set(self, key: StorageKey, value: Any, ex: Optional[ExpiryT] = None) -> None:
        if isinstance(value, BaseModel):
            value = value.model_dump(exclude_defaults=True)
        await self.client.set(name=key.pack(), value=json_utils.encode(value), ex=ex)

    async def exists(self, key: StorageKey) -> bool:
        return cast(bool, await self.client.exists(key.pack()))

    async def delete(self, key: StorageKey) -> None:
        await self.client.delete(key.pack())

    async def close(self) -> None:
        await self.client.aclose(close_connection_pool=True)

    #

    async def collection_add(self, key: StorageKey, *values: Any) -> int:
        str_values = [str(v) for v in values]
        return await cast(Awaitable[int], self.client.sadd(key.pack(), *str_values))

    async def collection_members(self, key: StorageKey) -> list[str]:
        members_bytes = await cast(Awaitable[Set[bytes]], self.client.smembers(key.pack()))
        return [member.decode() for member in members_bytes]

    async def collection_is_member(self, key: StorageKey, value: Any) -> bool:
        return await cast(Awaitable[bool], self.client.sismember(key.pack(), str(value)))

    async def collection_remove(self, key: StorageKey, *values: Any) -> int:
        str_values = [str(v) for v in values]
        return await cast(Awaitable[int], self.client.srem(key.pack(), *str_values))

    #

    async def list_push(self, key: StorageKey, *values: Any) -> int:
        str_values = [str(v) for v in values]
        return await cast(Awaitable[int], self.client.lpush(key.pack(), *str_values))

    async def list_remove(self, key: StorageKey, value: Any, count: int = 0) -> int:
        return await cast(Awaitable[int], self.client.lrem(key.pack(), count, str(value)))

    async def list_range(self, key: StorageKey, start: int, end: int) -> list[str]:
        items_bytes = await cast(Awaitable[list[bytes]], self.client.lrange(key.pack(), start, end))
        return [item.decode() for item in items_bytes]

    async def list_trim(self, key: StorageKey, start: int, end: int) -> None:
        await cast(Awaitable[str], self.client.ltrim(key.pack(), start, end))

    #

    async def sorted_collection_add(self, key: StorageKey, mapping: dict[Any, float]) -> int:
        str_mapping = {str(k): v for k, v in mapping.items()}
        return await cast(Awaitable[int], self.client.zadd(key.pack(), str_mapping))

    async def sorted_collection_revrange(self, key: StorageKey, start: int, end: int) -> list[str]:
        items_bytes = await cast(
            Awaitable[list[bytes]], self.client.zrevrange(key.pack(), start, end)
        )
        return [item.decode() for item in items_bytes]

    async def sorted_collection_remove(self, key: StorageKey, *values: Any) -> int:
        str_values = [str(v) for v in values]
        return await cast(Awaitable[int], self.client.zrem(key.pack(), *str_values))
