from __future__ import annotations

import secrets
from datetime import datetime

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.__version__ import __version__ as local_version
from src.core.config import AppConfig
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
