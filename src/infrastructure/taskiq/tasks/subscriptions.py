import traceback
from datetime import timedelta
from typing import Optional, cast
from uuid import UUID

from aiogram.utils.formatting import Text
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from remnawave import RemnawaveSDK

from src.bot.keyboards import get_user_keyboard
from src.core.constants import EXPIRED_SUBSCRIPTION_CLEANUP_DAYS
from src.core.enums import (
    DeviceType,
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
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks.notifications import (
    send_error_notification_task,
    send_system_notification_task,
)
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService

from .redirects import (
    redirect_to_failed_subscription_task,
    redirect_to_successed_payment_task,
    redirect_to_successed_trial_task,
)


@broker.task
@inject
async def trial_subscription_task(
    user: UserDto,
    plan: PlanSnapshotDto,
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Started trial for user '{user.telegram_id}'")

    try:
        created_user = await remnawave_service.create_user(user, plan)
        trial_subscription = SubscriptionDto(
            user_remna_id=created_user.uuid,
            status=created_user.status,
            is_trial=True,
            traffic_limit=plan.traffic_limit,
            device_limit=plan.device_limit,
            internal_squads=plan.internal_squads,
            external_squad=plan.external_squad,
            expire_at=created_user.expire_at,
            url=created_user.subscription_url,
            plan=plan,
        )
        await subscription_service.create(user, trial_subscription)
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


@broker.task
@inject
async def purchase_subscription_task(
    transaction: TransactionDto,
    subscription: Optional[SubscriptionDto],
    remnawave_service: FromDishka[RemnawaveService],
    subscription_service: FromDishka[SubscriptionService],
    transaction_service: FromDishka[TransactionService],
    plan_service: FromDishka[PlanService],
    subscriptions_to_renew: Optional[list[SubscriptionDto]] = None,
) -> None:
    purchase_type = transaction.purchase_type
    user = cast(UserDto, transaction.user)
    plan = transaction.plan

    if not user:
        logger.error(f"User not found for transaction '{transaction.id}'")
        return

    # Логируем входные параметры для отладки
    logger.info(
        f"Purchase subscription started: '{purchase_type}' for user '{user.telegram_id}' "
        f"(plan max subscriptions: {plan.subscription_count})"
    )
    logger.debug(
        f"Task params - subscription: {subscription.id if subscription else None}, "
        f"subscriptions_to_renew: {[s.id for s in subscriptions_to_renew] if subscriptions_to_renew else None}"
    )
    
    # Для RENEW нужна текущая подписка
    # Для NEW и ADDITIONAL подписка не нужна (создаём новую), но проверяем триальную для NEW
    current_subscription = await subscription_service.get_current(user.telegram_id)
    has_trial = current_subscription and current_subscription.is_trial
    
    logger.debug(
        f"Current subscription: {current_subscription.id if current_subscription else None}, "
        f"has_trial: {has_trial}"
    )
    
    # Для RENEW используем текущую подписку только если subscription не передан
    if subscription is None and purchase_type == PurchaseType.RENEW:
        logger.warning(
            f"No subscription passed for RENEW, using current subscription: "
            f"{current_subscription.id if current_subscription else None}"
        )
        subscription = current_subscription
    
    # Для NEW с триальной подпиской тоже нужна текущая подписка (для замены триала)
    if purchase_type == PurchaseType.NEW and has_trial:
        subscription = current_subscription

    try:
        if purchase_type == PurchaseType.NEW and not has_trial:
            # Create exactly 1 subscription per purchase
            # Получаем тип устройства из транзакции (первый элемент списка)
            device_type = None
            if transaction.device_types and len(transaction.device_types) > 0:
                device_type = transaction.device_types[0]
                logger.info(f"Using device_type '{device_type}' for new subscription")
            
            created_user = await remnawave_service.create_user(user, plan, subscription_index=0)
            new_subscription = SubscriptionDto(
                user_remna_id=created_user.uuid,
                status=created_user.status,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                internal_squads=plan.internal_squads,
                external_squad=plan.external_squad,
                expire_at=created_user.expire_at,
                url=created_user.subscription_url,
                plan=plan,
                device_type=device_type,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Created new subscription for user '{user.telegram_id}' with device_type '{device_type}'")
            
            await redirect_to_successed_payment_task.kiq(user, purchase_type)
            logger.info(f"Purchase subscription task completed for user '{user.telegram_id}'")
            return

        elif purchase_type == PurchaseType.ADDITIONAL:
            # Create additional subscription without affecting existing ones
            # remnawave_service.create_user will automatically generate unique username
            # with suffix like _sub1, _sub2, etc.
            # Получаем тип устройства из транзакции (первый элемент списка)
            device_type = None
            if transaction.device_types and len(transaction.device_types) > 0:
                device_type = transaction.device_types[0]
                logger.info(f"Using device_type '{device_type}' for additional subscription")
            
            created_user = await remnawave_service.create_user(user, plan, subscription_index=0)
            new_subscription = SubscriptionDto(
                user_remna_id=created_user.uuid,
                status=created_user.status,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                internal_squads=plan.internal_squads,
                external_squad=plan.external_squad,
                expire_at=created_user.expire_at,
                url=created_user.subscription_url,
                plan=plan,
                device_type=device_type,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Created additional subscription for user '{user.telegram_id}' with device_type '{device_type}'")
            
            await redirect_to_successed_payment_task.kiq(user, purchase_type)
            logger.info(f"Additional subscription task completed for user '{user.telegram_id}'")
            return

        elif purchase_type == PurchaseType.RENEW and not has_trial:
            # Множественное продление подписок
            if subscriptions_to_renew and len(subscriptions_to_renew) > 1:
                logger.info(
                    f"MULTIPLE RENEWAL: Renewing {len(subscriptions_to_renew)} subscriptions "
                    f"for user '{user.telegram_id}': {[s.id for s in subscriptions_to_renew]}"
                )
                
                # Получаем все доступные планы для определения плана каждой подписки
                available_plans = await plan_service.get_available_plans(user)
                
                for sub in subscriptions_to_renew:
                    # Находим план для этой конкретной подписки
                    matched_plan = sub.find_matching_plan(available_plans)
                    sub_plan = matched_plan if matched_plan else plan
                    
                    logger.info(
                        f"Renewing subscription '{sub.id}' (plan: {sub.plan.name}, "
                        f"matched_plan: {matched_plan.name if matched_plan else 'None'})"
                    )
                    
                    # Используем длительность из транзакции (выбранную пользователем)
                    old_expire = sub.expire_at
                    new_expire = sub.expire_at + timedelta(days=transaction.plan.duration)
                    sub.expire_at = new_expire

                    updated_user = await remnawave_service.updated_user(
                        user=user,
                        uuid=sub.user_remna_id,
                        subscription=sub,
                    )

                    sub.expire_at = updated_user.expire_at  # type: ignore[assignment]
                    # Сохраняем план подписки (не меняем на общий план транзакции)
                    # План подписки остаётся тем же, только продлевается срок
                    await subscription_service.update(sub)
                    logger.info(
                        f"Renewed subscription '{sub.id}' for user '{user.telegram_id}': "
                        f"{old_expire} -> {sub.expire_at} (plan: {sub.plan.name})"
                    )
            else:
                # Одиночное продление
                if not subscription:
                    raise ValueError(f"No subscription found for renewal for user '{user.telegram_id}'")

                logger.info(
                    f"SINGLE RENEWAL: Renewing subscription '{subscription.id}' "
                    f"for user '{user.telegram_id}'"
                )
                
                old_expire = subscription.expire_at
                new_expire = subscription.expire_at + timedelta(days=transaction.plan.duration)
                subscription.expire_at = new_expire

                updated_user = await remnawave_service.updated_user(
                    user=user,
                    uuid=subscription.user_remna_id,
                    subscription=subscription,
                )

                subscription.expire_at = updated_user.expire_at  # type: ignore[assignment]
                # При одиночном продлении план тоже не меняется
                await subscription_service.update(subscription)
                logger.info(
                    f"Renewed subscription '{subscription.id}' for user '{user.telegram_id}': "
                    f"{old_expire} -> {subscription.expire_at}"
                )

        elif has_trial:
            # Replace trial subscription with paid one
            if not subscription:
                raise ValueError(f"No trial subscription found for user '{user.telegram_id}'")

            subscription.status = SubscriptionStatus.DISABLED
            await subscription_service.update(subscription)

            # Получаем тип устройства из транзакции (первый элемент списка)
            device_type = None
            if transaction.device_types and len(transaction.device_types) > 0:
                device_type = transaction.device_types[0]
                logger.info(f"Using device_type '{device_type}' for subscription replacing trial")

            # Update the existing RemnaWave user for the change
            updated_user = await remnawave_service.updated_user(
                user=user, uuid=subscription.user_remna_id, plan=plan, reset_traffic=True
            )
            new_subscription = SubscriptionDto(
                user_remna_id=updated_user.uuid,
                status=updated_user.status,
                traffic_limit=plan.traffic_limit,
                device_limit=plan.device_limit,
                internal_squads=plan.internal_squads,
                external_squad=plan.external_squad,
                expire_at=updated_user.expire_at,
                url=updated_user.subscription_url,
                plan=plan,
                device_type=device_type,
            )
            await subscription_service.create(user, new_subscription)
            logger.debug(f"Replaced trial subscription for user '{user.telegram_id}' with device_type '{device_type}'")

        else:
            raise Exception(
                f"Unknown purchase type '{purchase_type}' for user '{user.telegram_id}'"
            )

        await redirect_to_successed_payment_task.kiq(user, purchase_type)
        logger.info(f"Purchase subscription task completed for user '{user.telegram_id}'")

    except Exception as exception:
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


@broker.task
@inject
async def delete_current_subscription_task(
    user_telegram_id: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Delete current subscription started for user '{user_telegram_id}'")

    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"User '{user_telegram_id}' not found, skipping deletion")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(f"No current subscription for user '{user.telegram_id}', skipping deletion")
        return

    subscription.status = SubscriptionStatus.DELETED
    await subscription_service.update(subscription)
    await user_service.delete_current_subscription(user.telegram_id)


@broker.task
@inject
async def update_status_current_subscription_task(
    user_telegram_id: int,
    status: SubscriptionStatus,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    logger.info(f"Update status current subscription started for user '{user_telegram_id}'")

    user = await user_service.get(user_telegram_id)

    if not user:
        logger.debug(f"User '{user_telegram_id}' not found, skipping status update")
        return

    subscription = await subscription_service.get_current(user.telegram_id)

    if not subscription:
        logger.debug(
            f"No current subscription for user '{user.telegram_id}', skipping status update"
        )
        return

    subscription.status = status
    await subscription_service.update(subscription)


@broker.task(schedule=[{"cron": "0 3 * * *"}])  # Run daily at 3:00 AM
@inject
async def cleanup_expired_subscriptions_task(
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
) -> None:
    """
    Periodic task to delete users from Remnawave panel
    if their subscription expired more than EXPIRED_SUBSCRIPTION_CLEANUP_DAYS days ago.
    """
    logger.info(
        f"Starting cleanup of subscriptions expired more than "
        f"{EXPIRED_SUBSCRIPTION_CLEANUP_DAYS} days ago"
    )
    
    expired_subscriptions = await subscription_service.get_expired_subscriptions_older_than(
        days=EXPIRED_SUBSCRIPTION_CLEANUP_DAYS
    )
    
    if not expired_subscriptions:
        logger.info("No expired subscriptions to cleanup")
        return
    
    deleted_count = 0
    failed_count = 0
    
    for subscription in expired_subscriptions:
        try:
            # Delete user from Remnawave panel
            remna_user_uuid = subscription.user_remna_id
            if remna_user_uuid:
                result = await remnawave.users.delete_user(uuid=str(remna_user_uuid))
                if result and result.is_deleted:
                    logger.info(
                        f"Deleted RemnaUser '{remna_user_uuid}' from panel "
                        f"(subscription '{subscription.id}')"
                    )
                else:
                    logger.warning(
                        f"Failed to delete RemnaUser '{remna_user_uuid}' from panel"
                    )
            
            # Mark subscription as deleted in database
            await subscription_service.delete_subscription(subscription.id)  # type: ignore[arg-type]
            deleted_count += 1
            
        except Exception as e:
            logger.error(
                f"Error cleaning up subscription '{subscription.id}': {e}"
            )
            failed_count += 1
    
    logger.info(
        f"Cleanup completed: {deleted_count} subscriptions deleted, "
        f"{failed_count} failed"
    )
