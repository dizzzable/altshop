from typing import Any, Optional
from uuid import UUID

from src.infrastructure.database.models.sql import Subscription

from .base import BaseRepository


class SubscriptionRepository(BaseRepository):
    async def create(self, subscription: Subscription) -> Subscription:
        return await self.create_instance(subscription)

    async def get(self, subscription_id: int) -> Optional[Subscription]:
        return await self._get_one(Subscription, Subscription.id == subscription_id)

    async def get_by_remna_id(self, user_remna_id: UUID) -> Optional[Subscription]:
        """Get subscription by Remnawave user UUID."""
        return await self._get_one(Subscription, Subscription.user_remna_id == user_remna_id)

    async def get_all_by_user(self, telegram_id: int) -> list[Subscription]:
        """Get all subscriptions for a user, sorted by ID (oldest first)."""
        return await self._get_many(
            Subscription,
            Subscription.user_telegram_id == telegram_id,
            order_by=Subscription.id,
        )

    async def get_all(self) -> list[Subscription]:
        return await self._get_many(Subscription)

    async def update(self, subscription_id: int, **data: Any) -> Optional[Subscription]:
        return await self._update(Subscription, Subscription.id == subscription_id, **data)

    async def filter_by_plan_id(self, plan_id: int) -> list[Subscription]:
        return await self._get_many(Subscription, Subscription.plan["id"].as_integer() == plan_id)
