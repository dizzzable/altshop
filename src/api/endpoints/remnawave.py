import traceback
import uuid
from typing import cast

from aiogram.utils.formatting import Text
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, HTTPException, Request, Response, status
from loguru import logger
from remnawave.controllers import WebhookUtility
from remnawave.models.webhook import NodeDto, UserDto, UserHwidDeviceEventDto

from src.core.config import AppConfig
from src.core.constants import API_V1, REMNAWAVE_WEBHOOK_PATH
from src.core.utils.system_events import build_system_event_payload
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.services.remnawave import RemnawaveService
from src.services.subscription_device import SubscriptionDeviceService
from src.services.subscription_runtime import SubscriptionRuntimeService

router = APIRouter(prefix=API_V1)


@router.post(REMNAWAVE_WEBHOOK_PATH)
@inject
async def remnawave_webhook(
    request: Request,
    config: FromDishka[AppConfig],
    remnawave_service: FromDishka[RemnawaveService],
    subscription_device_service: FromDishka[SubscriptionDeviceService],
    subscription_runtime_service: FromDishka[SubscriptionRuntimeService],
) -> Response:
    try:
        raw_body = await request.body()
        payload = WebhookUtility.parse_webhook(
            body=raw_body.decode("utf-8"),
            headers=dict(request.headers),
            webhook_secret=config.remnawave.webhook_secret.get_secret_value(),
            validate=True,
        )
    except Exception as exception:
        logger.exception(f"Webhook validation failed: {exception}")
        raise HTTPException(status_code=401)

    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        if WebhookUtility.is_user_event(payload.event):
            user = cast(UserDto, WebhookUtility.get_typed_data(payload))
            await remnawave_service.handle_user_event(payload.event, user)

        elif WebhookUtility.is_user_hwid_devices_event(payload.event):
            event = cast(UserHwidDeviceEventDto, WebhookUtility.get_typed_data(payload))
            await remnawave_service.handle_device_event(
                payload.event,
                event.user,
                event.hwid_user_device,
            )
            await subscription_device_service.apply_device_event_to_cached_list(
                user_remna_id=event.user.uuid,
                event=payload.event,
                hwid_device=event.hwid_user_device,
            )
            await subscription_runtime_service.apply_device_event_to_cached_runtime(
                user_remna_id=event.user.uuid,
                event=payload.event,
            )

        elif WebhookUtility.is_node_event(payload.event):
            node = cast(NodeDto, WebhookUtility.get_typed_data(payload))
            await remnawave_service.handle_node_event(payload.event, node)

        else:
            logger.warning(f"Unhandled Remnawave event type: '{payload.event}'")

    except Exception as exception:
        logger.exception(f"Error processing Remnawave webhook: {exception}")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=str(uuid.uuid4()),
            traceback_str=traceback_str,
            payload=build_system_event_payload(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": False,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
                severity="ERROR",
                event_source="api.remnawave",
                entry_surface="WEBHOOK",
                operation=f"remnawave_webhook:{payload.event}",
                impact=(
                    "Panel-originated sync events may be skipped "
                    "until webhook processing is restored."
                ),
                operator_hint=(
                    "Check the Remnawave payload, event type, and "
                    "downstream service health before replaying."
                ),
            ),
        )

    return Response(status_code=status.HTTP_200_OK)
