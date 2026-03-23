from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.utils.branding import resolve_bot_menu_button_text
from src.services.settings import SettingsService


@inject
async def dashboard_main_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    branding = await settings_service.get_branding_settings()
    return {
        "dashboard_shop_label": resolve_bot_menu_button_text(
            branding.bot_menu_button_text,
            project_name=branding.project_name,
        ),
    }
