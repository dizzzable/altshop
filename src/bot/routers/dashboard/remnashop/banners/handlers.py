from pathlib import Path
from tempfile import NamedTemporaryFile

from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.states import RemnashopBanners
from src.bot.widgets.banner import get_banner
from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY, USER_KEY
from src.core.enums import BannerFormat, BannerName
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto

ALL_BANNER_LOCALE = "all"
ALL_BANNER_SECTION = "__all_sections__"

SUPPORTED_BANNER_MIME_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
_BANNER_SCOPE_LABEL_KEYS = {
    ALL_BANNER_SECTION: "msg-banner-section-all",
    BannerName.MENU.value: "msg-banner-section-menu",
    BannerName.DASHBOARD.value: "msg-banner-section-dashboard",
    BannerName.SUBSCRIPTION.value: "msg-banner-section-subscription",
    BannerName.PROMOCODE.value: "msg-banner-section-promocode",
    BannerName.REFERRAL.value: "msg-banner-section-referral",
}
_BANNER_LOCALE_LABEL_KEYS = {
    ALL_BANNER_LOCALE: "msg-banner-locale-all",
    "ru": "msg-banner-locale-ru",
    "en": "msg-banner-locale-en",
}


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


def _resolve_banner_upload_file(
    message: Message,
    i18n: TranslatorRunner,
) -> tuple[str, str]:
    if message.content_type == ContentType.PHOTO:
        return message.photo[-1].file_id, "jpg"

    if message.content_type == ContentType.ANIMATION:
        animation = message.animation
        if not animation:
            raise ValueError(i18n.get("ntf-banner-animation-missing"))
        return animation.file_id, "gif"

    if message.content_type == ContentType.DOCUMENT:
        document = message.document
        if not document or not document.mime_type:
            raise ValueError(i18n.get("ntf-banner-file-type-missing"))

        file_ext = SUPPORTED_BANNER_MIME_TYPES.get(document.mime_type)
        if not file_ext:
            raise ValueError(
                i18n.get(
                    "ntf-banner-upload-unsupported",
                    formats=_resolve_supported_banner_formats_text(),
                )
            )
        return document.file_id, file_ext

    raise ValueError(i18n.get("ntf-banner-upload-prompt"))


def _delete_existing_banner_versions(path_locale: Path, banner_name: str) -> None:
    for banner_format in BannerFormat:
        old_path = path_locale / f"{banner_name}.{banner_format}"
        if old_path.exists():
            old_path.unlink()


def _resolve_banner_target_locales(config: AppConfig, locale: str) -> list[str]:
    if locale == ALL_BANNER_LOCALE:
        return [item.value for item in config.locales]
    return [locale]


def _resolve_banner_target_sections(section_key: str) -> list[BannerName]:
    if section_key == ALL_BANNER_SECTION:
        return [banner_name for banner_name in BannerName if banner_name != BannerName.DEFAULT]
    return [BannerName(section_key)]


def _resolve_banner_scope_label(i18n: TranslatorRunner, section_key: str) -> str:
    label_key = _BANNER_SCOPE_LABEL_KEYS.get(section_key)
    if label_key is not None:
        return i18n.get(label_key)
    return section_key.replace("_", " ").title()


def _resolve_banner_locale_label(i18n: TranslatorRunner, locale_key: str) -> str:
    label_key = _BANNER_LOCALE_LABEL_KEYS.get(locale_key.lower())
    if label_key is not None:
        return i18n.get(label_key)
    return locale_key.upper()


def _build_banner_target_paths(
    config: AppConfig,
    *,
    banner_name: str,
    locale: str,
    file_ext: str,
) -> list[Path]:
    target_paths: list[Path] = []

    for target_section in _resolve_banner_target_sections(banner_name):
        for target_locale in _resolve_banner_target_locales(config, locale):
            path_locale = config.banners_dir / target_locale
            path_locale.mkdir(parents=True, exist_ok=True)
            _delete_existing_banner_versions(path_locale, target_section.value)
            target_paths.append(path_locale / f"{target_section.value}.{file_ext}")

    return target_paths


def _store_banner_bytes(
    config: AppConfig,
    *,
    banner_name: str,
    locale: str,
    file_ext: str,
    file_bytes: bytes,
) -> list[Path]:
    target_paths = _build_banner_target_paths(
        config,
        banner_name=banner_name,
        locale=locale,
        file_ext=file_ext,
    )
    for target_path in target_paths:
        target_path.write_bytes(file_bytes)
    return target_paths


async def on_banner_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
) -> None:
    del callback, widget
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
    del callback, widget
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    dialog_manager.dialog_data["locale"] = item_id
    logger.info(f"{log(user)} Selected locale '{item_id}' for banner")
    await dialog_manager.show()


async def on_upload_banner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    del callback, widget
    await dialog_manager.switch_to(RemnashopBanners.UPLOAD_BANNER)


async def on_delete_banner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    del callback, widget
    await dialog_manager.switch_to(RemnashopBanners.CONFIRM_DELETE)


@inject
async def on_confirm_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    del widget
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    banner_name, locale = _get_banner_upload_context(dialog_manager, config)
    if not banner_name:
        await callback.answer(i18n.get("ntf-banner-not-selected"), show_alert=True)
        return

    deleted = False
    target_sections = _resolve_banner_target_sections(banner_name)
    for target_locale in _resolve_banner_target_locales(config, locale):
        path_locale = config.banners_dir / target_locale
        for target_section in target_sections:
            for banner_format in BannerFormat:
                path = path_locale / f"{target_section}.{banner_format}"
                if path.exists():
                    path.unlink()
                    deleted = True
                    logger.info(
                        f"{log(user)} Deleted banner '{target_section}' "
                        f"({banner_format}) for locale '{target_locale}'"
                    )

    if deleted:
        get_banner.cache_clear()
        await callback.answer(i18n.get("ntf-banner-deleted"), show_alert=True)
    else:
        await callback.answer(i18n.get("ntf-banner-not-found"), show_alert=True)

    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)


@inject
async def on_banner_upload_input(
    message: Message,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    del widget
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    banner_name, locale = _get_banner_upload_context(dialog_manager, config)
    if not banner_name:
        await message.answer(i18n.get("ntf-banner-not-selected"))
        return

    try:
        file_id, file_ext = _resolve_banner_upload_file(message, i18n)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    file = await message.bot.get_file(file_id)
    if not file.file_path:
        await message.answer(i18n.get("ntf-banner-file-missing"))
        return

    with NamedTemporaryFile(suffix=f".{file_ext}") as temporary_file:
        temporary_path = Path(temporary_file.name)
        await message.bot.download_file(file.file_path, temporary_path)
        file_bytes = temporary_path.read_bytes()

    _store_banner_bytes(
        config,
        banner_name=banner_name,
        locale=locale,
        file_ext=file_ext,
        file_bytes=file_bytes,
    )

    get_banner.cache_clear()

    logger.info(f"{log(user)} Uploaded banner '{banner_name}' ({file_ext}) for locale '{locale}'")
    await message.answer(
        i18n.get(
            "ntf-banner-upload-success",
            banner_name=_resolve_banner_scope_label(i18n, banner_name),
            locale=_resolve_banner_locale_label(i18n, locale),
        )
    )
    await dialog_manager.switch_to(RemnashopBanners.SELECT_BANNER)
