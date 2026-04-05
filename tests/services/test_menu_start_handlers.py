from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramForbiddenError

from src.bot.routers.menu.handlers import (
    _build_telegram_link_return_url,
    _build_tg_link_result_keyboard,
    _extract_tg_link_token_and_mode,
    on_start_dialog,
)
from src.infrastructure.database.models.dto import UserDto


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_on_start_dialog_marks_user_as_bot_blocked_on_forbidden() -> None:
    user = UserDto(telegram_id=901, name="Blocked User")
    dialog_manager = SimpleNamespace(
        start=AsyncMock(
            side_effect=TelegramForbiddenError(
                method=MagicMock(),
                message="bot was blocked by the user",
            )
        )
    )
    user_service = SimpleNamespace(set_bot_blocked=AsyncMock())

    run_async(on_start_dialog(user, dialog_manager, user_service))

    user_service.set_bot_blocked.assert_awaited_once_with(user=user, blocked=True)


def test_on_start_dialog_skips_known_blocked_user() -> None:
    user = UserDto(telegram_id=902, name="Known Blocked", is_bot_blocked=True)
    dialog_manager = SimpleNamespace(start=AsyncMock())
    user_service = SimpleNamespace(set_bot_blocked=AsyncMock())

    run_async(on_start_dialog(user, dialog_manager, user_service))

    dialog_manager.start.assert_not_awaited()
    user_service.set_bot_blocked.assert_not_awaited()


def test_extract_tg_link_token_and_mode_recognizes_miniapp_prefix() -> None:
    token, return_to_miniapp = _extract_tg_link_token_and_mode("tglinkapp_token-123")

    assert token == "token-123"
    assert return_to_miniapp is True


def test_build_tg_link_result_keyboard_uses_web_app_for_miniapp_return() -> None:
    user = UserDto(telegram_id=901, name="MiniApp User")

    keyboard = _build_tg_link_result_keyboard(
        user,
        "https://example.com/webapp/dashboard/settings?telegram_link=success",
        return_to_miniapp=True,
    )

    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.web_app is not None
    assert button.url is None


def test_build_telegram_link_return_url_uses_miniapp_settings_route() -> None:
    config = SimpleNamespace(
        web_app=SimpleNamespace(url_str="https://example.com/webapp"),
        domain=SimpleNamespace(get_secret_value=lambda: "example.com"),
        bot=SimpleNamespace(mini_app_url=""),
    )
    settings_service = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                bot_menu=SimpleNamespace(mini_app_url="https://example.com/webapp/miniapp")
            )
        )
    )

    result = run_async(
        _build_telegram_link_return_url(
            config,
            settings_service,
            telegram_link="success",
            telegram_id=901,
            return_to_miniapp=True,
        )
    )

    assert result == "https://example.com/webapp/dashboard/settings?telegram_link=success&telegram_id=901"
