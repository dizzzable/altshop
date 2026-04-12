from pathlib import Path


def test_event_coverage_matrix_documents_current_event_surface() -> None:
    content = Path("docs/EVENT_COVERAGE_MATRIX.md").read_text(encoding="utf-8")

    assert "Event Coverage Matrix" in content
    assert "ntf-event-web-user-registered" in content
    assert "ntf-event-web-account-linked" in content
    assert "ntf-event-subscription-upgrade" in content
    assert "ntf-event-access-policy" in content
