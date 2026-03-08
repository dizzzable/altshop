from pathlib import Path

from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select
from loguru import logger

from src.bot.states import RemnashopBanners
from src.bot.widgets.banner import get_banner
from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, USER_KEY
from src.core.enums import BannerFormat
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto

SUPPORTED_BANNER_MIME_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}

BANNER_NOT_SELECTED = "Баннер не выбран"
ANIMATION_MISSING = "Не удалось получить animation"
FILE_TYPE_MISSING = "Не удалось определить тип файла"
FILE_MISSING = "Не удалось получить файл"
BANNER_DELETED = "Баннер удален"
BANNER_NOT_FOUND = "Баннер не найден"
UPLOAD_PROMPT = (
    "Отправьте изображение "
    "(фото, GIF или документ) "
    "для загрузки баннера"
)
UNSUPPORTED_FORMAT_TEMPLATE = (
    "Неподдерживаемый формат файла. "
    "Поддерживаются: {formats}"
)
UPLOAD_SUCCESS_TEMPLATE = (
    "✅ Баннер '{banner_name}' "
    "успешно загружен для локали '{locale}'"
)


def _get_banner_upload_context(
    dialog_manager: DialogManager,
    config: AppConfig,
) -> tuple[str | None, str]:
    return (
        dialog_manager.dialog_data.get("banner_name"),
        dialog_manager.dialog_data.get("locale", config.default_locale.value),
    )


def _resolve_supported_banner_formats_text() -> str:
    return ", ".join(banner_format.value.upper() for banner_format in BannerFormat)


def _resolve_banner_upload_file(message: Message) -> tuple[str, str]:
    if message.content_type == ContentType.PHOTO:
        return message.photo[-1].file_id, "jpg"

    if message.content_type == ContentType.ANIMATION:
        animation = message.animation
        if not animation:
            raise ValueError(ANIMATION_MISSING)
        return animation.file_id, "gif"

    if message.content_type == ContentType.DOCUMENT:
        document = message.document
        if not document or not document.mime_type:
            raise ValueError(FILE_TYPE_MISSING)

        file_ext = SUPPORTED_BANNER_MIME_TYPES.get(document.mime_type)
        if not file_ext:
            raise ValueError(
                UNSUPPORTED_FORMAT_TEMPLATE.format(
                    formats=_resolve_supported_banner_formats_text(),
                )
            )
        return document.file_id, file_ext

    raise ValueError(UPLOAD_PROMPT)


def _delete_existing_banner_versions(path_locale: Path, banner_name: str) -> None:
    for banner_format in BannerFormat:
        old_path = path_locale / f"{banner_name}.{banner_format}"
        if old_path.exists():
            old_path.unlink()


async def on_banner_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
) -> None:
    """Handle selecting a banner to edit."""
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
    """Handle selecting a banner locale."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    dialog_manager.dialog_data["locale"] = item_id
    logger.info(f"{log(user)} Selected locale '{item_id}' for banner")


async def on_upload_banner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Switch to the banner upload screen."""
    await dialog_manager.switch_to(RemnashopBanners.UPLOAD_BANNER)


async def on_delete_banner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Switch to the banner delete confirmation screen."""
    await dialog_manager.switch_to(RemnashopBanners.CONFIRM_DELETE)


async def on_confirm_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Delete all stored variants of the selected banner."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    banner_name, locale = _get_banner_upload_context(dialog_manager, config)
    if not banner_name:
        await callback.answer(BANNER_NOT_SELECTED, show_alert=True)
        return

    path_locale = config.banners_dir / locale
    deleted = False
    for banner_format in BannerFormat:
        path = path_locale / f"{banner_name}.{banner_format}"
        if path.exists():
            path.unlink()
            deleted = True
            logger.info(
                f"{log(user)} Deleted banner '{banner_name}' "
                f"({banner_format}) for locale '{locale}'"
            )

    if deleted:
        get_banner.cache_clear()
        await callback.answer(BANNER_DELETED, show_alert=True)
    else:
        await callback.answer(BANNER_NOT_FOUND, show_alert=True)

    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)


async def on_banner_upload_input(
    message: Message,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Store a newly uploaded banner file."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    banner_name, locale = _get_banner_upload_context(dialog_manager, config)
    if not banner_name:
        await message.answer(BANNER_NOT_SELECTED)
        return

    try:
        file_id, file_ext = _resolve_banner_upload_file(message)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    file = await message.bot.get_file(file_id)
    if not file.file_path:
        await message.answer(FILE_MISSING)
        return

    path_locale = config.banners_dir / locale
    path_locale.mkdir(parents=True, exist_ok=True)
    _delete_existing_banner_versions(path_locale, banner_name)

    new_path = path_locale / f"{banner_name}.{file_ext}"
    await message.bot.download_file(file.file_path, new_path)
    get_banner.cache_clear()

    logger.info(f"{log(user)} Uploaded banner '{banner_name}' ({file_ext}) for locale '{locale}'")
    await message.answer(
        UPLOAD_SUCCESS_TEMPLATE.format(
            banner_name=banner_name,
            locale=locale,
        )
    )
    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)
