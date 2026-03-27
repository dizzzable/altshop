from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from src.core.enums import (
    Currency,
    PaymentGatewayType,
    PurchaseChannel,
    PurchaseType,
    TransactionStatus,
)
from src.infrastructure.database.models.dto import PlanSnapshotDto, PriceDetailsDto, TransactionDto
from src.services.user_activity_portal import UserActivityPortalService


def test_build_transaction_item_masks_payment_id() -> None:
    payment_id = uuid4()
    transaction = TransactionDto(
        payment_id=payment_id,
        status=TransactionStatus.PENDING,
        purchase_type=PurchaseType.NEW,
        channel=PurchaseChannel.WEB,
        gateway_type=PaymentGatewayType.MULENPAY,
        pricing=PriceDetailsDto(
            original_amount=Decimal("100"),
            final_amount=Decimal("90"),
        ),
        currency=Currency.RUB,
        plan=PlanSnapshotDto.test(),
    )

    snapshot = UserActivityPortalService._build_transaction_item(
        transaction,
        fallback_user_telegram_id=42,
    )

    assert snapshot.payment_id != str(payment_id)
    assert snapshot.payment_id.startswith(str(payment_id)[:8])
    assert snapshot.payment_id.endswith(str(payment_id)[-8:])
    assert "..." in snapshot.payment_id
