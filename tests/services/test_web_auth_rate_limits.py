from __future__ import annotations

import asyncio
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response

import src.api.endpoints.web_auth as web_auth_module
from src.api.contracts.web_auth import RegisterRequest, TelegramAuthRequest
from src.core.enums import AccessMode
from src.core.observability import clear_metrics_registry, render_metrics_text


def run_async(coroutine):
    return asyncio.run(coroutine)


def setup_function() -> None:
    clear_metrics_registry()


def teardown_function() -> None:
    clear_metrics_registry()


class FakeRedis:
    def __init__(self, *, seed: dict[str, int] | None = None) -> None:
        self._counts = defaultdict(int, seed or {})
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] += 1
        return self._counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds


class FakeRequest:
    def __init__(
        self,
        *,
        config: object,
        container: object,
        client_host: str = "203.0.113.10",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.headers = headers or {}
        self.client = SimpleNamespace(host=client_host)
        self.app = SimpleNamespace(state=SimpleNamespace(config=config))
        self.state = SimpleNamespace(dishka_container=container)
        self.scope = {"app": self.app}


class FakeDishkaContainer:
    def __init__(self, services: dict[object, object]) -> None:
        self.services = services

    async def get(self, type_hint, component=None):
        del component
        try:
            return self.services[type_hint]
        except KeyError as exc:
            raise AssertionError(f"Unexpected dependency request: {type_hint}") from exc


def make_config(
    *,
    register_ip_limit: int = 10,
    register_identity_limit: int = 5,
    telegram_ip_limit: int = 30,
    telegram_identity_limit: int = 10,
) -> object:
    return SimpleNamespace(
        trusted_proxy_ips=[],
        web_app=SimpleNamespace(
            rate_limit_enabled=True,
            rate_limit_window=60,
            rate_limit_max_requests=60,
            register_rate_limit_ip_max_requests=register_ip_limit,
            register_rate_limit_identity_max_requests=register_identity_limit,
            telegram_auth_rate_limit_ip_max_requests=telegram_ip_limit,
            telegram_auth_rate_limit_identity_max_requests=telegram_identity_limit,
            telegram_link_code_ttl_seconds=600,
            auth_challenge_attempts=5,
        ),
    )


def make_register_dependencies() -> dict[str, object]:
    return {
        "web_account_service": SimpleNamespace(register=AsyncMock()),
        "referral_service": SimpleNamespace(),
        "partner_service": SimpleNamespace(),
        "notification_service": SimpleNamespace(system_notify=AsyncMock()),
        "user_service": SimpleNamespace(update=AsyncMock()),
        "settings_service": SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(
                    access_mode=AccessMode.PUBLIC,
                    rules_required=False,
                    channel_required=False,
                )
            )
        ),
        "telegram_link_service": SimpleNamespace(request_code=AsyncMock()),
    }


def make_telegram_dependencies() -> dict[str, object]:
    return {
        "user_service": SimpleNamespace(get=AsyncMock()),
        "referral_service": SimpleNamespace(),
        "partner_service": SimpleNamespace(),
        "notification_service": SimpleNamespace(system_notify=AsyncMock()),
        "settings_service": SimpleNamespace(
            get_access_mode=AsyncMock(return_value=AccessMode.PUBLIC)
        ),
        "web_account_service": SimpleNamespace(get_or_create_for_telegram_user=AsyncMock()),
        "web_analytics_event_service": None,
    }


def make_register_container(
    config: object,
    redis_client: FakeRedis,
    dependencies: dict[str, object],
):
    return FakeDishkaContainer(
        {
            web_auth_module.WebAccountService: dependencies["web_account_service"],
            web_auth_module.ReferralService: dependencies["referral_service"],
            web_auth_module.PartnerService: dependencies["partner_service"],
            web_auth_module.NotificationService: dependencies["notification_service"],
            web_auth_module.UserService: dependencies["user_service"],
            web_auth_module.SettingsService: dependencies["settings_service"],
            web_auth_module.TelegramLinkService: dependencies["telegram_link_service"],
            web_auth_module.AppConfig: config,
            web_auth_module.Redis: redis_client,
        }
    )


def make_telegram_container(
    config: object,
    redis_client: FakeRedis,
    dependencies: dict[str, object],
):
    return FakeDishkaContainer(
        {
            web_auth_module.UserService: dependencies["user_service"],
            web_auth_module.ReferralService: dependencies["referral_service"],
            web_auth_module.PartnerService: dependencies["partner_service"],
            web_auth_module.NotificationService: dependencies["notification_service"],
            web_auth_module.SettingsService: dependencies["settings_service"],
            web_auth_module.WebAccountService: dependencies["web_account_service"],
            web_auth_module.WebAnalyticsEventService: dependencies["web_analytics_event_service"],
            web_auth_module.AppConfig: config,
            web_auth_module.Redis: redis_client,
        }
    )


def test_register_rate_limit_rejects_per_ip() -> None:
    config = make_config(register_ip_limit=1, register_identity_limit=5)
    redis_client = FakeRedis(seed={"auth:register:ip:198.51.100.20": 1})
    dependencies = make_register_dependencies()
    request = FakeRequest(
        config=config,
        container=make_register_container(config, redis_client, dependencies),
        client_host="198.51.100.20",
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async(
            web_auth_module.register(
                register_data=RegisterRequest(username="alice", password="secret123"),
                request=request,
                response=Response(),
            )
        )

    assert exc_info.value.status_code == 429
    assert (
        'web_auth_rate_limit_rejections_total{endpoint="register",scope="ip"} 1'
        in render_metrics_text()
    )
    dependencies["web_account_service"].register.assert_not_awaited()


def test_register_rate_limit_rejects_per_identity() -> None:
    config = make_config(register_ip_limit=10, register_identity_limit=1)
    redis_client = FakeRedis(seed={"auth:register:username:alice": 1})
    dependencies = make_register_dependencies()
    request = FakeRequest(
        config=config,
        container=make_register_container(config, redis_client, dependencies),
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async(
            web_auth_module.register(
                register_data=RegisterRequest(username="Alice", password="secret123"),
                request=request,
                response=Response(),
            )
        )

    assert exc_info.value.status_code == 429
    assert (
        'web_auth_rate_limit_rejections_total{endpoint="register",scope="username"} 1'
        in render_metrics_text()
    )
    dependencies["web_account_service"].register.assert_not_awaited()


def test_register_hides_account_discovery_errors() -> None:
    config = make_config()
    redis_client = FakeRedis()
    dependencies = make_register_dependencies()
    dependencies["web_account_service"].register.side_effect = ValueError("Username already taken")
    request = FakeRequest(
        config=config,
        container=make_register_container(config, redis_client, dependencies),
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async(
            web_auth_module.register(
                register_data=RegisterRequest(username="alice", password="secret123"),
                request=request,
                response=Response(),
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == web_auth_module.REGISTRATION_GENERIC_ERROR_DETAIL


def test_telegram_auth_rate_limit_rejects_per_ip() -> None:
    config = make_config(telegram_ip_limit=1, telegram_identity_limit=10)
    redis_client = FakeRedis(seed={"auth:telegram:ip:198.51.100.99": 1})
    dependencies = make_telegram_dependencies()
    request = FakeRequest(
        config=config,
        container=make_telegram_container(config, redis_client, dependencies),
        client_host="198.51.100.99",
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async(
            web_auth_module.telegram_auth(
                auth_request=TelegramAuthRequest(
                    id=123456,
                    first_name="Alice",
                    auth_date=1,
                    hash="test-hash",
                ),
                request=request,
                response=Response(),
            )
        )

    assert exc_info.value.status_code == 429
    assert (
        'web_auth_rate_limit_rejections_total{endpoint="telegram",scope="ip"} 1'
        in render_metrics_text()
    )
    dependencies["user_service"].get.assert_not_awaited()


def test_telegram_auth_rate_limit_rejects_per_identity() -> None:
    config = make_config(telegram_ip_limit=10, telegram_identity_limit=1)
    redis_client = FakeRedis(seed={"auth:telegram:telegram_id:123456": 1})
    dependencies = make_telegram_dependencies()
    request = FakeRequest(
        config=config,
        container=make_telegram_container(config, redis_client, dependencies),
    )

    with pytest.raises(HTTPException) as exc_info:
        run_async(
            web_auth_module.telegram_auth(
                auth_request=TelegramAuthRequest(
                    id=123456,
                    first_name="Alice",
                    auth_date=1,
                    hash="test-hash",
                ),
                request=request,
                response=Response(),
            )
        )

    assert exc_info.value.status_code == 429
    assert (
        'web_auth_rate_limit_rejections_total{endpoint="telegram",scope="telegram_id"} 1'
        in render_metrics_text()
    )
    dependencies["user_service"].get.assert_not_awaited()
