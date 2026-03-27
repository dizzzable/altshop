from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from pydantic import ValidationError
from remnawave.models import GetAllInternalSquadsResponseDto

from src.core.observability import clear_metrics_registry, render_metrics_text
from src.services.remnawave_external_squads import RemnawaveExternalSquadLookup


def run_async(coroutine):
    return asyncio.run(coroutine)


def setup_function() -> None:
    clear_metrics_registry()


def teardown_function() -> None:
    clear_metrics_registry()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def build_validation_error() -> ValidationError:
    try:
        GetAllInternalSquadsResponseDto.model_validate({"bad": "payload"})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected validation error")


def build_lookup() -> tuple[RemnawaveExternalSquadLookup, SimpleNamespace]:
    config = SimpleNamespace(
        remnawave=SimpleNamespace(
            token=SimpleNamespace(get_secret_value=lambda: "token"),
            caddy_token=SimpleNamespace(get_secret_value=lambda: "caddy"),
            is_external=True,
            url=SimpleNamespace(get_secret_value=lambda: "https://panel.example"),
            cookies={},
        )
    )
    remnawave = SimpleNamespace(
        external_squads=SimpleNamespace(get_external_squads=AsyncMock())
    )
    return RemnawaveExternalSquadLookup(config=config, remnawave=remnawave), remnawave


def test_get_external_squads_safe_uses_raw_fallback_on_validation_error() -> None:
    lookup, remnawave = build_lookup()
    fallback_result = [{"uuid": uuid4(), "name": "Europe"}]
    remnawave.external_squads.get_external_squads.side_effect = build_validation_error()
    lookup.get_external_squads_raw = AsyncMock(return_value=fallback_result)  # type: ignore[method-assign]

    result = run_async(lookup.get_external_squads_safe())

    assert result == fallback_result
    lookup.get_external_squads_raw.assert_awaited_once()  # type: ignore[attr-defined]
    assert (
        'remnawave_degraded_states_total{reason="sdk_validation",stage="external_squads"} 1'
        in render_metrics_text()
    )


def test_parse_external_squads_payload_accepts_newer_panel_shape() -> None:
    lookup, _remnawave = build_lookup()
    squad_uuid = uuid4()

    payload = {
        "response": {
            "externalSquads": [
                {
                    "uuid": str(squad_uuid),
                    "viewPosition": 7,
                    "name": "Europe",
                    "info": {},
                    "templates": [],
                    "createdAt": now_utc().isoformat(),
                    "updatedAt": now_utc().isoformat(),
                }
            ]
        }
    }

    assert lookup.parse_external_squads_payload(payload) == [
        {"uuid": squad_uuid, "name": "Europe"}
    ]
