from __future__ import annotations

from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import (
    CryptoAsset,
    Currency,
    DeviceType,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
)
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
    TbankGatewaySettingsDto,
    UserDto,
    WataGatewaySettingsDto,
    YookassaGatewaySettingsDto,
    YoomoneyGatewaySettingsDto,
    normalize_platega_payment_method,
)
from src.infrastructure.database.models.sql import PaymentGateway
from src.infrastructure.payment_gateways import BasePaymentGateway, PaymentGatewayFactory
from src.infrastructure.redis import RedisRepository
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .base import BaseService
from .payment_gateway_use_cases import (
    PaymentCreationUseCase,
    PaymentFinalizationUseCase,
    PlategaRecoveryUseCase,
)
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

        self.payment_creation_use_case = PaymentCreationUseCase(
            config=config,
            bot=bot,
            translator_hub=translator_hub,
            uow=uow,
            transaction_service=transaction_service,
            settings_service=settings_service,
            get_gateway_instance=lambda gateway_type: self._get_gateway_instance(gateway_type),
        )
        self.payment_finalization_use_case = PaymentFinalizationUseCase(
            uow=uow,
            transaction_service=transaction_service,
            subscription_service=subscription_service,
            referral_service=referral_service,
            partner_service=partner_service,
            user_service=user_service,
        )
        self.platega_recovery_use_case = PlategaRecoveryUseCase(
            payment_webhook_event_service=payment_webhook_event_service,
            transaction_service=transaction_service,
            get_gateway_instance=lambda gateway_type: self._get_gateway_instance(gateway_type),
            handle_payment_succeeded=lambda payment_id: self.handle_payment_succeeded(payment_id),
            handle_payment_canceled=lambda payment_id: self.handle_payment_canceled(payment_id),
        )

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
                    logger.warning(f"Unhandled payment gateway type '{gateway_type}' - skipping")
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
            await self.uow.repository.gateways.create(db_payment_gateway)
            logger.info(f"Payment gateway '{gateway_type}' created")

    async def normalize_gateway_settings(self) -> None:
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
        db_gateways.sort(key=lambda gateway: gateway.order_index)

        index = next((i for i, gateway in enumerate(db_gateways) if gateway.id == gateway_id), None)
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

        for order_index, gateway in enumerate(db_gateways, start=1):
            gateway.order_index = order_index

        logger.info(f"Payment gateway '{gateway_id}' reorder successfully")
        return True

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
        return await self.payment_creation_use_case.create_payment(
            user=user,
            plan=plan,
            pricing=pricing,
            purchase_type=purchase_type,
            gateway_type=gateway_type,
            payment_asset=payment_asset,
            renew_subscription_id=renew_subscription_id,
            renew_subscription_ids=renew_subscription_ids,
            device_types=device_types,
            channel=channel,
            success_redirect_url=success_redirect_url,
            fail_redirect_url=fail_redirect_url,
        )

    async def create_test_payment(
        self,
        user: UserDto,
        gateway_type: PaymentGatewayType,
    ) -> PaymentResult:
        return await self.payment_creation_use_case.create_test_payment(
            user=user,
            gateway_type=gateway_type,
        )

    async def handle_payment_succeeded(self, payment_id: UUID) -> None:
        await self.payment_finalization_use_case.handle_payment_succeeded(payment_id)

    async def handle_payment_canceled(self, payment_id: UUID) -> None:
        await self.payment_finalization_use_case.handle_payment_canceled(payment_id)

    async def recover_stuck_platega_payments(self, *, limit: int = 100) -> int:
        return await self.platega_recovery_use_case.recover_stuck_platega_payments(limit=limit)

    async def _get_gateway_instance(self, gateway_type: PaymentGatewayType) -> BasePaymentGateway:
        logger.debug(f"Creating gateway instance for type '{gateway_type}'")
        gateway = await self.get_by_type(gateway_type)
        if not gateway:
            raise ValueError(f"Payment gateway of type '{gateway_type}' not found")
        return self.payment_gateway_factory(gateway)
