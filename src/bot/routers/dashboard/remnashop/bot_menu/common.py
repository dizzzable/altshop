from __future__ import annotations

import hashlib
import re

from src.core.security.crypto import base62_encode
from src.infrastructure.database.models.dto import BotMenuCustomButtonDto

BOT_MENU_CALLBACK_ID_LENGTH = 10
BOT_MENU_LIST_WIDGET_ID = "custom_button_list"
BOT_MENU_SELECT_WIDGET_ID = "select_custom_button"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.]+$")


def sorted_buttons(buttons: list[BotMenuCustomButtonDto]) -> list[BotMenuCustomButtonDto]:
    return sorted(buttons, key=lambda item: (item.order, item.id))


def button_callback_id(raw_id: str) -> str:
    normalized = raw_id.strip()
    if 1 <= len(normalized) <= BOT_MENU_CALLBACK_ID_LENGTH and _SAFE_ID_RE.fullmatch(normalized):
        return normalized

    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    encoded = base62_encode(int.from_bytes(digest[:8], "big"))
    return encoded[:BOT_MENU_CALLBACK_ID_LENGTH].rjust(BOT_MENU_CALLBACK_ID_LENGTH, "0")


def bot_menu_callback_payload_length(raw_id: str) -> int:
    callback_id = button_callback_id(raw_id)
    return len(f"{BOT_MENU_LIST_WIDGET_ID}:{callback_id}:{BOT_MENU_SELECT_WIDGET_ID}")

