from __future__ import annotations

from types import SimpleNamespace

from src.infrastructure.taskiq import registry
from src.infrastructure.taskiq import scheduler as scheduler_module
from src.infrastructure.taskiq import worker as worker_module


def test_register_task_modules_imports_all_known_task_modules(monkeypatch) -> None:
    imported: list[str] = []

    def fake_import_module(module_path: str) -> SimpleNamespace:
        imported.append(module_path)
        return SimpleNamespace(__name__=module_path)

    monkeypatch.setattr(registry, "import_module", fake_import_module)

    modules = registry.register_task_modules()

    assert imported == list(registry.TASK_MODULES)
    assert [module.__name__ for module in modules] == list(registry.TASK_MODULES)


def test_worker_registers_task_modules_before_dispatcher_setup(monkeypatch) -> None:
    events: list[str] = []
    config = SimpleNamespace()
    dispatcher = SimpleNamespace()

    monkeypatch.setattr(worker_module, "setup_logger", lambda: events.append("logger"))
    monkeypatch.setattr(worker_module, "register_task_modules", lambda: events.append("register"))
    monkeypatch.setattr(worker_module.AppConfig, "get", staticmethod(lambda: config))
    monkeypatch.setattr(
        worker_module,
        "create_dispatcher",
        lambda config: events.append("dispatcher") or dispatcher,
    )
    monkeypatch.setattr(
        worker_module,
        "create_bg_manager_factory",
        lambda dispatcher: events.append("bg-manager") or SimpleNamespace(),
    )
    monkeypatch.setattr(
        worker_module,
        "setup_dispatcher",
        lambda dispatcher: events.append("setup"),
    )
    monkeypatch.setattr(
        worker_module,
        "create_container",
        lambda config, bg_manager_factory: events.append("container") or SimpleNamespace(),
    )
    monkeypatch.setattr(
        worker_module,
        "setup_taskiq_dishka",
        lambda container, broker: events.append("taskiq-dishka"),
    )
    monkeypatch.setattr(
        worker_module,
        "setup_aiogram_dishka",
        lambda container, router, auto_inject: events.append("aiogram-dishka"),
    )

    broker = worker_module.worker()

    assert broker is worker_module.broker
    assert events[:3] == ["logger", "register", "dispatcher"]


def test_scheduler_registers_task_modules_before_creating_scheduler(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(scheduler_module, "setup_logger", lambda: events.append("logger"))
    monkeypatch.setattr(
        scheduler_module,
        "register_task_modules",
        lambda: events.append("register"),
    )

    scheduler = scheduler_module.scheduler()

    assert scheduler.broker is scheduler_module.broker
    assert events[:2] == ["logger", "register"]
