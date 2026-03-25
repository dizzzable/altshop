from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr

from src.api.endpoints.internal import (
    ReleaseNotifyRequest,
    _notify_release_impl,
    _verify_release_notify_credentials,
)
from src.core.config import AppConfig


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_update_services(
    *,
    last_notified_version: str | None = None,
    toggle_enabled: bool = True,
    devs: list[object] | None = None,
    delivery_results: list[bool] | None = None,
):
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=last_notified_version),
        set=AsyncMock(),
    )
    settings_service = SimpleNamespace(
        is_notification_enabled=AsyncMock(return_value=toggle_enabled),
    )
    user_service = SimpleNamespace(
        get_by_role=AsyncMock(return_value=devs or []),
    )
    notification_service = SimpleNamespace(
        config=SimpleNamespace(bot=SimpleNamespace(dev_id=[999_999])),
        system_notify=AsyncMock(return_value=delivery_results or [True]),
    )
    return redis_repository, settings_service, user_service, notification_service


def test_verify_release_notify_credentials_rejects_invalid_secret() -> None:
    config = AppConfig.get()
    config.release_notify_secret = SecretStr("test-secret")

    with pytest.raises(HTTPException) as exc_info:
        _verify_release_notify_credentials(
            config=config,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="wrong-secret",
            ),
        )

    assert exc_info.value.status_code == 403


def test_verify_release_notify_credentials_rejects_missing_secret_configuration() -> None:
    config = AppConfig.get()
    config.release_notify_secret = None

    with pytest.raises(HTTPException) as exc_info:
        _verify_release_notify_credentials(
            config=config,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="test-secret",
            ),
        )

    assert exc_info.value.status_code == 503


def test_notify_release_returns_notified_snapshot_for_newer_remote_version() -> None:
    config = AppConfig.get()
    config.release_notify_secret = SecretStr("test-secret")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=config)))
    payload = ReleaseNotifyRequest(
        version="1.2.1",
        tag_name="v1.2.1",
        name="AltShop v1.2.1",
        html_url="https://github.com/dizzzable/altshop/releases/tag/v1.2.1",
        published_at=datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
    )
    redis_repository, settings_service, user_service, notification_service = (
        build_update_services(
            devs=[SimpleNamespace(telegram_id=1)],
            delivery_results=[True],
        )
    )

    snapshot = run_async(
        _notify_release_impl(
            payload=payload,
            request=request,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="test-secret",
            ),
            redis_repository=redis_repository,
            notification_service=notification_service,
            settings_service=settings_service,
            user_service=user_service,
        )
    )

    assert snapshot.outcome == "notified"
    assert snapshot.remote_version == "1.2.1"
    redis_repository.set.assert_awaited()
    notification_service.system_notify.assert_awaited_once()


def test_notify_release_skips_same_version_release() -> None:
    config = AppConfig.get()
    config.release_notify_secret = SecretStr("test-secret")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=config)))
    payload = ReleaseNotifyRequest(
        version="1.2.0",
        tag_name="v1.2.0",
        name="AltShop v1.2.0",
        html_url="https://github.com/dizzzable/altshop/releases/tag/v1.2.0",
        published_at=datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
    )
    redis_repository, settings_service, user_service, notification_service = (
        build_update_services(
            devs=[SimpleNamespace(telegram_id=1)],
            delivery_results=[True],
        )
    )

    snapshot = run_async(
        _notify_release_impl(
            payload=payload,
            request=request,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="test-secret",
            ),
            redis_repository=redis_repository,
            notification_service=notification_service,
            settings_service=settings_service,
            user_service=user_service,
        )
    )

    assert snapshot.outcome == "up_to_date"
    redis_repository.set.assert_awaited()
    notification_service.system_notify.assert_not_awaited()
