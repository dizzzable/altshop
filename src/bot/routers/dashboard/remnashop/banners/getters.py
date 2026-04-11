from pathlib import Path
from typing import Any

from aiogram_dialog import DialogManager

from src.core.config import AppConfig
from src.core.constants import CONFIG_KEY
from src.core.enums import BannerFormat, BannerName

ALL_BANNER_LOCALE = "all"
ALL_BANNER_SECTION = "__all_sections__"


def get_banner_info(banners_dir: Path, name: BannerName, locale: str) -> dict[str, Any]:
    path_locale = banners_dir / locale

    for banner_format in BannerFormat:
        path = path_locale / f"{name}.{banner_format}"
        if path.exists():
            return {
                "exists": True,
                "path": str(path),
                "format": banner_format.value,
                "size": path.stat().st_size,
            }

    return {
        "exists": False,
        "path": None,
        "format": None,
        "size": 0,
    }


def _real_banner_sections() -> list[BannerName]:
    return [banner_name for banner_name in BannerName if banner_name != BannerName.DEFAULT]


def _resolve_admin_locale(dialog_manager: DialogManager, config: AppConfig) -> str:
    user = dialog_manager.middleware_data.get("user")
    language = getattr(user, "language", None)
    return str(getattr(language, "value", language) or config.default_locale.value).lower()


def _translate_banner_meta(dialog_manager: DialogManager, config: AppConfig, key: str) -> str:
    is_ru = _resolve_admin_locale(dialog_manager, config).startswith("ru")
    values = {
        "section_all": "📣 Для всех" if is_ru else "📣 For all",
        "section_menu": "🖼️ Меню" if is_ru else "🖼️ Menu",
        "section_dashboard": "🖼️ Dashboard",
        "section_subscription": "🖼️ Подписки" if is_ru else "🖼️ Subscription",
        "section_promocode": "🖼️ Промокоды" if is_ru else "🖼️ Promocode",
        "section_referral": "🖼️ Рефералка" if is_ru else "🖼️ Referral",
        "locale_all": "Для всех локалей" if is_ru else "All locales",
        "locale_ru": "🇷🇺 RU",
        "locale_en": "🇬🇧 EN",
        "scope_empty": "Нет выбранных целей" if is_ru else "No targets selected",
        "scope_progress": "Загружено целей" if is_ru else "Uploaded targets",
    }
    return values[key]


def _resolve_section_display_name(
    section_key: str,
    dialog_manager: DialogManager,
    config: AppConfig,
) -> str:
    if section_key == ALL_BANNER_SECTION:
        return _translate_banner_meta(dialog_manager, config, "section_all")
    section_map = {
        BannerName.MENU.value: "section_menu",
        BannerName.DASHBOARD.value: "section_dashboard",
        BannerName.SUBSCRIPTION.value: "section_subscription",
        BannerName.PROMOCODE.value: "section_promocode",
        BannerName.REFERRAL.value: "section_referral",
    }
    return _translate_banner_meta(dialog_manager, config, section_map[section_key])


def _resolve_locale_display_name(
    locale_key: str,
    dialog_manager: DialogManager,
    config: AppConfig,
) -> str:
    if locale_key == ALL_BANNER_LOCALE:
        return _translate_banner_meta(dialog_manager, config, "locale_all")
    if locale_key.lower() == "ru":
        return _translate_banner_meta(dialog_manager, config, "locale_ru")
    if locale_key.lower() == "en":
        return _translate_banner_meta(dialog_manager, config, "locale_en")
    return locale_key.upper()


def _resolve_banner_target_sections(section_key: str) -> list[BannerName]:
    if section_key == ALL_BANNER_SECTION:
        return _real_banner_sections()
    return [BannerName(section_key)]


def _resolve_banner_target_locales(config: AppConfig, locale_key: str) -> list[str]:
    if locale_key == ALL_BANNER_LOCALE:
        return [locale.value for locale in config.locales]
    return [locale_key]


def _build_scope_summary(
    *,
    banners_dir: Path,
    section_key: str,
    locale_key: str,
    config: AppConfig,
    dialog_manager: DialogManager,
) -> str:
    target_sections = _resolve_banner_target_sections(section_key)
    target_locales = _resolve_banner_target_locales(config, locale_key)
    total_targets = len(target_sections) * len(target_locales)
    uploaded_targets = 0

    for section in target_sections:
        for locale in target_locales:
            if get_banner_info(banners_dir, section, locale)["exists"]:
                uploaded_targets += 1

    if total_targets == 0:
        return _translate_banner_meta(dialog_manager, config, "scope_empty")

    if uploaded_targets == 0:
        label = _translate_banner_meta(dialog_manager, config, "scope_progress")
        return f"{label}: 0 / {total_targets}"

    label = _translate_banner_meta(dialog_manager, config, "scope_progress")
    return f"{label}: {uploaded_targets} / {total_targets}"


async def banners_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    banners: list[dict[str, Any]] = [
        {
            "name": banner_name.value,
            "icon": "🖼️",
            "display_name": _resolve_section_display_name(
                banner_name.value,
                dialog_manager,
                config,
            ),
        }
        for banner_name in _real_banner_sections()
    ]
    banners.append(
        {
            "name": ALL_BANNER_SECTION,
            "icon": "📣",
            "display_name": _resolve_section_display_name(
                ALL_BANNER_SECTION,
                dialog_manager,
                config,
            ),
        }
    )

    default_banner_path = config.banners_dir / f"{BannerName.DEFAULT}.{BannerFormat.JPG}"
    default_banner_exists = default_banner_path.exists()

    return {
        "banners": banners,
        "default_banner_exists": default_banner_exists,
        "use_banners": config.bot.use_banners,
    }


async def banner_locale_scope_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")

    locale_scope_items = [
        {
            "locale": ALL_BANNER_LOCALE,
            "display_name": _resolve_locale_display_name(
                ALL_BANNER_LOCALE,
                dialog_manager,
                config,
            ),
            "selected": 1 if dialog_manager.dialog_data.get("locale") == ALL_BANNER_LOCALE else 0,
        },
        *[
            {
                "locale": locale.value,
                "display_name": locale.value.upper(),
                "selected": 1 if dialog_manager.dialog_data.get("locale") == locale.value else 0,
            }
            for locale in config.locales
        ],
    ]

    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(
            section_key,
            dialog_manager,
            config,
        ),
        "locale_scope_items": locale_scope_items,
    }


async def banner_select_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]
    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")
    locale_key = str(dialog_manager.dialog_data.get("locale") or config.default_locale.value)

    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(
            section_key,
            dialog_manager,
            config,
        ),
        "locale": locale_key,
        "locale_display_name": _resolve_locale_display_name(
            locale_key,
            dialog_manager,
            config,
        ),
        "scope_summary": _build_scope_summary(
            banners_dir=config.banners_dir,
            section_key=section_key,
            locale_key=locale_key,
            config=config,
            dialog_manager=dialog_manager,
        ),
        "has_banner": any(
            get_banner_info(config.banners_dir, section, locale)["exists"]
            for section in _resolve_banner_target_sections(section_key)
            for locale in _resolve_banner_target_locales(config, locale_key)
        ),
        "is_bulk_section": section_key == ALL_BANNER_SECTION,
    }


async def banner_upload_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")
    locale_key = str(dialog_manager.dialog_data.get("locale") or config.default_locale.value)

    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(
            section_key,
            dialog_manager,
            config,
        ),
        "locale": locale_key,
        "locale_display_name": _resolve_locale_display_name(
            locale_key,
            dialog_manager,
            config,
        ),
        "supported_formats": ", ".join(
            [banner_format.value.upper() for banner_format in BannerFormat]
        ),
    }


async def banner_confirm_delete_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    config: AppConfig = dialog_manager.middleware_data[CONFIG_KEY]

    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")
    locale_key = str(dialog_manager.dialog_data.get("locale") or config.default_locale.value)

    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(
            section_key,
            dialog_manager,
            config,
        ),
        "locale": locale_key,
        "locale_display_name": _resolve_locale_display_name(
            locale_key,
            dialog_manager,
            config,
        ),
    }
