from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.routers.dashboard.users.user.handlers import (
    on_open_web_cabinet,
    on_web_bind_back_to_cabinet,
)
from src.bot.states import DashboardUser


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_on_open_web_cabinet_clears_preview_state() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={
            "web_bind_target_telegram_id": 12,
            "web_bind_target_web_account_reclaimable": True,
            "web_bind_source_subscriptions": [1],
            "web_bind_keep_subscription_ids": [1, 2],
        },
        switch_to=AsyncMock(),
    )

    run_async(on_open_web_cabinet(SimpleNamespace(), SimpleNamespace(), dialog_manager))

    assert "web_bind_target_telegram_id" not in dialog_manager.dialog_data
    assert "web_bind_target_web_account_reclaimable" not in dialog_manager.dialog_data
    assert "web_bind_source_subscriptions" not in dialog_manager.dialog_data
    assert "web_bind_keep_subscription_ids" not in dialog_manager.dialog_data
    dialog_manager.switch_to.assert_awaited_once_with(DashboardUser.WEB_CABINET)


def test_on_web_bind_back_to_cabinet_clears_preview_state() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={
            "web_bind_target_telegram_id": 12,
            "web_bind_target_account_will_be_replaced": True,
            "web_bind_target_subscriptions": [2],
            "web_bind_keep_subscription_ids": [2],
        },
        switch_to=AsyncMock(),
    )

    run_async(on_web_bind_back_to_cabinet(SimpleNamespace(), SimpleNamespace(), dialog_manager))

    assert "web_bind_target_telegram_id" not in dialog_manager.dialog_data
    assert "web_bind_target_account_will_be_replaced" not in dialog_manager.dialog_data
    assert "web_bind_target_subscriptions" not in dialog_manager.dialog_data
    assert "web_bind_keep_subscription_ids" not in dialog_manager.dialog_data
    dialog_manager.switch_to.assert_awaited_once_with(DashboardUser.WEB_CABINET)
