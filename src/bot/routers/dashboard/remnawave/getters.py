import logging
from typing import Any, Optional

from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.common import ManagedScroll
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from remnawave.models import GetStatsResponseDto

from src.core.i18n.translator import get_translated_kwargs
from src.core.utils.formatters import (
    format_country_code,
    format_percent,
    i18n_format_bytes_to_unit,
    i18n_format_seconds,
)
from src.services.remnawave import RemnawaveService

logger = logging.getLogger(__name__)


async def _load_stats(remnawave_service: RemnawaveService) -> Optional[GetStatsResponseDto]:
    return await remnawave_service.get_stats_safe()


@inject
async def system_getter(
    dialog_manager: DialogManager,
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await _load_stats(remnawave_service)

    if response is None:
        return {
            "cpu_cores": 0,
            "cpu_threads": 0,
            "ram_used": i18n_format_bytes_to_unit(0),
            "ram_total": i18n_format_bytes_to_unit(0),
            "ram_used_percent": 0,
            "uptime": i18n_format_seconds(0),
        }

    return {
        "cpu_cores": response.cpu.physical_cores,
        "cpu_threads": response.cpu.cores,
        "ram_used": i18n_format_bytes_to_unit(response.memory.active),
        "ram_total": i18n_format_bytes_to_unit(response.memory.total),
        "ram_used_percent": format_percent(
            part=response.memory.active,
            whole=response.memory.total,
        ),
        "uptime": i18n_format_seconds(response.uptime),
    }


@inject
async def users_getter(
    dialog_manager: DialogManager,
    remnawave_service: FromDishka[RemnawaveService],
    **kwargs: Any,
) -> dict[str, Any]:
    response = await _load_stats(remnawave_service)

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
    remnawave_service: FromDishka[RemnawaveService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_hosts")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    response = await remnawave_service.get_hosts()
    hosts = []

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
    remnawave_service: FromDishka[RemnawaveService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_nodes")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    response = await remnawave_service.get_nodes()
    nodes = []

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
    remnawave_service: FromDishka[RemnawaveService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    widget: Optional[ManagedScroll] = dialog_manager.find("scroll_inbounds")

    if not widget:
        raise ValueError()

    current_page = await widget.get_page()
    response = await remnawave_service.get_inbounds()
    inbounds = []

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
