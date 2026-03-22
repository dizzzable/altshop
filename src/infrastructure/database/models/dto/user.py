from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import Field, PrivateAttr, field_validator

from src.core.constants import REMNASHOP_PREFIX
from src.core.enums import Currency, Locale, UserRole
from src.core.utils.time import datetime_now

from .base import BaseDto, TrackableDto

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto.base import SqlModel

    from .subscription import BaseSubscriptionDto


class ReferralInviteIndividualSettingsDto(BaseDto):
    use_global_settings: bool = True
    link_ttl_enabled: bool = False
    link_ttl_seconds: int | None = None
    slots_enabled: bool = False
    initial_slots: int | None = None
    refill_threshold_qualified: int | None = None
    refill_amount: int | None = None


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
    partner_balance_currency_override: Optional[Currency] = None
    referral_invite_settings: ReferralInviteIndividualSettingsDto = Field(
        default_factory=ReferralInviteIndividualSettingsDto
    )

    # Per-user subscription cap:
    # None -> use global, -1 -> unlimited, >0 -> explicit limit.
    max_subscriptions: Optional[int] = None

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @field_validator("referral_invite_settings", mode="before")
    @classmethod
    def parse_referral_invite_settings(
        cls,
        value: Union[dict[str, Any], ReferralInviteIndividualSettingsDto, None],
    ) -> ReferralInviteIndividualSettingsDto:
        if value is None:
            return ReferralInviteIndividualSettingsDto()
        if isinstance(value, ReferralInviteIndividualSettingsDto):
            return value
        if isinstance(value, dict):
            return ReferralInviteIndividualSettingsDto(**value)
        return ReferralInviteIndividualSettingsDto()

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

    @classmethod  # Compatibility-first conversion from SQL model.
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
