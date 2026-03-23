from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError

from src.bot.middlewares.error import ErrorMiddleware
from src.core.constants import CONTAINER_KEY
from src.infrastructure.database.models.dto import UserDto
from src.services.user import UserService


def run_async(coroutine):
    return asyncio.run(coroutine)


class _Container:
    def __init__(self, user_service: object) -> None:
        self._user_service = user_service

    async def get(self, cls: object) -> object:
        if cls is UserService:
            return self._user_service
        raise AssertionError(f"Unexpected dependency request: {cls}")


def test_error_middleware_swallows_blocked_bot_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    middleware = ErrorMiddleware()
    aiogram_user = SimpleNamespace(
        id=903,
        full_name="Blocked User",
        username="blocked_user",
    )
    user = UserDto(telegram_id=903, name="Blocked User")
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=user),
        set_bot_blocked=AsyncMock(),
    )
    handler = AsyncMock()
    redirect_mock = AsyncMock()
    send_error_mock = AsyncMock()

    monkeypatch.setattr(middleware, "_get_aiogram_user", lambda event: aiogram_user)
    monkeypatch.setattr(
        "src.bot.middlewares.error.redirect_to_main_menu_task.kiq",
        redirect_mock,
    )
    monkeypatch.setattr(
        "src.bot.middlewares.error.send_error_notification_task.kiq",
        send_error_mock,
    )

    event = SimpleNamespace(
        exception=TelegramForbiddenError(
            method=MagicMock(),
            message="bot was blocked by the user",
        ),
        update=SimpleNamespace(callback_query=None, message=None, update_id=1),
    )
    data = {CONTAINER_KEY: _Container(user_service)}

    result = run_async(middleware.middleware_logic(handler, event, data))

    assert result is True
    handler.assert_not_awaited()
    user_service.set_bot_blocked.assert_awaited_once_with(user=user, blocked=True)
    redirect_mock.assert_not_awaited()
    send_error_mock.assert_not_awaited()
