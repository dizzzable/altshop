from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request
from loguru import logger
from redis.asyncio import Redis

from src.api.utils.request_ip import resolve_client_ip
from src.core.config import AppConfig
from src.core.observability import emit_counter


def _normalize_rate_limit_subject(subject: str | int) -> str:
    normalized = str(subject).strip().lower()
    return normalized or "unknown"


def _rate_limit_subject_hash(subject: str | int) -> str:
    return hashlib.sha256(str(subject).encode("utf-8")).hexdigest()[:12]


async def enforce_rate_limit(
    config: AppConfig,
    redis_client: Redis,
    key: str,
    *,
    limit: int | None = None,
    endpoint: str | None = None,
    scope: str | None = None,
    client_ip: str | None = None,
    subject: str | int | None = None,
) -> None:
    if not config.web_app.rate_limit_enabled:
        return

    allowed_requests = max(limit or config.web_app.rate_limit_max_requests, 1)
    window = config.web_app.rate_limit_window
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, window)
    except Exception as exc:
        logger.warning("Rate-limit fallback disabled for key '{}': {}", key, exc)
        return

    if current <= allowed_requests:
        return

    if endpoint and scope:
        emit_counter(
            "web_auth_rate_limit_rejections_total",
            endpoint=endpoint,
            scope=scope,
        )
        logger.warning(
            (
                "Web auth rate limit exceeded. endpoint='{}' scope='{}' "
                "client_ip='{}' subject_hash='{}'"
            ),
            endpoint,
            scope,
            client_ip or "-",
            _rate_limit_subject_hash(subject or key),
        )

    raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")


async def enforce_public_auth_rate_limit(
    *,
    config: AppConfig,
    redis_client: Redis,
    endpoint: str,
    scope: str,
    subject: str | int,
    limit: int,
    client_ip: str,
) -> None:
    normalized_subject = _normalize_rate_limit_subject(subject)
    await enforce_rate_limit(
        config,
        redis_client,
        f"auth:{endpoint}:{scope}:{normalized_subject}",
        limit=limit,
        endpoint=endpoint,
        scope=scope,
        client_ip=client_ip,
        subject=normalized_subject,
    )


def request_ip(request: Request) -> str:
    app = request.scope.get("app")
    app_state = getattr(app, "state", None)
    config = getattr(app_state, "config", None)
    if config is None:
        client_host = request.client.host if request.client else ""
        return client_host or "unknown"
    return resolve_client_ip(request, config)


__all__ = [
    "enforce_public_auth_rate_limit",
    "enforce_rate_limit",
    "request_ip",
]
