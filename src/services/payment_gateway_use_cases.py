from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger

from src.api.utils.web_app_urls import build_web_payment_redirect_urls
from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.crypto_assets import get_default_payment_asset
from src.core.enums import (
    CryptoAsset,
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
from src.core.utils.time import datetime_now
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    PaymentResult,
    PlanSnapshotDto,
    PriceDetailsDto,
    SubscriptionDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.infrastructure.payment_gateways import BasePaymentGateway
from src.infrastructure.payment_gateways.platega import (
    PlategaGateway,
    PlategaTransactionNotFoundError,
    PlategaWebhookResolutionError,
)
from src.infrastructure.taskiq.tasks.notifications import (
    send_system_notification_task,
    send_test_transaction_notification_task,
)
from src.infrastructure.taskiq.tasks.subscriptions import purchase_subscription_task
from src.services.partner import PartnerService
from src.services.payment_redirect_policy import sanitize_payment_redirect_urls_for_channel
from src.services.payment_webhook_event import PaymentWebhookEventService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService

GatewayInstanceGetter = Callable[[PaymentGatewayType], Awaitable[BasePaymentGateway]]
PaymentLifecycleHandler = Callable[[UUID], Awaitable[None]]


class PaymentCreationUseCase:
    def __init__(
        self,
        *,
        config: AppConfig,
        bot: Bot,
        translator_hub: TranslatorHub,
        uow: UnitOfWork,
        transaction_service: TransactionService,
        settings_service: SettingsService,
        get_gateway_instance: GatewayInstanceGetter,
    ) -> None:
        self.config = config
        self.bot = bot
        self.translator_hub = translator_hub
        self.uow = uow
        self.transaction_service = transaction_service
        self.settings_service = settings_service
        self.get_gateway_instance = get_gateway_instance
        self._bot_username: str | None = None

    async def create_payment(
        self,
        *,
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
        gateway_instance = await self.get_gateway_instance(gateway_type)
        mini_app_url: str | None = None
        bot_username: str | None = None
        if channel == PurchaseChannel.TELEGRAM:
            settings = await self.settings_service.get()
            mini_app_url, _ = resolve_bot_menu_url(bot_menu=settings.bot_menu, config=self.config)
            bot_username = await self._get_bot_username()

        success_redirect_url, fail_redirect_url = sanitize_payment_redirect_urls_for_channel(
            channel=channel,
            config=self.config,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
            mini_app_url=mini_app_url,
            bot_username=bot_username,
        )

        if channel == PurchaseChannel.WEB and (
            success_redirect_url is None or fail_redirect_url is None
        ):
            (
                default_success_redirect_url,
                default_fail_redirect_url,
            ) = build_web_payment_redirect_urls(
                self.config,
            )
            success_redirect_url = success_redirect_url or default_success_redirect_url
            fail_redirect_url = fail_redirect_url or default_fail_redirect_url
        elif channel == PurchaseChannel.TELEGRAM and (
            success_redirect_url is None or fail_redirect_url is None
        ):
            (
                telegram_success_redirect_url,
                telegram_fail_redirect_url,
            ) = await self._resolve_telegram_payment_redirect_urls()
            success_redirect_url = success_redirect_url or telegram_success_redirect_url
            fail_redirect_url = fail_redirect_url or telegram_fail_redirect_url

        i18n = self.translator_hub.get_translator_by_locale(locale=user.language)
        key, kw = i18n_format_days(plan.duration)

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

        payment_id = uuid.uuid4()
        transaction = TransactionDto(payment_id=payment_id, **transaction_data)
        await self.transaction_service.create(user, transaction)
        await self.uow.commit()

        if pricing.is_free:
            logger.info(f"Payment for user '{user.telegram_id}' not created. Pricing is free")
            return PaymentResult(id=payment_id, url=None)

        payment = await gateway_instance.handle_create_payment(
            amount=pricing.final_amount,
            details=details,
            payment_id=payment_id,
            payment_asset=payment_asset,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
            is_test_payment=False,
        )
        if payment.id != payment_id:
            raise ValueError(
                f"Gateway '{gateway_type.value}' returned unexpected payment id '{payment.id}' "
                f"for pre-created transaction '{payment_id}'"
            )

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

    async def create_test_payment(
        self,
        *,
        user: UserDto,
        gateway_type: PaymentGatewayType,
    ) -> PaymentResult:
        gateway_instance = await self.get_gateway_instance(gateway_type)
        i18n = self.translator_hub.get_translator_by_locale(locale=user.language)
        test_details = i18n.get("test-payment")
        payment_asset = get_default_payment_asset(gateway_type)

        test_pricing = PriceDetailsDto()
        test_plan = PlanSnapshotDto.test()
        payment_id = uuid.uuid4()
        test_transaction = TransactionDto(
            payment_id=payment_id,
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
        await self.uow.commit()

        test_payment = await gateway_instance.handle_create_payment(
            amount=test_pricing.final_amount,
            details=test_details,
            payment_id=payment_id,
            payment_asset=payment_asset,
            is_test_payment=True,
        )
        if test_payment.id != payment_id:
            raise ValueError(
                f"Gateway '{gateway_type.value}' returned unexpected test payment id "
                f"'{test_payment.id}' for pre-created transaction '{payment_id}'"
            )

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

    async def _resolve_telegram_payment_redirect_urls(self) -> tuple[str | None, str | None]:
        settings = await self.settings_service.get()
        mini_app_url, _ = resolve_bot_menu_url(bot_menu=settings.bot_menu, config=self.config)
        bot_username = await self._get_bot_username()
        return self._build_telegram_payment_redirect_urls(
            mini_app_url=mini_app_url,
            bot_username=bot_username,
        )

    @staticmethod
    def _build_telegram_payment_redirect_urls(
        *,
        mini_app_url: str | None,
        bot_username: str | None,
    ) -> tuple[str | None, str | None]:
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


class PaymentFinalizationUseCase:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        transaction_service: TransactionService,
        subscription_service: SubscriptionService,
        referral_service: ReferralService,
        partner_service: PartnerService,
        user_service: UserService,
    ) -> None:
        self.uow = uow
        self.transaction_service = transaction_service
        self.subscription_service = subscription_service
        self.referral_service = referral_service
        self.partner_service = partner_service
        self.user_service = user_service

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
                (
                    "Transaction '{}' for user '{}' already completed; "
                    "resuming idempotent finalization"
                ),
                payment_id,
                transaction_user.telegram_id,
            )
        else:
            transaction.status = TransactionStatus.COMPLETED
            transaction = await self._persist_transaction(transaction)

        logger.info(f"Payment succeeded '{payment_id}' for user '{transaction_user.telegram_id}'")

        if transaction.is_test:
            transaction = await self._dispatch_transaction_side_effect(
                transaction=transaction,
                flag_name="test_notification_sent_at",
                description="test payment notification",
                dispatcher=lambda: send_test_transaction_notification_task.kiq(
                    user=transaction_user
                ),
            )
            return

        transaction = await self._consume_purchase_discount_if_needed(
            transaction=transaction,
            payment_id=payment_id,
        )
        subscription, subscriptions_to_renew = await self._resolve_subscriptions_for_purchase(
            transaction=transaction
        )
        transaction = await self._send_subscription_notification(transaction=transaction)
        transaction = await self._enqueue_subscription_purchase(
            transaction=transaction,
            subscription=subscription,
            subscriptions_to_renew=subscriptions_to_renew,
        )
        await self._run_post_payment_rewards(transaction=transaction)
        logger.debug(f"Called tasks payment for user '{transaction_user.telegram_id}'")

    async def handle_payment_canceled(self, payment_id: UUID) -> None:
        transaction = await self.transaction_service.get(payment_id)
        if transaction is None:
            logger.critical(f"Transaction not found for '{payment_id}'")
            raise LookupError(f"Transaction '{payment_id}' not found")
        if transaction.user is None:
            logger.critical(f"Transaction user not found for '{payment_id}'")
            raise LookupError(f"Transaction '{payment_id}' is missing user context")

        if transaction.status == TransactionStatus.CANCELED:
            logger.warning(
                "Transaction '{}' for user '{}' already canceled",
                payment_id,
                transaction.user.telegram_id,
            )
            return

        transaction.status = TransactionStatus.CANCELED
        await self._persist_transaction(transaction)
        logger.info(f"Payment canceled '{payment_id}' for user '{transaction.user.telegram_id}'")

    async def _persist_transaction(self, transaction: TransactionDto) -> TransactionDto:
        updated_transaction = await self.transaction_service.update(transaction)
        if updated_transaction is None:
            raise LookupError(f"Transaction '{transaction.payment_id}' not found during update")
        await self.uow.commit()
        return updated_transaction

    async def _dispatch_transaction_side_effect(
        self,
        *,
        transaction: TransactionDto,
        flag_name: str,
        description: str,
        dispatcher: Callable[[], Awaitable[None]],
    ) -> TransactionDto:
        if getattr(transaction, flag_name) is not None:
            logger.info(
                "Skipping '{}' for payment '{}' because '{}' is already set",
                description,
                transaction.payment_id,
                flag_name,
            )
            return transaction

        setattr(transaction, flag_name, datetime_now())
        transaction = await self._persist_transaction(transaction)
        try:
            await dispatcher()
        except Exception:
            setattr(transaction, flag_name, None)
            transaction = await self._persist_transaction(transaction)
            logger.exception(
                "Failed to dispatch '{}' for payment '{}'; cleared '{}'",
                description,
                transaction.payment_id,
                flag_name,
            )
            raise

        return transaction

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
        transaction_user = PaymentFinalizationUseCase._require_transaction_user(transaction)
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

    async def _send_subscription_notification(
        self,
        *,
        transaction: TransactionDto,
    ) -> TransactionDto:
        transaction_user = self._require_transaction_user(transaction)
        i18n_key = self._get_purchase_notification_key(transaction.purchase_type)
        return await self._dispatch_transaction_side_effect(
            transaction=transaction,
            flag_name="subscription_notification_sent_at",
            description="subscription notification",
            dispatcher=lambda: send_system_notification_task.kiq(
                ntf_type=SystemNotificationType.SUBSCRIPTION,
                payload=MessagePayload.not_deleted(
                    i18n_key=i18n_key,
                    i18n_kwargs=self._build_subscription_i18n_kwargs(transaction),
                    reply_markup=get_user_keyboard(transaction_user.telegram_id),
                ),
            ),
        )

    async def _enqueue_subscription_purchase(
        self,
        *,
        transaction: TransactionDto,
        subscription: SubscriptionDto | None,
        subscriptions_to_renew: list[SubscriptionDto],
    ) -> TransactionDto:
        return await self._dispatch_transaction_side_effect(
            transaction=transaction,
            flag_name="subscription_purchase_enqueued_at",
            description="subscription purchase task",
            dispatcher=lambda: purchase_subscription_task.kiq(
                transaction,
                subscription,
                subscriptions_to_renew=(
                    subscriptions_to_renew if len(subscriptions_to_renew) > 1 else None
                ),
            ),
        )

    async def _run_post_payment_rewards(self, *, transaction: TransactionDto) -> None:
        transaction_user = self._require_transaction_user(transaction)
        if transaction.pricing.is_free or transaction.id is None:
            return

        await self.referral_service.assign_referral_rewards(transaction=transaction)
        await self.partner_service.process_partner_earning(
            payer_user_id=transaction_user.telegram_id,
            payment_amount=transaction.pricing.final_amount,
            gateway_type=transaction.gateway_type,
            source_transaction_id=transaction.id,
        )

    async def _consume_purchase_discount_if_needed(
        self,
        *,
        transaction: TransactionDto,
        payment_id: UUID,
    ) -> TransactionDto:
        transaction_user = self._require_transaction_user(transaction)
        if (
            transaction.discount_consumed_at is not None
            or transaction.pricing.is_free
            or transaction.id is None
        ):
            return transaction

        if (
            transaction.pricing.discount_source != DiscountSource.PURCHASE
            or transaction.pricing.discount_percent <= 0
        ):
            transaction.discount_consumed_at = datetime_now()
            return await self._persist_transaction(transaction)

        current_user = await self.user_service.get(transaction_user.telegram_id)
        if not current_user:
            logger.warning(
                "Cannot consume purchase discount: user '{}' not found",
                transaction_user.telegram_id,
            )
            return transaction

        current_discount = max(current_user.purchase_discount or 0, 0)
        used_discount = min(max(transaction.pricing.discount_percent, 0), 100)
        new_purchase_discount = max(current_discount - used_discount, 0)

        if new_purchase_discount != current_discount:
            await self.user_service.set_purchase_discount(
                user=current_user,
                discount=new_purchase_discount,
            )
            transaction.discount_consumed_at = datetime_now()
            transaction = await self._persist_transaction(transaction)
            logger.info(
                "Consumed purchase discount for user '{}': {}% -> {}% (used {}% from payment '{}')",
                current_user.telegram_id,
                current_discount,
                new_purchase_discount,
                used_discount,
                payment_id,
            )
            return transaction

        transaction.discount_consumed_at = datetime_now()
        transaction = await self._persist_transaction(transaction)
        logger.info(
            "Purchase discount unchanged for user '{}': remains {}% (used {}% from payment '{}')",
            current_user.telegram_id,
            current_discount,
            used_discount,
            payment_id,
        )
        return transaction


class PlategaRecoveryUseCase:
    def __init__(
        self,
        *,
        payment_webhook_event_service: PaymentWebhookEventService,
        transaction_service: TransactionService,
        get_gateway_instance: GatewayInstanceGetter,
        handle_payment_succeeded: PaymentLifecycleHandler,
        handle_payment_canceled: PaymentLifecycleHandler,
    ) -> None:
        self.payment_webhook_event_service = payment_webhook_event_service
        self.transaction_service = transaction_service
        self.get_gateway_instance = get_gateway_instance
        self.handle_payment_succeeded = handle_payment_succeeded
        self.handle_payment_canceled = handle_payment_canceled

    async def recover_stuck_platega_payments(self, *, limit: int = 100) -> int:
        orphan_events = await self.payment_webhook_event_service.get_platega_orphan_events(
            limit=limit
        )
        if not orphan_events:
            logger.debug("No legacy Platega webhook events require recovery")
            return 0

        gateway_instance = await self.get_gateway_instance(PaymentGatewayType.PLATEGA)
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

        if receive_result.already_in_flight:
            emit_counter(
                "payment_gateway_platega_recovery_total",
                result="already_in_flight",
            )
            logger.info(
                (
                    "Skipping Platega recovery because payment webhook is already in flight. "
                    "external_transaction_id='{}' payment_id='{}'"
                ),
                external_transaction_id,
                internal_payment_id,
            )
            return False

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
