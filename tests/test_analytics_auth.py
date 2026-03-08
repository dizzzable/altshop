from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from src.api.endpoints import analytics as analytics_module
from src.api.endpoints.analytics import WebAnalyticsEventRequest, create_web_event

CREATE_WEB_EVENT_ENDPOINT = getattr(
    inspect.unwrap(create_web_event),
    "__dishka_orig_func__",
    inspect.unwrap(create_web_event),
)


def _build_payload() -> WebAnalyticsEventRequest:
    return WebAnalyticsEventRequest(
        event_name="post_login_route_resolved",
        source_path="/dashboard",
        session_id="session-1",
        device_mode="web",
        is_in_telegram=False,
        has_init_data=False,
    )


def test_create_web_event_uses_web_access_token_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analytics_service = SimpleNamespace(create_event=AsyncMock(return_value=None))
    monkeypatch.setattr(analytics_module, "verify_access_token", lambda _token: {"sub": "321"})

    response = asyncio.run(
        CREATE_WEB_EVENT_ENDPOINT(
            payload=_build_payload(),
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="web-token"),
            web_analytics_event_service=analytics_service,
        )
    )

    assert response.ok is True
    assert analytics_service.create_event.await_count == 1
    assert analytics_service.create_event.await_args.kwargs["user_telegram_id"] == 321


def test_create_web_event_ignores_legacy_or_invalid_bearer_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analytics_service = SimpleNamespace(create_event=AsyncMock(return_value=None))
    monkeypatch.setattr(analytics_module, "verify_access_token", lambda _token: None)

    response = asyncio.run(
        CREATE_WEB_EVENT_ENDPOINT(
            payload=_build_payload(),
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="legacy-bot-token",
            ),
            web_analytics_event_service=analytics_service,
        )
    )

    assert response.ok is True
    assert analytics_service.create_event.await_count == 1
    assert analytics_service.create_event.await_args.kwargs["user_telegram_id"] is None


def test_create_web_event_without_di_service_is_best_effort_ok() -> None:
    response = asyncio.run(
        CREATE_WEB_EVENT_ENDPOINT(
            payload=_build_payload(),
            credentials=None,
        )
    )

    assert response.ok is True
