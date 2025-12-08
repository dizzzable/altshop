from typing import Any, Optional

from sqlalchemy import func, select

from src.core.enums import PaymentGatewayType
from src.infrastructure.database.models.sql import PaymentGateway

from .base import BaseRepository


class PaymentGatewayRepository(BaseRepository):
    async def create(self, gateway: PaymentGateway) -> PaymentGateway:
        return await self.create_instance(gateway)

    async def get(self, gateway_id: int) -> Optional[PaymentGateway]:
        return await self._get_one(PaymentGateway, PaymentGateway.id == gateway_id)

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGateway]:
        return await self._get_one(PaymentGateway, PaymentGateway.type == gateway_type)

    async def get_all(self, sorted: bool = False) -> list[PaymentGateway]:
        if sorted:
            order_by = PaymentGateway.order_index.asc()
        else:
            order_by = PaymentGateway.id.asc()

        return await self._get_many(PaymentGateway, order_by=order_by)

    async def update(self, gateway_id: int, **data: Any) -> Optional[PaymentGateway]:
        return await self._update(PaymentGateway, PaymentGateway.id == gateway_id, **data)

    async def filter_active(self, is_active: bool) -> list[PaymentGateway]:
        return await self._get_many(
            PaymentGateway,
            PaymentGateway.is_active == is_active,
            order_by=PaymentGateway.order_index.asc(),
        )

    async def get_max_index(self) -> Optional[int]:
        return await self.session.scalar(select(func.max(PaymentGateway.order_index)))
