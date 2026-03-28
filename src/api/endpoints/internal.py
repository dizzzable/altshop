from __future__ import annotations

import asyncio
import inspect
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Awaitable, Callable, Literal, cast

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.engine import Connection
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
_MIGRATIONS_PATH = (
    Path(__file__).resolve().parents[2] / "infrastructure" / "database" / "migrations"
)


@dataclass(slots=True)
class ReadinessProbeResult:
    status: Literal["up", "down", "degraded"]
    detail: str | None = None
    current_revision: str | None = None
    expected_revision: str | None = None


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


async def _check_database_readiness(engine: AsyncEngine) -> ReadinessProbeResult:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return ReadinessProbeResult(status="up")


def _get_expected_migration_revision() -> str | None:
    config = AlembicConfig()
    config.set_main_option("script_location", str(_MIGRATIONS_PATH))
    return ScriptDirectory.from_config(config).get_current_head()


def _get_current_migration_revision(connection: Connection) -> str | None:
    context = MigrationContext.configure(connection)
    return context.get_current_revision()


async def _check_database_schema_readiness(engine: AsyncEngine) -> ReadinessProbeResult:
    expected_revision = _get_expected_migration_revision()
    if expected_revision is None:
        logger.error("Readiness schema check failed because the Alembic head is unavailable")
        return ReadinessProbeResult(
            status="down",
            detail="schema check unavailable",
        )

    async with engine.connect() as connection:
        current_revision = await connection.run_sync(_get_current_migration_revision)

    if current_revision != expected_revision:
        logger.warning(
            "Readiness schema mismatch detected. current_revision='{}' expected_revision='{}'",
            current_revision,
            expected_revision,
        )
        return ReadinessProbeResult(
            status="down",
            detail="schema mismatch detected",
            current_revision=current_revision,
            expected_revision=expected_revision,
        )

    return ReadinessProbeResult(
        status="up",
        current_revision=current_revision,
        expected_revision=expected_revision,
    )


async def _await_redis_ping(redis_client: Redis) -> bool:
    response = redis_client.ping()
    if inspect.isawaitable(response):
        return await cast(Awaitable[bool], response)
    return response


async def _check_redis_readiness(redis_client: Redis) -> ReadinessProbeResult:
    response = await _await_redis_ping(redis_client)
    if response is not True:
        raise RuntimeError(f"unexpected ping response: {response!r}")
    return ReadinessProbeResult(status="up")


async def _check_remnawave_posture(
    remnawave_service: RemnawaveService,
) -> ReadinessProbeResult:
    stats = await remnawave_service.get_stats_safe()
    if stats is None:
        return ReadinessProbeResult(status="degraded", detail="panel stats unavailable")
    return ReadinessProbeResult(status="up")


async def _run_readiness_probe(
    name: str,
    probe: Callable[[], Awaitable[ReadinessProbeResult]],
) -> tuple[str, ReadinessCheck]:
    started_at = perf_counter()

    try:
        result = await probe()
    except Exception as exception:
        logger.exception("Readiness probe '{}' failed: {}", name, exception)
        result = ReadinessProbeResult(
            status="down",
            detail="probe failed",
        )

    latency_ms = round((perf_counter() - started_at) * 1000, 2)
    set_gauge(
        "backend_dependency_status",
        1 if result.status == "up" else 0,
        dependency=name,
    )
    return (
        name,
        ReadinessCheck(
            status=result.status,
            latency_ms=latency_ms,
            detail=result.detail,
        ),
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
            _run_readiness_probe("schema", lambda: _check_database_schema_readiness(engine)),
            _run_readiness_probe("redis", lambda: _check_redis_readiness(redis_client)),
            _run_readiness_probe(
                "remnawave",
                lambda: _check_remnawave_posture(remnawave_service),
            ),
        )
    )

    ready = all(
        checks[dependency].status == "up"
        for dependency in ("postgresql", "schema", "redis")
    )
    all_dependencies_up = all(check.status == "up" for check in checks.values())
    overall_status: Literal["ready", "degraded", "not_ready"]
    if not ready:
        overall_status = "not_ready"
    elif all_dependencies_up:
        overall_status = "ready"
    else:
        overall_status = "degraded"

    set_gauge("backend_schema_revision_match", 1 if checks["schema"].status == "up" else 0)
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
