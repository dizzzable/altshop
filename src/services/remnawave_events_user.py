from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.core.constants import IMPORTED_TAG
from src.core.enums import (
    RemnaUserEvent,
    SubscriptionStatus,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    i18n_format_bytes_to_unit,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now


def build_user_event_i18n_kwargs(user: Any, remna_user: Any) -> dict[str, Any]:
    return {
        "is_trial": False,
        "user_id": str(user.telegram_id),
        "user_name": user.name,
        "username": user.username or False,
        "subscription_id": str(remna_user.uuid),
        "subscription_status": remna_user.status,
        "traffic_used": i18n_format_bytes_to_unit(
            remna_user.used_traffic_bytes,
            min_unit=ByteUnitKey.MEGABYTE,
        ),
        "traffic_limit": (
            i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes)
            if remna_user.traffic_limit_bytes > 0
            else i18n_format_traffic_limit(-1)
        ),
        "device_limit": (
            i18n_format_device_limit(remna_user.hwid_device_limit)
            if remna_user.hwid_device_limit
            else i18n_format_device_limit(-1)
        ),
        "expire_time": i18n_format_expire_time(remna_user.expire_at),
    }


async def handle_created_user_event(service: Any, remna_user: Any) -> None:
    if remna_user.tag != IMPORTED_TAG:
        logger.debug(
            "Created RemnaUser '{}' is not tagged as '{}', skipping sync",
            remna_user.telegram_id,
            IMPORTED_TAG,
        )
        return

    await service.sync_user(remna_user)


def is_expired_imported_user(remna_user: Any, user: Any) -> bool:
    if not remna_user.expire_at:
        return False

    if remna_user.expire_at + timedelta(days=2) >= datetime_now():
        return False

    logger.debug(
        "Subscription for RemnaUser '{}' expired more than 2 days ago, "
        "skipping - most likely an imported user",
        user.telegram_id,
    )
    return True


async def handle_status_change_user_event(
    service: Any,
    *,
    event: str,
    remna_user: Any,
    i18n_kwargs: dict[str, Any],
    update_status_current_subscription_task: Any,
) -> None:
    from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
        send_subscription_expire_notification_task,
        send_subscription_limited_notification_task,
    )
    expire_task = cast(Any, send_subscription_expire_notification_task)
    limited_task = cast(Any, send_subscription_limited_notification_task)

    logger.debug(
        "RemnaUser '{}' status changed to '{}'",
        remna_user.telegram_id,
        remna_user.status,
    )
    await update_status_current_subscription_task.kiq(
        user_telegram_id=remna_user.telegram_id,
        status=SubscriptionStatus(remna_user.status),
        user_remna_id=remna_user.uuid,
    )
    if event == RemnaUserEvent.LIMITED:
        await limited_task.kiq(
            remna_user=remna_user,
            i18n_kwargs=i18n_kwargs,
        )
        return

    if event == RemnaUserEvent.EXPIRED:
        await expire_task.kiq(
            remna_user=remna_user,
            ntf_type=UserNotificationType.EXPIRED,
            i18n_kwargs=i18n_kwargs,
        )


async def handle_expiration_user_event(
    service: Any,
    *,
    event: str,
    remna_user: Any,
    i18n_kwargs: dict[str, Any],
) -> None:
    from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
        send_subscription_expire_notification_task,
    )
    expire_task = cast(Any, send_subscription_expire_notification_task)

    logger.debug("Sending expiration notification for RemnaUser '{}'", remna_user.telegram_id)
    expire_map = {
        RemnaUserEvent.EXPIRES_IN_72_HOURS: UserNotificationType.EXPIRES_IN_3_DAYS,
        RemnaUserEvent.EXPIRES_IN_48_HOURS: UserNotificationType.EXPIRES_IN_2_DAYS,
        RemnaUserEvent.EXPIRES_IN_24_HOURS: UserNotificationType.EXPIRES_IN_1_DAYS,
        RemnaUserEvent.EXPIRED_24_HOURS_AGO: UserNotificationType.EXPIRED_1_DAY_AGO,
    }
    await expire_task.kiq(
        remna_user=remna_user,
        ntf_type=expire_map[RemnaUserEvent(event)],
        i18n_kwargs=i18n_kwargs,
    )


async def handle_user_event(service: Any, event: str, remna_user: Any) -> None:
    from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
        send_system_notification_task,
    )
    from src.infrastructure.taskiq.tasks.subscriptions import (  # noqa: PLC0415
        delete_current_subscription_task,
        update_status_current_subscription_task,
    )
    system_task = cast(Any, send_system_notification_task)
    delete_task = cast(Any, delete_current_subscription_task)
    update_status_task = cast(Any, update_status_current_subscription_task)

    logger.info("Received event '{}' for RemnaUser '{}'", event, remna_user.telegram_id)

    if not remna_user.telegram_id:
        logger.debug("Skipping RemnaUser '{}': telegram_id is empty", remna_user.username)
        return

    if event == RemnaUserEvent.CREATED:
        await service._handle_created_user_event(remna_user)
        return

    user = await service.user_service.get(telegram_id=remna_user.telegram_id)
    if not user:
        logger.warning("No local user found for telegram_id '{}'", remna_user.telegram_id)
        return

    i18n_kwargs = service._build_user_event_i18n_kwargs(user, remna_user)

    if event == RemnaUserEvent.MODIFIED:
        logger.debug("RemnaUser '{}' modified", remna_user.telegram_id)
        await service.sync_user(remna_user, creating=False)
        return

    if event == RemnaUserEvent.DELETED:
        logger.debug("RemnaUser '{}' deleted", remna_user.telegram_id)
        await delete_task.kiq(
            user_telegram_id=remna_user.telegram_id,
            user_remna_id=remna_user.uuid,
        )
        return

    if service._is_expired_imported_user(remna_user, user):
        logger.debug(
            "Subscription for RemnaUser '{}' expired more than 2 days ago, "
            "skipping - most likely an imported user",
            user.telegram_id,
        )
        return

    if event in {
        RemnaUserEvent.REVOKED,
        RemnaUserEvent.ENABLED,
        RemnaUserEvent.DISABLED,
        RemnaUserEvent.LIMITED,
        RemnaUserEvent.EXPIRED,
    }:
        await service._handle_status_change_user_event(
            event=event,
            remna_user=remna_user,
            i18n_kwargs=i18n_kwargs,
            update_status_current_subscription_task=update_status_task,
        )
        return

    if event == RemnaUserEvent.FIRST_CONNECTED:
        logger.debug("RemnaUser '{}' connected for the first time", remna_user.telegram_id)
        await system_task.kiq(
            ntf_type=SystemNotificationType.USER_FIRST_CONNECTED,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-user-first-connected",
                i18n_kwargs=i18n_kwargs,
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )
        return

    if event in {
        RemnaUserEvent.EXPIRES_IN_72_HOURS,
        RemnaUserEvent.EXPIRES_IN_48_HOURS,
        RemnaUserEvent.EXPIRES_IN_24_HOURS,
        RemnaUserEvent.EXPIRED_24_HOURS_AGO,
    }:
        await service._handle_expiration_user_event(
            event=event,
            remna_user=remna_user,
            i18n_kwargs=i18n_kwargs,
        )
        return

    logger.warning("Unhandled user event '{}' for '{}'", event, remna_user.telegram_id)
