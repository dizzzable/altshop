from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from src.core.config import AppConfig
from src.core.enums import BotMenuCustomButtonKind
from src.core.utils.branding import resolve_bot_menu_button_text, resolve_project_name
from src.infrastructure.database.models.dto import (
    BotMenuCustomButtonDto,
    BotMenuSettingsDto,
    BrandingSettingsDto,
)

BOT_MENU_SOURCE_CONFIG = "config"
BOT_MENU_SOURCE_MISSING = "missing"
BOT_MENU_SOURCE_SETTINGS = "settings"
BOT_MENU_MAX_CUSTOM_BUTTONS = 5
_TELEGRAM_MINI_APP_LINK_HOSTS = {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}


@dataclass(slots=True, frozen=True)
class ResolvedBotMenuButton:
    id: str
    label: str
    kind: BotMenuCustomButtonKind
    url: str
    enabled: bool
    order: int

    @property
    def is_url(self) -> bool:
        return self.kind == BotMenuCustomButtonKind.URL

    @property
    def is_web_app(self) -> bool:
        return self.kind == BotMenuCustomButtonKind.WEB_APP


@dataclass(slots=True, frozen=True)
class ResolvedBotMenuState:
    miniapp_only_enabled: bool
    miniapp_only_active: bool
    mini_app_url: str | None
    mini_app_source: str
    primary_button_text: str
    custom_buttons: tuple[ResolvedBotMenuButton, ...]


def resolve_bot_menu_state(
    *,
    bot_menu: BotMenuSettingsDto,
    branding: BrandingSettingsDto,
    config: AppConfig,
) -> ResolvedBotMenuState:
    mini_app_url, mini_app_source = resolve_bot_menu_web_app_url(
        bot_menu=bot_menu,
        config=config,
    )
    custom_buttons = tuple(_resolve_custom_buttons(bot_menu.custom_buttons))

    return ResolvedBotMenuState(
        miniapp_only_enabled=bot_menu.miniapp_only_enabled,
        miniapp_only_active=bot_menu.miniapp_only_enabled and bool(mini_app_url),
        mini_app_url=mini_app_url,
        mini_app_source=mini_app_source,
        primary_button_text=resolve_bot_menu_button_text(
            branding.bot_menu_button_text,
            project_name=resolve_project_name(branding.project_name),
        ),
        custom_buttons=custom_buttons,
    )


def resolve_bot_menu_url(
    *,
    bot_menu: BotMenuSettingsDto,
    config: AppConfig,
) -> tuple[str | None, str]:
    settings_url = _normalize_url(bot_menu.mini_app_url)
    if settings_url:
        return settings_url, BOT_MENU_SOURCE_SETTINGS

    config_url = _normalize_url(config.bot.mini_app_url)
    if config_url:
        return config_url, BOT_MENU_SOURCE_CONFIG

    return None, BOT_MENU_SOURCE_MISSING


def resolve_bot_menu_web_app_url(
    *,
    bot_menu: BotMenuSettingsDto,
    config: AppConfig,
) -> tuple[str | None, str]:
    settings_url = _normalize_url(bot_menu.mini_app_url)
    if settings_url and is_valid_bot_menu_web_app_url(settings_url):
        return settings_url, BOT_MENU_SOURCE_SETTINGS

    config_url = _normalize_url(config.bot.mini_app_url)
    if config_url and is_valid_bot_menu_web_app_url(config_url):
        return config_url, BOT_MENU_SOURCE_CONFIG

    if settings_url:
        return None, BOT_MENU_SOURCE_SETTINGS
    if config_url:
        return None, BOT_MENU_SOURCE_CONFIG
    return None, BOT_MENU_SOURCE_MISSING


def is_valid_bot_menu_web_app_url(value: str | bool | None) -> bool:
    normalized = _normalize_url(value)
    if not normalized:
        return False

    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme.lower() == "https"
        and bool(host)
        and parsed.username is None
        and parsed.password is None
        and host not in _TELEGRAM_MINI_APP_LINK_HOSTS
    )


def _resolve_custom_buttons(
    buttons: list[BotMenuCustomButtonDto],
) -> list[ResolvedBotMenuButton]:
    resolved: list[ResolvedBotMenuButton] = []
    for button in sorted(buttons, key=lambda item: (item.order, item.id)):
        if not button.enabled:
            continue
        if (
            button.kind == BotMenuCustomButtonKind.WEB_APP
            and not is_valid_bot_menu_web_app_url(button.url)
        ):
            continue
        resolved.append(
            ResolvedBotMenuButton(
                id=button.id,
                label=button.label,
                kind=button.kind,
                url=button.url,
                enabled=button.enabled,
                order=button.order,
            )
        )
    return resolved


def _normalize_url(value: str | bool | None) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized.rstrip("/")
    return None
