from aiogram.types import CallbackQuery, FSInputFile
from aiogram_dialog import DialogManager, SubManager
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.routers.dashboard.users.user.handlers import start_user_window
from src.core.constants import LOG_DIR, USER_KEY
from src.core.enums import MediaType, UserRole
from src.core.logger import LOG_FILENAME
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now
from src.core.utils.validators import is_double_click
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.notification import NotificationService
from src.services.user import UserService


@inject
async def on_logs_request(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    try:
        file = FSInputFile(
            path=LOG_DIR / LOG_FILENAME,
            filename=f"{datetime_now().strftime('%Y-%m-%d_%H-%M-%S')}.log",
        )
    except FileNotFoundError:
        logger.error(f"{log(user)} Log file not found at '{LOG_DIR}/{LOG_FILENAME}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error-log-not-found"),
        )
        return

    logger.info(f"{log(user)} Sending log file '{LOG_DIR / LOG_FILENAME}' as '{file.filename}'")
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="",
            media=file,
            media_type=MediaType.DOCUMENT,
            auto_delete_after=None,
            add_close_button=True,
        ),
    )


@inject
async def on_user_select(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    target_telegram_id = int(sub_manager.item_id)

    logger.info(f"{log(user)} User id '{target_telegram_id}' selected")
    await start_user_window(manager=sub_manager, target_telegram_id=target_telegram_id)


@inject
async def on_user_role_remove(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    target_telegram_id = int(sub_manager.item_id)
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"Attempted to remove role for non-existent user '{target_telegram_id}'")

    if is_double_click(
        sub_manager.manager,
        key=f"role_confirm_{target_telegram_id}",
        cooldown=10,
    ):
        await user_service.set_role(user=target_user, role=UserRole.USER)
        await redirect_to_main_menu_task.kiq(target_user.telegram_id)
        logger.info(f"{log(user)} Changed role for {log(target_user)} to '{UserRole.USER}'")
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )
    logger.debug(f"{log(user)} Waiting for confirmation to delete user role '{target_telegram_id}'")
