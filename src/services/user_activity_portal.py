from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.infrastructure.database.models.dto import (
    PromocodeActivationBaseDto,
    TransactionDto,
    UserDto,
    UserNotificationEventDto,
)

from .promocode import PromocodeService
from .transaction import TransactionService
from .user_notification_event import UserNotificationEventService


@dataclass(slots=True, frozen=True)
class TransactionPricingSnapshot:
    original_amount: float
    discount_percent: int
    final_amount: float


@dataclass(slots=True, frozen=True)
class TransactionRenewItemSnapshot:
    subscription_id: int
    renew_mode: str
    plan: dict[str, Any]
    pricing: TransactionPricingSnapshot


@dataclass(slots=True, frozen=True)
class TransactionHistoryItemSnapshot:
    payment_id: str
    user_telegram_id: int
    status: str
    purchase_type: str
    channel: str | None
    gateway_type: str
    pricing: TransactionPricingSnapshot
    currency: str
    payment_asset: str | None
    plan: dict[str, Any]
    renew_subscription_id: int | None
    renew_subscription_ids: list[int] | None
    renew_items: list[TransactionRenewItemSnapshot] | None
    device_types: list[str] | None
    is_test: bool
    created_at: str
    updated_at: str


@dataclass(slots=True, frozen=True)
class TransactionHistoryPageSnapshot:
    transactions: list[TransactionHistoryItemSnapshot]
    total: int
    page: int
    limit: int


@dataclass(slots=True, frozen=True)
class UserNotificationItemSnapshot:
    id: int
    type: str
    title: str
    message: str
    is_read: bool
    read_at: str | None
    created_at: str


@dataclass(slots=True, frozen=True)
class UserNotificationPageSnapshot:
    notifications: list[UserNotificationItemSnapshot]
    total: int
    page: int
    limit: int
    unread: int


@dataclass(slots=True, frozen=True)
class PromocodeActivationRewardSnapshot:
    type: str
    value: int


@dataclass(slots=True, frozen=True)
class PromocodeActivationHistoryItemSnapshot:
    id: int
    code: str
    reward: PromocodeActivationRewardSnapshot
    target_subscription_id: int | None
    activated_at: str


@dataclass(slots=True, frozen=True)
class PromocodeActivationHistoryPageSnapshot:
    activations: list[PromocodeActivationHistoryItemSnapshot]
    total: int
    page: int
    limit: int


class UserActivityPortalService:
    def __init__(
        self,
        transaction_service: TransactionService,
        user_notification_event_service: UserNotificationEventService,
        promocode_service: PromocodeService,
    ) -> None:
        self.transaction_service = transaction_service
        self.user_notification_event_service = user_notification_event_service
        self.promocode_service = promocode_service

    async def list_transactions(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> TransactionHistoryPageSnapshot:
        offset = (page - 1) * limit
        transactions = await self.transaction_service.get_by_user_paginated(
            current_user.telegram_id,
            limit=limit,
            offset=offset,
        )
        total = await self.transaction_service.count_by_user(current_user.telegram_id)
        return TransactionHistoryPageSnapshot(
            transactions=[
                self._build_transaction_item(
                    transaction,
                    fallback_user_telegram_id=current_user.telegram_id,
                )
                for transaction in transactions
            ],
            total=total,
            page=page,
            limit=limit,
        )

    async def list_notifications(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> UserNotificationPageSnapshot:
        events, total, unread = await self.user_notification_event_service.list_by_user(
            user_telegram_id=current_user.telegram_id,
            page=page,
            limit=limit,
        )
        return UserNotificationPageSnapshot(
            notifications=[self._build_notification_item(event) for event in events],
            total=total,
            page=page,
            limit=limit,
            unread=unread,
        )

    async def get_notifications_unread_count(self, *, current_user: UserDto) -> int:
        return await self.user_notification_event_service.count_unread(
            user_telegram_id=current_user.telegram_id
        )

    async def mark_notification_read(
        self,
        *,
        current_user: UserDto,
        notification_id: int,
    ) -> int:
        updated = await self.user_notification_event_service.mark_read(
            notification_id=notification_id,
            user_telegram_id=current_user.telegram_id,
            read_source="WEB",
        )
        return 1 if updated else 0

    async def mark_all_notifications_read(self, *, current_user: UserDto) -> int:
        return await self.user_notification_event_service.mark_all_read(
            user_telegram_id=current_user.telegram_id,
            read_source="WEB",
        )

    async def list_promocode_activations(
        self,
        *,
        current_user: UserDto,
        page: int,
        limit: int,
    ) -> PromocodeActivationHistoryPageSnapshot:
        activations, total = await self.promocode_service.get_user_activation_history(
            current_user.telegram_id,
            page=page,
            limit=limit,
        )
        return PromocodeActivationHistoryPageSnapshot(
            activations=[
                self._build_promocode_activation_item(activation) for activation in activations
            ],
            total=total,
            page=page,
            limit=limit,
        )

    @staticmethod
    def _build_transaction_item(
        transaction: TransactionDto,
        *,
        fallback_user_telegram_id: int,
    ) -> TransactionHistoryItemSnapshot:
        return TransactionHistoryItemSnapshot(
            payment_id=str(transaction.payment_id),
            user_telegram_id=fallback_user_telegram_id,
            status=_serialize_enum_value(transaction.status) or "",
            purchase_type=_serialize_enum_value(transaction.purchase_type) or "",
            channel=_serialize_enum_value(transaction.channel),
            gateway_type=_serialize_enum_value(transaction.gateway_type) or "",
            pricing=TransactionPricingSnapshot(
                original_amount=float(transaction.pricing.original_amount),
                discount_percent=transaction.pricing.discount_percent,
                final_amount=float(transaction.pricing.final_amount),
            ),
            currency=_serialize_enum_value(transaction.currency) or "",
            payment_asset=_serialize_enum_value(transaction.payment_asset),
            plan=transaction.plan.model_dump(mode="json"),
            renew_subscription_id=transaction.renew_subscription_id,
            renew_subscription_ids=transaction.renew_subscription_ids,
            renew_items=(
                [
                    TransactionRenewItemSnapshot(
                        subscription_id=item.subscription_id,
                        renew_mode=_serialize_enum_value(item.renew_mode) or "",
                        plan=item.plan.model_dump(mode="json"),
                        pricing=TransactionPricingSnapshot(
                            original_amount=float(item.pricing.original_amount),
                            discount_percent=item.pricing.discount_percent,
                            final_amount=float(item.pricing.final_amount),
                        ),
                    )
                    for item in transaction.renew_items
                ]
                if transaction.renew_items is not None
                else None
            ),
            device_types=(
                [
                    _serialize_enum_value(device_type) or ""
                    for device_type in transaction.device_types
                ]
                if transaction.device_types is not None
                else None
            ),
            is_test=transaction.is_test,
            created_at=transaction.created_at.isoformat() if transaction.created_at else "",
            updated_at=transaction.updated_at.isoformat() if transaction.updated_at else "",
        )

    @staticmethod
    def _build_notification_item(
        event: UserNotificationEventDto,
    ) -> UserNotificationItemSnapshot:
        notification_type = _serialize_enum_value(event.ntf_type) or ""
        return UserNotificationItemSnapshot(
            id=event.id or 0,
            type=notification_type,
            title=_build_notification_title(notification_type),
            message=event.rendered_text,
            is_read=event.is_read,
            read_at=event.read_at.isoformat() if event.read_at else None,
            created_at=event.created_at.isoformat() if event.created_at else "",
        )

    @staticmethod
    def _build_promocode_activation_item(
        activation: PromocodeActivationBaseDto,
    ) -> PromocodeActivationHistoryItemSnapshot:
        reward_type = _serialize_enum_value(activation.reward_type) or ""
        return PromocodeActivationHistoryItemSnapshot(
            id=activation.id or 0,
            code=activation.promocode_code,
            reward=PromocodeActivationRewardSnapshot(
                type=reward_type,
                value=activation.reward_value,
            ),
            target_subscription_id=activation.target_subscription_id,
            activated_at=activation.activated_at.isoformat() if activation.activated_at else "",
        )


def _serialize_enum_value(value: object | None) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(getattr(value, "value"))
    return str(value)


def _build_notification_title(ntf_type: str) -> str:
    return ntf_type.replace("_", " ").title()
