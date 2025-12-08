from datetime import datetime, timedelta
from typing import Optional

from aiogram_dialog import DialogManager

from src.core.constants import URL_PATTERN, USERNAME_PATTERN
from src.core.utils.time import datetime_now


def is_valid_url(text: str) -> bool:
    return bool(URL_PATTERN.match(text))


def is_valid_username(text: str) -> bool:
    return bool(USERNAME_PATTERN.match(text))


def is_valid_int(value: Optional[str]) -> bool:
    if value is None:
        return False
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def is_double_click(dialog_manager: DialogManager, key: str, cooldown: int = 10) -> bool:
    now = datetime_now()
    last_click_str: Optional[str] = dialog_manager.dialog_data.get(key)
    if last_click_str:
        last_click = datetime.fromisoformat(last_click_str.replace("Z", "+00:00"))
        if now - last_click < timedelta(seconds=cooldown):
            return True

    dialog_manager.dialog_data[key] = now.isoformat()
    return False
