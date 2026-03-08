from typing import TYPE_CHECKING, Optional

from src.core.enums import PurchaseChannel, ReferralInviteSource, ReferralLevel, ReferralRewardType

if TYPE_CHECKING:
    from .user import BaseUserDto

from datetime import datetime

from pydantic import Field

from .base import TrackableDto


class ReferralDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    level: ReferralLevel
    invite_source: ReferralInviteSource = ReferralInviteSource.UNKNOWN
    qualified_at: Optional[datetime] = None
    qualified_purchase_channel: Optional[PurchaseChannel] = None
    qualified_transaction_id: Optional[int] = None

    referrer: "BaseUserDto"
    referred: "BaseUserDto"

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def is_qualified(self) -> bool:
        return self.qualified_at is not None


class ReferralRewardDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    type: ReferralRewardType
    amount: int
    is_issued: bool = False

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def rewarded_at(self) -> Optional[datetime]:
        return self.created_at
