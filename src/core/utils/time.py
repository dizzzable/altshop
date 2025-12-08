import time
from datetime import datetime

from src.core.constants import TIMEZONE

START_TIME: int = int(time.time())


def datetime_now() -> datetime:
    return datetime.now(tz=TIMEZONE)


def get_uptime() -> int:  # TODO: Think about where to put this
    return int(time.time() - START_TIME)
