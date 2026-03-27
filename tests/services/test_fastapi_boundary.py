from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.app import configure_http_middleware
from src.api.endpoints.health import router as health_router
from src.core.config import AppConfig


@pytest.fixture
def boundary_config(monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    env = {
        "APP_DOMAIN": "example.com",
        "APP_ALLOWED_HOSTS": "example.com",
        "APP_CRYPT_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "BOT_TOKEN": "smoke-token",
        "BOT_SECRET_TOKEN": "smoke-secret-token",
        "BOT_DEV_ID": "1",
        "BOT_SUPPORT_USERNAME": "altsupport",
        "WEB_APP_JWT_SECRET": "smoke-web-app-jwt-secret-0123456789",
        "WEB_APP_API_SECRET_TOKEN": "smoke-api-secret-token",
        "REMNAWAVE_TOKEN": "smoke-remnawave-token",
        "REMNAWAVE_WEBHOOK_SECRET": "smoke-remnawave-webhook-secret",
        "DATABASE_PASSWORD": "smoke-db-password",
        "REDIS_PASSWORD": "smoke-redis-password",
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)

    return AppConfig(_env_file=None)


def _build_test_app(config: AppConfig) -> FastAPI:
    app = FastAPI()
    configure_http_middleware(app=app, config=config)
    app.include_router(health_router)

    @app.get("/probe")
    async def probe() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_trusted_host_middleware_allows_configured_domain(boundary_config: AppConfig) -> None:
    client = TestClient(_build_test_app(boundary_config), base_url="http://example.com")

    response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_trusted_host_middleware_rejects_unconfigured_host(boundary_config: AppConfig) -> None:
    client = TestClient(_build_test_app(boundary_config), base_url="http://example.com")

    response = client.get("/probe", headers={"host": "evil.example"})

    assert response.status_code == 400


def test_x_forwarded_host_cannot_bypass_host_allowlist(boundary_config: AppConfig) -> None:
    client = TestClient(_build_test_app(boundary_config), base_url="http://example.com")

    response = client.get(
        "/probe",
        headers={
            "host": "evil.example",
            "x-forwarded-host": "example.com",
        },
    )

    assert response.status_code == 400


def test_livez_remains_public_on_allowed_host(boundary_config: AppConfig) -> None:
    client = TestClient(_build_test_app(boundary_config), base_url="http://example.com")

    response = client.get("/api/v1/health/livez")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
