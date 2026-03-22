from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final

import httpx
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger
from packaging.version import InvalidVersion, Version

from src.__version__ import __version__ as local_version
from src.bot.keyboards import get_remnashop_update_keyboard
from src.core.constants import ALTSHOP_GITHUB_RELEASES_LATEST_API_URL
from src.core.enums import SystemNotificationType
from src.core.storage.keys import LastNotifiedVersionKey
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.redis.repository import RedisRepository
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks.notifications import send_system_notification_task

GITHUB_API_TIMEOUT_SECONDS: Final[float] = 10.0
GITHUB_API_HEADERS: Final[dict[str, str]] = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "AltShop-Update-Checker",
}
RELEASE_PUBLISHED_AT_FORMAT: Final[str] = "%Y-%m-%d %H:%M UTC"


@dataclass(slots=True, frozen=True)
class GitHubReleaseSnapshot:
    tag_name: str
    name: str | None
    published_at: datetime
    html_url: str

    @property
    def version(self) -> str:
        return normalize_release_version(self.tag_name)

    @property
    def release_title(self) -> str | None:
        if not self.name:
            return None

        normalized_title = normalize_release_identity(self.name)
        normalized_tag = normalize_release_identity(self.tag_name)

        if not normalized_title or normalized_title == normalized_tag:
            return None

        return self.name.strip()

    @property
    def published_at_label(self) -> str:
        return self.published_at.astimezone(timezone.utc).strftime(RELEASE_PUBLISHED_AT_FORMAT)


def normalize_release_version(raw_version: str) -> str:
    return raw_version.strip().removeprefix("v").strip()


def normalize_release_identity(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    normalized = normalized.removeprefix("altshop").strip()
    normalized = normalized.removeprefix("release").strip(" :-")
    normalized = normalized.removeprefix("v").strip()
    return normalized


def parse_github_release_snapshot(payload: dict[str, Any]) -> GitHubReleaseSnapshot | None:
    if payload.get("draft") or payload.get("prerelease"):
        return None

    tag_name = payload.get("tag_name")
    published_at_raw = payload.get("published_at")
    html_url = payload.get("html_url")
    name = payload.get("name")

    if not isinstance(tag_name, str) or not tag_name.strip():
        raise ValueError("GitHub release payload has no valid tag_name")
    if not isinstance(published_at_raw, str) or not published_at_raw.strip():
        raise ValueError("GitHub release payload has no valid published_at")
    if not isinstance(html_url, str) or not html_url.strip():
        raise ValueError("GitHub release payload has no valid html_url")
    if name is not None and not isinstance(name, str):
        raise ValueError("GitHub release payload has invalid name")

    published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))

    return GitHubReleaseSnapshot(
        tag_name=tag_name.strip(),
        name=name.strip() if isinstance(name, str) and name.strip() else None,
        published_at=published_at,
        html_url=html_url.strip(),
    )


async def fetch_latest_github_release() -> GitHubReleaseSnapshot | None:
    try:
        async with httpx.AsyncClient(
            timeout=GITHUB_API_TIMEOUT_SECONDS,
            headers=GITHUB_API_HEADERS,
        ) as client:
            response = await client.get(ALTSHOP_GITHUB_RELEASES_LATEST_API_URL)
    except Exception as exception:
        logger.error(f"Failed to fetch latest AltShop release from GitHub: {exception}")
        return None

    if response.status_code != 200:
        logger.error(
            "Failed to fetch latest AltShop release from GitHub: "
            f"status={response.status_code} body={response.text[:256]}"
        )
        return None

    try:
        return parse_github_release_snapshot(response.json())
    except Exception as exception:
        logger.error(f"Failed to parse latest AltShop release from GitHub: {exception}")
        return None


def build_update_notification_payload(
    *,
    current_version: str,
    latest_release: GitHubReleaseSnapshot,
) -> MessagePayload:
    release_title = latest_release.release_title

    return MessagePayload.not_deleted(
        i18n_key="ntf-event-bot-update",
        i18n_kwargs={
            "local_version": current_version,
            "remote_version": latest_release.version,
            "release_published_at": latest_release.published_at_label,
            "release_title": release_title or "",
            "has_release_title": bool(release_title),
        },
        reply_markup=get_remnashop_update_keyboard(),
    )


async def maybe_notify_about_release_update(
    *,
    redis_repository: RedisRepository,
    latest_release: GitHubReleaseSnapshot,
    current_version: str = local_version,
) -> bool:
    try:
        local_semver = Version(normalize_release_version(current_version))
        remote_semver = Version(latest_release.version)
    except InvalidVersion as exception:
        logger.error(f"Failed to compare release versions: {exception}")
        return False

    if remote_semver < local_semver:
        logger.debug(
            "Local version is ahead of remote "
            f"({current_version} > {latest_release.version})"
        )
        return False

    if remote_semver == local_semver:
        logger.debug(f"Project is up to date ({current_version})")
        return False

    key = LastNotifiedVersionKey()
    last_notified_version = await redis_repository.get(key, str)
    if last_notified_version == latest_release.version:
        logger.debug(f"Version {latest_release.version} already notified.")
        return False

    await redis_repository.set(key, value=latest_release.version)

    logger.info(
        "New AltShop release available: "
        f"{latest_release.version} (local: {normalize_release_version(current_version)})"
    )
    await send_system_notification_task.kiq(
        ntf_type=SystemNotificationType.BOT_UPDATE,
        payload=build_update_notification_payload(
            current_version=current_version,
            latest_release=latest_release,
        ),
    )
    return True


@broker.task(schedule=[{"cron": "*/60 * * * *"}])
@inject(patch_module=True)
async def check_bot_update(
    redis_repository: FromDishka[RedisRepository],
) -> None:
    latest_release = await fetch_latest_github_release()
    if latest_release is None:
        return

    await maybe_notify_about_release_update(
        redis_repository=redis_repository,
        latest_release=latest_release,
    )
