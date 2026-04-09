from __future__ import annotations

from types import SimpleNamespace

from src.bot.routers.dashboard.remnawave.getters import _build_system_stats_payload
from src.core.i18n.keys import TimeUnitKey


def test_build_system_stats_payload_handles_nullable_memory_fields() -> None:
    response = SimpleNamespace(
        cpu=SimpleNamespace(physical_cores=None, cores=8),
        memory=SimpleNamespace(active=None, total=16 * 1024**3),
        uptime=None,
    )

    payload = _build_system_stats_payload(response)

    assert payload["cpu_cores"] == 0
    assert payload["cpu_threads"] == 8
    assert payload["ram_used_percent"] == "0.00"
    assert payload["uptime"] == [(TimeUnitKey.MINUTE, {"value": 0})]


def test_build_system_stats_payload_returns_zero_defaults_without_response() -> None:
    payload = _build_system_stats_payload(None)

    assert payload["cpu_cores"] == 0
    assert payload["cpu_threads"] == 0
    assert payload["ram_used_percent"] == 0
