from __future__ import annotations

from typing import Any, cast

from loguru import logger
from pydantic import ValidationError
from remnawave.models import GetExternalSquadsResponseDto, GetStatsResponseDto


async def try_connection(service: Any) -> None:
    try:
        response = await service.remnawave.system.get_stats()
    except ValidationError as exception:
        logger.warning(
            "Remnawave SDK validation failed for /system/stats, "
            "falling back to raw health check: {}",
            exception,
        )
        await service._try_connection_raw()
        return

    if not isinstance(response, GetStatsResponseDto):
        if isinstance(response, (bytes, bytearray)):
            response = response.decode(errors="ignore")
        logger.warning(
            "Unexpected Remnawave /system/stats response type '{}', "
            "falling back to raw health check",
            type(response).__name__,
        )
        await service._try_connection_raw()


async def try_connection_raw(service: Any) -> None:
    await service._request_raw_api_response(
        "/system/stats",
        timeout=service._build_raw_api_timeout(
            connect=5.0,
            read=15.0,
            write=10.0,
            pool=5.0,
        ),
    )


async def get_external_squads_safe(service: Any) -> list[dict[str, Any]]:
    try:
        response = await service.remnawave.external_squads.get_external_squads()
        if isinstance(response, GetExternalSquadsResponseDto):
            return [{"uuid": squad.uuid, "name": squad.name} for squad in response.external_squads]
    except ValidationError as exc:
        logger.warning(
            "Remnawave SDK validation error for /external-squads, falling back to raw HTTP: {}",
            exc,
        )
    except Exception as exc:
        logger.warning(
            "Failed to fetch /external-squads via SDK, falling back to raw HTTP: {}",
            exc,
        )

    return cast(list[dict[str, Any]], await service._get_external_squads_raw())


async def get_external_squads_raw(service: Any) -> list[dict[str, Any]]:
    data = await service._request_raw_api_json("/external-squads")
    return cast(list[dict[str, Any]], service._parse_external_squads_payload(data))
