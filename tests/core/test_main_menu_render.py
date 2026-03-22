from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from src.bot.routers.menu.dialog import menu
from src.bot.routers.menu.getters import _resolve_main_menu_view_state
from src.core.constants import CONTAINER_KEY, MIDDLEWARE_DATA_KEY, USER_KEY
from src.core.enums import UserRole
from src.core.i18n.storage import OverlayFileStorage
from src.infrastructure.database.models.dto import UserDto


def run_async(coroutine):
    return asyncio.run(coroutine)


class FakeContainer:
    def __init__(self, translator):
        self.translator = translator

    async def get(self, _cls):
        return self.translator


class FakeDialogManager(SimpleNamespace):
    def is_preview(self) -> bool:
        return False

    def current_context(self):
        return SimpleNamespace(id="main-menu-test")


def _build_manager(locale: str = "en", *, is_privileged: bool = False):
    storage = OverlayFileStorage(Path("assets/translations/{locale}"))
    translator = storage.get_translator(locale)
    assert translator is not None
    user = UserDto(telegram_id=1, name="DIZZABLE")
    if is_privileged:
        user.role = UserRole.DEV

    return FakeDialogManager(
        middleware_data={
            CONTAINER_KEY: FakeContainer(translator),
            MIDDLEWARE_DATA_KEY: {USER_KEY: user},
            USER_KEY: user,
        }
    )


def _build_menu_data(*, locked: bool) -> dict[str, object]:
    menu_message_key, product_sections_enabled = _resolve_main_menu_view_state(locked)
    return {
        "menu_message_key": menu_message_key,
        "product_sections_enabled": product_sections_enabled,
        "user_id": "813364774",
        "user_name": "DIZZABLE",
        "personal_discount": 0,
        "status": "ACTIVE",
        "is_trial": False,
        "traffic_limit": ("unit-unlimited", {"value": -1}),
        "device_limit": ("unit-unlimited", {"value": 999}),
        "expire_time": [("unit-unlimited", {"value": -1})],
        "subscriptions_count": 2,
        "count": 2,
        "has_subscription": True,
        "has_device_limit": True,
        "connectable": True,
        "trial_available": False,
        "support": "https://t.me/support",
        "invite": "",
        "is_app": False,
        "can_show_referral_exchange": False,
        "can_show_referral_invite": True,
        "can_show_referral_send_inline": False,
        "is_partner": True,
    }


def _flatten_button_texts(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def _contains_button(buttons: list[str], label: str) -> bool:
    return any(label in button for button in buttons)


def test_resolve_main_menu_view_state_is_single_source() -> None:
    assert _resolve_main_menu_view_state(False) == ("msg-main-menu-default", True)
    assert _resolve_main_menu_view_state(True) == ("msg-main-menu-invite-locked", False)


def test_main_menu_public_render_shows_normal_text_and_product_buttons() -> None:
    manager = _build_manager()
    data = _build_menu_data(locked=False)

    text = run_async(menu.render_text(data, manager))
    keyboard = run_async(menu.render_kbd(data, manager))
    buttons = _flatten_button_texts(keyboard)

    assert "Invite-only access" not in text
    assert "Profile" in text
    assert _contains_button(buttons, "Connect")
    assert _contains_button(buttons, "Subscription (2)")
    assert _contains_button(buttons, "Partner")


def test_main_menu_locked_render_shows_locked_text_without_product_buttons() -> None:
    manager = _build_manager()
    data = _build_menu_data(locked=True)

    text = run_async(menu.render_text(data, manager))
    keyboard = run_async(menu.render_kbd(data, manager))
    buttons = _flatten_button_texts(keyboard)

    assert "Invite-only access" in text
    assert "product actions are locked" in text
    assert not _contains_button(buttons, "Connect")
    assert not _contains_button(buttons, "Subscription (2)")
    assert not _contains_button(buttons, "Partner")


def test_main_menu_locked_and_buttons_cannot_drift_into_hybrid_state() -> None:
    manager = _build_manager()
    locked_data = _build_menu_data(locked=True)

    locked_text = run_async(menu.render_text(locked_data, manager))
    locked_buttons = _flatten_button_texts(run_async(menu.render_kbd(locked_data, manager)))

    assert "Invite-only access" in locked_text
    assert all(
        not _contains_button(locked_buttons, label)
        for label in ("Connect", "Subscription (2)", "Invite", "Partner")
    )
