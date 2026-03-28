from __future__ import annotations

import asyncio
from types import SimpleNamespace
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


def probe_result(
    status: str,
    *,
    detail: str | None = None,
    current_revision: str | None = None,
    expected_revision: str | None = None,
) -> internal_module.ReadinessProbeResult:
    return internal_module.ReadinessProbeResult(
        status=status,
        detail=detail,
        current_revision=current_revision,
        expected_revision=expected_revision,
    )


def test_build_readiness_response_reports_degraded_when_remnawave_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        internal_module,
        "_check_database_readiness",
        AsyncMock(return_value=probe_result("up")),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_database_schema_readiness",
        AsyncMock(
            return_value=probe_result(
                "up",
                current_revision="0050",
                expected_revision="0050",
            )
        ),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_redis_readiness",
        AsyncMock(return_value=probe_result("up")),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_remnawave_posture",
        AsyncMock(return_value=probe_result("degraded", detail="panel stats unavailable")),
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
    assert 'backend_dependency_status{dependency="schema"} 1' in rendered_metrics
    assert 'backend_dependency_status{dependency="redis"} 1' in rendered_metrics
    assert 'backend_dependency_status{dependency="remnawave"} 0' in rendered_metrics
    assert "backend_schema_revision_match 1" in rendered_metrics
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
        "_check_database_schema_readiness",
        AsyncMock(
            return_value=probe_result(
                "up",
                current_revision="0050",
                expected_revision="0050",
            )
        ),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_redis_readiness",
        AsyncMock(return_value=probe_result("up")),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_remnawave_posture",
        AsyncMock(return_value=probe_result("up")),
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
    assert response.checks["postgresql"].detail == "probe failed"


def test_build_readiness_response_returns_not_ready_when_schema_drift_is_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        internal_module,
        "_check_database_readiness",
        AsyncMock(return_value=probe_result("up")),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_database_schema_readiness",
        AsyncMock(
            return_value=probe_result(
                "down",
                detail="schema mismatch detected",
                current_revision="0049",
                expected_revision="0050",
            )
        ),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_redis_readiness",
        AsyncMock(return_value=probe_result("up")),
    )
    monkeypatch.setattr(
        internal_module,
        "_check_remnawave_posture",
        AsyncMock(return_value=probe_result("up")),
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
    assert response.checks["schema"].status == "down"
    assert response.checks["schema"].detail == "schema mismatch detected"

    rendered_metrics = render_metrics_text()
    assert 'backend_dependency_status{dependency="schema"} 0' in rendered_metrics
    assert "backend_schema_revision_match 0" in rendered_metrics
    assert "backend_readiness_status 0" in rendered_metrics


def test_check_redis_readiness_accepts_non_awaitable_ping_response() -> None:
    redis_client = SimpleNamespace(ping=lambda: True)

    response = run_async(internal_module._check_redis_readiness(redis_client))

    assert response == probe_result("up")


def test_check_redis_readiness_accepts_awaitable_ping_response() -> None:
    redis_client = SimpleNamespace(ping=AsyncMock(return_value=True))

    response = run_async(internal_module._check_redis_readiness(redis_client))

    assert response == probe_result("up")


def test_check_database_schema_readiness_reports_current_and_expected_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(internal_module, "_get_expected_migration_revision", lambda: "0050")

    class DummyConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def run_sync(self, callback):
            return "0049"

    class DummyEngine:
        def connect(self):
            return DummyConnection()

    response = run_async(internal_module._check_database_schema_readiness(DummyEngine()))

    assert response == probe_result(
        "down",
        detail="schema mismatch detected",
        current_revision="0049",
        expected_revision="0050",
    )
