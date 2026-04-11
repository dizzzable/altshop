from types import SimpleNamespace

from src.infrastructure.taskiq.tasks.importer import _parse_telegram_id


def test_parse_telegram_id_accepts_negative_panel_id() -> None:
    remna_user = SimpleNamespace(uuid="profile-1", telegram_id="-605")

    result = _parse_telegram_id(remna_user)

    assert result == -605


def test_parse_telegram_id_rejects_non_numeric_value() -> None:
    remna_user = SimpleNamespace(uuid="profile-2", telegram_id="not-a-number")

    result = _parse_telegram_id(remna_user)

    assert result is None
