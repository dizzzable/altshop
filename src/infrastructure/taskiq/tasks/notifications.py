from __future__ import annotations

import asyncio
from datetime import date
from html import escape
from typing import Any, Union, cast

from aiogram.types import BufferedInputFile, InlineKeyboardMarkup
from dishka.integrations.taskiq import FromDishka, inject

from src.api.utils.web_app_urls import build_web_app_route_url
from src.bot.keyboards import get_renew_keyboard
from src.core.constants import BATCH_DELAY, BATCH_SIZE, DATETIME_FORMAT
from src.core.enums import MediaType, SystemNotificationType, UserNotificationType
from src.core.utils.bot_menu import (
    BOT_MENU_URL_KIND_URL,
    BOT_MENU_URL_KIND_WEB_APP,
    resolve_bot_menu_launch_target,
)
from src.core.utils.iterables import chunked
from src.core.utils.message_payload import MessagePayload
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.user import UserService
from src.services.user_notification_event import UserNotificationEventService


def _build_expiry_summary_key(
    *, telegram_id: int, ntf_type: UserNotificationType, target_date: date
) -> str:
    return f"user_expiry_summary:{telegram_id}:{ntf_type.value}:{target_date.isoformat()}"


def _resolve_expiry_notification_message(
    ntf_type: UserNotificationType,
) -> tuple[str, dict[str, Any], str | None]:
    if ntf_type == UserNotificationType.EXPIRES_IN_3_DAYS:
        return "ntf-event-user-expiring", {"value": 3}, "ntf-event-user-expiring-summary"
    if ntf_type == UserNotificationType.EXPIRES_IN_2_DAYS:
        return "ntf-event-user-expiring", {"value": 2}, "ntf-event-user-expiring-summary"
    if ntf_type == UserNotificationType.EXPIRES_IN_1_DAYS:
        return "ntf-event-user-expiring", {"value": 1}, "ntf-event-user-expiring-summary"
    if ntf_type == UserNotificationType.EXPIRED:
        return "ntf-event-user-expired", {}, "ntf-event-user-expired-summary"
    if ntf_type == UserNotificationType.EXPIRED_1_DAY_AGO:
        return "ntf-event-user-expired_ago", {"value": 1}, "ntf-event-user-expired-ago-summary"
    raise ValueError(f"Unsupported expiry notification type: {ntf_type}")


async def _build_expiry_summary_lines(
    *,
    subscriptions: list[SubscriptionDto],
    remnawave_service: RemnawaveService,
) -> str:
    lines: list[str] = []
    for subscription in subscriptions:
        profile_name = str(subscription.user_remna_id)
        try:
            remna_user = await remnawave_service.get_user(subscription.user_remna_id)
        except Exception:
            remna_user = None
        if remna_user is not None and getattr(remna_user, "username", None):
            profile_name = str(getattr(remna_user, "username"))
        lines.append(
            "- <b>{plan}</b> | <code>{profile}</code> | <b>{expires}</b>".format(
                plan=escape(subscription.plan.name),
                profile=escape(profile_name),
                expires=subscription.expire_at.strftime(DATETIME_FORMAT),
            )
        )
    return "\n".join(lines)


async def _resolve_expiry_summary_payload(
    *,
    telegram_id: int,
    ntf_type: UserNotificationType,
    target_date: date,
    i18n_kwargs: dict[str, Any],
    subscription_service: SubscriptionService,
    remnawave_service: RemnawaveService,
    redis_client: Any,
) -> tuple[str, dict[str, Any]] | None:
    summary_key = _build_expiry_summary_key(
        telegram_id=telegram_id,
        ntf_type=ntf_type,
        target_date=target_date,
    )
    is_new = await redis_client.set(summary_key, "1", ex=36 * 60 * 60, nx=True)
    if not is_new:
        return None

    subscriptions = [
        subscription
        for subscription in await subscription_service.get_all_by_user(telegram_id)
        if subscription.status.value != "DELETED" and subscription.expire_at.date() == target_date
    ]
    if len(subscriptions) <= 1:
        return None

    _, extra_kwargs, summary_key_name = _resolve_expiry_notification_message(ntf_type)
    if summary_key_name is None:
        return None

    return summary_key_name, {
        **i18n_kwargs,
        **extra_kwargs,
        "subscriptions_summary": await _build_expiry_summary_lines(
            subscriptions=subscriptions,
            remnawave_service=remnawave_service,
        ),
        "subscriptions_count": len(subscriptions),
    }


async def _resolve_renew_reply_markup(
    *,
    notification_service: NotificationService,
    settings_service: SettingsService,
) -> InlineKeyboardMarkup:
    settings = await settings_service.get()
    mini_app_url, _source, launch_kind = resolve_bot_menu_launch_target(
        bot_menu=settings.bot_menu,
        config=notification_service.config,
    )
    use_web_app = (
        settings.bot_menu.miniapp_only_enabled
        and launch_kind == BOT_MENU_URL_KIND_WEB_APP
        and bool(mini_app_url)
    )
    renew_web_app_url = (
        build_web_app_route_url(mini_app_url, "/dashboard/subscription")
        if use_web_app and mini_app_url
        else None
    )
    renew_url = mini_app_url if launch_kind == BOT_MENU_URL_KIND_URL else None
    return get_renew_keyboard(
        web_app_url=renew_web_app_url,
        url=renew_url,
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
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    telegram_id = cast(int, remna_user.telegram_id)
    i18n_key, i18n_kwargs_extra, _summary_key = _resolve_expiry_notification_message(ntf_type)

    user = await user_service.get(telegram_id)
    renew_reply_markup = await _resolve_renew_reply_markup(
        notification_service=notification_service,
        settings_service=settings_service,
    )

    target_date = getattr(getattr(remna_user, "expire_at", None), "date", lambda: None)()
    summary_payload = None
    if target_date is not None:
        summary_payload = await _resolve_expiry_summary_payload(
            telegram_id=telegram_id,
            ntf_type=ntf_type,
            target_date=target_date,
            i18n_kwargs=i18n_kwargs,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
            redis_client=notification_service.redis_client,
        )

    if summary_payload is not None:
        summary_i18n_key, summary_kwargs = summary_payload
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=summary_i18n_key,
                i18n_kwargs=summary_kwargs,
                reply_markup=renew_reply_markup,
                auto_delete_after=None,
                add_close_button=True,
            ),
            ntf_type=ntf_type,
        )
        return

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
