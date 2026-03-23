from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramForbiddenError

from src.bot.routers.menu.handlers import on_start_dialog
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
