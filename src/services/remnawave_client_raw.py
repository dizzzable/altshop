from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from httpx import AsyncClient, Response, Timeout


def build_raw_api_headers(service: Any) -> dict[str, str]:
    headers: dict[str, str] = {
        "Authorization": f"Bearer {service.config.remnawave.token.get_secret_value()}",
        "X-Api-Key": service.config.remnawave.caddy_token.get_secret_value(),
    }

    if not service.config.remnawave.is_external:
        headers["x-forwarded-proto"] = "https"
        headers["x-forwarded-for"] = "127.0.0.1"

    return headers


def build_raw_api_base_url(service: Any) -> str:
    return f"{service.config.remnawave.url.get_secret_value()}/api"


def build_raw_api_timeout(
    *,
    connect: float = 15.0,
    read: float = 25.0,
    write: float = 10.0,
    pool: float = 5.0,
) -> Timeout:
    return Timeout(connect=connect, read=read, write=write, pool=pool)


def build_raw_api_client(
    service: Any,
    *,
    timeout: Timeout | None = None,
) -> AsyncClient:
    return AsyncClient(
        base_url=service._build_raw_api_base_url(),
        headers=service._build_raw_api_headers(),
        cookies=service.config.remnawave.cookies,
        verify=True,
        timeout=timeout or service._build_raw_api_timeout(),
    )


async def request_raw_api_response(
    service: Any,
    path: str,
    *,
    timeout: Timeout | None = None,
) -> Response:
    async with service._build_raw_api_client(timeout=timeout) as client:
        response = await client.get(path)
        response.raise_for_status()
        return cast(Response, response)


async def request_raw_api_json(
    service: Any,
    path: str,
    *,
    timeout: Timeout | None = None,
) -> Any:
    response = await service._request_raw_api_response(path, timeout=timeout)
    return response.json()


def parse_external_squads_payload(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    response = data.get("response")
    if response is None:
        response = data

    if not isinstance(response, dict):
        return []

    squads = response.get("externalSquads") or response.get("external_squads")
    if not isinstance(squads, list):
        return []

    parsed: list[dict[str, Any]] = []
    for item in squads:
        if not isinstance(item, dict):
            continue
        raw_uuid = item.get("uuid")
        name = item.get("name")
        if not raw_uuid or not name:
            continue
        try:
            squad_uuid = UUID(str(raw_uuid))
        except Exception:
            continue
        parsed.append({"uuid": squad_uuid, "name": str(name)})

    return parsed
