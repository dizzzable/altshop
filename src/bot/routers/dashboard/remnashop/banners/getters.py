from pathlib import Path
from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.constants import CONFIG_KEY
from src.core.enums import BannerFormat, BannerName

ALL_BANNER_LOCALE = "all"
ALL_BANNER_SECTION = "__all_sections__"

_BANNER_SECTION_LABEL_KEYS = {
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


def _resolve_section_display_name(section_key: str, i18n: TranslatorRunner) -> str:
    label_key = _BANNER_SECTION_LABEL_KEYS.get(section_key)
    if label_key is None:
        return section_key.replace("_", " ").title()
    return i18n.get(label_key)


def _resolve_locale_display_name(locale_key: str, i18n: TranslatorRunner) -> str:
    label_key = _BANNER_LOCALE_LABEL_KEYS.get(locale_key.lower())
    if label_key is not None:
        return i18n.get(label_key)
    return locale_key.upper()


def _resolve_banner_target_sections(section_key: str) -> list[BannerName]:
    if section_key == ALL_BANNER_SECTION:
        return _real_banner_sections()
    return [BannerName(section_key)]


def _resolve_banner_target_locales(config: Any, locale_key: str) -> list[str]:
    if locale_key == ALL_BANNER_LOCALE:
        return [locale.value for locale in config.locales]
    return [locale_key]


def _build_locale_scope_items(
    *,
    config: Any,
    selected_locale: str,
    i18n: TranslatorRunner,
) -> list[dict[str, Any]]:
    return [
        {
            "locale": ALL_BANNER_LOCALE,
            "display_name": _resolve_locale_display_name(ALL_BANNER_LOCALE, i18n),
            "selected": 1 if selected_locale == ALL_BANNER_LOCALE else 0,
        },
        *[
            {
                "locale": locale.value,
                "display_name": _resolve_locale_display_name(locale.value, i18n),
                "selected": 1 if selected_locale == locale.value else 0,
            }
            for locale in config.locales
        ],
    ]


def _build_scope_summary(
    *,
    banners_dir: Path,
    section_key: str,
    locale_key: str,
    config: Any,
    i18n: TranslatorRunner,
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
        return i18n.get("msg-banner-scope-status-empty")

    return i18n.get(
        "msg-banner-scope-status-progress",
        uploaded=uploaded_targets,
        total=total_targets,
    )


@inject
async def banners_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    config = dialog_manager.middleware_data[CONFIG_KEY]
    return _build_banners_payload(config=config, i18n=i18n)


@inject
async def banner_select_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    config = dialog_manager.middleware_data[CONFIG_KEY]
    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")
    locale_key = str(dialog_manager.dialog_data.get("locale") or config.default_locale.value)
    return _build_banner_select_payload(
        config=config,
        section_key=section_key,
        locale_key=locale_key,
        i18n=i18n,
    )


@inject
async def banner_upload_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    config = dialog_manager.middleware_data[CONFIG_KEY]

    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")
    locale_key = str(dialog_manager.dialog_data.get("locale") or config.default_locale.value)

    return _build_banner_upload_payload(
        section_key=section_key,
        locale_key=locale_key,
        i18n=i18n,
    )


@inject
async def banner_confirm_delete_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    del kwargs
    config = dialog_manager.middleware_data[CONFIG_KEY]

    section_key = str(dialog_manager.dialog_data.get("banner_name") or "")
    locale_key = str(dialog_manager.dialog_data.get("locale") or config.default_locale.value)

    return _build_banner_confirm_delete_payload(
        section_key=section_key,
        locale_key=locale_key,
        i18n=i18n,
    )


def _build_banners_payload(*, config: Any, i18n: TranslatorRunner) -> dict[str, Any]:
    banners: list[dict[str, Any]] = [
        {
            "name": banner_name.value,
            "icon": "🖼️",
            "display_name": _resolve_section_display_name(banner_name.value, i18n),
        }
        for banner_name in _real_banner_sections()
    ]
    banners.append(
        {
            "name": ALL_BANNER_SECTION,
            "icon": "📣",
            "display_name": _resolve_section_display_name(ALL_BANNER_SECTION, i18n),
        }
    )

    default_banner_path = config.banners_dir / f"{BannerName.DEFAULT}.{BannerFormat.JPG}"
    return {
        "banners": banners,
        "default_banner_exists": default_banner_path.exists(),
        "use_banners": config.bot.use_banners,
    }


def _build_banner_select_payload(
    *,
    config: Any,
    section_key: str,
    locale_key: str,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(section_key, i18n),
        "locale": locale_key,
        "locale_display_name": _resolve_locale_display_name(locale_key, i18n),
        "locale_scope_items": _build_locale_scope_items(
            config=config,
            selected_locale=locale_key,
            i18n=i18n,
        ),
        "scope_summary": _build_scope_summary(
            banners_dir=config.banners_dir,
            section_key=section_key,
            locale_key=locale_key,
            config=config,
            i18n=i18n,
        ),
        "has_banner": any(
            get_banner_info(config.banners_dir, section, locale)["exists"]
            for section in _resolve_banner_target_sections(section_key)
            for locale in _resolve_banner_target_locales(config, locale_key)
        ),
        "is_bulk_section": section_key == ALL_BANNER_SECTION,
    }


def _build_banner_upload_payload(
    *,
    section_key: str,
    locale_key: str,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(section_key, i18n),
        "locale": locale_key,
        "locale_display_name": _resolve_locale_display_name(locale_key, i18n),
        "supported_formats": ", ".join(
            banner_format.value.upper() for banner_format in BannerFormat
        ),
    }


def _build_banner_confirm_delete_payload(
    *,
    section_key: str,
    locale_key: str,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    return {
        "banner_name": section_key,
        "banner_display_name": _resolve_section_display_name(section_key, i18n),
        "locale": locale_key,
        "locale_display_name": _resolve_locale_display_name(locale_key, i18n),
    }
