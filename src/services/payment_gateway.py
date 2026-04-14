from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import (
    CryptoAsset,
    DeviceType,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
)
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    PaymentGatewayDto,
    PaymentResult,
    PlanSnapshotDto,
    PriceDetailsDto,
    SubscriptionDto,
    TransactionDto,
    TransactionRenewItemDto,
    UserDto,
)
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.infrastructure.payment_gateways import BasePaymentGateway, PaymentGatewayFactory
from src.infrastructure.payment_gateways.platega import PlategaGateway
from src.infrastructure.redis import RedisRepository
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .base import BaseService
from .payment_gateway_catalog import create_default as _create_default_impl
from .payment_gateway_catalog import (
    normalize_gateway_settings as _normalize_gateway_settings_impl,
)
from .payment_gateway_creation import (
    _get_bot_username as _get_bot_username_impl,
)
from .payment_gateway_creation import (
    _get_purchase_notification_key as _get_purchase_notification_key_impl,
)
from .payment_gateway_creation import (
    _resolve_telegram_payment_redirect_urls as _resolve_telegram_payment_redirect_urls_impl,
)
from .payment_gateway_creation import create_payment as _create_payment_impl
from .payment_gateway_creation import create_test_payment as _create_test_payment_impl
from .payment_gateway_lifecycle import (
    _build_subscription_i18n_kwargs as _build_subscription_i18n_kwargs_impl,
)
from .payment_gateway_lifecycle import (
    _consume_purchase_discount_if_needed as _consume_purchase_discount_if_needed_impl,
)
from .payment_gateway_lifecycle import (
    _enqueue_subscription_purchase as _enqueue_subscription_purchase_impl,
)
from .payment_gateway_lifecycle import (
    _require_transaction_user as _require_transaction_user_impl,
)
from .payment_gateway_lifecycle import (
    _resolve_multiple_renewal_subscriptions as _resolve_multiple_renewal_subscriptions_impl,
)
from .payment_gateway_lifecycle import (
    _resolve_single_renewal_subscription as _resolve_single_renewal_subscription_impl,
)
from .payment_gateway_lifecycle import (
    _resolve_subscriptions_for_purchase as _resolve_subscriptions_for_purchase_impl,
)
from .payment_gateway_lifecycle import (
    _run_post_payment_rewards as _run_post_payment_rewards_impl,
)
from .payment_gateway_lifecycle import (
    _send_subscription_notification as _send_subscription_notification_impl,
)
from .payment_gateway_lifecycle import handle_payment_canceled as _handle_payment_canceled_impl
from .payment_gateway_lifecycle import handle_payment_succeeded as _handle_payment_succeeded_impl
from .payment_gateway_platega_recovery import (
    _recover_single_platega_event as _recover_single_platega_event_impl,
)
from .payment_gateway_platega_recovery import (
    recover_stuck_platega_payments as _recover_stuck_platega_payments_impl,
)
from .payment_gateway_registry import filter_active as _filter_active_impl
from .payment_gateway_registry import get as _get_impl
from .payment_gateway_registry import get_all as _get_all_impl
from .payment_gateway_registry import get_by_type as _get_by_type_impl
from .payment_gateway_registry import move_gateway_up as _move_gateway_up_impl
from .payment_gateway_registry import update as _update_impl
from .payment_gateway_runtime import get_gateway_instance as _get_gateway_instance_impl
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

    async def create_default(self) -> None:
        await _create_default_impl(self)

    async def normalize_gateway_settings(self) -> None:
        await _normalize_gateway_settings_impl(self)

    async def get(self, gateway_id: int) -> Optional[PaymentGatewayDto]:
        return await _get_impl(self, gateway_id)

    async def get_by_type(self, gateway_type: PaymentGatewayType) -> Optional[PaymentGatewayDto]:
        return await _get_by_type_impl(self, gateway_type)

    async def get_all(self, sorted: bool = False) -> list[PaymentGatewayDto]:
        return await _get_all_impl(self, sorted=sorted)

    async def update(self, gateway: PaymentGatewayDto) -> Optional[PaymentGatewayDto]:
        return await _update_impl(self, gateway)

    async def filter_active(self, is_active: bool = True) -> list[PaymentGatewayDto]:
        return await _filter_active_impl(self, is_active=is_active)

    async def move_gateway_up(self, gateway_id: int) -> bool:
        return await _move_gateway_up_impl(self, gateway_id)

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
        renew_items: Optional[list[TransactionRenewItemDto]] = None,
        device_types: Optional[list[DeviceType]] = None,
        channel: PurchaseChannel = PurchaseChannel.TELEGRAM,
        success_redirect_url: Optional[str] = None,
        fail_redirect_url: Optional[str] = None,
    ) -> PaymentResult:
        return await _create_payment_impl(
            self,
            user,
            plan,
            pricing,
            purchase_type,
            gateway_type,
            payment_asset=payment_asset,
            renew_subscription_id=renew_subscription_id,
            renew_subscription_ids=renew_subscription_ids,
            renew_items=renew_items,
            device_types=device_types,
            channel=channel,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
        )

    async def _resolve_telegram_payment_redirect_urls(self) -> tuple[str | None, str | None]:
        return await _resolve_telegram_payment_redirect_urls_impl(self)

    async def _get_bot_username(self) -> str | None:
        return await _get_bot_username_impl(self)

    async def create_test_payment(
        self,
        user: UserDto,
        gateway_type: PaymentGatewayType,
    ) -> PaymentResult:
        return await _create_test_payment_impl(self, user, gateway_type)

    @staticmethod
    def _get_purchase_notification_key(purchase_type: PurchaseType) -> str:
        return _get_purchase_notification_key_impl(None, purchase_type)

    @staticmethod
    def _require_transaction_user(transaction: TransactionDto) -> BaseUserDto:
        return _require_transaction_user_impl(None, transaction)

    async def _resolve_single_renewal_subscription(
        self,
        *,
        transaction: TransactionDto,
        subscription_id: int,
        source_label: str,
    ) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
        return await _resolve_single_renewal_subscription_impl(
            self,
            transaction=transaction,
            subscription_id=subscription_id,
            source_label=source_label,
        )

    async def _resolve_multiple_renewal_subscriptions(
        self,
        *,
        transaction: TransactionDto,
    ) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
        return await _resolve_multiple_renewal_subscriptions_impl(
            self,
            transaction=transaction,
        )

    async def _resolve_subscriptions_for_purchase(
        self,
        *,
        transaction: TransactionDto,
    ) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
        return await _resolve_subscriptions_for_purchase_impl(
            self,
            transaction=transaction,
        )

    async def _build_subscription_i18n_kwargs(
        self, transaction: TransactionDto
    ) -> dict[str, object]:
        return await _build_subscription_i18n_kwargs_impl(self, transaction)

    async def _send_subscription_notification(self, *, transaction: TransactionDto) -> None:
        await _send_subscription_notification_impl(
            self,
            transaction=transaction,
        )

    async def _enqueue_subscription_purchase(
        self,
        *,
        transaction: TransactionDto,
        subscription: SubscriptionDto | None,
        subscriptions_to_renew: list[SubscriptionDto],
    ) -> None:
        await _enqueue_subscription_purchase_impl(
            self,
            transaction=transaction,
            subscription=subscription,
            subscriptions_to_renew=subscriptions_to_renew,
        )

    async def _run_post_payment_rewards(self, *, transaction: TransactionDto) -> None:
        await _run_post_payment_rewards_impl(
            self,
            transaction=transaction,
        )

    async def handle_payment_succeeded(self, payment_id: UUID) -> None:
        await _handle_payment_succeeded_impl(self, payment_id)

    async def _consume_purchase_discount_if_needed(
        self,
        *,
        transaction: TransactionDto,
        payment_id: UUID,
    ) -> None:
        await _consume_purchase_discount_if_needed_impl(
            self,
            transaction=transaction,
            payment_id=payment_id,
        )

    async def handle_payment_canceled(self, payment_id: UUID) -> None:
        await _handle_payment_canceled_impl(self, payment_id)

    async def recover_stuck_platega_payments(self, *, limit: int = 100) -> int:
        return await _recover_stuck_platega_payments_impl(self, limit=limit)

    async def _recover_single_platega_event(
        self,
        *,
        gateway_instance: PlategaGateway,
        event: PaymentWebhookEvent,
    ) -> bool:
        return await _recover_single_platega_event_impl(
            self,
            gateway_instance=gateway_instance,
            event=event,
        )

    async def _get_gateway_instance(self, gateway_type: PaymentGatewayType) -> BasePaymentGateway:
        return await _get_gateway_instance_impl(self, gateway_type)
