from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.keyboards import get_remnashop_update_keyboard
from src.core.constants import (
    ALTSHOP_GITHUB_RELEASES_LATEST_URL,
    ALTSHOP_GITHUB_UPGRADE_GUIDE_URL,
)
from src.infrastructure.taskiq.tasks import updates
from src.infrastructure.taskiq.tasks.updates import (
    GitHubReleaseSnapshot,
    build_update_notification_payload,
    maybe_notify_about_release_update,
    normalize_release_version,
    parse_github_release_snapshot,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_release(
    *,
    tag_name: str = "v1.1.5",
    name: str | None = "Spring Release",
    published_at: str = "2026-03-22T10:15:00Z",
    html_url: str = "https://github.com/dizzzable/altshop/releases/tag/v1.1.5",
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


def test_normalize_release_version_strips_v_prefix() -> None:
    assert normalize_release_version("v1.1.5") == "1.1.5"
    assert normalize_release_version("1.1.5") == "1.1.5"


def test_parse_github_release_snapshot_ignores_prerelease() -> None:
    release = parse_github_release_snapshot(
        {
            "tag_name": "v1.1.5-rc1",
            "name": "RC 1",
            "published_at": "2026-03-22T10:15:00Z",
            "html_url": "https://example.com/release",
            "draft": False,
            "prerelease": True,
        }
    )

    assert release is None


def test_parse_github_release_snapshot_rejects_malformed_payload() -> None:
    try:
        parse_github_release_snapshot({"tag_name": "v1.1.5"})
    except ValueError as exception:
        assert "published_at" in str(exception)
    else:
        raise AssertionError("Expected malformed GitHub release payload to raise ValueError")


def test_parse_github_release_snapshot_hides_unhelpful_title() -> None:
    release = build_release(name="AltShop v1.1.5")

    assert release.release_title is None
    assert release.version == "1.1.5"
    assert release.published_at_label == "2026-03-22 10:15 UTC"


def test_build_update_notification_payload_includes_release_details() -> None:
    payload = build_update_notification_payload(
        current_version="1.1.4",
        latest_release=build_release(),
    )

    assert payload.i18n_key == "ntf-event-bot-update"
    assert payload.i18n_kwargs["local_version"] == "1.1.4"
    assert payload.i18n_kwargs["remote_version"] == "1.1.5"
    assert payload.i18n_kwargs["release_published_at"] == "2026-03-22 10:15 UTC"
    assert payload.i18n_kwargs["release_title"] == "Spring Release"
    assert payload.i18n_kwargs["has_release_title"] is True


def test_maybe_notify_about_release_update_sends_once(monkeypatch) -> None:
    send_mock = AsyncMock()
    monkeypatch.setattr(
        updates,
        "send_system_notification_task",
        SimpleNamespace(kiq=send_mock),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
    )

    notified = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            latest_release=build_release(),
            current_version="1.1.4",
        )
    )

    assert notified is True
    redis_repository.set.assert_awaited_once()
    send_mock.assert_awaited_once()


def test_maybe_notify_about_release_update_skips_same_release(monkeypatch) -> None:
    send_mock = AsyncMock()
    monkeypatch.setattr(
        updates,
        "send_system_notification_task",
        SimpleNamespace(kiq=send_mock),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value="1.1.5"),
        set=AsyncMock(),
    )

    notified = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            latest_release=build_release(),
            current_version="1.1.4",
        )
    )

    assert notified is False
    redis_repository.set.assert_not_awaited()
    send_mock.assert_not_awaited()


def test_maybe_notify_about_release_update_skips_when_local_is_current(monkeypatch) -> None:
    send_mock = AsyncMock()
    monkeypatch.setattr(
        updates,
        "send_system_notification_task",
        SimpleNamespace(kiq=send_mock),
    )
    redis_repository = SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(),
    )

    notified = run_async(
        maybe_notify_about_release_update(
            redis_repository=redis_repository,
            latest_release=build_release(tag_name="v1.1.4"),
            current_version="1.1.4",
        )
    )

    assert notified is False
    redis_repository.set.assert_not_awaited()
    send_mock.assert_not_awaited()


def test_update_keyboard_uses_official_release_urls() -> None:
    keyboard = get_remnashop_update_keyboard()
    first_row = keyboard.inline_keyboard[0]

    assert first_row[0].url == ALTSHOP_GITHUB_RELEASES_LATEST_URL
    assert first_row[1].url == ALTSHOP_GITHUB_UPGRADE_GUIDE_URL
