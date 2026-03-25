from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.core.enums import PaymentGatewayType, TransactionStatus
from src.infrastructure.taskiq.broker import broker
from src.services.payment_gateway import PaymentGatewayService
from src.services.payment_webhook_event import PaymentWebhookEventService
from src.services.transaction import TransactionService


def _is_stale_payment_lookup_error(exc: LookupError) -> bool:
    normalized = " ".join(str(exc).split()).lower()
    if not normalized:
        return False
    return "transaction" in normalized and (
        "not found" in normalized or "missing user context" in normalized
    )


def _build_stale_payment_diagnostic(exc: LookupError) -> str:
    return f"stale_after_restore: {str(exc)[:256]}"


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
            case TransactionStatus.PENDING:
                logger.info(
                    "Payment '{}' for gateway '{}' is still pending; waiting for a final webhook",
                    payment_uuid,
                    gateway_enum.value,
                )
                await payment_webhook_event_service.mark_enqueued(
                    gateway_type=gateway_enum.value,
                    payment_id=payment_uuid,
                )
                return
        await payment_webhook_event_service.mark_processed(
            gateway_type=gateway_enum.value,
            payment_id=payment_uuid,
        )
    except LookupError as exc:
        if not _is_stale_payment_lookup_error(exc):
            await payment_webhook_event_service.mark_failed(
                gateway_type=gateway_enum.value,
                payment_id=payment_uuid,
                error_message=str(exc),
            )
            raise

        logger.warning(
            (
                "Skipping stale payment task after restore "
                "for gateway='{}' payment_id='{}' status='{}': {}"
            ),
            gateway_enum.value,
            payment_uuid,
            payment_status_enum.value,
            exc,
        )
        await payment_webhook_event_service.mark_failed(
            gateway_type=gateway_enum.value,
            payment_id=payment_uuid,
            error_message=_build_stale_payment_diagnostic(exc),
        )
        return
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


@broker.task(schedule=[{"cron": "*/15 * * * *"}])
@inject(patch_module=True)
async def recover_platega_webhooks_task(
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    recovered = await payment_gateway_service.recover_stuck_platega_payments(limit=100)
    logger.info("Recovered '{}' stuck Platega webhook events", recovered)
