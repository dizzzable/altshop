import html
import uuid
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_dialog import DialogManager, ShowMode, SubManager
from aiogram_dialog.utils import remove_intent_id
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.keyboards import goto_buttons
from src.bot.states import DashboardBroadcast
from src.core.config import AppConfig
from src.core.constants import USER_KEY
from src.core.enums import BroadcastAudience, BroadcastStatus, MediaType
from src.core.utils.formatters import format_user_log as log
from src.core.utils.formatters import format_username_to_url
from src.core.utils.message_payload import MessagePayload
from src.core.utils.validators import is_double_click
from src.core.utils.web_app_urls import to_webapp_base_url
from src.infrastructure.database.models.dto import BroadcastDto, PlanDto, PromocodeDto, UserDto
from src.infrastructure.taskiq.tasks.broadcast import delete_broadcast_task, send_broadcast_task
from src.services.broadcast import BroadcastService
from src.services.notification import NotificationService
from src.services.plan import PlanService
from src.services.promocode import PromocodeService


def _update_payload(dialog_manager: DialogManager, **updates: Any) -> MessagePayload:
    raw_payload = dialog_manager.dialog_data.get("payload")

    old_payload = (
        MessagePayload.model_validate(raw_payload)
        if raw_payload
        else MessagePayload(
            i18n_key="ntf-broadcast-preview",
            auto_delete_after=None,
            add_close_button=True,
        )
    )

    payload_data = old_payload.model_dump()
    payload_data.update(updates)

    new_payload = MessagePayload(**payload_data)
    dialog_manager.dialog_data["payload"] = new_payload.model_dump()

    return new_payload


def _normalize_promocode(value: str | None) -> str:
    return str(value or "").strip().upper()


def _resolve_broadcast_web_url(config: AppConfig) -> str | None:
    web_url = config.web_app.url_str.strip()
    if web_url:
        return to_webapp_base_url(web_url).rstrip("/")

    if isinstance(config.bot.mini_app_url, str) and config.bot.mini_app_url:
        return to_webapp_base_url(config.bot.mini_app_url).rstrip("/")

    return None


def _build_promocode_button_url(config: AppConfig, promocode_code: str) -> str | None:
    base_url = _resolve_broadcast_web_url(config)
    if not base_url:
        return None

    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/dashboard/subscription"):
        target_path = path
    elif path.endswith("/dashboard"):
        target_path = f"{path}/subscription"
    elif path:
        target_path = f"{path}/dashboard/subscription"
    else:
        target_path = "/dashboard/subscription"

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["promocode"] = promocode_code
    query["open_promocode"] = "1"

    return urlunparse(
        parsed._replace(
            path=target_path,
            query=urlencode(query),
            params="",
            fragment="",
        )
    )


def _get_broadcast_promocode_error_key(promocode: PromocodeDto) -> str | None:
    if not promocode.is_active:
        return "ntf-promocode-inactive"
    if promocode.is_expired:
        return "ntf-promocode-expired"
    if promocode.is_depleted:
        return "ntf-promocode-depleted"
    return None


def _build_goto_button(
    *,
    button_id: int,
    config: AppConfig,
    i18n: TranslatorRunner,
) -> InlineKeyboardButton:
    button = goto_buttons[button_id].model_copy(deep=True)

    if button_id == 0:
        support_text = i18n.get("contact-support-help")
        support_username = config.bot.support_username.get_secret_value()
        button.url = format_username_to_url(support_username, support_text)

    return button


def _build_broadcast_keyboard(
    dialog_manager: DialogManager,
    config: AppConfig,
    i18n: TranslatorRunner,
) -> InlineKeyboardMarkup | None:
    buttons: list[dict[str, Any]] = dialog_manager.dialog_data.get("buttons", [])
    use_promocode_button = bool(dialog_manager.dialog_data.get("use_promocode_button"))
    promocode_code = _normalize_promocode(dialog_manager.dialog_data.get("promocode_code"))

    builder = InlineKeyboardBuilder()

    for button in buttons:
        if not button.get("selected"):
            continue

        button_id = int(button["id"])
        builder.row(
            _build_goto_button(
                button_id=button_id,
                config=config,
                i18n=i18n,
            )
        )

    if use_promocode_button and promocode_code:
        promocode_url = _build_promocode_button_url(config, promocode_code)
        if promocode_url:
            builder.row(
                InlineKeyboardButton(
                    text=f"Use promo {promocode_code}",
                    url=promocode_url,
                )
            )

    return builder.as_markup() if builder.export() else None


def _refresh_payload_keyboard(
    dialog_manager: DialogManager,
    config: AppConfig,
    i18n: TranslatorRunner,
) -> None:
    reply_markup = _build_broadcast_keyboard(dialog_manager, config, i18n)
    _update_payload(dialog_manager, reply_markup=reply_markup)


@inject
async def on_broadcast_list(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    broadcast_service: FromDishka[BroadcastService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    broadcasts = await broadcast_service.get_all()

    if not broadcasts:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-list-empty"),
        )
        return

    await dialog_manager.switch_to(state=DashboardBroadcast.LIST)


@inject
async def on_broadcast_select(
    callback: CallbackQuery,
    widget: Select[UUID],
    dialog_manager: DialogManager,
    selected_broadcast: UUID,
) -> None:
    dialog_manager.dialog_data["task_id"] = selected_broadcast
    await dialog_manager.switch_to(state=DashboardBroadcast.VIEW)


@inject
async def on_audience_select(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    broadcast_service: FromDishka[BroadcastService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    if not callback.data:
        raise ValueError("Callback data is empty")

    audience = BroadcastAudience(remove_intent_id(callback.data)[-1])
    dialog_manager.dialog_data["audience_type"] = audience
    logger.info(f"{log(user)} Selected audience '{audience}'")

    audience_count = await broadcast_service.get_audience_count(audience)
    if audience == BroadcastAudience.PLAN:
        if audience_count == 0:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-broadcast-plans-not-available"),
            )
            return
        await dialog_manager.switch_to(state=DashboardBroadcast.PLAN)
        return

    if audience_count == 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-audience-not-available"),
        )
        return

    dialog_manager.dialog_data["audience_count"] = audience_count
    await dialog_manager.switch_to(state=DashboardBroadcast.SEND)


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan_id: int,
    plan_service: FromDishka[PlanService],
    broadcast_service: FromDishka[BroadcastService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plan: Optional[PlanDto] = await plan_service.get(plan_id=selected_plan_id)

    if not plan:
        raise ValueError(f"Attempted to select non-existent plan '{selected_plan_id}'")

    logger.info(f"{log(user)} Selected plan ID '{plan.id}'")

    audience_count = await broadcast_service.get_audience_count(BroadcastAudience.PLAN, plan.id)

    if audience_count == 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-audience-not-active"),
        )
        return

    dialog_manager.dialog_data["plan_id"] = plan.id
    dialog_manager.dialog_data["audience_count"] = audience_count
    await dialog_manager.switch_to(state=DashboardBroadcast.SEND)


@inject
async def on_content_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set content")

    media_type: Optional[MediaType] = None
    file_id: Optional[str] = None

    if message.photo:
        media_type = MediaType.PHOTO
        file_id = message.photo[-1].file_id
    elif message.video:
        media_type = MediaType.VIDEO
        file_id = message.video.file_id
    elif message.document:
        media_type = MediaType.DOCUMENT
        file_id = message.document.file_id
    elif message.sticker:
        media_type = MediaType.DOCUMENT
        file_id = message.sticker.file_id

    if not (message.html_text or file_id):
        logger.warning(f"{log(user)} Provided invalid or empty content")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-wrong-content"),
        )
        return

    _update_payload(
        dialog_manager,
        i18n_kwargs={"content": html.unescape(message.html_text)},
        media_type=media_type,
        media_id=file_id,
    )

    logger.info(f"{log(user)} Updated message payload (content only)")
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-broadcast-content-saved"),
    )


@inject
async def on_button_select(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    config: FromDishka[AppConfig],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    selected_id = int(sub_manager.item_id)

    buttons: list[dict] = sub_manager.manager.dialog_data.get("buttons", [])
    for button in buttons:
        if button["id"] == selected_id:
            button["selected"] = not button.get("selected", False)
            break

    _refresh_payload_keyboard(
        dialog_manager=sub_manager.manager,
        config=config,
        i18n=i18n,
    )

    logger.debug(f"{log(user)} Updated payload keyboard: {buttons}")


@inject
async def on_promocode_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    i18n: FromDishka[TranslatorRunner],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    current_enabled = bool(dialog_manager.dialog_data.get("use_promocode_button"))
    promocode_code = _normalize_promocode(dialog_manager.dialog_data.get("promocode_code"))

    if not current_enabled and not promocode_code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-promocode-code-required"),
        )
        await dialog_manager.switch_to(state=DashboardBroadcast.PROMOCODE)
        return

    dialog_manager.dialog_data["use_promocode_button"] = not current_enabled
    _refresh_payload_keyboard(dialog_manager=dialog_manager, config=config, i18n=i18n)

    status_key = (
        "ntf-broadcast-promocode-button-enabled"
        if dialog_manager.dialog_data["use_promocode_button"]
        else "ntf-broadcast-promocode-button-disabled"
    )
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key=status_key),
    )


@inject
async def on_promocode_clear(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    i18n: FromDishka[TranslatorRunner],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    dialog_manager.dialog_data["promocode_code"] = ""
    dialog_manager.dialog_data["use_promocode_button"] = False
    _refresh_payload_keyboard(dialog_manager=dialog_manager, config=config, i18n=i18n)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-broadcast-promocode-cleared"),
    )


@inject
async def on_promocode_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    i18n: FromDishka[TranslatorRunner],
    notification_service: FromDishka[NotificationService],
    promocode_service: FromDishka[PromocodeService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    promocode_code = _normalize_promocode(message.text)

    if not promocode_code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-promocode-code-required"),
        )
        return

    promocode = await promocode_service.get_by_code(promocode_code)
    if not promocode:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-promocode-not-found"),
        )
        return

    promocode_error_key = _get_broadcast_promocode_error_key(promocode)
    if promocode_error_key:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key=promocode_error_key),
        )
        return

    dialog_manager.dialog_data["promocode_code"] = promocode_code
    dialog_manager.dialog_data["use_promocode_button"] = True
    _refresh_payload_keyboard(dialog_manager=dialog_manager, config=config, i18n=i18n)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-broadcast-promocode-saved",
            i18n_kwargs={"code": promocode_code},
        ),
    )


@inject
async def on_preview(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    payload = dialog_manager.dialog_data.get("payload")

    if not payload:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-empty-content"),
        )
        return

    await notification_service.notify_user(
        user=user, payload=MessagePayload.model_validate(payload)
    )


@inject
async def on_send(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    i18n: FromDishka[TranslatorRunner],
    notification_service: FromDishka[NotificationService],
    broadcast_service: FromDishka[BroadcastService],
    promocode_service: FromDishka[PromocodeService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    audience: Optional[BroadcastAudience] = dialog_manager.dialog_data.get("audience_type")
    plan_id = dialog_manager.dialog_data.get("plan_id")
    payload_data = dialog_manager.dialog_data.get("payload")
    use_promocode_button = bool(dialog_manager.dialog_data.get("use_promocode_button"))
    promocode_code = _normalize_promocode(dialog_manager.dialog_data.get("promocode_code"))

    if not payload_data:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-empty-content"),
        )
        return

    if not audience:
        raise ValueError("BroadcastAudience not found in dialog data")

    if use_promocode_button:
        if not promocode_code:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-broadcast-promocode-code-required"),
            )
            return

        promocode = await promocode_service.get_by_code(promocode_code)
        if not promocode:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-promocode-not-found"),
            )
            return

        promocode_error_key = _get_broadcast_promocode_error_key(promocode)
        if promocode_error_key:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key=promocode_error_key),
            )
            return

        if not _build_promocode_button_url(config, promocode_code):
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-broadcast-promocode-webapp-missing"),
            )
            return

    _refresh_payload_keyboard(dialog_manager=dialog_manager, config=config, i18n=i18n)
    payload = MessagePayload.model_validate(dialog_manager.dialog_data["payload"])

    if is_double_click(dialog_manager, key="broadcast_confirm", cooldown=10):
        users = await broadcast_service.get_audience_users(audience, plan_id=plan_id)

        task_id = uuid.uuid4()
        broadcast = BroadcastDto(
            task_id=task_id,
            status=BroadcastStatus.PROCESSING,
            total_count=len(users),
            audience=audience,
            payload=payload,
        )
        broadcast = await broadcast_service.create(broadcast)

        task = (
            await send_broadcast_task.kicker()
            .with_task_id(str(task_id))
            .kiq(broadcast, users, payload)
        )

        dialog_manager.dialog_data["task_id"] = task.task_id
        await dialog_manager.switch_to(state=DashboardBroadcast.VIEW)
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )
    logger.debug(f"{log(user)} Awaiting confirmation for broadcast send")


@inject
async def on_cancel(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    broadcast_service: FromDishka[BroadcastService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    task_id = dialog_manager.dialog_data["task_id"]
    broadcast = await broadcast_service.get(task_id)

    if not broadcast:
        raise ValueError(f"Broadcast '{task_id}' not found")

    if broadcast.status != BroadcastStatus.PROCESSING:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-not-cancelable"),
        )
        return

    broadcast.status = BroadcastStatus.CANCELED
    await broadcast_service.update(broadcast)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-broadcast-canceled"),
    )


@inject
async def on_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    broadcast_service: FromDishka[BroadcastService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    task_id = dialog_manager.dialog_data["task_id"]
    broadcast = await broadcast_service.get(task_id)

    if not broadcast:
        raise ValueError(f"Broadcast '{task_id}' not found")

    if broadcast.status == BroadcastStatus.DELETED:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-already-deleted"),
        )
        return

    broadcast.status = BroadcastStatus.DELETED
    await broadcast_service.update(broadcast)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-broadcast-deleting"),
    )

    task = await delete_broadcast_task.kiq(broadcast)
    result = await task.wait_result()
    total_count, deleted_count, failed_count = result.return_value

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-broadcast-deleted-success",
            i18n_kwargs={
                "task_id": str(broadcast.task_id),
                "total_count": total_count,
                "deleted_count": deleted_count,
                "failed_count": failed_count,
            },
            auto_delete_after=None,
            add_close_button=True,
        ),
    )
