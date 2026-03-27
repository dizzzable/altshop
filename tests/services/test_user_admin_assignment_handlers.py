from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message
from aiogram_dialog import ShowMode

from src.bot.routers.dashboard.users.user.handlers import (
    on_partner_source_assignment_input,
    on_referrer_assignment_input,
)
from src.bot.states import DashboardUser
from src.core.constants import USER_KEY
from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.partner import (
    PartnerAttributionAssignmentError,
    PartnerService,
)
from src.services.referral import ReferralService
from src.services.user import UserService


def run_async(coroutine):
    return asyncio.run(coroutine)


def build_message(text: str) -> Message:
    return Message.model_validate(
        {
            "message_id": 1,
            "date": "2026-03-26T20:00:00+00:00",
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "Admin"},
            "text": text,
        }
    )


def make_user(telegram_id: int, *, name: str | None = None) -> UserDto:
    return UserDto(
        telegram_id=telegram_id,
        username=f"user_{telegram_id}",
        referral_code=f"ref_{telegram_id}",
        name=name or f"User {telegram_id}",
        role=UserRole.ADMIN,
        language=Locale.EN,
    )


def build_dialog_manager(admin_user: UserDto, *, target_telegram_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        middleware_data={USER_KEY: admin_user},
        dialog_data={"target_telegram_id": target_telegram_id},
        switch_to=AsyncMock(),
        show_mode=None,
    )


class FakeDishkaContainer:
    def __init__(self, mapping: dict[type[object], object]) -> None:
        self.mapping = mapping

    async def get(self, type_hint, component=None):
        del component
        return self.mapping[type_hint]


def build_dialog_manager_with_container(
    admin_user: UserDto,
    *,
    target_telegram_id: int,
    notification_service: object,
    user_service: object,
    referral_service: object | None = None,
    partner_service: object | None = None,
) -> SimpleNamespace:
    container_mapping: dict[type[object], object] = {
        NotificationService: notification_service,
        UserService: user_service,
    }
    if referral_service is not None:
        container_mapping[ReferralService] = referral_service
    if partner_service is not None:
        container_mapping[PartnerService] = partner_service

    return SimpleNamespace(
        middleware_data={
            USER_KEY: admin_user,
            "dishka_container": FakeDishkaContainer(container_mapping),
        },
        dialog_data={"target_telegram_id": target_telegram_id},
        switch_to=AsyncMock(),
        show_mode=None,
    )


def test_on_referrer_assignment_input_notifies_and_returns_to_main_on_success() -> None:
    admin_user = make_user(1, name="Admin")
    target_user = make_user(500, name="Target")
    source_user = make_user(600, name="Referrer")
    notification_service = SimpleNamespace(notify_user=AsyncMock())
    referral_service = SimpleNamespace(assign_referrer=AsyncMock())
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=target_user),
        search_users=AsyncMock(return_value=[source_user]),
    )
    dialog_manager = build_dialog_manager_with_container(
        admin_user,
        target_telegram_id=target_user.telegram_id,
        notification_service=notification_service,
        referral_service=referral_service,
        user_service=user_service,
    )

    run_async(
        on_referrer_assignment_input(
            build_message("600"),
            MagicMock(),
            dialog_manager,
        )
    )

    assert dialog_manager.show_mode == ShowMode.EDIT
    referral_service.assign_referrer.assert_awaited_once_with(
        referred=target_user,
        referrer=source_user,
    )
    notify_call = notification_service.notify_user.await_args
    assert notify_call.kwargs["user"] == admin_user
    assert notify_call.kwargs["payload"].i18n_key == "ntf-user-referrer-assigned"
    dialog_manager.switch_to.assert_awaited_once_with(state=DashboardUser.MAIN)


def test_on_partner_source_assignment_input_maps_history_locked_error() -> None:
    admin_user = make_user(1, name="Admin")
    target_user = make_user(500, name="Target")
    source_user = make_user(700, name="Partner Source")
    notification_service = SimpleNamespace(notify_user=AsyncMock())
    partner_service = SimpleNamespace(
        assign_partner_attribution=AsyncMock(
            side_effect=PartnerAttributionAssignmentError("HAS_HISTORY")
        )
    )
    user_service = SimpleNamespace(
        get=AsyncMock(return_value=target_user),
        search_users=AsyncMock(return_value=[source_user]),
    )
    dialog_manager = build_dialog_manager_with_container(
        admin_user,
        target_telegram_id=target_user.telegram_id,
        notification_service=notification_service,
        partner_service=partner_service,
        user_service=user_service,
    )

    run_async(
        on_partner_source_assignment_input(
            build_message("700"),
            MagicMock(),
            dialog_manager,
        )
    )

    assert dialog_manager.show_mode == ShowMode.EDIT
    partner_service.assign_partner_attribution.assert_awaited_once_with(
        user=target_user,
        source_user=source_user,
    )
    notify_call = notification_service.notify_user.await_args
    assert notify_call.kwargs["user"] == admin_user
    assert notify_call.kwargs["payload"].i18n_key == "ntf-user-partner-source-history-locked"
    dialog_manager.switch_to.assert_not_awaited()
