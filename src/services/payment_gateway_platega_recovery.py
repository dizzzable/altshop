from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from src.core.enums import PaymentGatewayType, TransactionStatus
from src.core.observability import emit_counter
from src.infrastructure.database.models.sql import PaymentWebhookEvent
from src.infrastructure.payment_gateways.platega import (
    PlategaGateway,
    PlategaTransactionNotFoundError,
    PlategaWebhookResolutionError,
)

if TYPE_CHECKING:
    from .payment_gateway import PaymentGatewayService


async def recover_stuck_platega_payments(
    service: PaymentGatewayService,
    *,
    limit: int = 100,
) -> int:
    orphan_events = await service.payment_webhook_event_service.get_platega_orphan_events(
        limit=limit
    )
    if not orphan_events:
        return 0

    gateway_instance = await service._get_gateway_instance(PaymentGatewayType.PLATEGA)
    if not isinstance(gateway_instance, PlategaGateway):
        raise TypeError("PLATEGA gateway instance must be PlategaGateway")

    recovered_count = 0
    for event in orphan_events:
        if await service._recover_single_platega_event(
            gateway_instance=gateway_instance,
            event=event,
        ):
            recovered_count += 1

    return recovered_count


async def _recover_single_platega_event(  # noqa: C901
    service: PaymentGatewayService,
    *,
    gateway_instance: PlategaGateway,
    event: PaymentWebhookEvent,
) -> bool:
    external_transaction_id = event.payment_id

    try:
        transaction_details = await gateway_instance.get_transaction(str(external_transaction_id))
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
        await service.payment_webhook_event_service.mark_reconcile_failed(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=external_transaction_id,
            diagnostic=diagnostic,
        )
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="remote_transaction_missing",
        )
        return False
    except PlategaWebhookResolutionError as exception:
        diagnostic = str(exception)
        await service.payment_webhook_event_service.mark_reconcile_failed(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=external_transaction_id,
            diagnostic=diagnostic,
        )
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="reconcile_failed",
        )
        return False
    except Exception:
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="fetch_failed",
        )
        return False

    if resolved_status == TransactionStatus.PENDING:
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="pending",
        )
        return False

    transaction = await service.transaction_service.get(internal_payment_id)
    if transaction is None:
        diagnostic = f"Resolved internal payment UUID is missing locally: {internal_payment_id}"
        await service.payment_webhook_event_service.mark_reconcile_failed(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=external_transaction_id,
            diagnostic=diagnostic,
        )
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="local_transaction_missing",
        )
        return False

    if transaction.is_completed or transaction.status == TransactionStatus.CANCELED:
        await service.payment_webhook_event_service.mark_reconciled(
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
    receive_result = await service.payment_webhook_event_service.record_received(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=internal_payment_id,
        payload_hash=payload_hash,
    )

    if receive_result.already_processed:
        await service.payment_webhook_event_service.mark_reconciled(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=external_transaction_id,
            diagnostic=f"already_processed:{internal_payment_id}",
        )
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="already_processed",
        )
        return True

    await service.payment_webhook_event_service.mark_processing(
        gateway_type=PaymentGatewayType.PLATEGA.value,
        payment_id=internal_payment_id,
    )
    try:
        if resolved_status == TransactionStatus.COMPLETED:
            await service.handle_payment_succeeded(internal_payment_id)
        else:
            await service.handle_payment_canceled(internal_payment_id)
        await service.payment_webhook_event_service.mark_processed(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=internal_payment_id,
        )
        await service.payment_webhook_event_service.mark_reconciled(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=external_transaction_id,
            diagnostic=f"recovered_to:{internal_payment_id}",
        )
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="recovered",
        )
        return True
    except Exception as exception:
        await service.payment_webhook_event_service.mark_failed(
            gateway_type=PaymentGatewayType.PLATEGA.value,
            payment_id=internal_payment_id,
            error_message=f"recovery_failed: {exception}",
        )
        if isinstance(exception, LookupError):
            await service.payment_webhook_event_service.mark_reconcile_failed(
                gateway_type=PaymentGatewayType.PLATEGA.value,
                payment_id=external_transaction_id,
                diagnostic=f"processing_lookup_failed:{exception}",
            )
        emit_counter(
            "payment_gateway_platega_recovery_total",
            result="processing_failed",
        )
        return False
