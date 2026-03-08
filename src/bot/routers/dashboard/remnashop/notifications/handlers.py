from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.core.constants import USER_KEY
from src.core.enums import SystemNotificationType, UserNotificationType
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto
from src.services.settings import SettingsService


@inject
async def on_user_type_select(
    callback: CallbackQuery,
    widget: Select[UserNotificationType],
    dialog_manager: DialogManager,
    selected_type: UserNotificationType,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    new_value = await settings_service.toggle_notification(selected_type)
    logger.info(f"{log(user)} Change notification type: '{selected_type}' to '{new_value}'")


@inject
async def on_system_type_select(
    callback: CallbackQuery,
    widget: Select[SystemNotificationType],
    dialog_manager: DialogManager,
    selected_type: SystemNotificationType,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    new_value = await settings_service.toggle_notification(selected_type)
    logger.info(f"{log(user)} Change notification type: '{selected_type}' to '{new_value}'")
