from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from src.bot.keyboards import get_user_keyboard
from src.core.enums import (
    DiscountSource,
    MessageEffect,
    PurchaseType,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.system_events import build_system_event_payload
from src.infrastructure.database.models.dto import SubscriptionDto, TransactionDto
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.taskiq.tasks.notifications import (
    send_system_notification_task,
    send_test_transaction_notification_task,
)
from src.infrastructure.taskiq.tasks.subscriptions import purchase_subscription_task

if TYPE_CHECKING:
    from .payment_gateway import PaymentGatewayService


def _require_transaction_user(
    _service: PaymentGatewayService | None,
    transaction: TransactionDto,
) -> BaseUserDto:
    if transaction.user is None:
        raise ValueError(f"Transaction '{transaction.payment_id}' is missing user context")
    return transaction.user


async def _resolve_single_renewal_subscription(
    service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
    subscription_id: int,
    source_label: str,
) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
    transaction_user = service._require_transaction_user(transaction)
    subscription = await service.subscription_service.get(subscription_id)
    if subscription:
        return subscription, [subscription]

    fallback = await service.subscription_service.get_current(transaction_user.telegram_id)
    return fallback, [fallback] if fallback else []


async def _resolve_multiple_renewal_subscriptions(
    service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
    transaction_user = service._require_transaction_user(transaction)
    renew_ids = transaction.renew_subscription_ids or []
    subscriptions_to_renew: list[SubscriptionDto] = []
    for subscription_id in renew_ids:
        candidate = await service.subscription_service.get(subscription_id)
        if candidate:
            subscriptions_to_renew.append(candidate)

    if subscriptions_to_renew:
        return subscriptions_to_renew[0], subscriptions_to_renew

    fallback = await service.subscription_service.get_current(transaction_user.telegram_id)
    return fallback, [fallback] if fallback else []


async def _resolve_subscriptions_for_purchase(
    service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
) -> tuple[SubscriptionDto | None, list[SubscriptionDto]]:
    transaction_user = service._require_transaction_user(transaction)
    if transaction.purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        return None, []

    if transaction.renew_subscription_ids and len(transaction.renew_subscription_ids) > 1:
        return await service._resolve_multiple_renewal_subscriptions(transaction=transaction)

    if transaction.renew_subscription_id:
        return await service._resolve_single_renewal_subscription(
            transaction=transaction,
            subscription_id=transaction.renew_subscription_id,
            source_label="renew_subscription_id",
        )

    if transaction.renew_subscription_ids and len(transaction.renew_subscription_ids) == 1:
        return await service._resolve_single_renewal_subscription(
            transaction=transaction,
            subscription_id=transaction.renew_subscription_ids[0],
            source_label="renew_subscription_ids[0]",
        )

    fallback = await service.subscription_service.get_current(transaction_user.telegram_id)
    return fallback, [fallback] if fallback else []


async def _build_subscription_i18n_kwargs(
    service: PaymentGatewayService,
    transaction: TransactionDto,
) -> dict[str, object]:
    transaction_user = service._require_transaction_user(transaction)
    renew_subscription_ids = getattr(transaction, "renew_subscription_ids", None) or []
    renew_subscription_id = getattr(transaction, "renew_subscription_id", None)
    subscription_ids = renew_subscription_ids or (
        [renew_subscription_id] if renew_subscription_id else []
    )
    source_plan_name: str | bool = False
    source_subscription_id: str | bool = False
    if renew_subscription_id:
        source_subscription = await service.subscription_service.get(renew_subscription_id)
        if source_subscription is not None:
            source_plan_name = source_subscription.plan.name
            source_subscription_id = (
                str(source_subscription.id) if source_subscription.id is not None else False
            )

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
        "purchase_channel": getattr(
            getattr(transaction, "channel", None),
            "value",
            str(getattr(transaction, "channel", False))
            if getattr(transaction, "channel", None)
            else False,
        ),
        "subscription_ids": ", ".join(str(subscription_id) for subscription_id in subscription_ids)
        or False,
        "source_plan_name": source_plan_name,
        "source_subscription_id": source_subscription_id,
    }


async def _send_subscription_notification(
    service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
) -> None:
    transaction_user = service._require_transaction_user(transaction)
    i18n_key = service._get_purchase_notification_key(transaction.purchase_type)
    i18n_kwargs = await service._build_subscription_i18n_kwargs(transaction)
    extra_i18n_kwargs: dict[str, object] = {}

    await cast(Any, send_system_notification_task).kiq(
        ntf_type=SystemNotificationType.SUBSCRIPTION,
        payload=build_system_event_payload(
            i18n_key=i18n_key,
            i18n_kwargs={**i18n_kwargs, **extra_i18n_kwargs},
            severity="INFO",
            event_source="services.payment_gateway",
            entry_surface=(
                "WEB" if str(i18n_kwargs.get("purchase_channel")) == "WEB" else "BOT"
            ),
            operation=f"subscription_{transaction.purchase_type.value.lower()}",
            purchase_channel=str(i18n_kwargs.get("purchase_channel") or ""),
            impact="A subscription payment flow reached the successful notification stage.",
            operator_hint=(
                "Check the payment, user, and plan blocks if the "
                "purchase outcome looks inconsistent."
            ),
            reply_markup=get_user_keyboard(transaction_user.telegram_id),
            message_effect=MessageEffect.CONFETTI,
        ),
    )


async def _enqueue_subscription_purchase(
    _service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
    subscription: SubscriptionDto | None,
    subscriptions_to_renew: list[SubscriptionDto],
) -> None:
    await cast(Any, purchase_subscription_task).kiq(
        transaction,
        subscription,
        subscriptions_to_renew=(
            subscriptions_to_renew if len(subscriptions_to_renew) > 1 else None
        ),
    )


async def _run_post_payment_rewards(
    service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
) -> None:
    transaction_user = service._require_transaction_user(transaction)
    if transaction.pricing.is_free:
        return

    await service.referral_service.assign_referral_rewards(transaction=transaction)
    await service.partner_service.process_partner_earning(
        payer_user_id=transaction_user.telegram_id,
        payment_amount=transaction.pricing.final_amount,
        gateway_type=transaction.gateway_type,
    )


async def handle_payment_succeeded(
    service: PaymentGatewayService,
    payment_id: UUID,
) -> None:
    transaction = await service.transaction_service.get(payment_id)

    if transaction is None:
        raise LookupError(f"Transaction '{payment_id}' not found")
    if transaction.user is None:
        raise LookupError(f"Transaction '{payment_id}' is missing user context")

    if transaction.is_completed:
        return

    transaction.status = TransactionStatus.COMPLETED
    await service.transaction_service.update(transaction)

    transaction_user = transaction.user
    if transaction.is_test:
        await cast(Any, send_test_transaction_notification_task).kiq(user=transaction_user)
        return

    await service._consume_purchase_discount_if_needed(
        transaction=transaction,
        payment_id=payment_id,
    )
    subscription, subscriptions_to_renew = await service._resolve_subscriptions_for_purchase(
        transaction=transaction
    )
    await service._send_subscription_notification(transaction=transaction)
    await service._enqueue_subscription_purchase(
        transaction=transaction,
        subscription=subscription,
        subscriptions_to_renew=subscriptions_to_renew,
    )
    await service._run_post_payment_rewards(transaction=transaction)


async def _consume_purchase_discount_if_needed(
    service: PaymentGatewayService,
    *,
    transaction: TransactionDto,
    payment_id: UUID,
) -> None:
    transaction_user = service._require_transaction_user(transaction)
    if (
        transaction.pricing.discount_source != DiscountSource.PURCHASE
        or transaction.pricing.discount_percent <= 0
    ):
        return

    current_user = await service.user_service.get(transaction_user.telegram_id)
    if not current_user:
        return

    current_discount = max(current_user.purchase_discount or 0, 0)
    used_discount = min(max(transaction.pricing.discount_percent, 0), 100)
    new_purchase_discount = max(current_discount - used_discount, 0)

    if new_purchase_discount != current_discount:
        await service.user_service.set_purchase_discount(
            user=current_user,
            discount=new_purchase_discount,
        )


async def handle_payment_canceled(
    service: PaymentGatewayService,
    payment_id: UUID,
) -> None:
    transaction = await service.transaction_service.get(payment_id)

    if transaction is None:
        raise LookupError(f"Transaction '{payment_id}' not found")
    if transaction.user is None:
        raise LookupError(f"Transaction '{payment_id}' is missing user context")

    transaction.status = TransactionStatus.CANCELED
    await service.transaction_service.update(transaction)
