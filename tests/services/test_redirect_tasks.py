from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramForbiddenError

from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.redirects import run_redirect_to_main_menu


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_redirect_to_main_menu_marks_user_as_bot_blocked_on_forbidden() -> None:
    user = UserDto(telegram_id=777, name="Blocked User")
    bg_manager = SimpleNamespace(
        start=AsyncMock(
            side_effect=TelegramForbiddenError(
                method=MagicMock(),
                message="bot was blocked by the user",
            )
        )
    )
    bg_manager_factory = SimpleNamespace(bg=MagicMock(return_value=bg_manager))
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=user),
        set_bot_blocked=AsyncMock(),
    )

    run_async(
        run_redirect_to_main_menu(
            telegram_id=user.telegram_id,
            bot=MagicMock(),
            bg_manager_factory=bg_manager_factory,
            user_service=user_service,
        )
    )

    user_service.set_bot_blocked.assert_awaited_once_with(user=user, blocked=True)


def test_redirect_to_main_menu_skips_known_blocked_user() -> None:
    user = UserDto(telegram_id=778, name="Known Blocked", is_bot_blocked=True)
    bg_manager_factory = SimpleNamespace(bg=MagicMock())
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=user),
        set_bot_blocked=AsyncMock(),
    )

    run_async(
        run_redirect_to_main_menu(
            telegram_id=user.telegram_id,
            bot=MagicMock(),
            bg_manager_factory=bg_manager_factory,
            user_service=user_service,
        )
    )

    bg_manager_factory.bg.assert_not_called()
    user_service.set_bot_blocked.assert_not_awaited()
