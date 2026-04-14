from __future__ import annotations

from typing import Optional
from uuid import UUID

from dishka.integrations.taskiq import FromDishka, inject
from remnawave import RemnawaveSDK

from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models.dto import SubscriptionDto, TransactionDto, UserDto
from src.infrastructure.taskiq.broker import broker
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_runtime import SubscriptionRuntimeService
from src.services.subscription_trial import SubscriptionTrialService
from src.services.transaction import TransactionService
from src.services.user import UserService

from .subscriptions_lifecycle import (
    _cleanup_expired_subscriptions_task as _cleanup_expired_subscriptions_task_impl,
)
from .subscriptions_lifecycle import (
    _delete_current_subscription_task as _delete_current_subscription_task_impl,
)
from .subscriptions_lifecycle import (
    _refresh_user_subscriptions_runtime_task as _refresh_user_subscriptions_runtime_task_impl,
)
from .subscriptions_lifecycle import (
    _update_status_current_subscription_task as _update_status_current_subscription_task_impl,
)
from .subscriptions_purchase import _purchase_subscription_task as _purchase_subscription_task_impl
from .subscriptions_purchase import _trial_subscription_task as _trial_subscription_task_impl


@broker.task
@inject(patch_module=True)
async def trial_subscription_task(
    user: UserDto,
    subscription_trial_service: FromDishka[SubscriptionTrialService],
) -> None:
    return await _trial_subscription_task_impl(
        user=user,
        subscription_trial_service=subscription_trial_service,
    )


@broker.task
@inject(patch_module=True)
async def purchase_subscription_task(
    transaction: TransactionDto,
    subscription: Optional[SubscriptionDto],
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
    settings_service: FromDishka[SettingsService],
    transaction_service: FromDishka[TransactionService],
    plan_service: FromDishka[PlanService],
    subscriptions_to_renew: Optional[list[SubscriptionDto]] = None,
) -> None:
    return await _purchase_subscription_task_impl(
        transaction=transaction,
        subscription=subscription,
        remnawave_service=remnawave_service,
        subscription_service=subscription_service,
        settings_service=settings_service,
        transaction_service=transaction_service,
        plan_service=plan_service,
        subscriptions_to_renew=subscriptions_to_renew,
    )


@broker.task
@inject(patch_module=True)
async def refresh_user_subscriptions_runtime_task(
    subscription_ids: list[int],
    subscription_runtime_service: FromDishka[SubscriptionRuntimeService],
) -> None:
    return await _refresh_user_subscriptions_runtime_task_impl(
        subscription_ids=subscription_ids,
        subscription_runtime_service=subscription_runtime_service,
    )


@broker.task
@inject(patch_module=True)
async def delete_current_subscription_task(
    user_telegram_id: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    user_remna_id: Optional[UUID] = None,
) -> None:
    return await _delete_current_subscription_task_impl(
        user_telegram_id=user_telegram_id,
        user_service=user_service,
        subscription_service=subscription_service,
        user_remna_id=user_remna_id,
    )


@broker.task
@inject(patch_module=True)
async def update_status_current_subscription_task(
    user_telegram_id: int,
    status: SubscriptionStatus,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    user_remna_id: Optional[UUID] = None,
) -> None:
    return await _update_status_current_subscription_task_impl(
        user_telegram_id=user_telegram_id,
        status=status,
        user_service=user_service,
        subscription_service=subscription_service,
        user_remna_id=user_remna_id,
    )


@broker.task(schedule=[{"cron": "0 3 * * *"}])
@inject(patch_module=True)
async def cleanup_expired_subscriptions_task(
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
) -> None:
    return await _cleanup_expired_subscriptions_task_impl(
        subscription_service=subscription_service,
        remnawave=remnawave,
    )
