from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.enums import AccessMode
from src.infrastructure.database.models.dto import SettingsDto, UserDto


@dataclass(slots=True)
class AccessModePolicy:
    access_mode: AccessMode
    invite_locked: bool
    is_invited_grandfathered: bool
    can_view_product_screens: bool
    can_mutate_product: bool
    can_purchase: bool
    should_redirect_to_access_screen: bool


class AccessModePolicyService:
    def resolve(self, *, user: UserDto, settings: SettingsDto) -> AccessModePolicy:
        if user.is_privileged:
            return AccessModePolicy(
                access_mode=settings.access_mode,
                invite_locked=False,
                is_invited_grandfathered=False,
                can_view_product_screens=True,
                can_mutate_product=True,
                can_purchase=True,
                should_redirect_to_access_screen=False,
            )

        mode = settings.access_mode
        if mode == AccessMode.RESTRICTED:
            return AccessModePolicy(
                access_mode=mode,
                invite_locked=False,
                is_invited_grandfathered=False,
                can_view_product_screens=False,
                can_mutate_product=False,
                can_purchase=False,
                should_redirect_to_access_screen=True,
            )

        if mode == AccessMode.PURCHASE_BLOCKED:
            return AccessModePolicy(
                access_mode=mode,
                invite_locked=False,
                is_invited_grandfathered=False,
                can_view_product_screens=True,
                can_mutate_product=True,
                can_purchase=False,
                should_redirect_to_access_screen=False,
            )

        if mode == AccessMode.INVITED:
            is_grandfathered = self.is_grandfathered_invited_user(
                user=user,
                invite_mode_started_at=settings.invite_mode_started_at,
            )
            invite_locked = not is_grandfathered
            return AccessModePolicy(
                access_mode=mode,
                invite_locked=invite_locked,
                is_invited_grandfathered=is_grandfathered,
                can_view_product_screens=not invite_locked,
                can_mutate_product=not invite_locked,
                can_purchase=not invite_locked,
                should_redirect_to_access_screen=invite_locked,
            )

        return AccessModePolicy(
            access_mode=mode,
            invite_locked=False,
            is_invited_grandfathered=False,
            can_view_product_screens=True,
            can_mutate_product=True,
            can_purchase=True,
            should_redirect_to_access_screen=False,
        )

    @staticmethod
    def is_grandfathered_invited_user(
        *,
        user: UserDto,
        invite_mode_started_at: datetime | None,
    ) -> bool:
        if user.is_privileged or user.is_invited_user:
            return True

        if invite_mode_started_at is None or user.created_at is None:
            return True

        return user.created_at < invite_mode_started_at
