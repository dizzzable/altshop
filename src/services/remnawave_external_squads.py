from typing import Any
from uuid import UUID

from httpx import AsyncClient, Timeout
from loguru import logger
from pydantic import ValidationError
from remnawave import RemnawaveSDK
from remnawave.models import GetExternalSquadsResponseDto

from src.core.config import AppConfig
from src.core.observability import emit_counter


class RemnawaveExternalSquadLookup:
    def __init__(self, config: AppConfig, remnawave: RemnawaveSDK) -> None:
        self.config = config
        self.remnawave = remnawave

    async def get_external_squads_safe(self) -> list[dict[str, Any]]:
        """Fetch external squads while tolerating older SDK DTO validation drift."""

        try:
            response = await self.remnawave.external_squads.get_external_squads()
            if isinstance(response, GetExternalSquadsResponseDto):
                return [
                    {"uuid": squad.uuid, "name": squad.name}
                    for squad in response.external_squads
                ]
        except ValidationError as exc:
            emit_counter(
                "remnawave_degraded_states_total",
                stage="external_squads",
                reason="sdk_validation",
            )
            logger.warning(
                "Remnawave SDK validation error for /external-squads, falling back to raw HTTP: "
                f"{exc}"
            )
        except Exception as exc:
            emit_counter(
                "remnawave_degraded_states_total",
                stage="external_squads",
                reason="sdk_error",
            )
            logger.warning(
                f"Failed to fetch /external-squads via SDK, falling back to raw HTTP: {exc}"
            )

        return await self.get_external_squads_raw()

    async def get_external_squads_raw(self) -> list[dict[str, Any]]:
        config = self.config
        headers: dict[str, str] = {
            "Authorization": f"Bearer {config.remnawave.token.get_secret_value()}",
            "X-Api-Key": config.remnawave.caddy_token.get_secret_value(),
        }

        if not config.remnawave.is_external:
            headers["x-forwarded-proto"] = "https"
            headers["x-forwarded-for"] = "127.0.0.1"

        async with AsyncClient(
            base_url=f"{config.remnawave.url.get_secret_value()}/api",
            headers=headers,
            cookies=config.remnawave.cookies,
            verify=True,
            timeout=Timeout(connect=15.0, read=25.0, write=10.0, pool=5.0),
        ) as client:
            response = await client.get("/external-squads")
            response.raise_for_status()
            data = response.json()

        return self.parse_external_squads_payload(data)

    @staticmethod
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
