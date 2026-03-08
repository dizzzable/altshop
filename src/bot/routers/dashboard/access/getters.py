from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.services.access import AccessService
from src.services.settings import SettingsService


@inject
async def access_getter(
    dialog_manager: DialogManager,
    access_service: FromDishka[AccessService],
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    current_mode = await settings_service.get_access_mode()
    modes = await access_service.get_available_modes()

    return {
        "access_mode": current_mode,
        "modes": modes,
    }


@inject
async def conditions_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    settings = await settings_service.get()

    return {
        "rules": settings.rules_required,
        "channel": settings.channel_required,
    }
