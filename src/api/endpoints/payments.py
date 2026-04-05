import hashlib
import traceback
import uuid
from html import escape

from aiogram.utils.formatting import Text
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import HTMLResponse
from loguru import logger

from src.api.utils.request_ip import resolve_client_ip
from src.core.constants import API_V1, PAYMENTS_WEBHOOK_PATH
from src.core.enums import PaymentGatewayType
from src.core.observability import emit_counter
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.payment_gateways.platega import PlategaWebhookResolutionError
from src.infrastructure.payment_gateways.yoomoney import (
    YoomoneyGateway,
    parse_yoomoney_redirect_token,
)
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.infrastructure.taskiq.tasks.payments import handle_payment_transaction_task
from src.services.payment_gateway import PaymentGatewayService
from src.services.payment_webhook_event import PaymentWebhookEventService

router = APIRouter(prefix=API_V1 + PAYMENTS_WEBHOOK_PATH)


def _render_yoomoney_redirect_page(form_fields: dict[str, str]) -> str:
    hidden_inputs = "\n".join(
        (
            f'<input type="hidden" name="{escape(name)}" value="{escape(value)}" />'
            for name, value in form_fields.items()
        )
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        "  <title>Redirecting to YooMoney</title>\n"
        "</head>\n"
        "<body>\n"
        '  <form id="yoomoney-redirect-form" method="post"'
        f' action="{escape(YoomoneyGateway.QUICKPAY_URL)}">\n'
        f"{hidden_inputs}\n"
        "    <noscript>\n"
        '      <button type="submit">Continue to YooMoney</button>\n'
        "    </noscript>\n"
        "  </form>\n"
        "  <script>document.getElementById('yoomoney-redirect-form').submit();</script>\n"
        "</body>\n"
        "</html>\n"
    )


@router.get("/yoomoney/redirect")
async def yoomoney_redirect(
    token: str,
    request: Request,
) -> Response:
    app_state = getattr(getattr(request, "app", None), "state", None)
    app_config = getattr(app_state, "config", None)
    if app_config is None:
        logger.warning("YooMoney redirect requested without app config")
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    try:
        form_fields = parse_yoomoney_redirect_token(
            token=token,
            signing_secret=app_config.crypt_key.get_secret_value(),
        )
    except (PermissionError, ValueError) as exception:
        logger.warning(f"Invalid YooMoney redirect token: {exception}")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    return HTMLResponse(_render_yoomoney_redirect_page(form_fields))


@router.post("/{gateway_type}")
@inject
async def payments_webhook(
    gateway_type: str,
    request: Request,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    payment_webhook_event_service: FromDishka[PaymentWebhookEventService],
) -> Response:
    logger.info(f"Received webhook for gateway: '{gateway_type}'")
    app_state = getattr(getattr(request, "app", None), "state", None)
    app_config = getattr(app_state, "config", None)
    client_ip = (
        resolve_client_ip(request, app_config)
        if app_config is not None
        else (request.client.host if request.client else "unknown")
    )
    logger.debug(
        f"Webhook headers - X-Forwarded-For: '{request.headers.get('X-Forwarded-For', '')}', "
        f"X-Real-IP: '{request.headers.get('X-Real-IP', '')}', "
        f"Client: '{request.client.host if request.client else 'unknown'}', "
        f"Resolved IP: '{client_ip}'"
    )

    try:
        raw_body = await request.body()
        payload_hash = hashlib.sha256(raw_body).hexdigest()
        gateway_enum = PaymentGatewayType(gateway_type.upper())
        gateway = await payment_gateway_service._get_gateway_instance(gateway_enum)

        payment_id, payment_status = await gateway.handle_webhook(request)
        inbox_result = await payment_webhook_event_service.record_received(
            gateway_type=gateway_enum.value,
            payment_id=payment_id,
            payload_hash=payload_hash,
        )
        if inbox_result.already_processed:
            emit_counter(
                "payment_webhook_duplicate_total",
                gateway_type=gateway_enum.value,
            )
            logger.info(
                "Duplicate webhook already processed for gateway='{}' payment_id='{}'",
                gateway_enum.value,
                payment_id,
            )
            return await gateway.build_webhook_response(request)

        logger.info(
            "Webhook processed successfully - Payment ID: '{}' Status: '{}'",
            payment_id,
            payment_status,
        )
        try:
            await handle_payment_transaction_task.kiq(
                str(payment_id),
                payment_status.value,
                gateway_enum.value,
            )
        except Exception as queue_exception:
            emit_counter(
                "payment_webhook_enqueue_failures_total",
                gateway_type=gateway_enum.value,
            )
            await payment_webhook_event_service.mark_failed(
                gateway_type=gateway_enum.value,
                payment_id=payment_id,
                error_message=f"enqueue_failed: {queue_exception}",
            )
            logger.exception(
                "Failed to enqueue payment webhook for gateway='{}' payment_id='{}': {}",
                gateway_enum.value,
                payment_id,
                queue_exception,
            )
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        await payment_webhook_event_service.mark_enqueued(
            gateway_type=gateway_enum.value,
            payment_id=payment_id,
        )
        return await gateway.build_webhook_response(request)

    except ValueError as e:
        logger.warning(f"Invalid gateway type or webhook payload: '{gateway_type}' - {e}")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    except PermissionError as e:
        logger.warning(f"Permission denied for webhook: '{gateway_type}' - {e}")
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    except PlategaWebhookResolutionError as exception:
        logger.warning(
            "Platega webhook resolution failed for gateway='{}': {}",
            gateway_type,
            exception,
        )
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as exception:
        logger.exception(f"Error processing webhook for '{gateway_type}': {exception}")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=str(uuid.uuid4()),
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": False,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
            ),
        )

    return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
