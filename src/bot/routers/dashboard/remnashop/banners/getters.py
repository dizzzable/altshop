from pathlib import Path
from typing import Any

from aiogram_dialog import DialogManager

from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY
from src.core.enums import BannerFormat, BannerName, Locale


def get_banner_info(banners_dir: Path, name: BannerName, locale: Locale) -> dict[str, Any]:
    """Получает информацию о баннере."""
    path_locale = banners_dir / locale
    
    for format in BannerFormat:
        path = path_locale / f"{name}.{format}"
        if path.exists():
            return {
                "exists": True,
                "path": str(path),
                "format": format.value,
                "size": path.stat().st_size,
            }
    
    return {
        "exists": False,
        "path": None,
        "format": None,
        "size": 0,
    }


async def banners_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для списка баннеров."""
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    banners_dir = config.banners_dir
    
    # Получаем список локалей
    locales = config.locales
    default_locale = config.default_locale
    
    # Собираем информацию о баннерах
    banners = []
    for banner_name in BannerName:
        if banner_name == BannerName.DEFAULT:
            continue  # Пропускаем дефолтный баннер
            
        banner_info = {
            "name": banner_name.value,
            "display_name": banner_name.value.replace("_", " ").title(),
            "locales": {},
        }
        
        for locale in locales:
            info = get_banner_info(banners_dir, banner_name, locale)
            banner_info["locales"][locale.value] = info
        
        banners.append(banner_info)
    
    # Информация о дефолтном баннере
    default_banner_path = banners_dir / f"{BannerName.DEFAULT}.{BannerFormat.JPG}"
    default_banner_exists = default_banner_path.exists()
    
    return {
        "banners": banners,
        "locales": [locale.value for locale in locales],
        "default_locale": default_locale.value,
        "default_banner_exists": default_banner_exists,
        "use_banners": config.bot.use_banners,
    }


async def banner_select_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для выбора баннера."""
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    
    banner_name = dialog_manager.dialog_data.get("banner_name")
    locale = dialog_manager.dialog_data.get("locale", config.default_locale.value)
    
    banners_dir = config.banners_dir
    
    # Получаем информацию о текущем баннере
    if banner_name:
        banner_info = get_banner_info(
            banners_dir, 
            BannerName(banner_name), 
            Locale(locale)
        )
    else:
        banner_info = {"exists": False}
    
    # Список локалей для выбора
    locale_list = [
        {
            "locale": loc.value,
            "display_name": loc.value.upper(),
            "selected": 1 if loc.value == locale else 0,
        }
        for loc in config.locales
    ]
    
    return {
        "banner_name": banner_name,
        "banner_display_name": banner_name.replace("_", " ").title() if banner_name else "",
        "locale": locale,
        "banner_info": banner_info,
        "locale_list": locale_list,
        "has_banner": banner_info.get("exists", False),
    }


async def banner_upload_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для загрузки баннера."""
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    
    banner_name = dialog_manager.dialog_data.get("banner_name", "")
    locale = dialog_manager.dialog_data.get("locale", config.default_locale.value)
    
    return {
        "banner_name": banner_name,
        "banner_display_name": banner_name.replace("_", " ").title() if banner_name else "",
        "locale": locale,
        "supported_formats": ", ".join([f.value.upper() for f in BannerFormat]),
    }


async def banner_confirm_delete_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для подтверждения удаления баннера."""
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    
    banner_name = dialog_manager.dialog_data.get("banner_name", "")
    locale = dialog_manager.dialog_data.get("locale", config.default_locale.value)
    
    return {
        "banner_name": banner_name,
        "banner_display_name": banner_name.replace("_", " ").title() if banner_name else "",
        "locale": locale,
    }