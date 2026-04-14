from __future__ import annotations

from typing import Any, cast

from loguru import logger

from src.core.constants import DATETIME_FORMAT
from src.core.enums import RemnaNodeEvent, SystemNotificationType
from src.core.utils.formatters import format_country_code, i18n_format_bytes_to_unit
from src.core.utils.message_payload import MessagePayload


async def handle_node_event(service: Any, event: str, node: Any) -> None:
    from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
        send_system_notification_task,
    )
    system_task = cast(Any, send_system_notification_task)

    logger.info("Received node event '{}' for node '{}'", event, node.name)

    if event == RemnaNodeEvent.CONNECTION_LOST:
        logger.warning("Connection lost for node '{}'", node.name)
        i18n_key = "ntf-event-node-connection-lost"
    elif event == RemnaNodeEvent.CONNECTION_RESTORED:
        logger.info("Connection restored for node '{}'", node.name)
        i18n_key = "ntf-event-node-connection-restored"
    elif event == RemnaNodeEvent.TRAFFIC_NOTIFY:
        logger.debug("Traffic threshold reached on node '{}'", node.name)
        i18n_key = "ntf-event-node-traffic"
    else:
        logger.warning("Unhandled node event '{}' for node '{}'", event, node.name)
        return

    await system_task.kiq(
        ntf_type=SystemNotificationType.NODE_STATUS,
        payload=MessagePayload.not_deleted(
            i18n_key=i18n_key,
            i18n_kwargs={
                "country": format_country_code(code=node.country_code),
                "name": node.name,
                "address": node.address,
                "port": str(node.port),
                "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
                "traffic_limit": i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                "last_status_message": node.last_status_message or "None",
                "last_status_change": node.last_status_change.strftime(DATETIME_FORMAT)
                if node.last_status_change
                else "None",
            },
        ),
    )
