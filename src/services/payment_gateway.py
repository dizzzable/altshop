import uuid
from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.enums import (
    Currency,
    DeviceType,
    PaymentGatewayType,
    PurchaseType,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    AnyGatewaySettingsDto,
    CryptomusGatewaySettingsDto,
    CryptopayGatewaySettingsDto,
    HeleketGatewaySettingsDto,
    Pal24GatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
    PlategaGatewaySettingsDto,
    PlanSnapshotDto,
    PriceDetailsDto,
    RobokassaGatewaySettingsDto,
    TransactionDto,
    UserDto,
    WataGatewaySettingsDto,
    YookassaGatewaySettingsDto,
    YoomoneyGatewaySettingsDto,
)
from src.infrastructure.database.models.sql import PaymentGateway
from src.infrastructure.payment_gateways import BasePaymentGateway, PaymentGatewayFactory
from src.infrastructure.redis import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_system_notification_task,
    send_test_transaction_notification_task,
)
from src.infrastructure.taskiq.tasks.subscriptions import purchase_subscription_task
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.subscription import SubscriptionService

from .base import BaseService
from .transaction import TransactionService


class PaymentGatewayService(BaseService):
    uow: UnitOfWork
    transaction_service: TransactionService
    subscription_service: SubscriptionService
    payment_gateway_factory: PaymentGatewayFactory
    referral_service: ReferralService
    partner_service: PartnerService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        transaction_service: TransactionService,
        subscription_service: SubscriptionService,
        payment_gateway_factory: PaymentGatewayFactory,
        referral_service: ReferralService,
        partner_service: PartnerService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.transaction_service = transaction_service
        self.subscription_service = subscription_service
        self.payment_gateway_factory = payment_gateway_factory
        self.referral_service = referral_service
        self.partner_service = partner_service

    async def create_default(self) -> None:
        for gateway_type in PaymentGatewayType:
            settings: Optional[AnyGatewaySettingsDto]

            if await self.get_by_type(gateway_type):
                continue

            match gateway_type:
                case PaymentGatewayType.TELEGRAM_STARS:
                    is_active = True
                    settings = None
                case PaymentGatewayType.YOOKASSA:
                    is_active = False
                    settings = YookassaGatewaySettingsDto()
                case PaymentGatewayType.CRYPTOPAY:
                    is_active = False
                    settings = CryptopayGatewaySettingsDto()
                case PaymentGatewayType.HELEKET:
                    is_active = False
                    settings = HeleketGatewaySettingsDto()
                case PaymentGatewayType.PAL24:
                    is_active = False
                    settings = Pal24GatewaySettingsDto()
                case PaymentGatewayType.WATA:
                    is_active = False
                    settings = WataGatewaySettingsDto()
                case PaymentGatewayType.PLATEGA:
                    is_active = False
                    settings = PlategaGatewaySettingsDto()
                # case PaymentGatewayType.YOOMONEY:
                #     is_active = False
                #     settings = YoomoneyGatewaySettingsDto()
                # case PaymentGatewayType.CRYPTOMUS:
                #     is_active = False
                #     settings = CryptomusGatewaySettingsDto()
                # case PaymentGatewayType.ROBOKASSA:
                #     is_active = False
                #     settings = RobokassaGatewaySettingsDto()
                case _:
                    logger.warning(f"Unhandled payment gateway type '{gateway_type}' — skipping")
                    continue

            order_index = await self.uow.repository.gateways.get_max_index()
            order_index = (order_index or 0) + 1

            payment_gateway = PaymentGatewayDto(
                order_index=order_index,
                type=gateway_type,
                currency=Currency.from_gateway_type(gateway_type),
                is_active=is_active,
                settings=settings,
            )

            db_payment_gateway = PaymentGateway(**payment_gateway.model_dump())
            db_payment_gateway = await self.uow.repository.gateways.create(db_payment_gateway)

            logger.info(f"Payment gateway '{gateway_type}' created")

    async def get(self, gateway_id: int) -> Optional[PaymentGatewayDto]:
        db_gateway = await self.uow.repository.gateways.get(gateway_id)

        if not db_gateway:
            logger.warning(f"Payment gateway '{gateway_id}' not found")
            return None

        logger.debug(f"Retrieved payment gateway '{gateway_id}'")
        return PaymentGatewayDto.from_model(db_gateway, decrypt=True)

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGatewayDto]:
        db_gateway = await self.uow.repository.gateways.get_by_type(gateway_type)

        if not db_gateway:
            logger.warning(f"Payment gateway of type '{gateway_type}' not found")
            return None

        logger.debug(f"Retrieved payment gateway of type '{gateway_type}'")
        return PaymentGatewayDto.from_model(db_gateway, decrypt=True)

    async def get_all(self, sorted: bool = False) -> list[PaymentGatewayDto]:
        db_gateways = await self.uow.repository.gateways.get_all(sorted)
        logger.debug(f"Retrieved '{len(db_gateways)}' payment gateways")
        return PaymentGatewayDto.from_model_list(db_gateways, decrypt=False)

    async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]:
        updated_data = gateway.changed_data

        if gateway.settings and gateway.settings.changed_data:
            updated_data["settings"] = gateway.settings.prepare_init_data(encrypt=True)

        db_updated_gateway = await self.uow.repository.gateways.update(
            gateway_id=gateway.id,  # type: ignore[arg-type]
            **updated_data,
        )

        if db_updated_gateway:
            logger.info(f"Payment gateway '{gateway.type}' updated successfully")
        else:
            logger.warning(
                f"Attempted to update gateway '{gateway.type}' (ID: '{gateway.id}'), "
                f"but gateway was not found or update failed"
            )

        return PaymentGatewayDto.from_model(db_updated_gateway, decrypt=True)

    async def filter_active(self, is_active: bool = True) -> list[PaymentGatewayDto]:
        db_gateways = await self.uow.repository.gateways.filter_active(is_active)
        logger.debug(f"Filtered active gateways: '{is_active}', found '{len(db_gateways)}'")
        return PaymentGatewayDto.from_model_list(db_gateways, decrypt=False)

    async def move_gateway_up(self, gateway_id: int) -> bool:
        db_gateways = await self.uow.repository.gateways.get_all()
        db_gateways.sort(key=lambda p: p.order_index)

        index = next((i for i, p in enumerate(db_gateways) if p.id == gateway_id), None)
        if index is None:
            logger.warning(f"Payment gateway with ID '{gateway_id}' not found for move operation")
            return False

        if index == 0:
            gateway = db_gateways.pop(0)
            db_gateways.append(gateway)
            logger.debug(f"Payment gateway '{gateway_id}' moved from top to bottom")
        else:
            db_gateways[index - 1], db_gateways[index] = db_gateways[index], db_gateways[index - 1]
            logger.debug(f"Payment gateway '{gateway_id}' moved up one position")

        for i, gateway in enumerate(db_gateways, start=1):
            gateway.order_index = i

        logger.info(f"Payment gateway '{gateway_id}' reorder successfully")
        return True

    #

    async def create_payment(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        pricing: PriceDetailsDto,
        purchase_type: PurchaseType,
        gateway_type: PaymentGatewayType,
        renew_subscription_id: Optional[int] = None,
        renew_subscription_ids: Optional[list[int]] = None,
        device_types: Optional[list[DeviceType]] = None,
    ) -> PaymentResult:
        gateway_instance = await self._get_gateway_instance(gateway_type)

        i18n = self.translator_hub.get_translator_by_locale(locale=user.language)
        key, kw = i18n_format_days(plan.duration)
        
        # Формируем описание с учётом количества подписок
        subscription_count = len(renew_subscription_ids) if renew_subscription_ids else 1
        if subscription_count > 1:
            details = i18n.get(
                "payment-invoice-description-multi",
                purchase_type=purchase_type,
                name=plan.name,
                duration=i18n.get(key, **kw),
                count=subscription_count,
            )
        else:
            details = i18n.get(
                "payment-invoice-description",
                purchase_type=purchase_type,
                name=plan.name,
                duration=i18n.get(key, **kw),
            )

        transaction_data = {
            "status": TransactionStatus.PENDING,
            "purchase_type": purchase_type,
            "gateway_type": gateway_instance.gateway.type,
            "pricing": pricing,
            "currency": gateway_instance.gateway.currency,
            "plan": plan,
            "renew_subscription_id": renew_subscription_id,
            "renew_subscription_ids": renew_subscription_ids,
            "device_types": device_types,
        }

        if pricing.is_free:
            payment_id = uuid.uuid4()

            transaction = TransactionDto(payment_id=payment_id, **transaction_data)
            await self.transaction_service.create(user, transaction)

            logger.info(f"Payment for user '{user.telegram_id}' not created. Pricing is free")
            return PaymentResult(id=payment_id, url=None)

        payment: PaymentResult = await gateway_instance.handle_create_payment(
            amount=pricing.final_amount,
            details=details,
        )
        transaction = TransactionDto(payment_id=payment.id, **transaction_data)
        await self.transaction_service.create(user, transaction)

        logger.info(f"Created transaction '{payment.id}' for user '{user.telegram_id}'")
        logger.info(f"Payment link: '{payment.url}' for user '{user.telegram_id}'")
        return payment

    async def create_test_payment(
        self,
        user: UserDto,
        gateway_type: PaymentGatewayType,
    ) -> PaymentResult:
        gateway_instance = await self._get_gateway_instance(gateway_type)
        i18n = self.translator_hub.get_translator_by_locale(locale=user.language)
        test_details = i18n.get("test-payment")

        test_payment_id = uuid.uuid4()
        test_pricing = PriceDetailsDto()
        test_plan = PlanSnapshotDto.test()

        test_payment: PaymentResult = await gateway_instance.handle_create_payment(
            amount=test_pricing.final_amount,
            details=test_details,
        )
        test_transaction = TransactionDto(
            payment_id=test_payment.id,
            status=TransactionStatus.PENDING,
            purchase_type=PurchaseType.NEW,
            gateway_type=gateway_instance.gateway.type,
            is_test=True,
            pricing=test_pricing,
            currency=gateway_instance.gateway.currency,
            plan=test_plan,
        )
        await self.transaction_service.create(user, test_transaction)

        logger.info(f"Created test transaction '{test_payment_id}' for user '{user.telegram_id}'")
        logger.info(
            f"Created test payment '{test_payment.id}' for gateway '{gateway_type}', "
            f"link: '{test_payment.url}'"
        )
        return test_payment

    async def handle_payment_succeeded(self, payment_id: UUID) -> None:
        transaction = await self.transaction_service.get(payment_id)

        if not transaction or not transaction.user:
            logger.critical(f"Transaction or user not found for '{payment_id}'")
            return

        if transaction.is_completed:
            logger.warning(
                f"Transaction '{payment_id}' for user "
                f"'{transaction.user.telegram_id}' already completed"
            )
            return

        transaction.status = TransactionStatus.COMPLETED
        await self.transaction_service.update(transaction)

        logger.info(f"Payment succeeded '{payment_id}' for user '{transaction.user.telegram_id}'")

        if transaction.is_test:
            await send_test_transaction_notification_task.kiq(user=transaction.user)
            return

        i18n_keys = {
            PurchaseType.NEW: "ntf-event-subscription-new",
            PurchaseType.RENEW: "ntf-event-subscription-renew",
            PurchaseType.ADDITIONAL: "ntf-event-subscription-additional",
        }
        i18n_key = i18n_keys[transaction.purchase_type]

        # Для NEW и ADDITIONAL покупки не передаём существующую подписку, чтобы создавалась новая
        # Для RENEW нужна выбранная подписка (по renew_subscription_id/renew_subscription_ids) или текущая
        if transaction.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
            subscription = None
            subscriptions_to_renew = []
            logger.debug(
                f"Purchase type is {transaction.purchase_type}, no subscription needed"
            )
        elif transaction.renew_subscription_ids and len(transaction.renew_subscription_ids) > 1:
            # Множественное продление - получаем все выбранные подписки (только если больше одной)
            logger.info(
                f"Multiple renewal detected: {len(transaction.renew_subscription_ids)} subscriptions "
                f"(IDs: {transaction.renew_subscription_ids})"
            )
            subscriptions_to_renew = []
            for sub_id in transaction.renew_subscription_ids:
                sub = await self.subscription_service.get(sub_id)
                if sub:
                    subscriptions_to_renew.append(sub)
                else:
                    logger.warning(f"Subscription '{sub_id}' not found, skipping")
            
            if not subscriptions_to_renew:
                logger.warning(
                    f"No subscriptions found for renewal from list {transaction.renew_subscription_ids}, "
                    f"falling back to current subscription"
                )
                subscription = await self.subscription_service.get_current(transaction.user.telegram_id)
                subscriptions_to_renew = [subscription] if subscription else []
            else:
                # Для обратной совместимости используем первую подписку
                subscription = subscriptions_to_renew[0]
                logger.info(
                    f"Will renew {len(subscriptions_to_renew)} subscriptions: "
                    f"{[s.id for s in subscriptions_to_renew]}"
                )
        elif transaction.renew_subscription_id:
            # Используем конкретную подписку, выбранную пользователем для продления (одиночное продление)
            logger.info(
                f"Single renewal via renew_subscription_id: {transaction.renew_subscription_id}"
            )
            subscription = await self.subscription_service.get(transaction.renew_subscription_id)
            subscriptions_to_renew = [subscription] if subscription else []
            if not subscription:
                logger.warning(
                    f"Subscription '{transaction.renew_subscription_id}' not found for renewal, "
                    f"falling back to current subscription"
                )
                subscription = await self.subscription_service.get_current(transaction.user.telegram_id)
                subscriptions_to_renew = [subscription] if subscription else []
            else:
                logger.info(f"Will renew single subscription: {subscription.id}")
        elif transaction.renew_subscription_ids and len(transaction.renew_subscription_ids) == 1:
            # Одиночное продление через renew_subscription_ids (когда выбрана одна подписка из списка)
            sub_id = transaction.renew_subscription_ids[0]
            logger.info(
                f"Single renewal via renew_subscription_ids[0]: {sub_id}"
            )
            subscription = await self.subscription_service.get(sub_id)
            subscriptions_to_renew = [subscription] if subscription else []
            if not subscription:
                logger.warning(
                    f"Subscription '{sub_id}' not found for renewal, "
                    f"falling back to current subscription"
                )
                subscription = await self.subscription_service.get_current(transaction.user.telegram_id)
                subscriptions_to_renew = [subscription] if subscription else []
            else:
                logger.info(f"Will renew single subscription: {subscription.id}")
        else:
            # Fallback на текущую подписку
            logger.info(
                f"No specific subscription selected, using current subscription for user "
                f"'{transaction.user.telegram_id}'"
            )
            subscription = await self.subscription_service.get_current(transaction.user.telegram_id)
            subscriptions_to_renew = [subscription] if subscription else []
            if subscription:
                logger.info(f"Will renew current subscription: {subscription.id}")
            else:
                logger.warning("No current subscription found!")
        extra_i18n_kwargs = {}

        i18n_kwargs = {
            "payment_id": transaction.payment_id,
            "gateway_type": transaction.gateway_type,
            "final_amount": transaction.pricing.final_amount,
            "discount_percent": transaction.pricing.discount_percent,
            "original_amount": transaction.pricing.original_amount,
            "currency": transaction.currency.symbol,
            "user_id": str(transaction.user.telegram_id),
            "user_name": transaction.user.name,
            "username": transaction.user.username or False,
            "plan_name": transaction.plan.name,
            "plan_type": transaction.plan.type,
            "plan_traffic_limit": i18n_format_traffic_limit(transaction.plan.traffic_limit),
            "plan_device_limit": i18n_format_device_limit(transaction.plan.device_limit),
            "plan_duration": i18n_format_days(transaction.plan.duration),
        }

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.SUBSCRIPTION,
            payload=MessagePayload.not_deleted(
                i18n_key=i18n_key,
                i18n_kwargs={**i18n_kwargs, **extra_i18n_kwargs},
                reply_markup=get_user_keyboard(transaction.user.telegram_id),
            ),
        )

        # Передаём список подписок для множественного продления
        await purchase_subscription_task.kiq(
            transaction,
            subscription,
            subscriptions_to_renew=subscriptions_to_renew if len(subscriptions_to_renew) > 1 else None
        )

        if not transaction.pricing.is_free:
            await self.referral_service.assign_referral_rewards(transaction=transaction)
            
            # Начисляем партнерские проценты
            await self.partner_service.process_partner_earning(
                payer_user_id=transaction.user.telegram_id,
                payment_amount=transaction.pricing.final_amount,
                gateway_type=transaction.gateway_type,
            )

        logger.debug(f"Called tasks payment for user '{transaction.user.telegram_id}'")

    async def handle_payment_canceled(self, payment_id: UUID) -> None:
        transaction = await self.transaction_service.get(payment_id)

        if not transaction or not transaction.user:
            logger.critical(f"Transaction or user not found for '{payment_id}'")
            return

        transaction.status = TransactionStatus.CANCELED
        await self.transaction_service.update(transaction)
        logger.info(f"Payment canceled '{payment_id}' for user '{transaction.user.telegram_id}'")

    #

    async def _get_gateway_instance(self, gateway_type: PaymentGatewayType) -> BasePaymentGateway:
        logger.debug(f"Creating gateway instance for type '{gateway_type}'")
        gateway = await self.get_by_type(gateway_type)

        if not gateway:
            raise ValueError(f"Payment gateway of type '{gateway_type}' not found")

        return self.payment_gateway_factory(gateway)
