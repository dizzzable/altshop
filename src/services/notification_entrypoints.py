from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional, cast

from loguru import logger

from src.__version__ import __version__
from src.bot.keyboards import get_remnashop_keyboard
from src.core.enums import SystemNotificationType, UserNotificationType, UserRole
from src.core.utils.branding import resolve_project_name
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.user import BaseUserDto

if TYPE_CHECKING:
    from aiogram.types import Message

    from .notification import NotificationService


async def notify_user(
    service: NotificationService,
    user: Optional[BaseUserDto],
    payload: MessagePayload,
    ntf_type: Optional[UserNotificationType] = None,
) -> Optional[Message]:
    if not user:
        logger.warning("Skipping user notification: user object is empty")
        return None

    if user.is_bot_blocked:
        logger.debug(
            "Skipping user notification '{}' for '{}': user is marked as bot-blocked",
            payload.i18n_key,
            user.telegram_id,
        )
        return None

    if ntf_type and not await service.settings_service.is_notification_enabled(ntf_type):
        logger.debug(
            "Skipping user notification for '{}': notification type is disabled in settings",
            user.telegram_id,
        )
        return None

    logger.debug(
        "Attempting to send user notification '{}' to '{}'",
        payload.i18n_key,
        user.telegram_id,
    )

    close_notification_id: Optional[int] = None
    if ntf_type:
        try:
            rendered_text = service._get_translated_text(
                locale=user.language,
                i18n_key=payload.i18n_key,
                i18n_kwargs=payload.i18n_kwargs,
            )
            event = await service.user_notification_event_service.create_event(
                user_telegram_id=user.telegram_id,
                ntf_type=ntf_type,
                i18n_key=payload.i18n_key,
                i18n_kwargs=payload.i18n_kwargs,
                rendered_text=rendered_text,
            )
            close_notification_id = event.id
        except Exception as exception:
            logger.error(
                "Failed to create notification event for user '{}': {}",
                user.telegram_id,
                exception,
                exc_info=True,
            )

    sent_message = await service._send_message(
        user,
        payload,
        close_notification_id=close_notification_id,
    )

    if sent_message and close_notification_id is not None:
        try:
            await service.user_notification_event_service.set_bot_delivery_meta(
                notification_id=close_notification_id,
                bot_chat_id=user.telegram_id,
                bot_message_id=sent_message.message_id,
            )
        except Exception as exception:
            logger.error(
                "Failed to save delivery meta for notification '{}': {}",
                close_notification_id,
                exception,
                exc_info=True,
            )

    return sent_message


async def system_notify(
    service: NotificationService,
    payload: MessagePayload,
    ntf_type: SystemNotificationType,
) -> list[bool]:
    devs = await service.user_service.get_by_role(role=UserRole.DEV)

    if not devs:
        devs = [service._get_temp_dev()]

    if not await service.settings_service.is_notification_enabled(ntf_type):
        logger.debug("Skipping system notification: notification type is disabled in settings")
        return []

    if payload.dedupe_key and not await service._acquire_system_event_dedupe(
        dedupe_key=payload.dedupe_key,
        ttl_seconds=payload.dedupe_ttl_seconds,
    ):
        logger.debug("Skipping duplicated system notification '{}'", payload.dedupe_key)
        return []

    logger.debug(
        "Attempting to send system notification '{}' to '{}' devs",
        payload.i18n_key,
        len(devs),
    )

    async def send_to_dev(dev: UserDto) -> bool:
        return bool(await service._send_message(user=dev, payload=payload))

    tasks = [send_to_dev(dev) for dev in devs]
    results = await asyncio.gather(*tasks)
    return cast(list[bool], results)


async def acquire_system_event_dedupe(
    service: NotificationService,
    *,
    dedupe_key: str,
    ttl_seconds: int | None,
) -> bool:
    try:
        return bool(
            await service.redis_client.set(
                f"system_event:{dedupe_key}",
                "1",
                ex=ttl_seconds or 300,
                nx=True,
            )
        )
    except Exception as exc:
        logger.warning("System event dedupe unavailable for '{}': {}", dedupe_key, exc)
        return True


async def notify_super_dev(service: NotificationService, payload: MessagePayload) -> bool:
    dev = await service.user_service.get(telegram_id=service.config.bot.dev_id[0])
    if not dev:
        dev = service._get_temp_dev()

    logger.debug(
        "Attempting to send super dev notification '{}' to '{}'",
        payload.i18n_key,
        dev.telegram_id,
    )
    return bool(await service._send_message(user=dev, payload=payload))


async def remnashop_notify(service: NotificationService) -> bool:
    dev = await service.user_service.get(service.config.bot.dev_id[0]) or service._get_temp_dev()
    try:
        branding = await service.settings_service.get_branding_settings()
        project_name = resolve_project_name(branding.project_name)
    except Exception as exc:
        logger.warning("Failed to load branding settings for project info notification: {}", exc)
        project_name = resolve_project_name(None)

    payload = MessagePayload(
        i18n_key="ntf-remnashop-info",
        i18n_kwargs={"version": __version__, "project_name": project_name},
        reply_markup=get_remnashop_keyboard(),
        auto_delete_after=None,
        add_close_button=True,
        message_effect=service._love_effect(),
    )
    return bool(await service._send_message(user=dev, payload=payload))


def get_temp_dev(service: NotificationService) -> UserDto:
    temp_dev = UserDto(
        telegram_id=service.config.bot.dev_id[0],
        name="TempDev",
        role=UserRole.DEV,
    )

    logger.warning("Fallback to temporary dev user from environment for notifications")
    return temp_dev
