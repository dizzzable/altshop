from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.api.endpoints import internal as internal_module
from src.core.observability import clear_metrics_registry, render_metrics_text


def run_async(coroutine):
    return asyncio.run(coroutine)


def setup_function() -> None:
    clear_metrics_registry()


def teardown_function() -> None:
    clear_metrics_registry()


def test_build_readiness_response_reports_degraded_when_remnawave_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        internal_module,
        "_check_database_readiness",
        AsyncMock(return_value=("up", None)),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_redis_readiness",
        AsyncMock(return_value=("up", None)),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_remnawave_posture",
        AsyncMock(return_value=("degraded", "panel stats unavailable")),
    )

    response = run_async(
        internal_module._build_readiness_response(
            engine=object(),
            redis_client=object(),
            remnawave_service=object(),
        )
    )

    assert response.ready is True
    assert response.status == "degraded"
    assert response.checks["remnawave"].status == "degraded"
    rendered_metrics = render_metrics_text()
    assert 'backend_dependency_status{dependency="postgresql"} 1' in rendered_metrics
    assert 'backend_dependency_status{dependency="redis"} 1' in rendered_metrics
    assert 'backend_dependency_status{dependency="remnawave"} 0' in rendered_metrics
    assert "backend_readiness_status 1" in rendered_metrics


def test_build_readiness_response_returns_not_ready_when_core_dependency_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        internal_module,
        "_check_database_readiness",
        AsyncMock(side_effect=RuntimeError("db unavailable")),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_redis_readiness",
        AsyncMock(return_value=("up", None)),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_remnawave_posture",
        AsyncMock(return_value=("up", None)),
    )

    response = run_async(
        internal_module._build_readiness_response(
            engine=object(),
            redis_client=object(),
            remnawave_service=object(),
        )
    )

    assert response.ready is False
    assert response.status == "not_ready"
    assert response.checks["postgresql"].status == "down"
    assert "db unavailable" in (response.checks["postgresql"].detail or "")
