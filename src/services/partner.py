from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import (
    Currency,
    PartnerAccrualStrategy,
    PartnerLevel,
    PartnerRewardType,
    PaymentGatewayType,
    UserNotificationType,
    WithdrawalStatus,
)
from src.core.utils.message_payload import MessagePayload
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
from src.infrastructure.database.models.sql import (
    Partner,
    PartnerReferral,
    PartnerTransaction,
    PartnerWithdrawal,
)
from src.infrastructure.redis import RedisRepository
from src.services.settings import SettingsService
from src.services.user import UserService

from .base import BaseService
from .notification import NotificationService


class PartnerService(BaseService):
    """Сервис для работы с партнерской программой."""

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

    # ==================
    # PARTNER CRUD
    # ==================

    async def create_partner(self, user: UserDto) -> PartnerDto:
        """Создать партнера для пользователя."""
        existing = await self.get_partner_by_user(user.telegram_id)
        if existing:
            logger.warning(f"Partner for user '{user.telegram_id}' already exists")
            return existing

        partner = await self.uow.repository.partners.create_partner(
            Partner(
                user_telegram_id=user.telegram_id,
                balance=0,
                total_earned=0,
                total_withdrawn=0,
                referrals_count=0,
                level2_referrals_count=0,
                level3_referrals_count=0,
                is_active=True,
            )
        )

        logger.info(f"Partner created for user '{user.telegram_id}'")
        return PartnerDto.from_model(partner)  # type: ignore[return-value]

    async def get_partner(self, partner_id: int) -> Optional[PartnerDto]:
        """Получить партнера по ID."""
        partner = await self.uow.repository.partners.get_partner_by_id(partner_id)
        return PartnerDto.from_model(partner) if partner else None

    async def get_partner_by_user(self, telegram_id: int) -> Optional[PartnerDto]:
        """Получить партнера по telegram_id пользователя."""
        partner = await self.uow.repository.partners.get_partner_by_user(telegram_id)
        return PartnerDto.from_model(partner) if partner else None

    async def has_partner_attribution(self, telegram_id: int) -> bool:
        """Check whether a user is already attributed to a partner."""
        referral = await self.uow.repository.partners.get_partner_referral_by_user(telegram_id)
        return referral is not None

    async def is_partner(self, telegram_id: int) -> bool:
        """Проверить, является ли пользователь партнером."""
        partner = await self.get_partner_by_user(telegram_id)
        return partner is not None and partner.is_active

    async def debit_balance_for_subscription_purchase(
        self,
        *,
        user_telegram_id: int,
        amount_kopecks: int,
    ) -> bool:
        """Atomically debit partner balance for an internal subscription purchase."""
        if amount_kopecks <= 0:
            logger.warning(
                f"Invalid partner balance debit amount '{amount_kopecks}' "
                f"for user '{user_telegram_id}'"
            )
            return False

        partner = await self.get_partner_by_user(user_telegram_id)
        if not partner or not partner.id:
            logger.warning(f"Partner for user '{user_telegram_id}' not found for balance debit")
            return False
        if not partner.is_active:
            logger.warning(
                f"Partner '{partner.id}' for user '{user_telegram_id}' is inactive, "
                "partner balance debit is not allowed"
            )
            return False

        success = await self.uow.repository.partners.deduct_partner_balance_if_possible(
            partner_id=partner.id,
            amount=amount_kopecks,
        )
        if success:
            logger.info(
                f"Debited '{amount_kopecks}' kopecks from partner '{partner.id}' "
                f"for user '{user_telegram_id}' subscription purchase"
            )
        else:
            logger.warning(
                f"Failed to debit '{amount_kopecks}' kopecks from partner '{partner.id}' "
                f"(insufficient balance or race condition)"
            )

        return success

    async def credit_balance_for_failed_subscription_purchase(
        self,
        *,
        user_telegram_id: int,
        amount_kopecks: int,
    ) -> bool:
        """Restore partner balance when internal purchase flow fails after debit."""
        if amount_kopecks <= 0:
            return False

        partner = await self.get_partner_by_user(user_telegram_id)
        if not partner or not partner.id:
            logger.warning(f"Partner for user '{user_telegram_id}' not found for balance restore")
            return False

        success = await self.uow.repository.partners.add_partner_balance(
            partner_id=partner.id,
            amount=amount_kopecks,
        )
        if success:
            logger.info(
                f"Restored '{amount_kopecks}' kopecks to partner '{partner.id}' "
                f"for user '{user_telegram_id}' after failed subscription purchase"
            )
        else:
            logger.warning(
                f"Failed to restore '{amount_kopecks}' kopecks to partner '{partner.id}' "
                f"for user '{user_telegram_id}'"
            )

        return success

    async def get_all_partners(self) -> List[PartnerDto]:
        """Получить всех партнеров."""
        partners = await self.uow.repository.partners.get_all_partners()
        return PartnerDto.from_model_list(partners)

    async def toggle_partner_status(self, partner_id: int) -> Optional[PartnerDto]:
        """Переключить статус активности партнера."""
        partner = await self.get_partner(partner_id)
        if not partner:
            return None

        updated = await self.uow.repository.partners.update_partner(
            partner_id,
            is_active=not partner.is_active,
        )
        logger.info(f"Partner '{partner_id}' status changed to {not partner.is_active}")
        return PartnerDto.from_model(updated) if updated else None

    async def deactivate_partner(self, partner_id: int) -> Optional[PartnerDto]:
        """Деактивировать партнера."""
        updated = await self.uow.repository.partners.update_partner(
            partner_id,
            is_active=False,
        )
        logger.info(f"Partner '{partner_id}' deactivated")
        return PartnerDto.from_model(updated) if updated else None

    async def update_partner_individual_settings(
        self,
        partner_id: int,
        settings: PartnerIndividualSettingsDto,
    ) -> Optional[PartnerDto]:
        """
        Обновить индивидуальные настройки партнера.

        Args:
            partner_id: ID партнера
            settings: Новые индивидуальные настройки

        Returns:
            Обновленный партнер или None
        """
        partner = await self.get_partner(partner_id)
        if not partner:
            logger.warning(f"Partner '{partner_id}' not found for settings update")
            return None

        # Конвертируем DTO в словарь для сохранения в JSON
        settings_dict = {
            "use_global_settings": settings.use_global_settings,
            "accrual_strategy": settings.accrual_strategy.value,
            "reward_type": settings.reward_type.value,
            "level1_percent": str(settings.level1_percent)
            if settings.level1_percent is not None
            else None,
            "level2_percent": str(settings.level2_percent)
            if settings.level2_percent is not None
            else None,
            "level3_percent": str(settings.level3_percent)
            if settings.level3_percent is not None
            else None,
            "level1_fixed_amount": settings.level1_fixed_amount,
            "level2_fixed_amount": settings.level2_fixed_amount,
            "level3_fixed_amount": settings.level3_fixed_amount,
        }

        updated = await self.uow.repository.partners.update_partner(
            partner_id,
            individual_settings=settings_dict,
        )

        if updated:
            logger.info(
                f"Partner '{partner_id}' individual settings updated: "
                f"use_global={settings.use_global_settings}, "
                f"strategy={settings.accrual_strategy.value}, "
                f"type={settings.reward_type.value}"
            )
            return PartnerDto.from_model(updated)

        return None

    async def adjust_partner_balance(
        self,
        partner_id: int,
        amount: int,
        admin_telegram_id: int,
        reason: Optional[str] = None,
    ) -> Optional[PartnerDto]:
        """
        Изменить баланс партнера (добавить или вычесть средства).

        Args:
            partner_id: ID партнера
            amount: Сумма изменения в копейках (положительное - добавить, отрицательное - вычесть)
            admin_telegram_id: ID администратора, выполняющего операцию
            reason: Причина изменения баланса

        Returns:
            Обновленный партнер или None если операция не удалась
        """
        partner = await self.get_partner(partner_id)
        if not partner:
            logger.warning(f"Partner '{partner_id}' not found for balance adjustment")
            return None

        new_balance = partner.balance + amount

        if new_balance < 0:
            logger.warning(
                f"Cannot adjust partner '{partner_id}' balance by {amount}: "
                f"resulting balance {new_balance} would be negative"
            )
            return None

        # Обновляем баланс
        updated = await self.uow.repository.partners.update_partner(
            partner_id,
            balance=new_balance,
        )

        if updated:
            operation = "added" if amount > 0 else "subtracted"
            logger.info(
                f"Admin '{admin_telegram_id}' {operation} {abs(amount)} kopecks "
                f"to partner '{partner_id}' balance. "
                f"New balance: {new_balance}. Reason: {reason or 'Not specified'}"
            )
            return PartnerDto.from_model(updated)

        return None

    # ==================
    # REFERRAL MANAGEMENT
    # ==================

    async def add_partner_referral(
        self,
        partner: PartnerDto,
        referral_telegram_id: int,
        level: PartnerLevel = PartnerLevel.LEVEL_1,
        parent_partner_id: Optional[int] = None,
    ) -> PartnerReferralDto:
        """Добавить реферала к партнеру."""
        assert partner.id is not None, "Partner ID is required for referral creation"
        existing_referral = await self.uow.repository.partners.get_partner_referral(
            partner_id=partner.id,
            referral_telegram_id=referral_telegram_id,
            level=level,
        )
        if existing_referral:
            logger.info(
                "Partner referral already exists: partner '{}' -> referral '{}' (level {})",
                partner.id,
                referral_telegram_id,
                level,
            )
            return PartnerReferralDto.from_model(existing_referral)  # type: ignore[return-value]
        referral = await self.uow.repository.partners.create_partner_referral(
            PartnerReferral(
                partner_id=partner.id,
                referral_telegram_id=referral_telegram_id,
                level=level,
                parent_partner_id=parent_partner_id,
            )
        )

        # Обновить счетчики
        update_data = {}
        if level == PartnerLevel.LEVEL_1:
            update_data["referrals_count"] = partner.referrals_count + 1
        elif level == PartnerLevel.LEVEL_2:
            update_data["level2_referrals_count"] = partner.level2_referrals_count + 1
        elif level == PartnerLevel.LEVEL_3:
            update_data["level3_referrals_count"] = partner.level3_referrals_count + 1

        if update_data:
            assert partner.id is not None, "Partner ID is required for update"
            await self.uow.repository.partners.update_partner(partner.id, **update_data)

        logger.info(
            f"Partner referral added: partner '{partner.id}' -> "
            f"referral '{referral_telegram_id}' (level {level})"
        )
        return PartnerReferralDto.from_model(referral)  # type: ignore[return-value]

    async def attach_partner_referral_chain(self, *, user: UserDto, referrer: UserDto) -> bool:
        referrer_partner = await self.get_partner_by_user(referrer.telegram_id)
        if not referrer_partner or not referrer_partner.is_active:
            logger.debug(f"Referrer '{referrer.telegram_id}' is not an active partner")
            return False

        await self.add_partner_referral(
            partner=referrer_partner,
            referral_telegram_id=user.telegram_id,
            level=PartnerLevel.LEVEL_1,
        )

        referrer_referral = await self.uow.repository.partners.get_partner_referral_by_user(
            referrer.telegram_id
        )
        if referrer_referral:
            level2_partner = await self.get_partner(referrer_referral.partner_id)
            if level2_partner and level2_partner.is_active:
                await self.add_partner_referral(
                    partner=level2_partner,
                    referral_telegram_id=user.telegram_id,
                    level=PartnerLevel.LEVEL_2,
                    parent_partner_id=referrer_partner.id,
                )

                level2_user = await self.user_service.get(
                    telegram_id=level2_partner.user_telegram_id
                )
                if level2_user:
                    level2_user_referral = (
                        await self.uow.repository.partners.get_partner_referral_by_user(
                            level2_user.telegram_id
                        )
                    )
                    if level2_user_referral:
                        level3_partner = await self.get_partner(level2_user_referral.partner_id)
                        if level3_partner and level3_partner.is_active:
                            await self.add_partner_referral(
                                partner=level3_partner,
                                referral_telegram_id=user.telegram_id,
                                level=PartnerLevel.LEVEL_3,
                                parent_partner_id=level2_partner.id,
                            )

        return True

    async def handle_new_user_referral(self, user: UserDto, referrer_code: str) -> None:
        """
        Обработать регистрацию нового пользователя по реферальной ссылке.
        Создает связи партнер-реферал на всех уровнях.
        """
        # Получаем партнера по реферальному коду
        referrer = await self.user_service.get_by_referral_code(referrer_code)
        if not referrer:
            logger.warning(f"Referrer with code '{referrer_code}' not found")
            return
        attached = await self.attach_partner_referral_chain(user=user, referrer=referrer)
        if not attached:
            return
        logger.info(
            f"User '{user.telegram_id}' registered via partner referral "
            f"from '{referrer.telegram_id}'"
        )
        try:
            await self.notification_service.notify_user(
                user=referrer,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-partner-referral-registered",
                    i18n_kwargs={"name": user.name or str(user.telegram_id)},
                ),
                ntf_type=UserNotificationType.PARTNER_REFERRAL_REGISTERED,
            )
        except Exception as exception:
            logger.warning(
                f"Failed to send partner referral registration notification "
                f"to '{referrer.telegram_id}': {exception}"
            )

    async def get_partner_referrals(
        self,
        partner_id: int,
        level: Optional[PartnerLevel] = None,
    ) -> List[PartnerReferralDto]:
        """Получить рефералов партнера."""
        referrals = await self.uow.repository.partners.get_referrals_by_partner(
            partner_id,
            level,
        )
        return PartnerReferralDto.from_model_list(referrals)

    async def get_partner_referral_transaction_stats(
        self,
        *,
        partner_id: int,
        referral_telegram_ids: List[int],
    ) -> dict[int, dict[str, Any]]:
        """Aggregate partner earnings and payments per referred user."""
        return await self.uow.repository.partners.get_partner_referral_transaction_stats(
            partner_id=partner_id,
            referral_telegram_ids=referral_telegram_ids,
        )

    async def get_referral_invite_sources(
        self,
        *,
        referral_telegram_ids: List[int],
    ) -> dict[int, str]:
        """Return invite source (BOT/WEB/UNKNOWN) for referred users."""
        return await self.uow.repository.referrals.get_invite_sources_by_referred_ids(
            referral_telegram_ids
        )

    # ==================
    # EARNINGS & TRANSACTIONS
    # ==================

    def _format_rub(self, value_kopecks: int) -> str:
        amount_rub = (Decimal(value_kopecks) / Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return f"{amount_rub} RUB"

    async def _resolve_payer_name(self, payer_user_id: int) -> str:
        payer_user = await self.user_service.get(payer_user_id)
        payer_name = (payer_user.name or payer_user.username) if payer_user else None
        return payer_name or str(payer_user_id)

    def _resolve_accrual_strategy(self, partner: PartnerDto) -> PartnerAccrualStrategy:
        ind_settings = partner.individual_settings
        if ind_settings.use_global_settings:
            return PartnerAccrualStrategy.ON_EACH_PAYMENT
        return ind_settings.accrual_strategy

    async def _should_skip_partner_earning(
        self,
        *,
        partner: PartnerDto,
        payer_user_id: int,
    ) -> bool:
        if self._resolve_accrual_strategy(partner) != PartnerAccrualStrategy.ON_FIRST_PAYMENT:
            return False

        assert partner.id is not None, "Partner ID is required"
        already_received = (
            await self.uow.repository.partners.has_partner_received_payment_from_referral(
                partner_id=partner.id,
                referral_telegram_id=payer_user_id,
            )
        )
        if not already_received:
            return False

        logger.debug(
            f"Partner '{partner.id}' already received payment from referral "
            f"'{payer_user_id}', skipping (ON_FIRST_PAYMENT strategy)"
        )
        return True

    async def _notify_partner_earning(
        self,
        *,
        partner: PartnerDto,
        payer_name: str,
        level: PartnerLevel,
        earning: int,
    ) -> None:
        try:
            partner_user = await self.user_service.get(telegram_id=partner.user_telegram_id)
            if not partner_user:
                return

            await self.notification_service.notify_user(
                user=partner_user,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-partner-earning",
                    i18n_kwargs={
                        "referral_name": payer_name,
                        "level": level.value,
                        "amount": self._format_rub(earning),
                        "new_balance": self._format_rub(partner.balance),
                    },
                ),
                ntf_type=UserNotificationType.PARTNER_EARNING,
            )
        except Exception as exception:
            logger.warning(
                f"Failed to send partner earning notification to '{partner.user_telegram_id}': "
                f"{exception}"
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
        partner = await self.get_partner(referral.partner_id)
        if not partner or not partner.is_active:
            return
        assert partner.id is not None, "Partner ID is required"

        level = PartnerLevel(referral.level)
        if await self._should_skip_partner_earning(partner=partner, payer_user_id=payer_user_id):
            return

        earning, percent_used = await self._calculate_partner_earning(
            partner=partner,
            partner_settings=partner_settings,
            payment_amount=payment_amount_kopecks,
            level=level,
            gateway_commission=gateway_commission,
        )
        if earning <= 0:
            logger.debug(f"Zero earning for partner '{partner.id}' at level {level}")
            return

        if source_transaction_id is not None:
            existing_transaction = (
                await self.uow.repository.partners.get_transaction_by_partner_and_source(
                    partner_id=partner.id,
                    source_transaction_id=source_transaction_id,
                )
            )
            if existing_transaction:
                logger.info(
                    "Partner earning already exists for partner '{}' and source transaction '{}'",
                    partner.id,
                    source_transaction_id,
                )
                return

        await self.create_partner_transaction(
            partner=partner,
            referral_telegram_id=payer_user_id,
            level=level,
            payment_amount=payment_amount_kopecks,
            percent=percent_used,
            earned_amount=earning,
            source_transaction_id=source_transaction_id,
            description=(
                "Earnings from referral payment via "
                f"{gateway_name} "
                f"(level {level.value})"
            ),
        )
        logger.info(
            f"Partner '{partner.id}' earned {earning} kopecks from "
            f"user '{payer_user_id}' payment via {gateway_name} "
            f"(level {level}, gateway_commission={gateway_commission}%)"
        )

        partner.balance += earning
        partner.total_earned += earning
        await self._notify_partner_earning(
            partner=partner,
            payer_name=payer_name,
            level=level,
            earning=earning,
        )

    async def process_partner_earning(
        self,
        payer_user_id: int,
        payment_amount: Decimal,
        gateway_type: Optional[PaymentGatewayType] = None,
        source_transaction_id: Optional[int] = None,
    ) -> None:
        """
        Обработать начисление партнерского вознаграждения при оплате.
        Вызывается после успешной оплаты.

        Args:
            payer_user_id: telegram_id пользователя, который совершил оплату
            payment_amount: Сумма оплаты (в валюте транзакции, например рублях)
            gateway_type: Тип платёжной системы для учёта комиссии
        """
        # Получаем настройки партнерской программы
        settings = await self.settings_service.get()
        partner_settings = settings.partner

        if not partner_settings.enabled:
            logger.debug("Partner program is disabled, skipping earning")
            return

        # Получаем цепочку партнеров для пользователя
        partner_chain = await self.uow.repository.partners.get_partner_chain_for_user(payer_user_id)

        if not partner_chain:
            logger.debug(f"No partner chain for user '{payer_user_id}'")
            return

        payer_name = await self._resolve_payer_name(payer_user_id)

        # Конвертируем сумму в копейки
        payment_amount_kopecks = int(payment_amount * 100)

        # Получаем комиссию платежной системы из настроек
        gateway_commission = Decimal("0")
        if gateway_type:
            gateway_commission = partner_settings.get_gateway_commission(gateway_type.value)
            logger.debug(f"Gateway '{gateway_type.value}' commission: {gateway_commission}%")
        gateway_name = gateway_type.value if gateway_type else "unknown"

        # Начисляем вознаграждения для каждого уровня
        for referral in partner_chain:
            await self._process_partner_referral_earning(
                referral=referral,
                payer_user_id=payer_user_id,
                payer_name=payer_name,
                payment_amount_kopecks=payment_amount_kopecks,
                partner_settings=partner_settings,
                gateway_commission=gateway_commission,
                gateway_name=gateway_name,
                source_transaction_id=source_transaction_id,
            )

    async def _calculate_partner_earning(
        self,
        partner: PartnerDto,
        partner_settings: PartnerSettingsDto,
        payment_amount: int,
        level: PartnerLevel,
        gateway_commission: Decimal,
    ) -> tuple[int, Decimal]:
        """
        Рассчитать заработок партнера с учетом индивидуальных настроек.

        Args:
            partner: Партнер
            partner_settings: Глобальные настройки партнерской программы
            payment_amount: Сумма оплаты в копейках
            level: Уровень партнера
            gateway_commission: Комиссия платежной системы

        Returns:
            Кортеж (заработок в копейках, использованный процент)
        """
        ind_settings = partner.individual_settings

        # Если используем глобальные настройки
        if ind_settings.use_global_settings:
            earning = partner_settings.calculate_partner_earning(
                payment_amount=payment_amount,
                level=level,
                gateway_commission=gateway_commission,
            )
            return earning, partner_settings.get_level_percent(level)

        # Используем индивидуальные настройки
        reward_type = ind_settings.reward_type

        if reward_type == PartnerRewardType.FIXED_AMOUNT:
            # Фиксированная сумма
            fixed_amount = ind_settings.get_level_fixed_amount(level)
            if fixed_amount is not None and fixed_amount > 0:
                return fixed_amount, Decimal("0")
            # Если фиксированная сумма не задана, используем глобальный процент
            earning = partner_settings.calculate_partner_earning(
                payment_amount=payment_amount,
                level=level,
                gateway_commission=gateway_commission,
            )
            return earning, partner_settings.get_level_percent(level)

        # Процент от суммы
        individual_percent = ind_settings.get_level_percent(level)
        if individual_percent is not None:
            percent = individual_percent
        else:
            # Используем глобальный процент
            percent = partner_settings.get_level_percent(level)

        # Рассчитываем чистую сумму с учетом комиссий
        if partner_settings.auto_calculate_commission:
            net_amount = Decimal(payment_amount) * (100 - gateway_commission) / 100
            net_amount = net_amount * (100 - partner_settings.tax_percent) / 100
        else:
            net_amount = Decimal(payment_amount)

        earning = int(net_amount * percent / 100)
        return max(0, earning), percent

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
        """Создать транзакцию начисления партнеру."""
        transaction = await self.uow.repository.partners.create_transaction(
            PartnerTransaction(
                partner_id=partner.id,
                referral_telegram_id=referral_telegram_id,
                level=level,
                payment_amount=payment_amount,
                percent=percent,
                earned_amount=earned_amount,
                source_transaction_id=source_transaction_id,
                description=description,
            )
        )

        # Обновляем баланс партнера
        assert partner.id is not None, "Partner ID is required for balance update"
        await self.uow.repository.partners.update_partner(
            partner.id,
            balance=partner.balance + earned_amount,
            total_earned=partner.total_earned + earned_amount,
        )

        return PartnerTransactionDto.from_model(transaction)  # type: ignore[return-value]

    async def get_partner_transactions(
        self,
        partner_id: int,
        limit: Optional[int] = None,
    ) -> List[PartnerTransactionDto]:
        """Получить транзакции партнера."""
        transactions = await self.uow.repository.partners.get_transactions_by_partner(
            partner_id, limit=limit
        )
        return PartnerTransactionDto.from_model_list(transactions)

    async def get_partner_statistics(self, partner: Optional[PartnerDto] = None) -> Dict[str, Any]:
        """Получить статистику партнера или общую статистику партнерской программы."""
        if partner:
            # Статистика конкретного партнера
            assert partner.id is not None, "Partner ID is required for statistics"
            await self.uow.repository.partners.sum_earnings_by_partner(partner.id)
            level1_earnings = await self.uow.repository.partners.sum_earnings_by_level(
                partner.id, PartnerLevel.LEVEL_1
            )
            level2_earnings = await self.uow.repository.partners.sum_earnings_by_level(
                partner.id, PartnerLevel.LEVEL_2
            )
            level3_earnings = await self.uow.repository.partners.sum_earnings_by_level(
                partner.id, PartnerLevel.LEVEL_3
            )

            return {
                "balance": partner.balance,
                "total_earned": partner.total_earned,
                "total_withdrawn": partner.total_withdrawn,
                "referrals_count": partner.referrals_count,
                "level2_referrals_count": partner.level2_referrals_count,
                "level3_referrals_count": partner.level3_referrals_count,
                "total_referrals": partner.total_referrals,
                "level1_earnings": level1_earnings,
                "level2_earnings": level2_earnings,
                "level3_earnings": level3_earnings,
            }
        else:
            # Общая статистика партнерской программы для админки
            all_partners = await self.get_all_partners()
            pending_withdrawals = await self.get_pending_withdrawals()

            total_referrals = sum(p.total_referrals for p in all_partners)
            total_earned = sum(p.total_earned for p in all_partners)
            total_withdrawn = sum(p.total_withdrawn for p in all_partners)

            return {
                "total_partners": len(all_partners),
                "total_referrals": total_referrals,
                "pending_withdrawals": len(pending_withdrawals),
                "total_earned": total_earned,
                "total_withdrawn": total_withdrawn,
            }

    # ==================
    # WITHDRAWALS
    # ==================

    async def request_withdrawal(
        self,
        partner: PartnerDto,
        amount: int,
        method: str,
        requisites: str,
        settings: PartnerSettingsDto,
    ) -> Optional[PartnerWithdrawalDto]:
        """Запросить вывод средств."""
        if amount < settings.min_withdrawal_amount:
            logger.warning(
                f"Withdrawal amount {amount} is less than minimum {settings.min_withdrawal_amount}"
            )
            return None

        if amount > partner.balance:
            logger.warning(f"Withdrawal amount {amount} exceeds partner balance {partner.balance}")
            return None

        withdrawal = await self.uow.repository.partners.create_withdrawal(
            PartnerWithdrawal(
                partner_id=partner.id,
                amount=amount,
                status=WithdrawalStatus.PENDING.value,
                method=method,
                requisites=requisites,
            )
        )

        # Резервируем средства (вычитаем из баланса)
        assert partner.id is not None, "Partner ID is required for withdrawal"
        await self.uow.repository.partners.update_partner(
            partner.id,
            balance=partner.balance - amount,
        )

        logger.info(f"Partner '{partner.id}' requested withdrawal of {amount} kopecks via {method}")
        return PartnerWithdrawalDto.from_model(withdrawal)  # type: ignore[return-value]

    async def get_withdrawal(self, withdrawal_id: int) -> Optional[PartnerWithdrawalDto]:
        """Получить запрос на вывод по ID."""
        withdrawal = await self.uow.repository.partners.get_withdrawal_by_id(withdrawal_id)
        return PartnerWithdrawalDto.from_model(withdrawal) if withdrawal else None

    async def get_all_withdrawals(
        self,
        status: Optional[WithdrawalStatus] = None,
    ) -> List[PartnerWithdrawalDto]:
        """Получить все запросы на вывод с опциональным фильтром по статусу."""
        withdrawals = await self.uow.repository.partners.get_all_withdrawals(status)
        return PartnerWithdrawalDto.from_model_list(withdrawals)

    async def approve_withdrawal(
        self,
        withdrawal_id: int,
        admin_telegram_id: int,
        comment: Optional[str] = None,
    ) -> bool:
        """Подтвердить вывод средств."""
        withdrawal = await self.uow.repository.partners.get_withdrawal_by_id(withdrawal_id)
        if not withdrawal:
            return False

        await self.uow.repository.partners.update_withdrawal(
            withdrawal_id,
            status=WithdrawalStatus.COMPLETED,
            processed_by=admin_telegram_id,
            admin_comment=comment,
        )

        # Обновляем total_withdrawn у партнера
        partner = await self.uow.repository.partners.get_partner_by_id(withdrawal.partner_id)
        if partner and partner.id:
            await self.uow.repository.partners.update_partner(
                partner.id,
                total_withdrawn=partner.total_withdrawn + withdrawal.amount,
            )

        logger.info(f"Withdrawal '{withdrawal_id}' approved by admin '{admin_telegram_id}'")
        return True

    async def reject_withdrawal(
        self,
        withdrawal_id: int,
        admin_telegram_id: int,
        reason: Optional[str] = None,
    ) -> bool:
        """Отклонить вывод средств."""
        withdrawal = await self.uow.repository.partners.get_withdrawal_by_id(withdrawal_id)
        if not withdrawal:
            return False

        await self.uow.repository.partners.update_withdrawal(
            withdrawal_id,
            status=WithdrawalStatus.REJECTED,
            processed_by=admin_telegram_id,
            admin_comment=reason,
        )

        # Возвращаем средства на баланс
        partner = await self.uow.repository.partners.get_partner_by_id(withdrawal.partner_id)
        if partner:
            await self.uow.repository.partners.update_partner(
                partner.id,
                balance=partner.balance + withdrawal.amount,
            )

        logger.info(f"Withdrawal '{withdrawal_id}' rejected by admin '{admin_telegram_id}'")
        return True

    async def get_pending_withdrawals(self) -> List[PartnerWithdrawalDto]:
        """Получить ожидающие выплаты."""
        withdrawals = await self.uow.repository.partners.get_pending_withdrawals()
        return PartnerWithdrawalDto.from_model_list(withdrawals)

    async def get_partner_withdrawals(self, partner_id: int) -> List[PartnerWithdrawalDto]:
        """Получить историю выплат партнера."""
        withdrawals = await self.uow.repository.partners.get_withdrawals_by_partner(partner_id)
        return PartnerWithdrawalDto.from_model_list(withdrawals)

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
        """
        Создать запрос на вывод средств.

        Args:
            partner_id: ID партнера
            amount: Сумма вывода в рублях
            method: Метод вывода
            requisites: Реквизиты для вывода

        Returns:
            Созданный запрос на вывод или None
        """
        partner = await self.get_partner(partner_id)
        if not partner:
            logger.warning(f"Partner '{partner_id}' not found for withdrawal request")
            return None

        if amount <= 0:
            logger.warning(f"Withdrawal amount must be positive: {amount}")
            return None

        # Конвертируем рубли в копейки с точным округлением
        amount_kopecks = int(
            (amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

        if amount_kopecks <= 0:
            logger.warning(f"Withdrawal amount is too small after conversion: {amount}")
            return None

        # Получаем настройки партнерской программы
        settings = await self.settings_service.get()
        partner_settings = settings.partner

        # Проверяем минимальную сумму вывода (в копейках)
        if amount_kopecks < partner_settings.min_withdrawal_amount:
            logger.warning(
                f"Withdrawal amount {amount_kopecks} is less than minimum "
                f"{partner_settings.min_withdrawal_amount}"
            )
            return None

        # Проверяем баланс партнера (в копейках)
        if amount_kopecks > partner.balance:
            logger.warning(
                f"Withdrawal amount {amount_kopecks} exceeds partner balance {partner.balance}"
            )
            return None

        withdrawal = await self.uow.repository.partners.create_withdrawal(
            PartnerWithdrawal(
                partner_id=partner.id,
                amount=amount_kopecks,
                status=WithdrawalStatus.PENDING.value,
                method=method,
                requisites=requisites,
                requested_amount=requested_amount or amount,
                requested_currency=requested_currency or Currency.RUB,
                quote_rate=quote_rate,
                quote_source=quote_source,
            )
        )

        # Резервируем средства (вычитаем полную запрошенную сумму из баланса)
        assert partner.id is not None, "Partner ID is required for withdrawal request"
        await self.uow.repository.partners.update_partner(
            partner.id,
            balance=partner.balance - amount_kopecks,
        )

        logger.info(
            f"Partner '{partner.id}' created withdrawal request for {amount_kopecks} kopecks"
        )
        return PartnerWithdrawalDto.from_model(withdrawal)  # type: ignore[return-value]
