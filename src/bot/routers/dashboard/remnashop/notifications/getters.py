from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.services.settings import SettingsService


@inject
async def user_types_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    return {"types": await settings_service.list_user_notifications()}


@inject
async def system_types_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    return {"types": await settings_service.list_system_notifications()}
