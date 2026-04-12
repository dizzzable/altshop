import traceback
from typing import Any

from aiogram.utils.formatting import Text
from loguru import logger
from taskiq import TaskiqMessage, TaskiqResult
from taskiq.abc.middleware import TaskiqMiddleware

from src.core.utils.system_events import build_system_event_payload


class ErrorMiddleware(TaskiqMiddleware):
    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        logger.error(f"Task '{message.task_name}' error: {exception}")
        from src.infrastructure.taskiq.tasks.notifications import (  # noqa: PLC0415
            send_error_notification_task,
        )

        traceback_str = "".join(
            traceback.format_exception(type(exception), exception, exception.__traceback__)
        )
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=message.task_id,
            traceback_str=traceback_str,
            payload=build_system_event_payload(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": False,
                    "error": f"{error_type_name}: {error_message.as_html()}",
                },
                severity="ERROR",
                event_source="taskiq.middleware.error",
                entry_surface="BACKGROUND",
                operation=message.task_name,
                impact=(
                    "A background task failed and may leave "
                    "asynchronous workflows incomplete until repaired."
                ),
                operator_hint=(
                    "Open the traceback attachment and inspect the "
                    "failed task arguments or upstream dependency state."
                ),
            ),
        )
