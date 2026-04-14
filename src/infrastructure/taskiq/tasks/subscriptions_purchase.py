from __future__ import annotations

import traceback
from datetime import timedelta
from typing import Any, Optional, cast

from aiogram.utils.formatting import Text
from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.core.enums import (
    DeviceType,
    PurchaseChannel,
    PurchaseType,
    SubscriptionStatus,
    SystemNotificationType,
    TransactionStatus,
)
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    SubscriptionDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.taskiq.tasks.notifications import (
    send_error_notification_task,
    send_system_notification_task,
)
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_trial import SubscriptionTrialService
from src.services.transaction import TransactionService

from .redirects import (
    redirect_to_failed_subscription_task,
    redirect_to_successed_payment_task,
    redirect_to_successed_trial_task,
)


async def _trial_subscription_task(
    *,
    user: UserDto,
    subscription_trial_service: SubscriptionTrialService,
) -> None:
    logger.info(f"Started trial for user '{user.telegram_id}'")

    try:
        trial_subscription = await subscription_trial_service.create_trial_subscription(
            current_user=user,
            plan_id=None,
            channel=PurchaseChannel.TELEGRAM,
        )
        plan = trial_subscription.plan
        logger.debug(f"Created new trial subscription for user '{user.telegram_id}'")

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.TRIAL_GETTED,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-subscription-trial",
                i18n_kwargs={
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "plan_name": plan.name,
                    "plan_type": plan.type,
                    "plan_traffic_limit": i18n_format_traffic_limit(plan.traffic_limit),
                    "plan_device_limit": i18n_format_device_limit(plan.device_limit),
                    "plan_duration": i18n_format_days(plan.duration),
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )
        await redirect_to_successed_trial_task.kiq(user)
        logger.info(f"Trial subscription task completed successfully for user '{user.telegram_id}'")

    except Exception as exception:
        logger.exception(
            f"Failed to give trial for user '{user.telegram_id}' exception: {exception}"
        )
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": True,
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )

        await redirect_to_failed_subscription_task.kiq(user)


def _resolve_requested_subscription_count(
    *,
    purchase_type: PurchaseType,
    device_types: list[DeviceType],
) -> int:
    if purchase_type not in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        return 1

    return max(1, len(device_types))


def _get_device_type(device_types: list[DeviceType], index: int) -> Optional[DeviceType]:
    if index < 0:
        return None
    if index < len(device_types):
        return device_types[index]
    return None


async def _ensure_subscription_limit_guardrail(
    *,
    purchase_type: PurchaseType,
    requested_subscription_count: int,
    user: UserDto,
    settings_service: SettingsService,
    subscription_service: SubscriptionService,
) -> None:
    if purchase_type not in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        return

    max_subscriptions = await settings_service.get_max_subscriptions_for_user(user)
    if max_subscriptions < 1:
        logger.warning(
            f"Invalid max subscriptions '{max_subscriptions}' for user '{user.telegram_id}', "
            "falling back to 1"
        )
        max_subscriptions = 1

    existing_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
    active_count = len(
        [
            subscription
            for subscription in existing_subscriptions
            if subscription.status != SubscriptionStatus.DELETED
        ]
    )

    if active_count + requested_subscription_count > max_subscriptions:
        raise ValueError(
            f"User '{user.telegram_id}' would exceed maximum subscriptions limit "
            f"({max_subscriptions}). Current: {active_count}, "
            f"Requested new: {requested_subscription_count}"
        )


async def _resolve_created_subscription_url(
    *,
    created_user: Any,
    remnawave_service: RemnawaveService,
    user: UserDto,
    idx: int,
    trial_upgrade: bool = False,
) -> str:
    subscription_url: str | None = getattr(created_user, "subscription_url", None)
    if not subscription_url:
        subscription_url = await remnawave_service.get_subscription_url(created_user.uuid)

    if subscription_url:
        return subscription_url

    if trial_upgrade:
        raise ValueError(
            f"Missing subscription_url for created RemnaUser '{created_user.uuid}' "
            f"(user '{user.telegram_id}', idx={idx}, trial upgrade)"
        )

    raise ValueError(
        f"Missing subscription_url for created RemnaUser '{created_user.uuid}' "
        f"(user '{user.telegram_id}', idx={idx})"
    )


async def _resolve_updated_subscription_url(
    *,
    updated_user: Any,
    remnawave_service: RemnawaveService,
    user: UserDto,
) -> str:
    subscription_url: str | None = getattr(updated_user, "subscription_url", None)
    if not subscription_url:
        subscription_url = await remnawave_service.get_subscription_url(updated_user.uuid)

    if subscription_url:
        return subscription_url

    raise ValueError(
        f"Missing subscription_url for updated RemnaUser '{updated_user.uuid}' "
        f"(user '{user.telegram_id}')"
    )


async def _create_subscription_from_panel(
    *,
    idx: int,
    user: UserDto,
    plan: PlanSnapshotDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
    device_type: Optional[DeviceType],
    trial_upgrade: bool = False,
) -> SubscriptionDto:
    created_user = await remnawave_service.create_user(user, plan)
    subscription_url = await _resolve_created_subscription_url(
        created_user=created_user,
        remnawave_service=remnawave_service,
        user=user,
        idx=idx,
        trial_upgrade=trial_upgrade,
    )

    new_subscription = SubscriptionDto(
        user_remna_id=created_user.uuid,
        status=created_user.status,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=plan.internal_squads,
        external_squad=plan.external_squad,
        expire_at=created_user.expire_at,
        url=subscription_url,
        plan=plan,
        device_type=device_type,
    )
    return await subscription_service.create(user, new_subscription)


async def _create_new_or_additional_subscriptions(
    *,
    purchase_type: PurchaseType,
    requested_subscription_count: int,
    device_types: list[DeviceType],
    user: UserDto,
    plan: PlanSnapshotDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
) -> None:
    created_subscriptions: list[SubscriptionDto] = []

    for idx in range(requested_subscription_count):
        device_type = _get_device_type(device_types, idx)
        created_sub = await _create_subscription_from_panel(
            idx=idx,
            user=user,
            plan=plan,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            device_type=device_type,
        )
        created_subscriptions.append(created_sub)

        if purchase_type == PurchaseType.NEW:
            logger.debug(
                f"Created subscription idx={idx + 1}/{requested_subscription_count} "
                f"for user '{user.telegram_id}' (device_type='{device_type}')"
            )
        else:
            logger.debug(
                f"Created additional subscription idx={idx + 1}/{requested_subscription_count} "
                f"for user '{user.telegram_id}' (device_type='{device_type}')"
            )

    if purchase_type == PurchaseType.NEW:
        logger.info(
            f"Created {len(created_subscriptions)} new subscription(s) "
            f"for user '{user.telegram_id}'"
        )
        return

    logger.info(
        f"Created {len(created_subscriptions)} additional subscription(s) "
        f"for user '{user.telegram_id}'"
    )


async def _renew_one_subscription(
    *,
    subscription: SubscriptionDto,
    target_plan: PlanSnapshotDto,
    user: UserDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
) -> None:
    old_expire = subscription.expire_at
    subscription.expire_at = subscription.expire_at + timedelta(days=target_plan.duration)
    subscription.plan.duration = target_plan.duration

    updated_user = await remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    subscription.expire_at = updated_user.expire_at  # type: ignore[assignment]
    await subscription_service.update(subscription)
    logger.info(
        f"Renewed subscription '{subscription.id}' for user '{user.telegram_id}': "
        f"{old_expire} -> {subscription.expire_at}"
    )


def _uses_same_plan(
    *,
    subscription: SubscriptionDto,
    plan: PlanSnapshotDto,
) -> bool:
    if subscription.plan.id > 0 and plan.id > 0:
        return subscription.plan.id == plan.id

    return (
        subscription.plan.tag == plan.tag
        and subscription.plan.type == plan.type
        and subscription.plan.traffic_limit == plan.traffic_limit
        and subscription.plan.device_limit == plan.device_limit
        and subscription.plan.traffic_limit_strategy == plan.traffic_limit_strategy
        and subscription.plan.internal_squads == plan.internal_squads
        and subscription.plan.external_squad == plan.external_squad
    )


def _get_requested_single_device_type(device_types: list[DeviceType]) -> Optional[DeviceType]:
    return _get_device_type(device_types, 0)


def _apply_plan_snapshot_to_subscription(
    *,
    subscription: SubscriptionDto,
    plan: PlanSnapshotDto,
    device_type: Optional[DeviceType] = None,
) -> None:
    subscription.traffic_limit = plan.traffic_limit
    subscription.device_limit = plan.device_limit
    subscription.internal_squads = plan.internal_squads
    subscription.external_squad = plan.external_squad
    subscription.plan = plan.model_copy(deep=True)

    if device_type is not None:
        subscription.device_type = device_type


async def _replace_plan_on_renew(
    *,
    subscription: SubscriptionDto,
    target_plan: PlanSnapshotDto,
    user: UserDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
) -> None:
    old_expire = subscription.expire_at
    subscription.expire_at = subscription.expire_at + timedelta(days=target_plan.duration)
    _apply_plan_snapshot_to_subscription(subscription=subscription, plan=target_plan)

    updated_user = await remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )
    subscription.status = updated_user.status  # type: ignore[assignment]
    subscription.expire_at = updated_user.expire_at  # type: ignore[assignment]
    subscription.url = await _resolve_updated_subscription_url(
        updated_user=updated_user,
        remnawave_service=remnawave_service,
        user=user,
    )
    await subscription_service.update(subscription)
    logger.info(
        f"Renewed archived subscription '{subscription.id}' with replacement plan "
        f"for user '{user.telegram_id}': {old_expire} -> {subscription.expire_at}"
    )


async def _apply_renew_item(
    *,
    subscription: SubscriptionDto,
    target_plan: PlanSnapshotDto,
    user: UserDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
) -> None:
    if not _uses_same_plan(subscription=subscription, plan=target_plan):
        logger.info(
            f"RENEWAL WITH REPLACEMENT: Updating subscription '{subscription.id}' "
            f"for user '{user.telegram_id}' to plan '{target_plan.name}'"
        )
        await _replace_plan_on_renew(
            subscription=subscription,
            target_plan=target_plan,
            user=user,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
        )
        return

    logger.info(
        f"RENEWAL WITH SAME PLAN: Renewing subscription '{subscription.id}' "
        f"for user '{user.telegram_id}'"
    )
    await _renew_one_subscription(
        subscription=subscription,
        target_plan=target_plan,
        user=user,
        remnawave_service=remnawave_service,
        subscription_service=subscription_service,
    )


async def _process_upgrade_purchase(
    *,
    subscription: Optional[SubscriptionDto],
    device_types: list[DeviceType],
    user: UserDto,
    plan: PlanSnapshotDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
) -> None:
    if not subscription:
        raise ValueError(f"No subscription found for upgrade for user '{user.telegram_id}'")

    updated_user = await remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        plan=plan,
        reset_traffic=True,
    )

    _apply_plan_snapshot_to_subscription(
        subscription=subscription,
        plan=plan,
        device_type=_get_requested_single_device_type(device_types),
    )
    subscription.is_trial = False
    subscription.status = updated_user.status  # type: ignore[assignment]
    subscription.expire_at = updated_user.expire_at  # type: ignore[assignment]
    subscription.url = await _resolve_updated_subscription_url(
        updated_user=updated_user,
        remnawave_service=remnawave_service,
        user=user,
    )
    await subscription_service.update(subscription)
    logger.info(
        f"Upgraded subscription '{subscription.id}' for user '{user.telegram_id}' "
        f"to plan '{plan.name}'"
    )


async def _renew_multiple_subscriptions(
    *,
    subscriptions_to_renew: list[SubscriptionDto],
    transaction: TransactionDto,
    user: UserDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
) -> None:
    logger.info(
        f"MULTIPLE RENEWAL: Renewing {len(subscriptions_to_renew)} subscriptions "
        f"for user '{user.telegram_id}': "
        f"{[subscription.id for subscription in subscriptions_to_renew]}"
    )
    renew_items_by_subscription_id = {
        item.subscription_id: item for item in (transaction.renew_items or [])
    }
    for subscription in subscriptions_to_renew:
        renew_item = renew_items_by_subscription_id.get(subscription.id or 0)
        target_plan = renew_item.plan if renew_item else transaction.plan
        await _apply_renew_item(
            subscription=subscription,
            target_plan=target_plan,
            user=user,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
        )


async def _process_renew_purchase(
    *,
    user: UserDto,
    transaction: TransactionDto,
    subscription: Optional[SubscriptionDto],
    subscriptions_to_renew: Optional[list[SubscriptionDto]],
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
) -> None:
    del plan_service

    if subscriptions_to_renew and len(subscriptions_to_renew) > 1:
        await _renew_multiple_subscriptions(
            subscriptions_to_renew=subscriptions_to_renew,
            transaction=transaction,
            user=user,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
        )
        return

    if not subscription:
        raise ValueError(f"No subscription found for renewal for user '{user.telegram_id}'")

    target_plan = transaction.renew_items[0].plan if transaction.renew_items else transaction.plan
    await _apply_renew_item(
        subscription=subscription,
        target_plan=target_plan,
        user=user,
        remnawave_service=remnawave_service,
        subscription_service=subscription_service,
    )


async def _process_purchase_pipeline(
    *,
    purchase_type: PurchaseType,
    subscription: Optional[SubscriptionDto],
    subscriptions_to_renew: Optional[list[SubscriptionDto]],
    requested_subscription_count: int,
    device_types: list[DeviceType],
    transaction: TransactionDto,
    user: UserDto,
    plan: PlanSnapshotDto,
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
    plan_service: PlanService,
) -> None:
    if purchase_type == PurchaseType.NEW:
        await _create_new_or_additional_subscriptions(
            purchase_type=purchase_type,
            requested_subscription_count=requested_subscription_count,
            device_types=device_types,
            user=user,
            plan=plan,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
        )
        return

    if purchase_type == PurchaseType.ADDITIONAL:
        await _create_new_or_additional_subscriptions(
            purchase_type=purchase_type,
            requested_subscription_count=requested_subscription_count,
            device_types=device_types,
            user=user,
            plan=plan,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
        )
        return

    if purchase_type == PurchaseType.RENEW:
        await _process_renew_purchase(
            user=user,
            transaction=transaction,
            subscription=subscription,
            subscriptions_to_renew=subscriptions_to_renew,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            plan_service=plan_service,
        )
        return

    if purchase_type == PurchaseType.UPGRADE:
        await _process_upgrade_purchase(
            subscription=subscription,
            device_types=device_types,
            user=user,
            plan=plan,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
        )
        return

    raise Exception(f"Unknown purchase type '{purchase_type}' for user '{user.telegram_id}'")


async def _handle_purchase_subscription_failure(
    *,
    exception: Exception,
    purchase_type: PurchaseType,
    user: UserDto,
    transaction: TransactionDto,
    transaction_service: TransactionService,
) -> None:
    logger.exception(
        f"Failed to process purchase type '{purchase_type}' for user "
        f"'{user.telegram_id}' exception: {exception}"
    )

    traceback_str = traceback.format_exc()
    error_type_name = type(exception).__name__
    error_message = Text(str(exception)[:512])

    transaction.status = TransactionStatus.FAILED
    await transaction_service.update(transaction)

    await send_error_notification_task.kiq(
        error_id=user.telegram_id,
        traceback_str=traceback_str,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-event-error",
            i18n_kwargs={
                "user": True,
                "user_id": str(user.telegram_id),
                "user_name": user.name,
                "username": user.username or False,
                "error": f"{error_type_name}: {error_message.as_html()}",
            },
            reply_markup=get_user_keyboard(user.telegram_id),
        ),
    )

    await redirect_to_failed_subscription_task.kiq(user)


async def _purchase_subscription_task(
    *,
    transaction: TransactionDto,
    subscription: Optional[SubscriptionDto],
    remnawave_service: RemnawaveService,
    subscription_service: SubscriptionService,
    settings_service: SettingsService,
    transaction_service: TransactionService,
    plan_service: PlanService,
    subscriptions_to_renew: Optional[list[SubscriptionDto]] = None,
) -> None:
    purchase_type = transaction.purchase_type
    user = cast(UserDto, transaction.user)
    plan = transaction.plan

    if not user:
        logger.error(f"User not found for transaction '{transaction.id}'")
        return

    logger.info(
        f"Purchase subscription started: '{purchase_type}' for user '{user.telegram_id}' "
        f"(requested subscriptions: {len(transaction.device_types or []) or 1})"
    )
    subscriptions_to_renew_ids = (
        [subscription.id for subscription in subscriptions_to_renew]
        if subscriptions_to_renew
        else None
    )
    logger.debug(
        f"Task params - subscription: {subscription.id if subscription else None}, "
        f"subscriptions_to_renew: {subscriptions_to_renew_ids}"
    )

    current_subscription = await subscription_service.get_current(user.telegram_id)
    logger.debug(
        f"Current subscription: {current_subscription.id if current_subscription else None}"
    )

    if subscription is None and purchase_type == PurchaseType.RENEW:
        logger.warning(
            "No subscription passed for RENEW, using current subscription: "
            f"{current_subscription.id if current_subscription else None}"
        )
        subscription = current_subscription

    device_types = list(transaction.device_types or [])
    requested_subscription_count = _resolve_requested_subscription_count(
        purchase_type=purchase_type,
        device_types=device_types,
    )

    await _ensure_subscription_limit_guardrail(
        purchase_type=purchase_type,
        requested_subscription_count=requested_subscription_count,
        user=user,
        settings_service=settings_service,
        subscription_service=subscription_service,
    )

    if device_types and len(device_types) != requested_subscription_count:
        logger.warning(
            f"Device types count mismatch for user '{user.telegram_id}': "
            f"selected={len(device_types)} expected={requested_subscription_count}. "
            "Will fill missing with None and ignore extra"
        )

    try:
        await _process_purchase_pipeline(
            purchase_type=purchase_type,
            subscription=subscription,
            subscriptions_to_renew=subscriptions_to_renew,
            requested_subscription_count=requested_subscription_count,
            device_types=device_types,
            transaction=transaction,
            user=user,
            plan=plan,
            remnawave_service=remnawave_service,
            subscription_service=subscription_service,
            plan_service=plan_service,
        )

        await redirect_to_successed_payment_task.kiq(user, purchase_type)
        if purchase_type == PurchaseType.ADDITIONAL:
            logger.info(f"Additional subscription task completed for user '{user.telegram_id}'")
            return

        logger.info(f"Purchase subscription task completed for user '{user.telegram_id}'")

    except Exception as exception:
        await _handle_purchase_subscription_failure(
            exception=exception,
            purchase_type=purchase_type,
            user=user,
            transaction=transaction,
            transaction_service=transaction_service,
        )
