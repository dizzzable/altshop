from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.core.enums import PaymentGatewayType, TransactionStatus
from src.infrastructure.taskiq.broker import broker
from src.services.payment_gateway import PaymentGatewayService
from src.services.payment_webhook_event import PaymentWebhookEventService
from src.services.transaction import TransactionService


@broker.task()
@inject(patch_module=True)
async def handle_payment_transaction_task(
    payment_id: str,
    payment_status: str,
    gateway_type: str,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    payment_webhook_event_service: FromDishka[PaymentWebhookEventService],
) -> None:
    payment_uuid = UUID(payment_id)
    payment_status_enum = TransactionStatus(payment_status)
    gateway_enum = PaymentGatewayType(gateway_type)

    await payment_webhook_event_service.mark_processing(
        gateway_type=gateway_enum.value,
        payment_id=payment_uuid,
    )

    try:
        match payment_status_enum:
            case TransactionStatus.COMPLETED:
                await payment_gateway_service.handle_payment_succeeded(payment_uuid)
            case TransactionStatus.CANCELED:
                await payment_gateway_service.handle_payment_canceled(payment_uuid)
        await payment_webhook_event_service.mark_processed(
            gateway_type=gateway_enum.value,
            payment_id=payment_uuid,
        )
    except Exception as exc:
        await payment_webhook_event_service.mark_failed(
            gateway_type=gateway_enum.value,
            payment_id=payment_uuid,
            error_message=str(exc),
        )
        raise


@broker.task(schedule=[{"cron": "*/30 * * * *"}])
@inject(patch_module=True)
async def cancel_transaction_task(transaction_service: FromDishka[TransactionService]) -> None:
    transactions = await transaction_service.get_by_status(TransactionStatus.PENDING)

    if not transactions:
        logger.debug("No pending transactions found")
        return

    old_transactions = [tx for tx in transactions if tx.has_old]
    logger.debug(f"Found '{len(old_transactions)}' old transactions to cancel")

    for transaction in old_transactions:
        transaction.status = TransactionStatus.CANCELED
        await transaction_service.update(transaction)
        logger.debug(f"Transaction '{transaction.id}' canceled")
