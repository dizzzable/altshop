from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone
from time import perf_counter
from typing import Awaitable, Callable, Literal

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.__version__ import __version__ as local_version
from src.core.config import AppConfig
from src.core.observability import render_metrics_text, set_gauge
from src.infrastructure.redis.repository import RedisRepository
from src.services.notification import NotificationService
from src.services.release_notification import (
    GitHubReleaseSnapshot,
    UpdateCheckAuditSnapshot,
    log_update_check_audit,
    maybe_notify_about_release_update,
    normalize_release_version,
    persist_update_check_audit,
)
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.user import UserService

router = APIRouter(prefix="/api/v1/internal", tags=["Internal"])
security = HTTPBearer(auto_error=False)


class ReleaseNotifyRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    tag_name: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    html_url: str = Field(min_length=1, max_length=1024)
    published_at: datetime


class ReadinessCheck(BaseModel):
    status: Literal["up", "down", "degraded"]
    latency_ms: float = Field(ge=0)
    detail: str | None = None


class ReadinessResponse(BaseModel):
    ready: bool
    status: Literal["ready", "degraded", "not_ready"]
    checked_at: datetime
    checks: dict[str, ReadinessCheck]


def _verify_release_notify_credentials(
    *,
    config: AppConfig,
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    secret = config.release_notify_secret
    if secret is None or not secret.get_secret_value().strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="release notify secret is not configured",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unsupported authorization scheme",
        )

    if not secrets.compare_digest(credentials.credentials, secret.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid bearer token",
        )


async def _check_database_readiness(engine: AsyncEngine) -> tuple[str, str | None]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return "up", None


async def _check_redis_readiness(redis_client: Redis) -> tuple[str, str | None]:
    response = await redis_client.ping()
    if response is not True:
        raise RuntimeError(f"unexpected ping response: {response!r}")
    return "up", None


async def _check_remnawave_posture(
    remnawave_service: RemnawaveService,
) -> tuple[str, str | None]:
    stats = await remnawave_service.get_stats_safe()
    if stats is None:
        return "degraded", "panel stats unavailable"
    return "up", None


async def _run_readiness_probe(
    name: str,
    probe: Callable[[], Awaitable[tuple[str, str | None]]],
) -> tuple[str, ReadinessCheck]:
    started_at = perf_counter()

    try:
        status_name, detail = await probe()
    except Exception as exception:
        status_name = "down"
        detail = f"{type(exception).__name__}: {exception}"

    latency_ms = round((perf_counter() - started_at) * 1000, 2)
    set_gauge(
        "backend_dependency_status",
        1 if status_name == "up" else 0,
        dependency=name,
    )
    return (
        name,
        ReadinessCheck(status=status_name, latency_ms=latency_ms, detail=detail),
    )


async def _build_readiness_response(
    *,
    engine: AsyncEngine,
    redis_client: Redis,
    remnawave_service: RemnawaveService,
) -> ReadinessResponse:
    checks = dict(
        await asyncio.gather(
            _run_readiness_probe("postgresql", lambda: _check_database_readiness(engine)),
            _run_readiness_probe("redis", lambda: _check_redis_readiness(redis_client)),
            _run_readiness_probe(
                "remnawave",
                lambda: _check_remnawave_posture(remnawave_service),
            ),
        )
    )

    ready = all(checks[dependency].status == "up" for dependency in ("postgresql", "redis"))
    all_dependencies_up = all(check.status == "up" for check in checks.values())
    overall_status: Literal["ready", "degraded", "not_ready"]
    if not ready:
        overall_status = "not_ready"
    elif all_dependencies_up:
        overall_status = "ready"
    else:
        overall_status = "degraded"

    set_gauge("backend_readiness_status", 1 if ready else 0)
    return ReadinessResponse(
        ready=ready,
        status=overall_status,
        checked_at=datetime.now(tz=timezone.utc),
        checks=checks,
    )


async def _notify_release_impl(
    payload: ReleaseNotifyRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    redis_repository: FromDishka[RedisRepository] = None,  # type: ignore[assignment]
    notification_service: FromDishka[NotificationService] = None,  # type: ignore[assignment]
    settings_service: FromDishka[SettingsService] = None,  # type: ignore[assignment]
    user_service: FromDishka[UserService] = None,  # type: ignore[assignment]
) -> UpdateCheckAuditSnapshot:
    config: AppConfig = request.app.state.config
    _verify_release_notify_credentials(config=config, credentials=credentials)

    if normalize_release_version(payload.version) != normalize_release_version(payload.tag_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="version does not match tag_name",
        )

    release = GitHubReleaseSnapshot(
        tag_name=payload.tag_name.strip(),
        name=payload.name.strip() if payload.name and payload.name.strip() else None,
        published_at=payload.published_at,
        html_url=payload.html_url.strip(),
    )
    snapshot = await maybe_notify_about_release_update(
        redis_repository=redis_repository,
        notification_service=notification_service,
        settings_service=settings_service,
        user_service=user_service,
        latest_release=release,
        current_version=local_version,
    )
    await persist_update_check_audit(
        redis_repository=redis_repository,
        snapshot=snapshot,
    )
    log_update_check_audit(snapshot)
    return snapshot


@router.get("/readiness", response_model=ReadinessResponse)
@inject
async def readiness(
    engine: FromDishka[AsyncEngine],
    redis_client: FromDishka[Redis],
    remnawave_service: FromDishka[RemnawaveService],
) -> JSONResponse:
    payload = await _build_readiness_response(
        engine=engine,
        redis_client=redis_client,
        remnawave_service=remnawave_service,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if payload.ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        render_metrics_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/release-notify", response_model=UpdateCheckAuditSnapshot)
@inject
async def notify_release(
    payload: ReleaseNotifyRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    redis_repository: FromDishka[RedisRepository] = None,  # type: ignore[assignment]
    notification_service: FromDishka[NotificationService] = None,  # type: ignore[assignment]
    settings_service: FromDishka[SettingsService] = None,  # type: ignore[assignment]
    user_service: FromDishka[UserService] = None,  # type: ignore[assignment]
) -> UpdateCheckAuditSnapshot:
    return await _notify_release_impl(
        payload=payload,
        request=request,
        credentials=credentials,
        redis_repository=redis_repository,
        notification_service=notification_service,
        settings_service=settings_service,
        user_service=user_service,
    )
