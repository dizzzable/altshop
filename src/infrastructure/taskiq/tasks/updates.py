from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import httpx
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.__version__ import __version__ as local_version
from src.core.constants import ALTSHOP_GITHUB_RELEASES_LATEST_API_URL
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.broker import broker
from src.services.notification import NotificationService
from src.services.release_notification import (
    GitHubReleaseSnapshot,
    UpdateCheckAuditSnapshot,
    UpdateCheckOutcome,
    log_update_check_audit,
    maybe_notify_about_release_update,
    parse_github_release_snapshot,
    persist_update_check_audit,
)
from src.services.settings import SettingsService
from src.services.user import UserService

GITHUB_API_TIMEOUT_SECONDS: Final[float] = 10.0
GITHUB_API_HEADERS: Final[dict[str, str]] = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "AltShop-Update-Checker",
}


@dataclass(slots=True, frozen=True)
class GitHubReleaseFetchResult:
    outcome: UpdateCheckOutcome
    release: GitHubReleaseSnapshot | None = None


async def fetch_latest_github_release() -> GitHubReleaseFetchResult:
    try:
        async with httpx.AsyncClient(
            timeout=GITHUB_API_TIMEOUT_SECONDS,
            headers=GITHUB_API_HEADERS,
        ) as client:
            response = await client.get(ALTSHOP_GITHUB_RELEASES_LATEST_API_URL)
    except Exception as exception:
        logger.error(f"Failed to fetch latest AltShop release from GitHub: {exception}")
        return GitHubReleaseFetchResult(outcome="github_fetch_failed")

    if response.status_code != 200:
        logger.error(
            "Failed to fetch latest AltShop release from GitHub: "
            f"status={response.status_code} body={response.text[:256]}"
        )
        return GitHubReleaseFetchResult(outcome="github_fetch_failed")

    try:
        release = parse_github_release_snapshot(response.json())
    except Exception as exception:
        logger.error(f"Failed to parse latest AltShop release from GitHub: {exception}")
        return GitHubReleaseFetchResult(outcome="payload_parse_failed")

    if release is None:
        logger.error("Latest AltShop GitHub release payload did not resolve to a stable release")
        return GitHubReleaseFetchResult(outcome="payload_parse_failed")

    return GitHubReleaseFetchResult(outcome="notified", release=release)


async def run_check_bot_update(
    *,
    redis_repository: RedisRepository,
    notification_service: NotificationService,
    settings_service: SettingsService,
    user_service: UserService,
) -> UpdateCheckAuditSnapshot:
    fetch_result = await fetch_latest_github_release()
    if fetch_result.release is None:
        snapshot = UpdateCheckAuditSnapshot.build(
            outcome=fetch_result.outcome,
            current_version=local_version,
        )
    else:
        snapshot = await maybe_notify_about_release_update(
            redis_repository=redis_repository,
            notification_service=notification_service,
            settings_service=settings_service,
            user_service=user_service,
            latest_release=fetch_result.release,
        )

    await persist_update_check_audit(
        redis_repository=redis_repository,
        snapshot=snapshot,
    )
    log_update_check_audit(snapshot)
    return snapshot


@broker.task(schedule=[{"cron": "*/60 * * * *"}])
@inject(patch_module=True)
async def check_bot_update(
    redis_repository: FromDishka[RedisRepository],
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
    user_service: FromDishka[UserService],
) -> None:
    await run_check_bot_update(
        redis_repository=redis_repository,
        notification_service=notification_service,
        settings_service=settings_service,
        user_service=user_service,
    )
