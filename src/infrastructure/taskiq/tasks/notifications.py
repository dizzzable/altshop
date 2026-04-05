import asyncio
from typing import Any, Union, cast

from aiogram.types import BufferedInputFile, InlineKeyboardMarkup
from dishka.integrations.taskiq import FromDishka, inject

from src.api.utils.web_app_urls import build_web_app_route_url
from src.bot.keyboards import get_renew_keyboard
from src.core.constants import BATCH_DELAY, BATCH_SIZE
from src.core.enums import MediaType, SystemNotificationType, UserNotificationType
from src.core.utils.bot_menu import resolve_bot_menu_url
from src.core.utils.iterables import chunked
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService
from src.services.settings import SettingsService
from src.services.user import UserService
from src.services.user_notification_event import UserNotificationEventService


async def _resolve_renew_reply_markup(
    *,
    notification_service: NotificationService,
    settings_service: SettingsService,
) -> InlineKeyboardMarkup:
    settings = await settings_service.get()
    mini_app_url, _ = resolve_bot_menu_url(
        bot_menu=settings.bot_menu,
        config=notification_service.config,
    )
    use_web_app = settings.bot_menu.miniapp_only_enabled and bool(mini_app_url)
    if use_web_app and mini_app_url and not mini_app_url.startswith(("http://", "https://")):
        use_web_app = False
    renew_web_app_url = (
        build_web_app_route_url(mini_app_url, "/dashboard/subscription")
        if use_web_app and mini_app_url
        else None
    )
    return get_renew_keyboard(
        web_app_url=renew_web_app_url,
        use_web_app=bool(renew_web_app_url),
    )


@broker.task
@inject(patch_module=True)
async def send_user_notification_task(
    user: UserDto,
    ntf_type: UserNotificationType,
    payload: MessagePayload,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.notify_user(user=user, payload=payload, ntf_type=ntf_type)


@broker.task
@inject(patch_module=True)
async def send_system_notification_task(
    ntf_type: SystemNotificationType,
    payload: MessagePayload,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.system_notify(payload=payload, ntf_type=ntf_type)


@broker.task
@inject(patch_module=True)
async def send_remnashop_notification_task(
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.remnashop_notify()


@broker.task
@inject(patch_module=True)
async def send_error_notification_task(
    error_id: Union[str, int],
    traceback_str: str,
    payload: MessagePayload,
    notification_service: FromDishka[NotificationService],
) -> None:
    file_data = BufferedInputFile(
        file=traceback_str.encode(),
        filename=f"error_{error_id}.txt",
    )
    payload.media = file_data
    payload.media_type = MediaType.DOCUMENT
    await notification_service.notify_super_dev(payload=payload)


@broker.task
@inject(patch_module=True)
async def send_access_denied_notification_task(
    user: UserDto,
    i18n_key: str,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key=i18n_key),
    )


@broker.task
@inject(patch_module=True)
async def send_access_opened_notifications_task(
    waiting_user_ids: list[int],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    for batch in chunked(waiting_user_ids, BATCH_SIZE):
        for user_telegram_id in batch:
            user = await user_service.get(user_telegram_id)
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(
                    i18n_key="ntf-access-allowed",
                    auto_delete_after=None,
                    add_close_button=True,
                ),
            )
        await asyncio.sleep(BATCH_DELAY)


@broker.task
@inject(patch_module=True)
async def send_subscription_expire_notification_task(
    remna_user: RemnaUserDto,
    ntf_type: UserNotificationType,
    i18n_kwargs: dict[str, Any],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)

    if ntf_type == UserNotificationType.EXPIRES_IN_3_DAYS:
        i18n_key = "ntf-event-user-expiring"
        i18n_kwargs_extra = {"value": 3}
    elif ntf_type == UserNotificationType.EXPIRES_IN_2_DAYS:
        i18n_key = "ntf-event-user-expiring"
        i18n_kwargs_extra = {"value": 2}
    elif ntf_type == UserNotificationType.EXPIRES_IN_1_DAYS:
        i18n_key = "ntf-event-user-expiring"
        i18n_kwargs_extra = {"value": 1}
    elif ntf_type == UserNotificationType.EXPIRED:
        i18n_key = "ntf-event-user-expired"
        i18n_kwargs_extra = {}
    elif ntf_type == UserNotificationType.EXPIRED_1_DAY_AGO:
        i18n_key = "ntf-event-user-expired_ago"
        i18n_kwargs_extra = {"value": 1}

    user = await user_service.get(telegram_id)
    renew_reply_markup = await _resolve_renew_reply_markup(
        notification_service=notification_service,
        settings_service=settings_service,
    )

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key=i18n_key,
            i18n_kwargs={**i18n_kwargs, **i18n_kwargs_extra},
            reply_markup=renew_reply_markup,
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=ntf_type,
    )


@broker.task
@inject(patch_module=True)
async def send_subscription_limited_notification_task(
    remna_user: RemnaUserDto,
    i18n_kwargs: dict[str, Any],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)
    user = await user_service.get(telegram_id)
    renew_reply_markup = await _resolve_renew_reply_markup(
        notification_service=notification_service,
        settings_service=settings_service,
    )

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-event-user-limited",
            i18n_kwargs=i18n_kwargs,
            reply_markup=renew_reply_markup,
            auto_delete_after=None,
            add_close_button=True,
        ),
        ntf_type=UserNotificationType.LIMITED,
    )


@broker.task
@inject(patch_module=True)
async def send_test_transaction_notification_task(
    user: UserDto,
    notification_service: FromDishka[NotificationService],
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-gateway-test-payment-confirmed",
        ),
    )


@broker.task(schedule=[{"cron": "0 4 * * *"}])  # Run daily at 4:00 AM
@inject(patch_module=True)
async def cleanup_user_notification_events_task(
    user_notification_event_service: FromDishka[UserNotificationEventService],
) -> None:
    await user_notification_event_service.cleanup_older_than(days=30)
