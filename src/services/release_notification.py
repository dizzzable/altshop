from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from loguru import logger
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel

from src.__version__ import __version__ as local_version
from src.bot.keyboards import get_remnashop_update_keyboard
from src.core.enums import SystemNotificationType, UserRole
from src.core.storage.keys import LastNotifiedVersionKey, LastUpdateCheckAuditKey
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.redis.repository import RedisRepository
from src.services.notification import NotificationService
from src.services.settings import SettingsService
from src.services.user import UserService

RELEASE_PUBLISHED_AT_FORMAT = "%Y-%m-%d %H:%M UTC"
UpdateCheckOutcome = Literal[
    "github_fetch_failed",
    "payload_parse_failed",
    "up_to_date",
    "local_ahead",
    "toggle_disabled",
    "already_notified",
    "no_recipients",
    "delivery_failed",
    "notified",
]


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


class UpdateCheckAuditSnapshot(BaseModel):
    outcome: UpdateCheckOutcome
    local_version: str
    remote_version: str | None = None
    remote_tag: str | None = None
    release_published_at: str | None = None
    dedupe_version: str | None = None
    recipient_count: int = 0
    dev_recipient_count: int = 0
    used_fallback_recipient: bool = False
    delivery_success_count: int = 0
    toggle_enabled: bool | None = None

    @classmethod
    def build(
        cls,
        *,
        outcome: UpdateCheckOutcome,
        current_version: str,
        latest_release: GitHubReleaseSnapshot | None = None,
        dedupe_version: str | None = None,
        recipient_count: int = 0,
        dev_recipient_count: int = 0,
        used_fallback_recipient: bool = False,
        delivery_success_count: int = 0,
        toggle_enabled: bool | None = None,
    ) -> "UpdateCheckAuditSnapshot":
        return cls(
            outcome=outcome,
            local_version=normalize_release_version(current_version),
            remote_version=latest_release.version if latest_release else None,
            remote_tag=latest_release.tag_name if latest_release else None,
            release_published_at=(
                latest_release.published_at_label if latest_release else None
            ),
            dedupe_version=dedupe_version,
            recipient_count=recipient_count,
            dev_recipient_count=dev_recipient_count,
            used_fallback_recipient=used_fallback_recipient,
            delivery_success_count=delivery_success_count,
            toggle_enabled=toggle_enabled,
        )


def normalize_release_version(raw_version: str) -> str:
    return raw_version.strip().removeprefix("v").strip()


def normalize_release_identity(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    normalized = normalized.removeprefix("altshop").strip()
    normalized = normalized.removeprefix("release").strip(" :-")
    normalized = normalized.removeprefix("v").strip()
    return normalized


def parse_github_release_snapshot(payload: dict[str, object]) -> GitHubReleaseSnapshot | None:
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


def build_update_notification_payload(
    *,
    current_version: str,
    latest_release: GitHubReleaseSnapshot,
) -> MessagePayload:
    release_title = latest_release.release_title

    return MessagePayload.not_deleted(
        i18n_key="ntf-event-release-update-altshop",
        i18n_kwargs={
            "local_version": current_version,
            "remote_version": latest_release.version,
            "release_published_at": latest_release.published_at_label,
            "release_title": release_title or "",
            "has_release_title": bool(release_title),
        },
        reply_markup=get_remnashop_update_keyboard(),
    )


def log_update_check_audit(snapshot: UpdateCheckAuditSnapshot) -> None:
    logger.bind(**snapshot.model_dump()).info("AltShop update check completed")


async def persist_update_check_audit(
    *,
    redis_repository: RedisRepository,
    snapshot: UpdateCheckAuditSnapshot,
) -> None:
    await redis_repository.set(LastUpdateCheckAuditKey(), snapshot)


async def maybe_notify_about_release_update(
    *,
    redis_repository: RedisRepository,
    notification_service: NotificationService,
    settings_service: SettingsService,
    user_service: UserService,
    latest_release: GitHubReleaseSnapshot,
    current_version: str = local_version,
) -> UpdateCheckAuditSnapshot:
    try:
        local_semver = Version(normalize_release_version(current_version))
        remote_semver = Version(latest_release.version)
    except InvalidVersion as exception:
        logger.error(f"Failed to compare release versions: {exception}")
        return UpdateCheckAuditSnapshot.build(
            outcome="payload_parse_failed",
            current_version=current_version,
            latest_release=latest_release,
        )

    if remote_semver < local_semver:
        logger.debug(
            "Local version is ahead of remote "
            f"({current_version} > {latest_release.version})"
        )
        return UpdateCheckAuditSnapshot.build(
            outcome="local_ahead",
            current_version=current_version,
            latest_release=latest_release,
        )

    if remote_semver == local_semver:
        logger.debug(f"Project is up to date ({current_version})")
        return UpdateCheckAuditSnapshot.build(
            outcome="up_to_date",
            current_version=current_version,
            latest_release=latest_release,
        )

    toggle_enabled = await settings_service.is_notification_enabled(
        SystemNotificationType.BOT_UPDATE
    )
    if not toggle_enabled:
        logger.debug("Skipping AltShop update notification: BOT_UPDATE toggle is disabled")
        return UpdateCheckAuditSnapshot.build(
            outcome="toggle_disabled",
            current_version=current_version,
            latest_release=latest_release,
            toggle_enabled=False,
        )

    last_notified_version = await redis_repository.get(LastNotifiedVersionKey(), str)
    if last_notified_version == latest_release.version:
        logger.debug(f"Version {latest_release.version} already notified.")
        return UpdateCheckAuditSnapshot.build(
            outcome="already_notified",
            current_version=current_version,
            latest_release=latest_release,
            dedupe_version=last_notified_version,
            toggle_enabled=True,
        )

    devs = await user_service.get_by_role(role=UserRole.DEV)
    dev_recipient_count = len(devs)
    fallback_dev_ids = list(notification_service.config.bot.dev_id or [])
    used_fallback_recipient = dev_recipient_count == 0 and bool(fallback_dev_ids)
    recipient_count = dev_recipient_count or (1 if used_fallback_recipient else 0)

    logger.bind(
        dev_recipient_count=dev_recipient_count,
        recipient_count=recipient_count,
        used_fallback_recipient=used_fallback_recipient,
        remote_version=latest_release.version,
    ).info("Resolved AltShop update notification recipients")

    if recipient_count == 0:
        logger.warning("Skipping AltShop update notification: no DEV recipients available")
        return UpdateCheckAuditSnapshot.build(
            outcome="no_recipients",
            current_version=current_version,
            latest_release=latest_release,
            dedupe_version=last_notified_version,
            recipient_count=recipient_count,
            dev_recipient_count=dev_recipient_count,
            used_fallback_recipient=used_fallback_recipient,
            toggle_enabled=True,
        )

    try:
        delivery_results = await notification_service.system_notify(
            ntf_type=SystemNotificationType.BOT_UPDATE,
            payload=build_update_notification_payload(
                current_version=current_version,
                latest_release=latest_release,
            ),
        )
    except Exception as exception:
        logger.error(f"Failed to send AltShop update notification: {exception}")
        return UpdateCheckAuditSnapshot.build(
            outcome="delivery_failed",
            current_version=current_version,
            latest_release=latest_release,
            dedupe_version=last_notified_version,
            recipient_count=recipient_count,
            dev_recipient_count=dev_recipient_count,
            used_fallback_recipient=used_fallback_recipient,
            toggle_enabled=True,
        )

    delivery_success_count = sum(bool(result) for result in delivery_results)
    if delivery_success_count < 1:
        logger.warning(
            "Skipping AltShop update dedupe write: notification delivery failed for all recipients"
        )
        return UpdateCheckAuditSnapshot.build(
            outcome="delivery_failed",
            current_version=current_version,
            latest_release=latest_release,
            dedupe_version=last_notified_version,
            recipient_count=recipient_count,
            dev_recipient_count=dev_recipient_count,
            used_fallback_recipient=used_fallback_recipient,
            delivery_success_count=delivery_success_count,
            toggle_enabled=True,
        )

    try:
        await redis_repository.set(LastNotifiedVersionKey(), value=latest_release.version)
        dedupe_version: str | None = latest_release.version
    except Exception as exception:
        logger.error(f"Failed to persist last notified AltShop release version: {exception}")
        dedupe_version = last_notified_version

    logger.info(
        "New AltShop release available: "
        f"{latest_release.version} (local: {normalize_release_version(current_version)})"
    )
    return UpdateCheckAuditSnapshot.build(
        outcome="notified",
        current_version=current_version,
        latest_release=latest_release,
        dedupe_version=dedupe_version,
        recipient_count=recipient_count,
        dev_recipient_count=dev_recipient_count,
        used_fallback_recipient=used_fallback_recipient,
        delivery_success_count=delivery_success_count,
        toggle_enabled=True,
    )
