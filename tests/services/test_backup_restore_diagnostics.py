from __future__ import annotations

from src.services.backup_restore_diagnostics import (
    analyze_restore_archive,
    extract_current_subscription_refs,
)


def test_extract_current_subscription_refs_skips_incomplete_rows() -> None:
    refs = extract_current_subscription_refs(
        [
            {"telegram_id": 123, "current_subscription_id": "7"},
            {"telegram_id": None, "current_subscription_id": 8},
            {"telegram_id": 456, "current_subscription_id": None},
            {"telegram_id": "bad", "current_subscription_id": "9"},
            "not-a-row",
        ]
    )

    assert refs == [(123, 7)]


def test_analyze_restore_archive_flags_legacy_plan_and_subscription_gaps() -> None:
    diagnostics = analyze_restore_archive(
        {
            "plans": [],
            "plan_durations": [{"id": 1, "plan_id": 1, "days": 30}],
            "plan_prices": [{"id": 2, "plan_duration_id": 1, "price": "100"}],
            "users": [{"id": 10, "telegram_id": "123", "current_subscription_id": "77"}],
            "subscriptions": [{"id": 55}],
        }
    )

    assert diagnostics.current_subscription_refs == [(123, 77)]
    assert diagnostics.missing_archive_subscription_refs == [(123, 77)]
    assert diagnostics.panel_sync_candidate_ids == [123]
    assert diagnostics.archive_issue_messages == [
        "Archive is missing plan rows and requires legacy plan recovery",
        "Archive is missing subscription rows referenced by users.current_subscription_id",
    ]
