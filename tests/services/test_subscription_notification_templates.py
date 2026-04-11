from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _extract_block(*, file_path: Path, start_key: str, end_key: str) -> str:
    text = file_path.read_text(encoding="utf-8")
    _, tail = text.split(f"{start_key} =", maxsplit=1)
    block, _ = tail.split(f"{end_key} =", maxsplit=1)
    return block


def test_ru_upgrade_notification_template_matches_subscription_event_layout() -> None:
    block = _extract_block(
        file_path=ROOT_DIR / "assets/translations/ru/notifications.ftl",
        start_key="ntf-event-subscription-upgrade",
        end_key="ntf-event-subscription-additional",
    )

    assert "#EventSubscriptionUpgrade" in block
    assert "{ hdr-payment }" in block
    assert "{ frg-payment-info }" in block
    assert "{ hdr-user }" in block
    assert "{ frg-user-info }" in block
    assert "{ hdr-plan }" in block
    assert "{ frg-plan-snapshot }" in block


def test_en_upgrade_notification_template_matches_subscription_event_layout() -> None:
    block = _extract_block(
        file_path=ROOT_DIR / "assets/translations/en/notifications.ftl",
        start_key="ntf-event-subscription-upgrade",
        end_key="ntf-event-subscription-additional",
    )

    assert "#EventSubscriptionUpgrade" in block
    assert "{ hdr-payment }" in block
    assert "{ frg-payment-info }" in block
    assert "{ hdr-user }" in block
    assert "{ frg-user-info }" in block
    assert "{ hdr-plan }" in block
    assert "{ frg-plan-snapshot }" in block


def test_notification_tasks_import_real_remnawave_service_instead_of_any_alias() -> None:
    module_text = (
        ROOT_DIR / "src/infrastructure/taskiq/tasks/notifications.py"
    ).read_text(encoding="utf-8")

    assert "from src.services.remnawave import RemnawaveService" in module_text
    assert "RemnawaveService = Any" not in module_text
