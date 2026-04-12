# mypy: ignore-errors
# ruff: noqa: E501

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient, Response, Timeout
from loguru import logger
from pydantic import ValidationError
from remnawave import RemnawaveSDK
from remnawave.models import GetExternalSquadsResponseDto, GetStatsResponseDto


class RemnawaveClientMixin:
    remnawave: RemnawaveSDK

    async def try_connection(self) -> None:
        try:
            response = await self.remnawave.system.get_stats()
        except ValidationError as exception:
            logger.warning(
                "Remnawave SDK validation failed for /system/stats, "
                "falling back to raw health check: {}",
                exception,
            )
            await self._try_connection_raw()
            return

        if not isinstance(response, GetStatsResponseDto):
            if isinstance(response, (bytes, bytearray)):
                response = response.decode(errors="ignore")
            logger.warning(
                "Unexpected Remnawave /system/stats response type '{}', "
                "falling back to raw health check",
                type(response).__name__,
            )
            await self._try_connection_raw()

    def _build_raw_api_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.config.remnawave.token.get_secret_value()}",
            "X-Api-Key": self.config.remnawave.caddy_token.get_secret_value(),
        }

        if not self.config.remnawave.is_external:
            headers["x-forwarded-proto"] = "https"
            headers["x-forwarded-for"] = "127.0.0.1"

        return headers

    def _build_raw_api_base_url(self) -> str:
        return f"{self.config.remnawave.url.get_secret_value()}/api"

    @staticmethod
    def _build_raw_api_timeout(
        *,
        connect: float = 15.0,
        read: float = 25.0,
        write: float = 10.0,
        pool: float = 5.0,
    ) -> Timeout:
        return Timeout(connect=connect, read=read, write=write, pool=pool)

    def _build_raw_api_client(self, *, timeout: Timeout | None = None) -> AsyncClient:
        return AsyncClient(
            base_url=self._build_raw_api_base_url(),
            headers=self._build_raw_api_headers(),
            cookies=self.config.remnawave.cookies,
            verify=True,
            timeout=timeout or self._build_raw_api_timeout(),
        )

    async def _request_raw_api_response(
        self,
        path: str,
        *,
        timeout: Timeout | None = None,
    ) -> Response:
        async with self._build_raw_api_client(timeout=timeout) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response

    async def _request_raw_api_json(
        self,
        path: str,
        *,
        timeout: Timeout | None = None,
    ) -> Any:
        response = await self._request_raw_api_response(path, timeout=timeout)
        return response.json()

    async def _try_connection_raw(self) -> None:
        await self._request_raw_api_response(
            "/system/stats",
            timeout=self._build_raw_api_timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
        )

    async def get_external_squads_safe(self) -> list[dict[str, Any]]:
        try:
            response = await self.remnawave.external_squads.get_external_squads()
            if isinstance(response, GetExternalSquadsResponseDto):
                return [{"uuid": s.uuid, "name": s.name} for s in response.external_squads]
        except ValidationError as exc:
            logger.warning(
                "Remnawave SDK validation error for /external-squads, falling back to raw HTTP: "
                f"{exc}"
            )
        except Exception as exc:
            logger.warning(
                f"Failed to fetch /external-squads via SDK, falling back to raw HTTP: {exc}"
            )

        return await self._get_external_squads_raw()

    async def _get_external_squads_raw(self) -> list[dict[str, Any]]:
        data = await self._request_raw_api_json("/external-squads")
        return self._parse_external_squads_payload(data)

    @staticmethod
    def _parse_external_squads_payload(data: Any) -> list[dict[str, Any]]:
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
