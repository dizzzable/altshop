from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import func, select

from src.core.enums import PartnerLevel, WithdrawalStatus
from src.infrastructure.database.models.sql import (
    Partner,
    PartnerReferral,
    PartnerTransaction,
    PartnerWithdrawal,
)

from .base import BaseRepository


class PartnerRepository(BaseRepository):
    # Partner CRUD
    async def create_partner(self, partner: Partner) -> Partner:
        return await self.create_instance(partner)

    async def get_partner_by_id(self, partner_id: int) -> Optional[Partner]:
        return await self._get_one(Partner, Partner.id == partner_id)

    async def get_partner_by_user(self, telegram_id: int) -> Optional[Partner]:
        return await self._get_one(Partner, Partner.user_telegram_id == telegram_id)

    async def get_all_partners(self) -> List[Partner]:
        return await self._get_many(Partner)

    async def get_active_partners(self) -> List[Partner]:
        return await self._get_many(Partner, Partner.is_active == True)

    async def update_partner(self, partner_id: int, **data: Any) -> Optional[Partner]:
        return await self._update(Partner, Partner.id == partner_id, **data)

    async def delete_partner(self, partner_id: int) -> bool:
        return bool(await self._delete(Partner, Partner.id == partner_id))

    async def count_partners(self) -> int:
        return await self._count(Partner)

    # Partner Transactions
    async def create_transaction(self, transaction: PartnerTransaction) -> PartnerTransaction:
        return await self.create_instance(transaction)

    async def get_transactions_by_partner(
        self,
        partner_id: int,
        limit: Optional[int] = None,
    ) -> List[PartnerTransaction]:
        query = select(PartnerTransaction).where(
            PartnerTransaction.partner_id == partner_id
        ).order_by(PartnerTransaction.created_at.desc())
        if limit:
            query = query.limit(limit)
        result = await self.session.scalars(query)
        return list(result.all())

    async def get_transactions_by_referral(self, telegram_id: int) -> List[PartnerTransaction]:
        return await self._get_many(
            PartnerTransaction,
            PartnerTransaction.referral_telegram_id == telegram_id,
        )

    async def has_partner_received_payment_from_referral(
        self,
        partner_id: int,
        referral_telegram_id: int,
    ) -> bool:
        """
        Проверить, получал ли партнер уже вознаграждение от реферала.
        Используется для стратегии ON_FIRST_PAYMENT.
        """
        query = select(func.count()).where(
            PartnerTransaction.partner_id == partner_id,
            PartnerTransaction.referral_telegram_id == referral_telegram_id,
        )
        result = await self.session.scalar(query)
        return (result or 0) > 0

    async def sum_earnings_by_partner(self, partner_id: int) -> int:
        query = select(func.sum(PartnerTransaction.earned_amount)).where(
            PartnerTransaction.partner_id == partner_id
        )
        result = await self.session.scalar(query)
        return result or 0

    async def sum_earnings_by_level(self, partner_id: int, level: PartnerLevel) -> int:
        query = select(func.sum(PartnerTransaction.earned_amount)).where(
            PartnerTransaction.partner_id == partner_id,
            PartnerTransaction.level == level,
        )
        result = await self.session.scalar(query)
        return result or 0

    # Partner Withdrawals
    async def create_withdrawal(self, withdrawal: PartnerWithdrawal) -> PartnerWithdrawal:
        return await self.create_instance(withdrawal)

    async def get_withdrawal_by_id(self, withdrawal_id: UUID) -> Optional[PartnerWithdrawal]:
        return await self._get_one(PartnerWithdrawal, PartnerWithdrawal.id == withdrawal_id)

    async def get_withdrawals_by_partner(self, partner_id: int) -> List[PartnerWithdrawal]:
        return await self._get_many(
            PartnerWithdrawal,
            PartnerWithdrawal.partner_id == partner_id,
        )

    async def get_pending_withdrawals(self) -> List[PartnerWithdrawal]:
        return await self._get_many(
            PartnerWithdrawal,
            PartnerWithdrawal.status == WithdrawalStatus.PENDING,
        )

    async def get_all_withdrawals(
        self,
        status: Optional[WithdrawalStatus] = None,
    ) -> List[PartnerWithdrawal]:
        """Получить все запросы на вывод с опциональным фильтром по статусу."""
        if status:
            return await self._get_many(
                PartnerWithdrawal,
                PartnerWithdrawal.status == status,
            )
        return await self._get_many(PartnerWithdrawal)

    async def update_withdrawal(self, withdrawal_id: UUID, **data: Any) -> Optional[PartnerWithdrawal]:
        return await self._update(
            PartnerWithdrawal,
            PartnerWithdrawal.id == withdrawal_id,
            **data,
        )

    async def sum_withdrawals_by_partner(self, partner_id: int) -> int:
        query = select(func.sum(PartnerWithdrawal.amount)).where(
            PartnerWithdrawal.partner_id == partner_id,
            PartnerWithdrawal.status == WithdrawalStatus.COMPLETED,
        )
        result = await self.session.scalar(query)
        return result or 0

    # Partner Referrals
    async def create_partner_referral(self, referral: PartnerReferral) -> PartnerReferral:
        return await self.create_instance(referral)

    async def get_referrals_by_partner(
        self,
        partner_id: int,
        level: Optional[PartnerLevel] = None,
    ) -> List[PartnerReferral]:
        conditions = [PartnerReferral.partner_id == partner_id]
        if level:
            conditions.append(PartnerReferral.level == level)
        return await self._get_many(PartnerReferral, *conditions)

    async def get_partner_referral_by_user(self, telegram_id: int) -> Optional[PartnerReferral]:
        """Получить запись о реферале по telegram_id пользователя."""
        return await self._get_one(
            PartnerReferral,
            PartnerReferral.referral_telegram_id == telegram_id,
        )

    async def count_referrals_by_partner(
        self,
        partner_id: int,
        level: Optional[PartnerLevel] = None,
    ) -> int:
        conditions = [PartnerReferral.partner_id == partner_id]
        if level:
            conditions.append(PartnerReferral.level == level)
        return await self._count(PartnerReferral, *conditions)

    async def get_partner_chain_for_user(self, telegram_id: int) -> List[PartnerReferral]:
        """
        Получить цепочку партнеров для пользователя.
        Возвращает список записей партнер-реферал, начиная с прямого партнера.
        """
        result = []
        current_user_id = telegram_id
        visited = set()

        for _ in range(3):  # Максимум 3 уровня
            if current_user_id in visited:
                break
            visited.add(current_user_id)

            referral = await self.get_partner_referral_by_user(current_user_id)
            if not referral:
                break

            result.append(referral)

            # Следующий в цепочке - партнер текущего уровня
            partner = await self.get_partner_by_id(referral.partner_id)
            if not partner:
                break
            current_user_id = partner.user_telegram_id

        return result