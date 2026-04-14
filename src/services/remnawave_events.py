from __future__ import annotations

from typing import Any

from src.core.enums import DeviceType

from .remnawave_events_device import (
    handle_device_event as _handle_device_event_impl,
)
from .remnawave_events_device import (
    normalize_platform_to_device_type as _normalize_platform_to_device_type_impl,
)
from .remnawave_events_node import handle_node_event as _handle_node_event_impl
from .remnawave_events_user import (
    build_user_event_i18n_kwargs as _build_user_event_i18n_kwargs_impl,
)
from .remnawave_events_user import (
    handle_created_user_event as _handle_created_user_event_impl,
)
from .remnawave_events_user import (
    handle_expiration_user_event as _handle_expiration_user_event_impl,
)
from .remnawave_events_user import (
    handle_status_change_user_event as _handle_status_change_user_event_impl,
)
from .remnawave_events_user import (
    handle_user_event as _handle_user_event_impl,
)
from .remnawave_events_user import (
    is_expired_imported_user as _is_expired_imported_user_impl,
)


class RemnawaveEventsMixin:
    @staticmethod
    def _normalize_platform_to_device_type(platform: str | None) -> DeviceType:
        return _normalize_platform_to_device_type_impl(platform)

    @staticmethod
    def _build_user_event_i18n_kwargs(user: Any, remna_user: Any) -> dict[str, Any]:
        return _build_user_event_i18n_kwargs_impl(user, remna_user)

    async def _handle_created_user_event(self, remna_user: Any) -> None:
        await _handle_created_user_event_impl(self, remna_user)

    @staticmethod
    def _is_expired_imported_user(remna_user: Any, user: Any) -> bool:
        return _is_expired_imported_user_impl(remna_user, user)

    async def _handle_status_change_user_event(
        self,
        *,
        event: str,
        remna_user: Any,
        i18n_kwargs: dict[str, Any],
        update_status_current_subscription_task: Any,
    ) -> None:
        await _handle_status_change_user_event_impl(
            self,
            event=event,
            remna_user=remna_user,
            i18n_kwargs=i18n_kwargs,
            update_status_current_subscription_task=update_status_current_subscription_task,
        )

    async def _handle_expiration_user_event(
        self,
        *,
        event: str,
        remna_user: Any,
        i18n_kwargs: dict[str, Any],
    ) -> None:
        await _handle_expiration_user_event_impl(
            self,
            event=event,
            remna_user=remna_user,
            i18n_kwargs=i18n_kwargs,
        )

    async def handle_user_event(self, event: str, remna_user: Any) -> None:
        await _handle_user_event_impl(self, event, remna_user)

    async def handle_device_event(self, event: str, remna_user: Any, device: Any) -> None:
        await _handle_device_event_impl(self, event, remna_user, device)

    async def handle_node_event(self, event: str, node: Any) -> None:
        await _handle_node_event_impl(self, event, node)
