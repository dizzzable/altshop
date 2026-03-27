from __future__ import annotations

import pytest

from src.core.config import AppConfig


@pytest.fixture
def required_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "APP_DOMAIN": "example.com",
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
        "BACKUP_SEND_TOPIC_ID": "",
    }

    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_app_config_parses_comma_separated_host_lists(
    required_app_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ALLOWED_HOSTS", "example.com, localhost,127.0.0.1, ::1")
    monkeypatch.setenv("APP_TRUSTED_PROXY_IPS", "127.0.0.1, ::1")

    config = AppConfig(_env_file=None)

    assert config.allowed_hosts == ["example.com", "localhost", "127.0.0.1", "::1"]
    assert config.trusted_proxy_ips == ["127.0.0.1", "::1"]
    assert config.backup.send_topic_id is None
