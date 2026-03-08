from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_services_provider_module_imports_without_undefined_type_analysis_errors() -> None:
    module = importlib.import_module("src.infrastructure.di.providers.services")

    reloaded_module = importlib.reload(module)

    assert hasattr(reloaded_module.ServicesProvider, "subscription_device_service")
    assert hasattr(reloaded_module.ServicesProvider, "user_profile_service")


def test_app_entrypoint_imports_without_di_errors() -> None:
    module = importlib.import_module("src.__main__")

    reloaded_module = importlib.reload(module)

    assert callable(reloaded_module.application)


def test_taskiq_worker_imports_without_di_errors(monkeypatch) -> None:
    fake_broker_module = ModuleType("src.infrastructure.taskiq.broker")
    fake_broker_module.broker = object()

    monkeypatch.setitem(sys.modules, "src.infrastructure.taskiq.broker", fake_broker_module)
    sys.modules.pop("src.infrastructure.taskiq.worker", None)

    worker_module = importlib.import_module("src.infrastructure.taskiq.worker")

    assert worker_module.broker is fake_broker_module.broker
    assert callable(worker_module.worker)


def test_alembic_revision_graph_is_valid() -> None:
    config = Config(str(Path("src/infrastructure/database/alembic.ini")))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    revisions = list(script.walk_revisions())

    assert heads
    assert revisions
    assert all(len(revision.revision) <= 32 for revision in revisions if revision.revision)
