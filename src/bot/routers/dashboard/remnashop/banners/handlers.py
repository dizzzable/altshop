import shutil
from pathlib import Path

from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select
from loguru import logger

from src.bot.states import RemnashopBanners
from src.bot.widgets.banner import get_banner
from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, USER_KEY
from src.core.enums import BannerFormat, BannerName, Locale
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto


async def on_banner_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
) -> None:
    """Обработчик выбора баннера для редактирования."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    
    dialog_manager.dialog_data["banner_name"] = item_id
    dialog_manager.dialog_data["locale"] = config.default_locale.value
    
    logger.info(f"{log(user)} Selected banner '{item_id}' for editing")
    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)


async def on_locale_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
) -> None:
    """Обработчик выбора локали для баннера."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    dialog_manager.dialog_data["locale"] = item_id
    
    logger.info(f"{log(user)} Selected locale '{item_id}' for banner")


async def on_upload_banner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переход к загрузке баннера."""
    await dialog_manager.switch_to(RemnashopBanners.UPLOAD_BANNER)


async def on_delete_banner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переход к подтверждению удаления баннера."""
    await dialog_manager.switch_to(RemnashopBanners.CONFIRM_DELETE)


async def on_confirm_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Подтверждение удаления баннера."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    
    banner_name = dialog_manager.dialog_data.get("banner_name")
    locale = dialog_manager.dialog_data.get("locale", config.default_locale.value)
    
    if not banner_name:
        await callback.answer("Баннер не выбран", show_alert=True)
        return
    
    banners_dir = config.banners_dir
    path_locale = banners_dir / locale
    
    # Удаляем все форматы баннера
    deleted = False
    for format in BannerFormat:
        path = path_locale / f"{banner_name}.{format}"
        if path.exists():
            path.unlink()
            deleted = True
            logger.info(f"{log(user)} Deleted banner '{banner_name}' ({format}) for locale '{locale}'")
    
    if deleted:
        # Очищаем кэш баннеров
        get_banner.cache_clear()
        await callback.answer("Баннер удален", show_alert=True)
    else:
        await callback.answer("Баннер не найден", show_alert=True)
    
    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)


async def on_banner_upload_input(
    message: Message,
    widget: any,
    dialog_manager: DialogManager,
) -> None:
    """Обработчик загрузки нового баннера."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    
    banner_name = dialog_manager.dialog_data.get("banner_name")
    locale = dialog_manager.dialog_data.get("locale", config.default_locale.value)
    
    if not banner_name:
        await message.answer("Баннер не выбран")
        return
    
    # Проверяем тип контента
    if message.content_type == ContentType.PHOTO:
        # Получаем фото максимального размера
        photo = message.photo[-1]
        file_id = photo.file_id
        file_ext = "jpg"
    elif message.content_type == ContentType.ANIMATION:
        animation = message.animation
        file_id = animation.file_id
        file_ext = "gif"
    elif message.content_type == ContentType.DOCUMENT:
        document = message.document
        if not document.mime_type:
            await message.answer("Не удалось определить тип файла")
            return
        
        # Определяем расширение по MIME типу
        mime_to_ext = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
        }
        
        file_ext = mime_to_ext.get(document.mime_type)
        if not file_ext:
            await message.answer(
                f"Неподдерживаемый формат файла. "
                f"Поддерживаются: {', '.join([f.value.upper() for f in BannerFormat])}"
            )
            return
        
        file_id = document.file_id
    else:
        await message.answer(
            "Отправьте изображение (фото, GIF или документ) для загрузки баннера"
        )
        return
    
    # Скачиваем файл
    bot = message.bot
    file = await bot.get_file(file_id)
    
    if not file.file_path:
        await message.answer("Не удалось получить файл")
        return
    
    # Создаем директорию для локали если не существует
    banners_dir = config.banners_dir
    path_locale = banners_dir / locale
    path_locale.mkdir(parents=True, exist_ok=True)
    
    # Удаляем старые версии баннера (все форматы)
    for format in BannerFormat:
        old_path = path_locale / f"{banner_name}.{format}"
        if old_path.exists():
            old_path.unlink()
    
    # Сохраняем новый баннер
    new_path = path_locale / f"{banner_name}.{file_ext}"
    await bot.download_file(file.file_path, new_path)
    
    # Очищаем кэш баннеров
    get_banner.cache_clear()
    
    logger.info(f"{log(user)} Uploaded banner '{banner_name}' ({file_ext}) for locale '{locale}'")
    
    await message.answer(f"✅ Баннер '{banner_name}' успешно загружен для локали '{locale}'")
    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)