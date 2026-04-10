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

    assert payload["cpu_cores"] == 8
    assert payload["ram_used_percent"] == "0.00"
    assert payload["version_suffix"] == ""
    assert payload["uptime"] == [(TimeUnitKey.MINUTE, {"value": 0})]


def test_build_system_stats_payload_returns_zero_defaults_without_response() -> None:
    payload = _build_system_stats_payload(None)

    assert payload["cpu_cores"] == 0
    assert payload["ram_used_percent"] == 0
    assert payload["version_suffix"] == ""


def test_build_system_stats_payload_supports_new_memory_used_alias_and_metadata_version() -> None:
    response = SimpleNamespace(
        cpu=SimpleNamespace(physical_cores=None, cores=2),
        memory=SimpleNamespace(used=8 * 1024**3, total=16 * 1024**3),
        uptime=3600,
    )
    metadata = SimpleNamespace(metadata={"version": "2.7.1"})

    payload = _build_system_stats_payload(response, metadata=metadata)

    assert payload["version_suffix"] == " v2.7.1"
    assert payload["cpu_cores"] == 2
    assert payload["ram_used_percent"] == "50.00"


def test_build_system_stats_payload_handles_missing_metadata_version() -> None:
    response = SimpleNamespace(
        cpu=SimpleNamespace(physical_cores=4, cores=8),
        memory=SimpleNamespace(active=4 * 1024**3, total=8 * 1024**3),
        uptime=7200,
    )
    metadata = SimpleNamespace(metadata={"build": {}})

    payload = _build_system_stats_payload(response, metadata=metadata)

    assert payload["version_suffix"] == ""
