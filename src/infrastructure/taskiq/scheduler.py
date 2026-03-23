from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from src.core.logger import setup_logger

from .broker import broker
from .registry import register_task_modules


def scheduler() -> TaskiqScheduler:
    setup_logger()
    register_task_modules()
    scheduler = TaskiqScheduler(
        broker=broker,
        sources=[LabelScheduleSource(broker)],
    )
    return scheduler
