from decimal import Decimal
from typing import Any, Dict, List, Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import (
    Currency,
    PartnerAccrualStrategy,
    PartnerLevel,
    PaymentGatewayType,
    WithdrawalStatus,
)
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    PartnerDto,
    PartnerIndividualSettingsDto,
    PartnerReferralDto,
    PartnerSettingsDto,
    PartnerTransactionDto,
    PartnerWithdrawalDto,
    UserDto,
)
from src.infrastructure.redis import RedisRepository
from src.services.settings import SettingsService
from src.services.user import UserService

from . import partner_earnings, partner_referrals, partner_withdrawals
from .base import BaseService
from .notification import NotificationService
from .partner_balance_ops import calculate_partner_earning as _calculate_partner_earning_impl
from .partner_balance_ops import (
    credit_balance_for_failed_subscription_purchase as _credit_failed_purchase_impl,
)
from .partner_balance_ops import debit_balance_for_subscription_purchase as _debit_purchase_impl
from .partner_balance_ops import format_rub as _format_rub_impl
from .partner_balance_ops import notify_partner_earning as _notify_partner_earning_impl
from .partner_balance_ops import process_partner_earning as _process_partner_earning_impl
from .partner_balance_ops import (
    process_partner_referral_earning as _process_partner_referral_earning_impl,
)
from .partner_balance_ops import resolve_accrual_strategy as _resolve_accrual_strategy_impl
from .partner_balance_ops import resolve_payer_name as _resolve_payer_name_impl
from .partner_balance_ops import should_skip_partner_earning as _should_skip_partner_earning_impl
from .partner_core import adjust_partner_balance as _adjust_partner_balance_impl
from .partner_core import create_partner as _create_partner_impl
from .partner_core import deactivate_partner as _deactivate_partner_impl
from .partner_core import get_all_partners as _get_all_partners_impl
from .partner_core import get_partner as _get_partner_impl
from .partner_core import get_partner_by_user as _get_partner_by_user_impl
from .partner_core import has_partner_attribution as _has_partner_attribution_impl
from .partner_core import is_partner as _is_partner_impl
from .partner_core import toggle_partner_status as _toggle_partner_status_impl
from .partner_core import (
    update_partner_individual_settings as _update_partner_individual_settings_impl,
)


class PartnerService(BaseService):
    """Service for partner program management."""

    uow: UnitOfWork
    user_service: UserService
    settings_service: SettingsService
    notification_service: NotificationService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        uow: UnitOfWork,
        user_service: UserService,
        settings_service: SettingsService,
        notification_service: NotificationService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.user_service = user_service
        self.settings_service = settings_service
        self.notification_service = notification_service

    async def create_partner(self, user: UserDto) -> PartnerDto:
        return await _create_partner_impl(self, user)

    async def get_partner(self, partner_id: int) -> Optional[PartnerDto]:
        return await _get_partner_impl(self, partner_id)

    async def get_partner_by_user(self, telegram_id: int) -> Optional[PartnerDto]:
        return await _get_partner_by_user_impl(self, telegram_id)

    async def has_partner_attribution(self, telegram_id: int) -> bool:
        return await _has_partner_attribution_impl(self, telegram_id)

    async def is_partner(self, telegram_id: int) -> bool:
        return await _is_partner_impl(self, telegram_id)

    async def debit_balance_for_subscription_purchase(
        self,
        *,
        user_telegram_id: int,
        amount_kopecks: int,
    ) -> bool:
        return await _debit_purchase_impl(
            self,
            user_telegram_id=user_telegram_id,
            amount_kopecks=amount_kopecks,
        )

    async def credit_balance_for_failed_subscription_purchase(
        self,
        *,
        user_telegram_id: int,
        amount_kopecks: int,
    ) -> bool:
        return await _credit_failed_purchase_impl(
            self,
            user_telegram_id=user_telegram_id,
            amount_kopecks=amount_kopecks,
        )

    async def get_all_partners(self) -> List[PartnerDto]:
        return await _get_all_partners_impl(self)

    async def toggle_partner_status(self, partner_id: int) -> Optional[PartnerDto]:
        return await _toggle_partner_status_impl(self, partner_id)

    async def deactivate_partner(self, partner_id: int) -> Optional[PartnerDto]:
        return await _deactivate_partner_impl(self, partner_id)

    async def update_partner_individual_settings(
        self,
        partner_id: int,
        settings: PartnerIndividualSettingsDto,
    ) -> Optional[PartnerDto]:
        return await _update_partner_individual_settings_impl(self, partner_id, settings)

    async def adjust_partner_balance(
        self,
        partner_id: int,
        amount: int,
        admin_telegram_id: int,
        reason: Optional[str] = None,
    ) -> Optional[PartnerDto]:
        return await _adjust_partner_balance_impl(
            self,
            partner_id,
            amount,
            admin_telegram_id,
            reason,
        )

    async def add_partner_referral(
        self,
        partner: PartnerDto,
        referral_telegram_id: int,
        level: PartnerLevel = PartnerLevel.LEVEL_1,
        parent_partner_id: Optional[int] = None,
    ) -> PartnerReferralDto:
        return await partner_referrals.add_partner_referral(
            self,
            partner=partner,
            referral_telegram_id=referral_telegram_id,
            level=level,
            parent_partner_id=parent_partner_id,
        )

    async def attach_partner_referral_chain(self, *, user: UserDto, referrer: UserDto) -> bool:
        return await partner_referrals.attach_partner_referral_chain(
            self,
            user=user,
            referrer=referrer,
        )

    async def handle_new_user_referral(self, user: UserDto, referrer_code: str) -> None:
        return await partner_referrals.handle_new_user_referral(
            self,
            user=user,
            referrer_code=referrer_code,
        )

    async def get_partner_referrals(
        self,
        partner_id: int,
        level: Optional[PartnerLevel] = None,
    ) -> List[PartnerReferralDto]:
        return await partner_referrals.get_partner_referrals(
            self,
            partner_id=partner_id,
            level=level,
        )

    async def get_partner_referral_transaction_stats(
        self,
        *,
        partner_id: int,
        referral_telegram_ids: List[int],
    ) -> dict[int, dict[str, Any]]:
        return await partner_referrals.get_partner_referral_transaction_stats(
            self,
            partner_id=partner_id,
            referral_telegram_ids=referral_telegram_ids,
        )

    async def get_referral_invite_sources(
        self,
        *,
        referral_telegram_ids: List[int],
    ) -> dict[int, str]:
        return await partner_referrals.get_referral_invite_sources(
            self,
            referral_telegram_ids=referral_telegram_ids,
        )

    def _format_rub(self, value_kopecks: int) -> str:
        return _format_rub_impl(self, value_kopecks)

    async def _resolve_payer_name(self, payer_user_id: int) -> str:
        return await _resolve_payer_name_impl(self, payer_user_id)

    def _resolve_accrual_strategy(self, partner: PartnerDto) -> PartnerAccrualStrategy:
        return _resolve_accrual_strategy_impl(self, partner)

    async def _should_skip_partner_earning(
        self,
        *,
        partner: PartnerDto,
        payer_user_id: int,
    ) -> bool:
        return await _should_skip_partner_earning_impl(
            self,
            partner=partner,
            payer_user_id=payer_user_id,
        )

    async def _notify_partner_earning(
        self,
        *,
        partner: PartnerDto,
        payer_name: str,
        level: PartnerLevel,
        earning: int,
    ) -> None:
        return await _notify_partner_earning_impl(
            self,
            partner=partner,
            payer_name=payer_name,
            level=level,
            earning=earning,
        )

    async def _process_partner_referral_earning(
        self,
        *,
        referral: Any,
        payer_user_id: int,
        payer_name: str,
        payment_amount_kopecks: int,
        partner_settings: PartnerSettingsDto,
        gateway_commission: Decimal,
        gateway_name: str,
        source_transaction_id: Optional[int] = None,
    ) -> None:
        return await _process_partner_referral_earning_impl(
            self,
            referral=referral,
            payer_user_id=payer_user_id,
            payer_name=payer_name,
            payment_amount_kopecks=payment_amount_kopecks,
            partner_settings=partner_settings,
            gateway_commission=gateway_commission,
            gateway_name=gateway_name,
            source_transaction_id=source_transaction_id,
        )

    async def process_partner_earning(
        self,
        payer_user_id: int,
        payment_amount: Decimal,
        gateway_type: Optional[PaymentGatewayType] = None,
        source_transaction_id: Optional[int] = None,
    ) -> None:
        return await _process_partner_earning_impl(
            self,
            payer_user_id,
            payment_amount,
            gateway_type,
            source_transaction_id,
        )

    async def _calculate_partner_earning(
        self,
        partner: PartnerDto,
        partner_settings: PartnerSettingsDto,
        payment_amount: int,
        level: PartnerLevel,
        gateway_commission: Decimal,
    ) -> tuple[int, Decimal]:
        return await _calculate_partner_earning_impl(
            self,
            partner,
            partner_settings,
            payment_amount,
            level,
            gateway_commission,
        )

    async def create_partner_transaction(
        self,
        partner: PartnerDto,
        referral_telegram_id: int,
        level: PartnerLevel,
        payment_amount: int,
        percent: Decimal,
        earned_amount: int,
        source_transaction_id: Optional[int] = None,
        description: Optional[str] = None,
    ) -> PartnerTransactionDto:
        return await partner_earnings.create_partner_transaction(
            self,
            partner=partner,
            referral_telegram_id=referral_telegram_id,
            level=level,
            payment_amount=payment_amount,
            percent=percent,
            earned_amount=earned_amount,
            source_transaction_id=source_transaction_id,
            description=description,
        )

    async def get_partner_transactions(
        self,
        partner_id: int,
        limit: Optional[int] = None,
    ) -> List[PartnerTransactionDto]:
        return await partner_earnings.get_partner_transactions(
            self,
            partner_id=partner_id,
            limit=limit,
        )

    async def get_partner_statistics(self, partner: Optional[PartnerDto] = None) -> Dict[str, Any]:
        return await partner_earnings.get_partner_statistics(self, partner=partner)

    async def request_withdrawal(
        self,
        partner: PartnerDto,
        amount: int,
        method: str,
        requisites: str,
        settings: PartnerSettingsDto,
    ) -> Optional[PartnerWithdrawalDto]:
        return await partner_withdrawals.request_withdrawal(
            self,
            partner=partner,
            amount=amount,
            method=method,
            requisites=requisites,
            settings=settings,
        )

    async def get_withdrawal(self, withdrawal_id: int) -> Optional[PartnerWithdrawalDto]:
        return await partner_withdrawals.get_withdrawal(self, withdrawal_id)

    async def get_all_withdrawals(
        self,
        status: Optional[WithdrawalStatus] = None,
    ) -> List[PartnerWithdrawalDto]:
        return await partner_withdrawals.get_all_withdrawals(self, status=status)

    async def approve_withdrawal(
        self,
        withdrawal_id: int,
        admin_telegram_id: int,
        comment: Optional[str] = None,
    ) -> bool:
        return await partner_withdrawals.approve_withdrawal(
            self,
            withdrawal_id=withdrawal_id,
            admin_telegram_id=admin_telegram_id,
            comment=comment,
        )

    async def reject_withdrawal(
        self,
        withdrawal_id: int,
        admin_telegram_id: int,
        reason: Optional[str] = None,
    ) -> bool:
        return await partner_withdrawals.reject_withdrawal(
            self,
            withdrawal_id=withdrawal_id,
            admin_telegram_id=admin_telegram_id,
            reason=reason,
        )

    async def get_pending_withdrawals(self) -> List[PartnerWithdrawalDto]:
        return await partner_withdrawals.get_pending_withdrawals(self)

    async def get_partner_withdrawals(self, partner_id: int) -> List[PartnerWithdrawalDto]:
        return await partner_withdrawals.get_partner_withdrawals(self, partner_id)

    async def create_withdrawal_request(
        self,
        partner_id: int,
        amount: Decimal,
        method: str = "",
        requisites: str = "",
        requested_amount: Decimal | None = None,
        requested_currency: Currency | None = None,
        quote_rate: Decimal | None = None,
        quote_source: str | None = None,
    ) -> Optional[PartnerWithdrawalDto]:
        return await partner_withdrawals.create_withdrawal_request(
            self,
            partner_id=partner_id,
            amount=amount,
            method=method,
            requisites=requisites,
            requested_amount=requested_amount,
            requested_currency=requested_currency,
            quote_rate=quote_rate,
            quote_source=quote_source,
        )
