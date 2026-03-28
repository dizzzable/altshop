from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from remnawave.models.webhook import UserDto as WebhookUserDto
from remnawave.models.webhook import UserTrafficDto as WebhookUserTrafficDto

import src.api.endpoints.remnawave as remnawave_endpoint_module


def run_async(coroutine):
    return asyncio.run(coroutine)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class FakeDishkaContainer:
    def __init__(
        self,
        *,
        config: object,
        remnawave_service: object,
        subscription_device_service: object,
        subscription_runtime_service: object,
    ) -> None:
        self._config = config
        self._remnawave_service = remnawave_service
        self._subscription_device_service = subscription_device_service
        self._subscription_runtime_service = subscription_runtime_service

    async def get(self, type_hint, component=None):
        del component
        type_name = getattr(type_hint, "__name__", "")
        if type_name == "AppConfig":
            return self._config
        if type_name == "RemnawaveService":
            return self._remnawave_service
        if type_name == "SubscriptionDeviceService":
            return self._subscription_device_service
        if type_name == "SubscriptionRuntimeService":
            return self._subscription_runtime_service
        raise AssertionError(f"Unexpected dependency request: {type_hint}")


class FakeRequest:
    def __init__(self, *, payload: str, secret: str, container: FakeDishkaContainer) -> None:
        self._payload = payload.encode("utf-8")
        self.headers = {
            "x-remnawave-signature": hmac.new(
                secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest(),
            "x-remnawave-timestamp": str(int(now_utc().timestamp())),
        }
        self.state = SimpleNamespace(dishka_container=container)

    async def body(self) -> bytes:
        return self._payload


def build_config(secret: str = "scope-secret") -> SimpleNamespace:
    return SimpleNamespace(
        remnawave=SimpleNamespace(
            webhook_secret=SimpleNamespace(get_secret_value=lambda: secret)
        )
    )


def build_webhook_user(*, telegram_id: int = 700) -> WebhookUserDto:
    timestamp = now_utc()
    return WebhookUserDto(
        uuid=uuid4(),
        id=1,
        short_uuid="short-123",
        username=f"user-{telegram_id}",
        status="ACTIVE",
        user_traffic=WebhookUserTrafficDto(
            used_traffic_bytes=0,
            lifetime_used_traffic_bytes=0,
        ),
        traffic_limit_bytes=1024,
        traffic_limit_strategy="NO_RESET",
        expire_at=timestamp,
        trojan_password="password123",
        vless_uuid=uuid4(),
        ss_password="password456",
        last_triggered_threshold=0,
        subscription_url="https://example.com/subscription",
        created_at=timestamp,
        updated_at=timestamp,
        telegram_id=telegram_id,
        active_internal_squads=[],
    )


def test_remnawave_webhook_accepts_scoped_user_payload() -> None:
    secret = "scope-secret"
    config = build_config(secret)
    remnawave_service = SimpleNamespace(handle_user_event=AsyncMock())
    container = FakeDishkaContainer(
        config=config,
        remnawave_service=remnawave_service,
        subscription_device_service=SimpleNamespace(),
        subscription_runtime_service=SimpleNamespace(),
    )
    payload = json.dumps(
        {
            "scope": "user",
            "event": "user.modified",
            "timestamp": now_utc().isoformat(),
            "data": build_webhook_user().model_dump(mode="json", by_alias=True),
        },
        separators=(",", ":"),
    )
    request = FakeRequest(payload=payload, secret=secret, container=container)

    response = run_async(remnawave_endpoint_module.remnawave_webhook(request=request))

    assert response.status_code == 200
    remnawave_service.handle_user_event.assert_awaited_once()
    event_name, webhook_user = remnawave_service.handle_user_event.await_args.args
    assert event_name == "user.modified"
    assert webhook_user.telegram_id == 700


def test_remnawave_webhook_returns_200_for_scoped_service_payload() -> None:
    secret = "scope-secret"
    config = build_config(secret)
    remnawave_service = SimpleNamespace(
        handle_user_event=AsyncMock(),
        handle_node_event=AsyncMock(),
    )
    subscription_device_service = SimpleNamespace(apply_device_event_to_cached_list=AsyncMock())
    subscription_runtime_service = SimpleNamespace(apply_device_event_to_cached_runtime=AsyncMock())
    container = FakeDishkaContainer(
        config=config,
        remnawave_service=remnawave_service,
        subscription_device_service=subscription_device_service,
        subscription_runtime_service=subscription_runtime_service,
    )
    payload = json.dumps(
        {
            "scope": "service",
            "event": "service.panel_started",
            "timestamp": now_utc().isoformat(),
            "data": {"panelVersion": "2.5.0"},
        },
        separators=(",", ":"),
    )
    request = FakeRequest(payload=payload, secret=secret, container=container)

    response = run_async(remnawave_endpoint_module.remnawave_webhook(request=request))

    assert response.status_code == 200
    remnawave_service.handle_user_event.assert_not_awaited()
    remnawave_service.handle_node_event.assert_not_awaited()
    subscription_device_service.apply_device_event_to_cached_list.assert_not_awaited()
    subscription_runtime_service.apply_device_event_to_cached_runtime.assert_not_awaited()
