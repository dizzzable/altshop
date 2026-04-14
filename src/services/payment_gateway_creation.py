from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from src.core.crypto_assets import get_default_payment_asset
from src.core.enums import (
    CryptoAsset,
    DeviceType,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.core.utils.bot_menu import resolve_bot_menu_url
from src.core.utils.formatters import i18n_format_days
from src.core.utils.mini_app_urls import build_telegram_payment_return_url
from src.infrastructure.database.models.dto import (
    PaymentResult,
    PlanSnapshotDto,
    PriceDetailsDto,
    TransactionDto,
    TransactionRenewItemDto,
    UserDto,
)

if TYPE_CHECKING:
    from .payment_gateway import PaymentGatewayService


async def create_payment(
    service: PaymentGatewayService,
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
    gateway_instance = await service._get_gateway_instance(gateway_type)
    if channel == PurchaseChannel.TELEGRAM and (
        success_redirect_url is None or fail_redirect_url is None
    ):
        (
            default_success_redirect_url,
            default_fail_redirect_url,
        ) = await service._resolve_telegram_payment_redirect_urls()
        success_redirect_url = success_redirect_url or default_success_redirect_url
        fail_redirect_url = fail_redirect_url or default_fail_redirect_url

    i18n = service.translator_hub.get_translator_by_locale(locale=user.language)
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
        "renew_items": renew_items,
        "device_types": device_types,
    }

    if pricing.is_free:
        payment_id = uuid.uuid4()
        transaction = TransactionDto(payment_id=payment_id, **transaction_data)
        await service.transaction_service.create(user, transaction)
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
    await service.transaction_service.create(user, transaction)
    return payment


async def _resolve_telegram_payment_redirect_urls(
    service: PaymentGatewayService,
) -> tuple[str | None, str | None]:
    settings = await service.settings_service.get()
    mini_app_url, _ = resolve_bot_menu_url(bot_menu=settings.bot_menu, config=service.config)
    bot_username = await service._get_bot_username()
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


async def _get_bot_username(service: PaymentGatewayService) -> str | None:
    if service._bot_username is None:
        bot_info = await service.bot.get_me()
        service._bot_username = (bot_info.username or "").strip().lstrip("@") or None
    return service._bot_username


async def create_test_payment(
    service: PaymentGatewayService,
    user: UserDto,
    gateway_type: PaymentGatewayType,
) -> PaymentResult:
    gateway_instance = await service._get_gateway_instance(gateway_type)
    i18n = service.translator_hub.get_translator_by_locale(locale=user.language)
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
    await service.transaction_service.create(user, test_transaction)
    return test_payment


def _get_purchase_notification_key(
    _service: PaymentGatewayService | None,
    purchase_type: PurchaseType,
) -> str:
    i18n_keys = {
        PurchaseType.NEW: "ntf-event-subscription-new",
        PurchaseType.RENEW: "ntf-event-subscription-renew",
        PurchaseType.UPGRADE: "ntf-event-subscription-upgrade",
        PurchaseType.ADDITIONAL: "ntf-event-subscription-additional",
    }
    return i18n_keys[purchase_type]
