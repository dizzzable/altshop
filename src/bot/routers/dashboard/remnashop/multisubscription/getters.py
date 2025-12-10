from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.services.settings import SettingsService


@inject
async def multi_subscription_main_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для главного окна настроек мультиподписок."""
    settings = await settings_service.get_multi_subscription_settings()
    
    return {
        "is_enabled": 1 if settings.enabled else 0,
        "default_max": settings.default_max_subscriptions,
        "is_single_mode": settings.is_single_subscription_mode,
    }


@inject
async def max_subscriptions_getter(
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для окна выбора максимального количества подписок."""
    settings = await settings_service.get_multi_subscription_settings()
    
    # Предлагаемые варианты количества подписок
    subscription_options = [
        {"value": 1, "label": "1 "},
        {"value": 2, "label": "2"},
        {"value": 3, "label": "3"},
        {"value": 5, "label": "5"},
        {"value": 10, "label": "10"},
        {"value": -1, "label": "∞ (безлимит)"},
    ]
    
    return {
        "current_max": settings.default_max_subscriptions,
        "subscription_options": subscription_options,
    }