from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram_dialog import StartMode

from src.bot.routers.dashboard.remnashop.plans.handlers import (
    on_plan_configurator_back,
    on_plan_create,
)
from src.bot.states import RemnashopPlans
from src.core.utils.adapter import DialogDataAdapter
from src.infrastructure.database.models.dto import PlanDto


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_on_plan_create_clears_previous_editor_state() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={
            "plandto": PlanDto(id=1, name="Starter", traffic_limit=100).model_dump(),
            "is_edit": True,
            "selected_duration": 30,
            "selected_currency": "RUB",
        },
        switch_to=AsyncMock(),
    )

    run_async(on_plan_create(SimpleNamespace(), SimpleNamespace(), dialog_manager))

    assert DialogDataAdapter(dialog_manager).load(PlanDto) is None
    assert "is_edit" not in dialog_manager.dialog_data
    assert "selected_duration" not in dialog_manager.dialog_data
    assert "selected_currency" not in dialog_manager.dialog_data
    dialog_manager.switch_to.assert_awaited_once_with(state=RemnashopPlans.CONFIGURATOR)


def test_on_plan_configurator_back_clears_editor_state() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={
            "plandto": PlanDto(id=2, name="Pro", traffic_limit=350).model_dump(),
            "is_edit": True,
            "selected_duration": 30,
            "selected_currency": "USD",
        },
        start=AsyncMock(),
    )

    run_async(on_plan_configurator_back(SimpleNamespace(), SimpleNamespace(), dialog_manager))

    assert DialogDataAdapter(dialog_manager).load(PlanDto) is None
    assert "is_edit" not in dialog_manager.dialog_data
    dialog_manager.start.assert_awaited_once_with(
        state=RemnashopPlans.MAIN,
        mode=StartMode.RESET_STACK,
    )
