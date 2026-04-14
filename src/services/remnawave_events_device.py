from __future__ import annotations

from typing import Any, cast

from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.core.enums import DeviceType, RemnaUserHwidDevicesEvent, SystemNotificationType
from src.core.utils.message_payload import MessagePayload


def normalize_platform_to_device_type(platform: str | None) -> DeviceType:
    platform_upper = (platform or "").upper()

    if "ANDROID" in platform_upper:
        return DeviceType.ANDROID
    if "IPHONE" in platform_upper or "IOS" in platform_upper:
        return DeviceType.IPHONE
    if "WINDOWS" in platform_upper:
        return DeviceType.WINDOWS
    if any(marker in platform_upper for marker in ("MAC", "MACOS", "OS X", "OSX", "DARWIN")):
        return DeviceType.MAC

    return DeviceType.OTHER


async def handle_device_event(
    service: Any,
    event: str,
    remna_user: Any,
    device: Any,
) -> None:
    from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
        send_system_notification_task,
    )
    system_task = cast(Any, send_system_notification_task)

    logger.info("Received device event '{}' for RemnaUser '{}'", event, remna_user.telegram_id)

    if not remna_user.telegram_id:
        logger.debug("Skipping RemnaUser '{}': telegram_id is empty", remna_user.username)
        return

    user = await service.user_service.get(telegram_id=remna_user.telegram_id)
    if not user:
        logger.warning("No local user found for telegram_id '{}'", remna_user.telegram_id)
        return

    if event == RemnaUserHwidDevicesEvent.ADDED:
        logger.debug("Device '{}' added for RemnaUser '{}'", device.hwid, remna_user.telegram_id)
        i18n_key = "ntf-event-user-hwid-added"
        detected_device_type = service._normalize_platform_to_device_type(device.platform)

        try:
            subscription = await service.subscription_service.get_by_remna_id(remna_user.uuid)
        except Exception as exception:
            logger.warning(
                "Failed to load subscription by remna_id '{}' for HWID event '{}': {}",
                remna_user.uuid,
                event,
                exception,
            )
            subscription = None

        if subscription:
            current_device_type = subscription.device_type
            should_update_device_type = detected_device_type != DeviceType.OTHER and (
                current_device_type is None or current_device_type == DeviceType.OTHER
            )
            if should_update_device_type:
                subscription.device_type = detected_device_type
                updated = await service.subscription_service.update(subscription)
                if updated:
                    logger.info(
                        "Auto-assigned device_type '{}' for subscription '{}' from platform '{}'",
                        detected_device_type.value,
                        subscription.id,
                        device.platform,
                    )
        else:
            logger.debug(
                "Subscription with remna_id '{}' not found for HWID event '{}'",
                remna_user.uuid,
                event,
            )

    elif event == RemnaUserHwidDevicesEvent.DELETED:
        logger.debug("Device '{}' deleted for RemnaUser '{}'", device.hwid, remna_user.telegram_id)
        i18n_key = "ntf-event-user-hwid-deleted"
    else:
        logger.warning(
            "Unhandled device event '{}' for RemnaUser '{}'",
            event,
            remna_user.telegram_id,
        )
        return

    await system_task.kiq(
        ntf_type=SystemNotificationType.USER_HWID,
        payload=MessagePayload.not_deleted(
            i18n_key=i18n_key,
            i18n_kwargs={
                "user_id": str(user.telegram_id),
                "user_name": user.name,
                "username": user.username or False,
                "hwid": device.hwid,
                "platform": device.platform,
                "device_model": device.device_model,
                "os_version": device.os_version,
                "user_agent": device.user_agent,
            },
            reply_markup=get_user_keyboard(user.telegram_id),
        ),
    )
