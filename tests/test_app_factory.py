from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from aiogram import Dispatcher
from pydantic import SecretStr

from src.api.app import create_app
from src.core.config import AppConfig


def _build_config() -> AppConfig:
    return cast(
        AppConfig,
        SimpleNamespace(
            origins=[],
            bot=SimpleNamespace(
                secret_token=SecretStr("telegram-secret-token"),
                webhook_path="/telegram/webhook",
            ),
        ),
    )


def test_create_app_does_not_mount_legacy_auth_routes() -> None:
    app = create_app(
        config=_build_config(),
        dispatcher=cast(Dispatcher, SimpleNamespace()),
    )

    assert all(route.path != "/auth/login" for route in app.routes)
    assert all(route.path != "/auth/register" for route in app.routes)
    assert all(route.path != "/auth/logout" for route in app.routes)


def test_create_app_mounts_split_user_routes() -> None:
    app = create_app(
        config=_build_config(),
        dispatcher=cast(Dispatcher, SimpleNamespace()),
    )

    route_paths = {route.path for route in app.routes}

    assert "/api/v1/user/me" in route_paths
    assert "/api/v1/subscription/list" in route_paths
    assert "/api/v1/referral/info" in route_paths
