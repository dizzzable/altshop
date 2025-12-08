from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from src.core.utils.formatters import (
    format_bytes_to_gb,
    format_device_count,
    i18n_format_expire_time,
)

if TYPE_CHECKING:
    from .plan import PlanDto, PlanSnapshotDto
    from .user import BaseUserDto

from datetime import datetime, timedelta
from uuid import UUID

from loguru import logger
from pydantic import BaseModel, Field
from remnawave.enums import TrafficLimitStrategy

from src.core.enums import DeviceType, PlanType, SubscriptionStatus
from src.core.utils.time import datetime_now

from .base import TrackableDto


class RemnaSubscriptionDto(BaseModel):
    uuid: UUID
    status: SubscriptionStatus
    expire_at: datetime
    url: str

    traffic_limit: int
    device_limit: int
    traffic_limit_strategy: Optional[TrafficLimitStrategy] = None

    tag: Optional[str] = None
    internal_squads: list[UUID]
    external_squad: Optional[UUID] = None

    @classmethod
    def from_remna_user(cls, user: dict[str, Any]) -> "RemnaSubscriptionDto":
        traffic_limit_bytes = user.get("traffic_limit_bytes") or user.get("trafficLimitBytes")
        hwid_device_limit = user.get("hwid_device_limit") or user.get("hwidDeviceLimit")

        raw_squads = user.get("active_internal_squads") or user.get("activeInternalSquads") or []
        internal_squads = [
            s["uuid"] if isinstance(s, dict) and "uuid" in s else s for s in raw_squads
        ]

        return cls(
            uuid=user.get("uuid"),
            status=user.get("status"),
            expire_at=user.get("expire_at") or user.get("expireAt"),
            url=user.get("subscription_url") or user.get("subscriptionUrl") or "",
            traffic_limit=format_bytes_to_gb(traffic_limit_bytes),
            device_limit=format_device_count(hwid_device_limit),
            traffic_limit_strategy=user.get("traffic_limit_strategy")
            or user.get("trafficLimitStrategy"),
            tag=user.get("tag"),
            internal_squads=internal_squads,
            external_squad=user.get("external_squad_uuid") or user.get("externalSquadUuid"),
        )


class BaseSubscriptionDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    user_remna_id: UUID

    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    is_trial: bool = False

    traffic_limit: int
    device_limit: int
    internal_squads: list[UUID]
    external_squad: Optional[UUID]

    expire_at: datetime
    url: str

    device_type: Optional[DeviceType] = None

    plan: "PlanSnapshotDto"

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def is_active(self) -> bool:
        return self.get_status == SubscriptionStatus.ACTIVE

    @property
    def is_unlimited(self) -> bool:
        return self.expire_at.year == 2099

    @property
    def get_status(self) -> SubscriptionStatus:
        """Get actual status considering expiration time."""
        if datetime_now() > self.expire_at:
            return SubscriptionStatus.EXPIRED
        return self.status

    @property
    def get_traffic_reset_delta(self) -> Optional[timedelta]:
        """Get time until next traffic reset based on plan strategy."""
        from src.services.subscription import SubscriptionService  # noqa: PLC0415

        return SubscriptionService.get_traffic_reset_delta(self.plan.traffic_limit_strategy)

    @property
    def get_expire_time(self) -> Union[list[tuple[str, dict[str, int]]], bool]:
        """Get formatted expire time for i18n display."""
        if self.get_traffic_reset_delta:
            return i18n_format_expire_time(self.get_traffic_reset_delta)
        else:
            return False

    @property
    def get_subscription_type(self) -> PlanType:
        has_traffic = self.traffic_limit > 0
        has_devices = self.device_limit > 0

        if has_traffic and has_devices:
            return PlanType.BOTH
        elif has_traffic:
            return PlanType.TRAFFIC
        elif has_devices:
            return PlanType.DEVICES
        else:
            return PlanType.UNLIMITED

    @property
    def has_devices_limit(self) -> bool:
        return self.get_subscription_type in (PlanType.DEVICES, PlanType.BOTH)

    @property
    def has_traffic_limit(self) -> bool:
        return self.get_subscription_type in (PlanType.TRAFFIC, PlanType.BOTH)

    def has_same_plan(self, plan: "PlanDto") -> bool:
        if plan is None or self.plan is None:
            return False

        # Compare by plan ID first (most reliable)
        if self.plan.id == plan.id:
            return True

        # Fallback to comparing key attributes (for legacy subscriptions)
        return (
            self.plan.tag == plan.tag
            and self.plan.type == plan.type
            and self.plan.traffic_limit == plan.traffic_limit
            and self.plan.device_limit == plan.device_limit
            and self.plan.traffic_limit_strategy == plan.traffic_limit_strategy
            and self.plan.internal_squads == plan.internal_squads
            and self.plan.external_squad == plan.external_squad
        )

    def find_matching_plan(self, plans: list[PlanDto]) -> Optional[PlanDto]:
        return next((plan for plan in plans if self.has_same_plan(plan)), None)


class SubscriptionDto(BaseSubscriptionDto):
    user: Optional["BaseUserDto"] = None

    def apply_sync(self, sync_data: RemnaSubscriptionDto) -> SubscriptionDto:
        for field in type(sync_data).model_fields:
            if hasattr(self, field):
                old_value = getattr(self, field)
                new_value = getattr(sync_data, field)
                if old_value != new_value:
                    setattr(self, field, new_value)
                    logger.info(f"Field '{field}' updated: '{old_value}' → '{new_value}'")

        return self
