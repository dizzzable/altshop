from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.app import configure_http_middleware
from src.api.endpoints.health import router as health_router
from src.core.config import AppConfig


def _build_test_app() -> FastAPI:
    app = FastAPI()
    configure_http_middleware(app=app, config=AppConfig())
    app.include_router(health_router)

    @app.get("/probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_trusted_host_middleware_allows_configured_domain() -> None:
    client = TestClient(_build_test_app(), base_url="http://example.com")

    response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_trusted_host_middleware_rejects_unconfigured_host() -> None:
    client = TestClient(_build_test_app(), base_url="http://example.com")

    response = client.get("/probe", headers={"host": "evil.example"})

    assert response.status_code == 400


def test_x_forwarded_host_cannot_bypass_host_allowlist() -> None:
    client = TestClient(_build_test_app(), base_url="http://example.com")

    response = client.get(
        "/probe",
        headers={
            "host": "evil.example",
            "x-forwarded-host": "example.com",
        },
    )

    assert response.status_code == 400


def test_livez_remains_public_on_allowed_host() -> None:
    client = TestClient(_build_test_app(), base_url="http://example.com")

    response = client.get("/api/v1/health/livez")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
