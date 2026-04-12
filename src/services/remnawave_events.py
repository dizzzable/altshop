# mypy: ignore-errors
# ruff: noqa: E501

from __future__ import annotations

from datetime import timedelta
from typing import Any

from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.core.constants import DATETIME_FORMAT, IMPORTED_TAG
from src.core.enums import (
    DeviceType,
    RemnaNodeEvent,
    RemnaUserEvent,
    RemnaUserHwidDevicesEvent,
    SubscriptionStatus,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    format_country_code,
    i18n_format_bytes_to_unit,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now


class RemnawaveEventsMixin:
    @staticmethod
    def _normalize_platform_to_device_type(platform: str | None) -> DeviceType:
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

    @staticmethod
    def _build_user_event_i18n_kwargs(user, remna_user) -> dict[str, Any]:
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

    async def _handle_created_user_event(self, remna_user) -> None:
        if remna_user.tag != IMPORTED_TAG:
            logger.debug(
                f"Created RemnaUser '{remna_user.telegram_id}' "
                f"is not tagged as '{IMPORTED_TAG}', skipping sync"
            )
            return

        await self.sync_user(remna_user)

    @staticmethod
    def _is_expired_imported_user(remna_user, user) -> bool:
        if not remna_user.expire_at:
            return False

        if remna_user.expire_at + timedelta(days=2) >= datetime_now():
            return False

        logger.debug(
            f"Subscription for RemnaUser '{user.telegram_id}' expired more than 2 days ago, "
            "skipping – most likely an imported user"
        )
        return True

    async def _handle_status_change_user_event(
        self,
        *,
        event: str,
        remna_user,
        i18n_kwargs: dict[str, Any],
        update_status_current_subscription_task: Any,
    ) -> None:
        from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
            send_subscription_expire_notification_task,
            send_subscription_limited_notification_task,
        )

        logger.debug(
            f"RemnaUser '{remna_user.telegram_id}' status changed to '{remna_user.status}'"
        )
        await update_status_current_subscription_task.kiq(
            user_telegram_id=remna_user.telegram_id,
            status=SubscriptionStatus(remna_user.status),
            user_remna_id=remna_user.uuid,
        )
        if event == RemnaUserEvent.LIMITED:
            await send_subscription_limited_notification_task.kiq(
                remna_user=remna_user,
                i18n_kwargs=i18n_kwargs,
            )
            return

        if event == RemnaUserEvent.EXPIRED:
            await send_subscription_expire_notification_task.kiq(
                remna_user=remna_user,
                ntf_type=UserNotificationType.EXPIRED,
                i18n_kwargs=i18n_kwargs,
            )

    async def _handle_expiration_user_event(
        self,
        *,
        event: str,
        remna_user,
        i18n_kwargs: dict[str, Any],
    ) -> None:
        from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
            send_subscription_expire_notification_task,
        )

        logger.debug(f"Sending expiration notification for RemnaUser '{remna_user.telegram_id}'")
        expire_map = {
            RemnaUserEvent.EXPIRES_IN_72_HOURS: UserNotificationType.EXPIRES_IN_3_DAYS,
            RemnaUserEvent.EXPIRES_IN_48_HOURS: UserNotificationType.EXPIRES_IN_2_DAYS,
            RemnaUserEvent.EXPIRES_IN_24_HOURS: UserNotificationType.EXPIRES_IN_1_DAYS,
            RemnaUserEvent.EXPIRED_24_HOURS_AGO: UserNotificationType.EXPIRED_1_DAY_AGO,
        }
        await send_subscription_expire_notification_task.kiq(
            remna_user=remna_user,
            ntf_type=expire_map[RemnaUserEvent(event)],
            i18n_kwargs=i18n_kwargs,
        )

    async def handle_user_event(self, event: str, remna_user) -> None:
        from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
            send_system_notification_task,
        )
        from src.infrastructure.taskiq.tasks.subscriptions import (  # noqa: PLC0415
            delete_current_subscription_task,
            update_status_current_subscription_task,
        )

        logger.info(f"Received event '{event}' for RemnaUser '{remna_user.telegram_id}'")

        if not remna_user.telegram_id:
            logger.debug(f"Skipping RemnaUser '{remna_user.username}': telegram_id is empty")
            return

        if event == RemnaUserEvent.CREATED:
            await self._handle_created_user_event(remna_user)
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        i18n_kwargs = self._build_user_event_i18n_kwargs(user, remna_user)

        if event == RemnaUserEvent.MODIFIED:
            logger.debug(f"RemnaUser '{remna_user.telegram_id}' modified")
            await self.sync_user(remna_user, creating=False)
            return

        if event == RemnaUserEvent.DELETED:
            logger.debug(f"RemnaUser '{remna_user.telegram_id}' deleted")
            await delete_current_subscription_task.kiq(
                user_telegram_id=remna_user.telegram_id,
                user_remna_id=remna_user.uuid,
            )
            return

        if self._is_expired_imported_user(remna_user, user):
            logger.debug(
                f"Subscription for RemnaUser '{user.telegram_id}' expired more than 2 days ago, "
                "skipping – most likely an imported user"
            )
            return

        if event in {
            RemnaUserEvent.REVOKED,
            RemnaUserEvent.ENABLED,
            RemnaUserEvent.DISABLED,
            RemnaUserEvent.LIMITED,
            RemnaUserEvent.EXPIRED,
        }:
            await self._handle_status_change_user_event(
                event=event,
                remna_user=remna_user,
                i18n_kwargs=i18n_kwargs,
                update_status_current_subscription_task=update_status_current_subscription_task,
            )
            return

        if event == RemnaUserEvent.FIRST_CONNECTED:
            logger.debug(f"RemnaUser '{remna_user.telegram_id}' connected for the first time")
            await send_system_notification_task.kiq(
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
            await self._handle_expiration_user_event(
                event=event,
                remna_user=remna_user,
                i18n_kwargs=i18n_kwargs,
            )
            return

        logger.warning(f"Unhandled user event '{event}' for '{remna_user.telegram_id}'")

    async def handle_device_event(
        self,
        event: str,
        remna_user,
        device,
    ) -> None:
        from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
            send_system_notification_task,
        )

        logger.info(f"Received device event '{event}' for RemnaUser '{remna_user.telegram_id}'")

        if not remna_user.telegram_id:
            logger.debug(f"Skipping RemnaUser '{remna_user.username}': telegram_id is empty")
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        if event == RemnaUserHwidDevicesEvent.ADDED:
            logger.debug(f"Device '{device.hwid}' added for RemnaUser '{remna_user.telegram_id}'")
            i18n_key = "ntf-event-user-hwid-added"
            detected_device_type = self._normalize_platform_to_device_type(device.platform)

            try:
                subscription = await self.subscription_service.get_by_remna_id(remna_user.uuid)
            except Exception as exception:
                logger.warning(
                    f"Failed to load subscription by remna_id '{remna_user.uuid}' "
                    f"for HWID event '{event}': {exception}"
                )
                subscription = None

            if subscription:
                current_device_type = subscription.device_type
                should_update_device_type = detected_device_type != DeviceType.OTHER and (
                    current_device_type is None or current_device_type == DeviceType.OTHER
                )
                if should_update_device_type:
                    subscription.device_type = detected_device_type
                    updated = await self.subscription_service.update(subscription)
                    if updated:
                        logger.info(
                            f"Auto-assigned device_type '{detected_device_type.value}' "
                            f"for subscription '{subscription.id}' "
                            f"from platform '{device.platform}'"
                        )
            else:
                logger.debug(
                    f"Subscription with remna_id '{remna_user.uuid}' "
                    f"not found for HWID event '{event}'"
                )

        elif event == RemnaUserHwidDevicesEvent.DELETED:
            logger.debug(f"Device '{device.hwid}' deleted for RemnaUser '{remna_user.telegram_id}'")
            i18n_key = "ntf-event-user-hwid-deleted"
        else:
            logger.warning(
                f"Unhandled device event '{event}' for RemnaUser '{remna_user.telegram_id}'"
            )
            return

        await send_system_notification_task.kiq(
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

    async def handle_node_event(self, event: str, node) -> None:
        from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
            send_system_notification_task,
        )

        logger.info(f"Received node event '{event}' for node '{node.name}'")

        if event == RemnaNodeEvent.CONNECTION_LOST:
            logger.warning(f"Connection lost for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-lost"
        elif event == RemnaNodeEvent.CONNECTION_RESTORED:
            logger.info(f"Connection restored for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-restored"
        elif event == RemnaNodeEvent.TRAFFIC_NOTIFY:
            logger.debug(f"Traffic threshold reached on node '{node.name}'")
            i18n_key = "ntf-event-node-traffic"
        else:
            logger.warning(f"Unhandled node event '{event}' for node '{node.name}'")
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.NODE_STATUS,
            payload=MessagePayload.not_deleted(
                i18n_key=i18n_key,
                i18n_kwargs={
                    "country": format_country_code(code=node.country_code),
                    "name": node.name,
                    "address": node.address,
                    "port": str(node.port),
                    "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
                    "traffic_limit": i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                    "last_status_message": node.last_status_message or "None",
                    "last_status_change": node.last_status_change.strftime(DATETIME_FORMAT)
                    if node.last_status_change
                    else "None",
                },
            ),
        )
