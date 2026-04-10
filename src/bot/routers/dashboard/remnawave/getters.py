import asyncio
import logging
from typing import Any, Optional

import httpx
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from remnawave import RemnawaveSDK
from remnawave.models import (
    GetAllHostsResponseDto,
    GetAllInboundsResponseDto,
    GetMetadataResponseDto,
    GetAllNodesResponseDto,
    GetStatsResponseDto,
)

from src.core.i18n.translator import get_translated_kwargs
from src.core.utils.formatters import (
    format_country_code,
    format_percent,
    i18n_format_bytes_to_unit,
    i18n_format_seconds,
)

logger = logging.getLogger(__name__)


async def _load_stats(remnawave: RemnawaveSDK) -> Optional[GetStatsResponseDto]:
    try:
        response = await remnawave.system.get_stats()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch Remnawave stats: %s", exc)
        return None

    if not isinstance(response, GetStatsResponseDto):
        logger.warning("Unexpected response from Remnawave system.get_stats()")
        return None

    return response


async def _load_metadata(remnawave: RemnawaveSDK) -> Optional[GetMetadataResponseDto]:
    try:
        response = await remnawave.system.get_metadata()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch Remnawave metadata: %s", exc)
        return None

    if not isinstance(response, GetMetadataResponseDto):
        logger.warning("Unexpected response from Remnawave system.get_metadata()")
        return None

    return response


def _coerce_stat_int(value: object | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _first_present_value(source: object | None, *names: str) -> object | None:
    if source is None:
        return None
    for name in names:
        value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _build_version_suffix(metadata: Optional[GetMetadataResponseDto]) -> str:
    if metadata is None:
        return ""

    raw_metadata = getattr(metadata, "metadata", None)
    candidates: list[object | None] = []
    if isinstance(raw_metadata, dict):
        candidates.extend(
            [
                raw_metadata.get("version"),
                raw_metadata.get("panelVersion"),
                raw_metadata.get("appVersion"),
            ]
        )
        build = raw_metadata.get("build")
        if isinstance(build, dict):
            candidates.append(build.get("version"))

    candidates.append(getattr(metadata, "version", None))

    for candidate in candidates:
        if candidate is None:
            continue
        version = str(candidate).strip()
        if version:
            return f" v{version}"
    return ""


def _build_system_stats_payload(
    response: Optional[GetStatsResponseDto],
    *,
    metadata: Optional[GetMetadataResponseDto] = None,
) -> dict[str, Any]:
    if response is None:
        return {
            "version_suffix": _build_version_suffix(metadata),
            "cpu_cores": 0,
            "ram_used": i18n_format_bytes_to_unit(0),
            "ram_total": i18n_format_bytes_to_unit(0),
            "ram_used_percent": 0,
            "uptime": i18n_format_seconds(0),
        }

    cpu_cores = _coerce_stat_int(_first_present_value(response.cpu, "physical_cores", "cores"))
    memory_used = _coerce_stat_int(_first_present_value(response.memory, "active", "used"))
    memory_total = _coerce_stat_int(_first_present_value(response.memory, "total"))
    uptime_seconds = _coerce_stat_int(getattr(response, "uptime", None))

    return {
        "version_suffix": _build_version_suffix(metadata),
        "cpu_cores": cpu_cores,
        "ram_used": i18n_format_bytes_to_unit(memory_used),
        "ram_total": i18n_format_bytes_to_unit(memory_total),
        "ram_used_percent": format_percent(part=memory_used, whole=memory_total)
        if memory_total > 0
        else 0,
        "uptime": i18n_format_seconds(uptime_seconds),
    }


@inject
async def system_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    response, metadata = await asyncio.gather(
        _load_stats(remnawave),
        _load_metadata(remnawave),
    )
    return _build_system_stats_payload(response, metadata=metadata)


@inject
async def users_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await _load_stats(remnawave)

    if response is None:
        return {
            "users_total": "0",
            "users_active": "0",
            "users_disabled": "0",
            "users_limited": "0",
            "users_expired": "0",
            "online_last_day": "0",
            "online_last_week": "0",
            "online_never": "0",
            "online_now": "0",
        }

    return {
        "users_total": str(response.users.total_users),
        # Remnawave SDK >= 2.3.2: status_counts is a dict-like mapping
        "users_active": str(response.users.status_counts.get("ACTIVE", 0)),
        "users_disabled": str(response.users.status_counts.get("DISABLED", 0)),
        "users_limited": str(response.users.status_counts.get("LIMITED", 0)),
        "users_expired": str(response.users.status_counts.get("EXPIRED", 0)),
        "online_last_day": str(response.online_stats.last_day),
        "online_last_week": str(response.online_stats.last_week),
        "online_never": str(response.online_stats.never_online),
        "online_now": str(response.online_stats.online_now),
    }


@inject
async def hosts_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_hosts")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    response = await remnawave.hosts.get_all_hosts()
    hosts = []

    if not isinstance(response, GetAllHostsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    for host in response:
        hosts.append(
            i18n.get(
                "msg-remnawave-host-details",
                remark=host.remark,
                status="OFF" if host.is_disabled else "ON",
                address=host.address,
                port=str(host.port),
                inbound_uuid=str(host.inbound_uuid) if host.inbound_uuid else False,
            )
        )

    return {
        "pages": len(hosts),
        "current_page": current_page + 1,
        "host": hosts[current_page],
    }


@inject
async def nodes_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_nodes")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    response = await remnawave.nodes.get_all_nodes()
    nodes = []

    if not isinstance(response, GetAllNodesResponseDto):
        raise ValueError("Wrong response from Remnawave")

    # SDK compatibility: some versions expose nodes as RootModel (.root),
    # others are iterable directly.
    nodes_iter = response.root if hasattr(response, "root") else response

    for node in nodes_iter:
        kwargs_for_i18n = {
            "xray_uptime": i18n_format_seconds(node.xray_uptime),
            "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
            "traffic_limit": i18n_format_bytes_to_unit(
                node.traffic_limit_bytes or -1, round_up=True
            ),
        }

        translated_data = get_translated_kwargs(i18n, kwargs_for_i18n)

        nodes.append(
            i18n.get(
                "msg-remnawave-node-details",
                country=format_country_code(code=node.country_code),
                name=node.name,
                status="ON" if node.is_connected else "OFF",
                address=node.address,
                port=str(node.port) if node.port else False,
                xray_uptime=translated_data["xray_uptime"],
                users_online=str(node.users_online),
                traffic_used=translated_data["traffic_used"],
                traffic_limit=translated_data["traffic_limit"],
            )
        )

    return {
        "pages": len(nodes),
        "current_page": current_page + 1,
        "node": nodes[current_page],
    }


@inject
async def inbounds_getter(
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_inbounds")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    response = await remnawave.inbounds.get_all_inbounds()
    inbounds = []

    if not isinstance(response, GetAllInboundsResponseDto):
        raise ValueError("Wrong response from Remnawave")

    for inbound in response.inbounds:  # type: ignore[attr-defined]
        inbounds.append(
            i18n.get(
                "msg-remnawave-inbound-details",
                inbound_id=str(inbound.uuid),
                tag=inbound.tag,
                type=inbound.type,
                port=str(int(inbound.port)) if inbound.port else False,
                network=inbound.network or False,
                security=inbound.security or False,
            )
        )

    return {
        "pages": len(inbounds),
        "current_page": current_page + 1,
        "inbound": inbounds[current_page],
    }
