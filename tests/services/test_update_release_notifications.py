from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.keyboards import get_remnashop_update_keyboard
from src.core.constants import (
    ALTSHOP_GITHUB_RELEASES_LATEST_URL,
    ALTSHOP_GITHUB_UPGRADE_GUIDE_URL,
)
from src.core.enums import SystemNotificationType
from src.core.storage.keys import LastUpdateCheckAuditKey
from src.infrastructure.taskiq.tasks.updates import (
    GitHubReleaseFetchResult,
    GitHubReleaseSnapshot,
    UpdateCheckAuditSnapshot,
    build_update_notification_payload,
    maybe_notify_about_release_update,
    normalize_release_version,
    parse_github_release_snapshot,
    run_check_bot_update,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_release(
    *,
    tag_name: str = "v1.1.12",
    name: str | None = "Audit Release",
    published_at: str = "2026-03-23T14:15:00Z",
    html_url: str = "https://github.com/dizzzable/altshop/releases/tag/v1.1.12",
) -> GitHubReleaseSnapshot:
    release = parse_github_release_snapshot(
        {
            "tag_name": tag_name,
            "name": name,
            "published_at": published_at,
            "html_url": html_url,
            "draft": False,
            "prerelease": False,
        }
    )
    assert release is not None
    return release


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


def test_normalize_release_version_strips_v_prefix() -> None:
    assert normalize_release_version("v1.1.12") == "1.1.12"
    assert normalize_release_version("1.1.12") == "1.1.12"


def test_parse_github_release_snapshot_ignores_prerelease() -> None:
    release = parse_github_release_snapshot(
        {
            "tag_name": "v1.1.12-rc1",
            "name": "RC 1",
            "published_at": "2026-03-23T14:15:00Z",
            "html_url": "https://example.com/release",
            "draft": False,
            "prerelease": True,
        }
    )

    assert release is None


def test_build_update_notification_payload_includes_release_details() -> None:
    payload = build_update_notification_payload(
        current_version="1.1.11",
        latest_release=build_release(),
    )

    assert payload.i18n_key == "ntf-event-bot-update"
    assert payload.i18n_kwargs["local_version"] == "1.1.11"
    assert payload.i18n_kwargs["remote_version"] == "1.1.12"
    assert payload.i18n_kwargs["release_published_at"] == "2026-03-23 14:15 UTC"
    assert payload.i18n_kwargs["release_title"] == "Audit Release"
    assert payload.i18n_kwargs["has_release_title"] is True


def test_maybe_notify_about_release_update_returns_notified_snapshot() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        devs=[SimpleNamespace(telegram_id=1)],
        delivery_results=[True],
    )

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(),
            current_version="1.1.11",
        )
    )

    assert snapshot.outcome == "notified"
    assert snapshot.delivery_success_count == 1
    assert snapshot.dev_recipient_count == 1
    assert snapshot.recipient_count == 1
    assert snapshot.used_fallback_recipient is False
    redis_repository.set.assert_awaited_once()
    notification_service.system_notify.assert_awaited_once()


def test_maybe_notify_about_release_update_returns_up_to_date_snapshot() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services()

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(tag_name="v1.1.11"),
            current_version="1.1.11",
        )
    )

    assert snapshot.outcome == "up_to_date"
    redis_repository.set.assert_not_awaited()
    notification_service.system_notify.assert_not_awaited()


def test_maybe_notify_about_release_update_returns_local_ahead_snapshot() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services()

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(tag_name="v1.1.11"),
            current_version="1.1.12",
        )
    )

    assert snapshot.outcome == "local_ahead"
    redis_repository.set.assert_not_awaited()
    notification_service.system_notify.assert_not_awaited()


def test_maybe_notify_about_release_update_returns_toggle_disabled_snapshot() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        toggle_enabled=False
    )

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(),
            current_version="1.1.11",
        )
    )

    assert snapshot.outcome == "toggle_disabled"
    assert snapshot.toggle_enabled is False
    redis_repository.set.assert_not_awaited()
    notification_service.system_notify.assert_not_awaited()


def test_maybe_notify_about_release_update_uses_fallback_recipient_when_no_devs() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        devs=[],
        delivery_results=[True],
    )

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(),
            current_version="1.1.11",
        )
    )

    assert snapshot.outcome == "notified"
    assert snapshot.dev_recipient_count == 0
    assert snapshot.recipient_count == 1
    assert snapshot.used_fallback_recipient is True
    notification_service.system_notify.assert_awaited_once()


def test_maybe_notify_about_release_update_returns_delivery_failed_snapshot() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        devs=[SimpleNamespace(telegram_id=1)],
        delivery_results=[False],
    )

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(),
            current_version="1.1.11",
        )
    )

    assert snapshot.outcome == "delivery_failed"
    assert snapshot.delivery_success_count == 0
    redis_repository.set.assert_not_awaited()


def test_maybe_notify_about_release_update_returns_already_notified_snapshot() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        last_notified_version="1.1.12"
    )

    snapshot = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(),
            current_version="1.1.11",
        )
    )

    assert snapshot.outcome == "already_notified"
    assert snapshot.dedupe_version == "1.1.12"
    notification_service.system_notify.assert_not_awaited()


def test_run_check_bot_update_persists_last_audit_snapshot(monkeypatch) -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        devs=[SimpleNamespace(telegram_id=1)],
        delivery_results=[True],
    )
    snapshots: list[UpdateCheckAuditSnapshot] = []

    async def remember_snapshot(key, value, ex=None):
        del ex
        if isinstance(key, LastUpdateCheckAuditKey):
            snapshots.append(value)

    redis_repository.set = AsyncMock(side_effect=remember_snapshot)

    async def fake_fetch_latest_release() -> GitHubReleaseFetchResult:
        return GitHubReleaseFetchResult(
            outcome="notified",
            release=build_release(
                tag_name="v1.1.13",
                name="Future Release",
                html_url="https://github.com/dizzzable/altshop/releases/tag/v1.1.13",
            ),
        )

    monkeypatch.setattr(
        "src.infrastructure.taskiq.tasks.updates.fetch_latest_github_release",
        fake_fetch_latest_release,
    )

    snapshot = run_async(
        run_check_bot_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
        )
    )

    assert snapshot.outcome == "notified"
    assert snapshots and snapshots[-1].outcome == "notified"


def test_run_check_bot_update_persists_fetch_failure_snapshot(monkeypatch) -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services()
    snapshots: list[UpdateCheckAuditSnapshot] = []

    async def remember_snapshot(key, value, ex=None):
        del ex
        if isinstance(key, LastUpdateCheckAuditKey):
            snapshots.append(value)

    redis_repository.set = AsyncMock(side_effect=remember_snapshot)

    async def fake_fetch_latest_release() -> GitHubReleaseFetchResult:
        return GitHubReleaseFetchResult(outcome="github_fetch_failed", release=None)

    monkeypatch.setattr(
        "src.infrastructure.taskiq.tasks.updates.fetch_latest_github_release",
        fake_fetch_latest_release,
    )

    snapshot = run_async(
        run_check_bot_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
        )
    )

    assert snapshot.outcome == "github_fetch_failed"
    assert snapshots and snapshots[-1].outcome == "github_fetch_failed"
    notification_service.system_notify.assert_not_awaited()


def test_update_keyboard_uses_official_release_urls() -> None:
    keyboard = get_remnashop_update_keyboard()
    first_row = keyboard.inline_keyboard[0]

    assert first_row[0].url == ALTSHOP_GITHUB_RELEASES_LATEST_URL
    assert first_row[1].url == ALTSHOP_GITHUB_UPGRADE_GUIDE_URL


def test_update_notification_flow_uses_bot_update_type() -> None:
    redis_repository, settings_service, user_service, notification_service = build_update_services(
        devs=[SimpleNamespace(telegram_id=1)],
        delivery_results=[True],
    )

    run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            settings_service=settings_service,
            user_service=user_service,
            notification_service=notification_service,
            latest_release=build_release(),
            current_version="1.1.11",
        )
    )

    assert (
        notification_service.system_notify.await_args.kwargs["ntf_type"]
        == SystemNotificationType.BOT_UPDATE
    )
