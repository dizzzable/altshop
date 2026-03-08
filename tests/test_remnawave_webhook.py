from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from starlette.requests import Request

from src.api.endpoints import remnawave as remnawave_module
from src.api.endpoints.remnawave import remnawave_webhook
from src.core.enums import RemnaUserHwidDevicesEvent

REMNAWAVE_WEBHOOK_ENDPOINT = getattr(
    inspect.unwrap(remnawave_webhook),
    "__dishka_orig_func__",
    inspect.unwrap(remnawave_webhook),
)


def _build_request(body: bytes = b"{}") -> Request:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "headers": []}
    return Request(scope, receive)


def test_remnawave_webhook_updates_runtime_snapshot_on_device_event(
    monkeypatch,
) -> None:
    payload = SimpleNamespace(event=RemnaUserHwidDevicesEvent.ADDED)
    device_event = SimpleNamespace(
        user=SimpleNamespace(uuid=uuid4(), telegram_id=1001),
        hwid_user_device=SimpleNamespace(
            hwid="HWID-001",
            platform="Windows 11",
            device_model="PC",
            os_version="11",
            user_agent="test-agent",
        ),
    )
    config = SimpleNamespace(
        remnawave=SimpleNamespace(
            webhook_secret=SimpleNamespace(get_secret_value=lambda: "secret")
        )
    )
    remnawave_service = SimpleNamespace(handle_device_event=AsyncMock(return_value=None))
    subscription_device_service = SimpleNamespace(
        apply_device_event_to_cached_list=AsyncMock(return_value=True)
    )
    subscription_runtime_service = SimpleNamespace(
        apply_device_event_to_cached_runtime=AsyncMock(return_value=True)
    )

    monkeypatch.setattr(remnawave_module.WebhookUtility, "parse_webhook", lambda **_: payload)
    monkeypatch.setattr(
        remnawave_module.WebhookUtility,
        "is_user_event",
        lambda event: False,
    )
    monkeypatch.setattr(
        remnawave_module.WebhookUtility,
        "is_user_hwid_devices_event",
        lambda event: event == RemnaUserHwidDevicesEvent.ADDED,
    )
    monkeypatch.setattr(
        remnawave_module.WebhookUtility,
        "is_node_event",
        lambda event: False,
    )
    monkeypatch.setattr(
        remnawave_module.WebhookUtility,
        "get_typed_data",
        lambda _payload: device_event,
    )

    response = asyncio.run(
        REMNAWAVE_WEBHOOK_ENDPOINT(
            request=_build_request(),
            config=config,
            remnawave_service=remnawave_service,
            subscription_device_service=subscription_device_service,
            subscription_runtime_service=subscription_runtime_service,
        )
    )

    assert response.status_code == 200
    remnawave_service.handle_device_event.assert_awaited_once_with(
        payload.event,
        device_event.user,
        device_event.hwid_user_device,
    )
    subscription_device_service.apply_device_event_to_cached_list.assert_awaited_once_with(
        user_remna_id=device_event.user.uuid,
        event=payload.event,
        hwid_device=device_event.hwid_user_device,
    )
    subscription_runtime_service.apply_device_event_to_cached_runtime.assert_awaited_once_with(
        user_remna_id=device_event.user.uuid,
        event=payload.event,
    )
