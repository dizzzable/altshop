import hashlib
import uuid
from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.crypto_assets import get_default_payment_asset
from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    DiscountSource,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.observability import emit_counter
from src.core.utils.bot_menu import resolve_bot_menu_url
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.core.utils.mini_app_urls import build_telegram_payment_return_url
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    AnyGatewaySettingsDto,
    CloudPaymentsGatewaySettingsDto,
    CryptomusGatewaySettingsDto,
    CryptopayGatewaySettingsDto,
    HeleketGatewaySettingsDto,
    MulenpayGatewaySettingsDto,
    Pal24GatewaySettingsDto,
    PaymentGatewayDto,
    PaymentResult,
    PlanSnapshotDto,
    PlategaGatewaySettingsDto,
    PriceDetailsDto,
    RobokassaGatewaySettingsDto,
    StripeGatewaySettingsDto,
    SubscriptionDto,
    TbankGatewaySettingsDto,
    TransactionDto,
    UserDto,
    WataGatewaySettingsDto,
    YookassaGatewaySettingsDto,
    YoomoneyGatewaySettingsDto,
    normalize_platega_payment_method,
)
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.database.models.sql import PaymentGateway, PaymentWebhookEvent
from src.infrastructure.payment_gateways import BasePaymentGateway, PaymentGatewayFactory
from src.infrastructure.payment_gateways.platega import (
    PlategaGateway,
    PlategaTransactionNotFoundError,
    PlategaWebhookResolutionError,
)
from src.infrastructure.redis import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_system_notification_task,
    send_test_transaction_notification_task,
)
from src.infrastructure.taskiq.tasks.subscriptions import purchase_subscription_task
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .base import BaseService
from .payment_webhook_event import PaymentWebhookEventService
from .settings import SettingsService
from .transaction import TransactionService


class PaymentGatewayService(BaseService):
    uow: UnitOfWork
    transaction_service: TransactionService
    subscription_service: SubscriptionService
    payment_gateway_factory: PaymentGatewayFactory
    payment_webhook_event_service: PaymentWebhookEventService
    referral_service: ReferralService
    partner_service: PartnerService
    user_service: UserService
    settings_service: SettingsService

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
        payment_webhook_event_service: PaymentWebhookEventService,
        referral_service: ReferralService,
        partner_service: PartnerService,
        user_service: UserService,
        settings_service: SettingsService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.transaction_service = transaction_service
        self.subscription_service = subscription_service
        self.payment_gateway_factory = payment_gateway_factory
        self.payment_webhook_event_service = payment_webhook_event_service
        self.referral_service = referral_service
        self.partner_service = partner_service
        self.user_service = user_service
        self.settings_service = settings_service
        self._bot_username: str | None = None

    async def create_default(self) -> None:  # noqa: C901
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
                case PaymentGatewayType.YOOMONEY:
                    is_active = False
                    settings = YoomoneyGatewaySettingsDto()
                case PaymentGatewayType.CRYPTOPAY:
                    is_active = False
                    settings = CryptopayGatewaySettingsDto()
                case PaymentGatewayType.TBANK:
                    is_active = False
                    settings = TbankGatewaySettingsDto()
                case PaymentGatewayType.CRYPTOMUS:
                    is_active = False
                    settings = CryptomusGatewaySettingsDto()
                case PaymentGatewayType.HELEKET:
                    is_active = False
                    settings = HeleketGatewaySettingsDto()
                case PaymentGatewayType.ROBOKASSA:
                    is_active = False
                    settings = RobokassaGatewaySettingsDto()
                case PaymentGatewayType.STRIPE:
                    is_active = False
                    settings = StripeGatewaySettingsDto()
                case PaymentGatewayType.MULENPAY:
                    is_active = False
                    settings = MulenpayGatewaySettingsDto()
                case PaymentGatewayType.CLOUDPAYMENTS:
                    is_active = False
                    settings = CloudPaymentsGatewaySettingsDto()
                case PaymentGatewayType.PAL24:
                    is_active = False
                    settings = Pal24GatewaySettingsDto()
                case PaymentGatewayType.WATA:
                    is_active = False
                    settings = WataGatewaySettingsDto()
                case PaymentGatewayType.PLATEGA:
                    is_active = False
                    settings = PlategaGatewaySettingsDto()
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

    async def normalize_gateway_settings(self) -> None:
        """Normalize legacy gateway settings values to canonical forms."""
        db_gateways = await self.uow.repository.gateways.get_all()

        for db_gateway in db_gateways:
            if db_gateway.type != PaymentGatewayType.PLATEGA:
                if (
                    db_gateway.type == PaymentGatewayType.CRYPTOPAY
                    and db_gateway.currency != Currency.USD
                ):
                    await self.uow.repository.gateways.update(
                        gateway_id=db_gateway.id,
                        currency=Currency.USD,
                    )
                    logger.warning(
                        "Normalized CRYPTOPAY currency for gateway_id='{}'. '{}' -> '{}'",
                        db_gateway.id,
                        db_gateway.currency,
                        Currency.USD,
                    )
                continue

            if not isinstance(db_gateway.settings, dict):
                continue

            settings_data = dict(db_gateway.settings)
            old_method = settings_data.get("payment_method")
            normalized_method = normalize_platega_payment_method(
                old_method,
                strict=False,
                default=PlategaGatewaySettingsDto().payment_method,
            )

            if old_method == normalized_method and settings_data.get("type") is not None:
                continue

            settings_data["type"] = PaymentGatewayType.PLATEGA.value
            settings_data["payment_method"] = normalized_method

            await self.uow.repository.gateways.update(
                gateway_id=db_gateway.id,
                settings=settings_data,
            )
            logger.warning(
                "Normalized PLATEGA settings for gateway_id='{}'. payment_method: '{}' -> '{}'",
                db_gateway.id,
                old_method,
                normalized_method,
            )

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
        payment_asset: Optional[CryptoAsset] = None,
        renew_subscription_id: Optional[int] = None,
        renew_subscription_ids: Optional[list[int]] = None,
        device_types: Optional[list[DeviceType]] = None,
        channel: PurchaseChannel = PurchaseChannel.TELEGRAM,
        success_redirect_url: Optional[str] = None,
        fail_redirect_url: Optional[str] = None,
    ) -> PaymentResult:
        gateway_instance = await self._get_gateway_instance(gateway_type)
        if channel == PurchaseChannel.TELEGRAM and (
            success_redirect_url is None or fail_redirect_url is None
        ):
            (
                default_success_redirect_url,
                default_fail_redirect_url,
            ) = await self._resolve_telegram_payment_redirect_urls()
            success_redirect_url = success_redirect_url or default_success_redirect_url
            fail_redirect_url = fail_redirect_url or default_fail_redirect_url

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
            "channel": channel,
            "gateway_type": gateway_instance.gateway.type,
            "pricing": pricing,
            "currency": gateway_instance.gateway.currency,
            "payment_asset": payment_asset,
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
            payment_asset=payment_asset,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
            is_test_payment=False,
        )
        transaction = TransactionDto(payment_id=payment.id, **transaction_data)
        await self.transaction_service.create(user, transaction)

        logger.info(
            "Created transaction '{}' for user '{}' gateway='{}' payment_asset='{}'",
            payment.id,
            user.telegram_id,
            gateway_type.value,
            payment_asset.value if payment_asset else None,
        )
        logger.info(
            "Payment link created for user '{}' gateway='{}' payment_asset='{}' url='{}'",
            user.telegram_id,
            gateway_type.value,
            payment_asset.value if payment_asset else None,
            payment.url,
        )
        return payment

    async def _resolve_telegram_payment_redirect_urls(self) -> tuple[str | None, str | None]:
        settings = await self.settings_service.get()
        mini_app_url, _ = resolve_bot_menu_url(bot_menu=settings.bot_menu, config=self.config)
        bot_username = await self._get_bot_username()
        return (
            build_telegram_payment_return_url(
                status="success",
                mini_app_url=mini_app_url,
                bot_username=bot_username,
            ),
            build_telegram_payment_return_url(
                status="failed",
                mini_app_url=mini_app_url,
                bot_username=bot_username,
            ),
        )

    async def _get_bot_username(self) -> str | None:
        if self._bot_username is None:
            bot_info = await self.bot.get_me()
            self._bot_username = (bot_info.username or "").strip().lstrip("@") or None
        return self._bot_username

    async def create_test_payment(
        self,
        user: UserDto,
        gateway_type: PaymentGatewayType,
    ) -> PaymentResult:
        gateway_instance = await self._get_gateway_instance(gateway_type)
        i18n = self.translator_hub.get_translator_by_locale(locale=user.language)
        test_details = i18n.get("test-payment")
        payment_asset = get_default_payment_asset(gateway_type)

        test_pricing = PriceDetailsDto()
        test_plan = PlanSnapshotDto.test()

        test_payment: PaymentResult = await gateway_instance.handle_create_payment(
            amount=test_pricing.final_amount,
            details=test_details,
            payment_asset=payment_asset,
            is_test_payment=True,
        )
        test_transaction = TransactionDto(
            payment_id=test_payment.id,
            status=TransactionStatus.PENDING,
            purchase_type=PurchaseType.NEW,
            channel=PurchaseChannel.TELEGRAM,
            gateway_type=gateway_instance.gateway.type,
            is_test=True,
            pricing=test_pricing,
            currency=gateway_instance.gateway.currency,
            payment_asset=payment_asset,
            plan=test_plan,
        )
        await self.transaction_service.create(user, test_transaction)

        logger.info(
            "Created test transaction '{}' for user '{}' gateway='{}' payment_asset='{}'",
            test_payment.id,
            user.telegram_id,
            gateway_type.value,
            payment_asset.value if payment_asset else None,
        )
        logger.info(
            "Created test payment '{}' for gateway '{}' payment_asset='{}' link='{}'",
            test_payment.id,
            gateway_type.value,
            payment_asset.value if payment_asset else None,
            test_payment.url,
        )
        return test_payment

    @staticmethod
    def _get_purchase_notification_key(purchase_type: PurchaseType) -> str:
        i18n_keys = {
            PurchaseType.NEW: "ntf-event-subscription-new",
            PurchaseType.RENEW: "ntf-event-subscription-renew",
            PurchaseType.UPGRADE: "ntf-event-subscription-upgrade",
            PurchaseType.ADDITIONAL: "ntf-event-subscription-additional",
        }
        return i18n_keys[purchase_type]

    @staticmethod
    def _require_transaction_user(transaction: TransactionDto) -> BaseUserDto:
        if transaction.user is None:
            raise ValueError(f"Transaction '{transaction.payment_id}' is missing user context")
        return transaction.user

    async def _resolve_single_renewal_subscription(
        self,
        *,
        transaction: TransactionDto,
        subscription_id: int,
        source_label: str,
    ) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
        transaction_user = self._require_transaction_user(transaction)
        logger.info(f"Single renewal via {source_label}: {subscription_id}")
        subscription = await self.subscription_service.get(subscription_id)
        if subscription:
            logger.info(f"Will renew single subscription: {subscription.id}")
            return subscription, [subscription]

        logger.warning(
            f"Subscription '{subscription_id}' not found for renewal, "
            f"falling back to current subscription"
        )
        fallback = await self.subscription_service.get_current(transaction_user.telegram_id)
        return fallback, [fallback] if fallback else []

    async def _resolve_multiple_renewal_subscriptions(
        self,
        *,
        transaction: TransactionDto,
    ) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
        transaction_user = self._require_transaction_user(transaction)
        renew_ids = transaction.renew_subscription_ids or []
        logger.info(f"Multiple renewal detected: {len(renew_ids)} subscriptions (IDs: {renew_ids})")
        subscriptions_to_renew: list[SubscriptionDto] = []
        for subscription_id in renew_ids:
            candidate = await self.subscription_service.get(subscription_id)
            if candidate:
                subscriptions_to_renew.append(candidate)
            else:
                logger.warning(f"Subscription '{subscription_id}' not found, skipping")

        if subscriptions_to_renew:
            primary_subscription = subscriptions_to_renew[0]
            logger.info(
                f"Will renew {len(subscriptions_to_renew)} subscriptions: "
                f"{[item.id for item in subscriptions_to_renew]}"
            )
            return primary_subscription, subscriptions_to_renew

        logger.warning(
            f"No subscriptions found for renewal from list {renew_ids}, "
            f"falling back to current subscription"
        )
        fallback = await self.subscription_service.get_current(transaction_user.telegram_id)
        return fallback, [fallback] if fallback else []

    async def _resolve_subscriptions_for_purchase(
        self,
        *,
        transaction: TransactionDto,
    ) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
        transaction_user = self._require_transaction_user(transaction)
        if transaction.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
            logger.debug(f"Purchase type is {transaction.purchase_type}, no subscription needed")
            return None, []

        if transaction.renew_subscription_ids and len(transaction.renew_subscription_ids) > 1:
            return await self._resolve_multiple_renewal_subscriptions(transaction=transaction)

        if transaction.renew_subscription_id:
            return await self._resolve_single_renewal_subscription(
                transaction=transaction,
                subscription_id=transaction.renew_subscription_id,
                source_label="renew_subscription_id",
            )

        if transaction.renew_subscription_ids and len(transaction.renew_subscription_ids) == 1:
            return await self._resolve_single_renewal_subscription(
                transaction=transaction,
                subscription_id=transaction.renew_subscription_ids[0],
                source_label="renew_subscription_ids[0]",
            )

        logger.info(
            f"No specific subscription selected, using current subscription for user "
            f"'{transaction_user.telegram_id}'"
        )
        fallback = await self.subscription_service.get_current(transaction_user.telegram_id)
        if fallback:
            logger.info(f"Will renew current subscription: {fallback.id}")
        else:
            logger.warning("No current subscription found!")
        return fallback, [fallback] if fallback else []

    @staticmethod
    def _build_subscription_i18n_kwargs(transaction: TransactionDto) -> dict[str, object]:
        transaction_user = PaymentGatewayService._require_transaction_user(transaction)
        return {
            "payment_id": transaction.payment_id,
            "gateway_type": transaction.gateway_type,
            "final_amount": transaction.pricing.final_amount,
            "discount_percent": transaction.pricing.discount_percent,
            "original_amount": transaction.pricing.original_amount,
            "currency": transaction.currency.symbol,
            "user_id": str(transaction_user.telegram_id),
            "user_name": transaction_user.name,
            "username": transaction_user.username or False,
            "plan_name": transaction.plan.name,
            "plan_type": transaction.plan.type,
            "plan_traffic_limit": i18n_format_traffic_limit(transaction.plan.traffic_limit),
            "plan_device_limit": i18n_format_device_limit(transaction.plan.device_limit),
            "plan_duration": i18n_format_days(transaction.plan.duration),
        }

    async def _send_subscription_notification(self, *, transaction: TransactionDto) -> None:
        transaction_user = self._require_transaction_user(transaction)
        i18n_key = self._get_purchase_notification_key(transaction.purchase_type)
        i18n_kwargs = self._build_subscription_i18n_kwargs(transaction)
        extra_i18n_kwargs: dict[str, object] = {}

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.SUBSCRIPTION,
            payload=MessagePayload.not_deleted(
                i18n_key=i18n_key,
                i18n_kwargs={**i18n_kwargs, **extra_i18n_kwargs},
                reply_markup=get_user_keyboard(transaction_user.telegram_id),
            ),
        )

    async def _enqueue_subscription_purchase(
        self,
        *,
        transaction: TransactionDto,
        subscription: SubscriptionDto | None,
        subscriptions_to_renew: list[SubscriptionDto],
    ) -> None:
        await purchase_subscription_task.kiq(
            transaction,
            subscription,
            subscriptions_to_renew=(
                subscriptions_to_renew if len(subscriptions_to_renew) > 1 else None
            ),
        )

    async def _run_post_payment_rewards(self, *, transaction: TransactionDto) -> None:
        transaction_user = self._require_transaction_user(transaction)
        if transaction.pricing.is_free:
            return

        await self.referral_service.assign_referral_rewards(transaction=transaction)
        await self.partner_service.process_partner_earning(
            payer_user_id=transaction_user.telegram_id,
            payment_amount=transaction.pricing.final_amount,
            gateway_type=transaction.gateway_type,
        )

    async def handle_payment_succeeded(self, payment_id: UUID) -> None:
        transaction = await self.transaction_service.get(payment_id)

        if transaction is None:
            logger.critical(f"Transaction not found for '{payment_id}'")
            raise LookupError(f"Transaction '{payment_id}' not found")
        if transaction.user is None:
            logger.critical(f"Transaction user not found for '{payment_id}'")
            raise LookupError(f"Transaction '{payment_id}' is missing user context")
        transaction_user = transaction.user

        if transaction.is_completed:
            logger.warning(
                f"Transaction '{payment_id}' for user "
                f"'{transaction_user.telegram_id}' already completed"
            )
            return

        transaction.status = TransactionStatus.COMPLETED
        await self.transaction_service.update(transaction)

        logger.info(f"Payment succeeded '{payment_id}' for user '{transaction_user.telegram_id}'")

        if transaction.is_test:
            await send_test_transaction_notification_task.kiq(user=transaction_user)
            return

        await self._consume_purchase_discount_if_needed(
            transaction=transaction,
            payment_id=payment_id,
        )
        subscription, subscriptions_to_renew = await self._resolve_subscriptions_for_purchase(
            transaction=transaction
        )
        await self._send_subscription_notification(transaction=transaction)
        await self._enqueue_subscription_purchase(
            transaction=transaction,
            subscription=subscription,
            subscriptions_to_renew=subscriptions_to_renew,
        )
        await self._run_post_payment_rewards(transaction=transaction)
        logger.debug(f"Called tasks payment for user '{transaction_user.telegram_id}'")
        return

    async def _consume_purchase_discount_if_needed(
        self,
        *,
        transaction: TransactionDto,
        payment_id: UUID,
    ) -> None:
        transaction_user = self._require_transaction_user(transaction)
        if (
            transaction.pricing.discount_source != DiscountSource.PURCHASE
            or transaction.pricing.discount_percent <= 0
        ):
            return

        current_user = await self.user_service.get(transaction_user.telegram_id)
        if not current_user:
            logger.warning(
                "Cannot consume purchase discount: user '{}' not found",
                transaction_user.telegram_id,
            )
            return

        current_discount = max(current_user.purchase_discount or 0, 0)
        used_discount = min(max(transaction.pricing.discount_percent, 0), 100)
        new_purchase_discount = max(current_discount - used_discount, 0)

        if new_purchase_discount != current_discount:
            await self.user_service.set_purchase_discount(
                user=current_user,
                discount=new_purchase_discount,
            )
            logger.info(
                "Consumed purchase discount for user '{}': {}% -> {}% (used {}% from payment '{}')",
                current_user.telegram_id,
                current_discount,
                new_purchase_discount,
                used_discount,
                payment_id,
            )
            return

        logger.info(
            "Purchase discount unchanged for user '{}': remains {}% (used {}% from payment '{}')",
            current_user.telegram_id,
            current_discount,
            used_discount,
            payment_id,
        )

    async def handle_payment_canceled(self, payment_id: UUID) -> None:
        transaction = await self.transaction_service.get(payment_id)

        if transaction is None:
            logger.critical(f"Transaction not found for '{payment_id}'")
            raise LookupError(f"Transaction '{payment_id}' not found")
        if transaction.user is None:
            logger.critical(f"Transaction user not found for '{payment_id}'")
            raise LookupError(f"Transaction '{payment_id}' is missing user context")
        transaction_user = transaction.user

        transaction.status = TransactionStatus.CANCELED
        await self.transaction_service.update(transaction)
        logger.info(f"Payment canceled '{payment_id}' for user '{transaction_user.telegram_id}'")

    async def recover_stuck_platega_payments(self, *, limit: int = 100) -> int:
        orphan_events = await self.payment_webhook_event_service.get_platega_orphan_events(
            limit=limit
        )
        if not orphan_events:
            logger.debug("No legacy Platega webhook events require recovery")
            return 0

        gateway_instance = await self._get_gateway_instance(PaymentGatewayType.PLATEGA)
        if not isinstance(gateway_instance, PlategaGateway):
            raise TypeError("PLATEGA gateway instance must be PlategaGateway")

        recovered_count = 0
        for event in orphan_events:
            if await self._recover_single_platega_event(
                gateway_instance=gateway_instance,
                event=event,
            ):
                recovered_count += 1

        logger.info(
            "Platega legacy webhook recovery completed. recovered='{}' scanned='{}'",
            recovered_count,
            len(orphan_events),
        )
        return recovered_count

    async def _recover_single_platega_event(  # noqa: C901
        self,
        *,
        gateway_instance: PlategaGateway,
        event: PaymentWebhookEvent,
    ) -> bool:
        external_transaction_id = event.payment_id

        try:
            transaction_details = await gateway_instance.get_transaction(
                str(external_transaction_id)
            )
            internal_payment_id = gateway_instance.extract_internal_payment_id_from_transaction(
                transaction_details=transaction_details,
                external_transaction_id=str(external_transaction_id),
            )
            resolved_status = gateway_instance.resolve_transaction_status_from_transaction(
                transaction_details=transaction_details,
                external_transaction_id=str(external_transaction_id),
            )
        except PlategaTransactionNotFoundError:
            diagnostic = f"remote_transaction_missing:{external_transaction_id}"
            await self.payment_webhook_event_service.mark_reconcile_failed(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=diagnostic,
            )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="remote_transaction_missing",
            )
            logger.warning(
                (
                    "Skipping Platega recovery because the remote transaction is gone. "
                    "external_transaction_id='{}'"
                ),
                external_transaction_id,
            )
            return False
        except PlategaWebhookResolutionError as exception:
            diagnostic = str(exception)
            await self.payment_webhook_event_service.mark_reconcile_failed(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=diagnostic,
            )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="reconcile_failed",
            )
            logger.error(
                "Platega recovery failed permanently. external_transaction_id='{}' error='{}'",
                external_transaction_id,
                diagnostic,
            )
            return False
        except Exception as exception:
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="fetch_failed",
            )
            logger.exception(
                "Platega recovery fetch failed. external_transaction_id='{}' error='{}'",
                external_transaction_id,
                exception,
            )
            return False

        logger.info(
            "Recovered Platega mapping. external_transaction_id='{}' payment_id='{}' status='{}'",
            external_transaction_id,
            internal_payment_id,
            resolved_status.value,
        )

        if resolved_status == TransactionStatus.PENDING:
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="pending",
            )
            logger.info(
                "Skipping Platega recovery until transaction reaches a final status. "
                "external_transaction_id='{}' payment_id='{}'",
                external_transaction_id,
                internal_payment_id,
            )
            return False

        transaction = await self.transaction_service.get(internal_payment_id)
        if transaction is None:
            diagnostic = (
                "Resolved internal payment UUID is missing locally: "
                f"{internal_payment_id}"
            )
            await self.payment_webhook_event_service.mark_reconcile_failed(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=diagnostic,
            )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="local_transaction_missing",
            )
            logger.error(
                "Platega recovery could not find local transaction. "
                "external_transaction_id='{}' payment_id='{}'",
                external_transaction_id,
                internal_payment_id,
            )
            return False

        if transaction.is_completed or transaction.status == TransactionStatus.CANCELED:
            await self.payment_webhook_event_service.mark_reconciled(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=f"already_terminal:{internal_payment_id}:{transaction.status.value}",
            )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="already_terminal",
            )
            return True

        payload_hash = hashlib.sha256(
            (
                f"platega-recovery:{external_transaction_id}:"
                f"{internal_payment_id}:{resolved_status.value}"
            ).encode("utf-8")
        ).hexdigest()
        receive_result = await self.payment_webhook_event_service.record_received(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=internal_payment_id,
            payload_hash=payload_hash,
        )

        if receive_result.already_processed:
            await self.payment_webhook_event_service.mark_reconciled(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=f"already_processed:{internal_payment_id}",
            )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="already_processed",
            )
            return True

        await self.payment_webhook_event_service.mark_processing(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=internal_payment_id,
        )
        try:
            if resolved_status == TransactionStatus.COMPLETED:
                await self.handle_payment_succeeded(internal_payment_id)
            else:
                await self.handle_payment_canceled(internal_payment_id)
            await self.payment_webhook_event_service.mark_processed(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=internal_payment_id,
            )
            await self.payment_webhook_event_service.mark_reconciled(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=f"recovered_to:{internal_payment_id}",
            )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="recovered",
            )
            logger.info(
                (
                    "Recovered legacy Platega webhook event. "
                    "external_transaction_id='{}' payment_id='{}'"
                ),
                external_transaction_id,
                internal_payment_id,
            )
            return True
        except Exception as exception:
            await self.payment_webhook_event_service.mark_failed(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=internal_payment_id,
                error_message=f"recovery_failed: {exception}",
            )
            if isinstance(exception, LookupError):
                await self.payment_webhook_event_service.mark_reconcile_failed(
                    gateway_type=PaymentGatewayType.PLATEGA.value,
                    payment_id=external_transaction_id,
                    diagnostic=f"processing_lookup_failed:{exception}",
                )
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="processing_failed",
            )
            logger.exception(
                (
                    "Platega recovery processing failed. "
                    "external_transaction_id='{}' payment_id='{}' error='{}'"
                ),
                external_transaction_id,
                internal_payment_id,
                exception,
            )
            return False

    #

    async def _get_gateway_instance(self, gateway_type: PaymentGatewayType) -> BasePaymentGateway:
        logger.debug(f"Creating gateway instance for type '{gateway_type}'")
        gateway = await self.get_by_type(gateway_type)

        if not gateway:
            raise ValueError(f"Payment gateway of type '{gateway_type}' not found")

        return self.payment_gateway_factory(gateway)
