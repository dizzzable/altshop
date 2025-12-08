from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto.base import SqlModel

    from .subscription import BaseSubscriptionDto

from datetime import datetime

from pydantic import Field, PrivateAttr

from src.core.constants import REMNASHOP_PREFIX
from src.core.enums import Locale, UserRole
from src.core.utils.time import datetime_now

from .base import TrackableDto


class BaseUserDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)
    telegram_id: int
    username: Optional[str] = None
    referral_code: str = ""

    name: str
    role: UserRole = UserRole.USER
    language: Locale = Locale.EN

    personal_discount: int = 0
    purchase_discount: int = 0
    points: int = 0

    is_blocked: bool = False
    is_bot_blocked: bool = False
    is_rules_accepted: bool = True

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def remna_name(self) -> str:  # NOTE: DONT USE FOR GET!
        return f"{REMNASHOP_PREFIX}{self.telegram_id}"

    @property
    def remna_description(self) -> str:
        return f"name: {self.name}\nusername: {self.username or ''}"

    @property
    def is_dev(self) -> bool:
        return self.role == UserRole.DEV

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_privileged(self) -> bool:
        return self.is_admin or self.is_dev

    @property
    def age_days(self) -> Optional[int]:
        if self.created_at is None:
            return None

        return (datetime_now() - self.created_at).days


class UserDto(BaseUserDto):
    current_subscription: Optional["BaseSubscriptionDto"] = None

    _is_invited_user: bool = PrivateAttr(default=False)
    _has_any_subscription: bool = PrivateAttr(default=False)

    @property
    def is_invited_user(self) -> bool:
        return self._is_invited_user

    @property
    def has_subscription(self) -> bool:
        return bool(self.current_subscription)

    @property
    def has_any_subscription(self) -> bool:
        return self._has_any_subscription

    @classmethod  # Fuck it, the main thing is that it works
    def from_model(
        cls,
        model_instance: Optional["SqlModel"],
        *,
        decrypt: bool = False,
    ) -> Optional["UserDto"]:
        dto = super().from_model(model_instance, decrypt=decrypt)
        if dto and model_instance:
            dto._has_any_subscription = bool(getattr(model_instance, "subscriptions", []))
            dto._is_invited_user = bool(getattr(model_instance, "referral", None))
        return dto
