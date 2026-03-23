from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Final

TASK_MODULES: Final[tuple[str, ...]] = (
    "src.infrastructure.taskiq.tasks.broadcast",
    "src.infrastructure.taskiq.tasks.importer",
    "src.infrastructure.taskiq.tasks.notifications",
    "src.infrastructure.taskiq.tasks.payments",
    "src.infrastructure.taskiq.tasks.redirects",
    "src.infrastructure.taskiq.tasks.referrals",
    "src.infrastructure.taskiq.tasks.subscriptions",
    "src.infrastructure.taskiq.tasks.updates",
)


def register_task_modules() -> tuple[ModuleType, ...]:
    return tuple(import_module(module_path) for module_path in TASK_MODULES)
