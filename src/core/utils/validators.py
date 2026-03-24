from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from aiogram_dialog import DialogManager

from src.core.constants import URL_PATTERN, USERNAME_PATTERN, WEB_LOGIN_PATTERN
from src.core.utils.time import datetime_now


def is_valid_url(text: str) -> bool:
    return bool(URL_PATTERN.match(text))


def is_valid_username(text: str) -> bool:
    return bool(USERNAME_PATTERN.match(text))


def normalize_web_login(text: str) -> str:
    return text.strip().lower()


def is_valid_web_login(text: str) -> bool:
    return bool(WEB_LOGIN_PATTERN.match(normalize_web_login(text)))


def validate_web_login_or_raise(text: str) -> str:
    normalized = normalize_web_login(text)
    if not is_valid_web_login(normalized):
        raise ValueError(
            "Invalid username format. Use lowercase Latin letters, digits, "
            "dots, and underscores without leading or trailing dot/underscore."
        )
    return normalized


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


def parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if not value:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
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
