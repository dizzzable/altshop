from __future__ import annotations

from typing import Any

from httpx import AsyncClient, Response, Timeout
from remnawave import RemnawaveSDK

from .remnawave_client_health import (
    get_external_squads_raw as _get_external_squads_raw_impl,
)
from .remnawave_client_health import (
    get_external_squads_safe as _get_external_squads_safe_impl,
)
from .remnawave_client_health import (
    try_connection as _try_connection_impl,
)
from .remnawave_client_health import (
    try_connection_raw as _try_connection_raw_impl,
)
from .remnawave_client_raw import (
    build_raw_api_base_url as _build_raw_api_base_url_impl,
)
from .remnawave_client_raw import (
    build_raw_api_client as _build_raw_api_client_impl,
)
from .remnawave_client_raw import (
    build_raw_api_headers as _build_raw_api_headers_impl,
)
from .remnawave_client_raw import (
    build_raw_api_timeout as _build_raw_api_timeout_impl,
)
from .remnawave_client_raw import (
    parse_external_squads_payload as _parse_external_squads_payload_impl,
)
from .remnawave_client_raw import (
    request_raw_api_json as _request_raw_api_json_impl,
)
from .remnawave_client_raw import (
    request_raw_api_response as _request_raw_api_response_impl,
)


class RemnawaveClientMixin:
    remnawave: RemnawaveSDK

    async def try_connection(self) -> None:
        await _try_connection_impl(self)

    def _build_raw_api_headers(self) -> dict[str, str]:
        return _build_raw_api_headers_impl(self)

    def _build_raw_api_base_url(self) -> str:
        return _build_raw_api_base_url_impl(self)

    @staticmethod
    def _build_raw_api_timeout(
        *,
        connect: float = 15.0,
        read: float = 25.0,
        write: float = 10.0,
        pool: float = 5.0,
    ) -> Timeout:
        return _build_raw_api_timeout_impl(
            connect=connect,
            read=read,
            write=write,
            pool=pool,
        )

    def _build_raw_api_client(self, *, timeout: Timeout | None = None) -> AsyncClient:
        return _build_raw_api_client_impl(self, timeout=timeout)

    async def _request_raw_api_response(
        self,
        path: str,
        *,
        timeout: Timeout | None = None,
    ) -> Response:
        return await _request_raw_api_response_impl(self, path, timeout=timeout)

    async def _request_raw_api_json(
        self,
        path: str,
        *,
        timeout: Timeout | None = None,
    ) -> Any:
        return await _request_raw_api_json_impl(self, path, timeout=timeout)

    async def _try_connection_raw(self) -> None:
        await _try_connection_raw_impl(self)

    async def get_external_squads_safe(self) -> list[dict[str, Any]]:
        return await _get_external_squads_safe_impl(self)

    async def _get_external_squads_raw(self) -> list[dict[str, Any]]:
        return await _get_external_squads_raw_impl(self)

    @staticmethod
    def _parse_external_squads_payload(data: Any) -> list[dict[str, Any]]:
        return _parse_external_squads_payload_impl(data)
