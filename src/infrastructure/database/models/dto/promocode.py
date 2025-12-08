from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING, Any, Optional, Type

if TYPE_CHECKING:
    from .plan import PlanSnapshotDto
    from .user import BaseUserDto

from datetime import datetime, timedelta

from pydantic import Field

from src.core.enums import PromocodeAvailability, PromocodeRewardType
from src.core.utils.time import datetime_now

from .base import BaseDto, TrackableDto


class PromocodeActivationBaseDto(BaseDto):
    """Base DTO for promocode activation without back-reference to promocode (to avoid recursion)"""
    id: Optional[int] = Field(default=None, frozen=True)

    promocode_id: int
    user_telegram_id: int

    activated_at: Optional[datetime] = Field(default=None, frozen=True)

    user: Optional["BaseUserDto"] = None


class PromocodeDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    code: str = Field(default_factory=lambda: PromocodeDto.generate_code())
    is_active: bool = False

    availability: PromocodeAvailability = PromocodeAvailability.ALL
    reward_type: PromocodeRewardType = PromocodeRewardType.PERSONAL_DISCOUNT
    reward: Optional[int] = 1
    plan: Optional["PlanSnapshotDto"] = None

    lifetime: int = -1  # -1 означает бессрочный
    max_activations: int = -1  # -1 означает безлимитный
    allowed_user_ids: list[int] = Field(default_factory=list)  # Список разрешенных пользователей для ALLOWED

    activations: list["PromocodeActivationBaseDto"] = []

    @classmethod
    def from_model(
        cls: Type["PromocodeDto"],
        model_instance: Any,
        *,
        decrypt: bool = False,
    ) -> Optional["PromocodeDto"]:
        """Override from_model to handle circular reference in activations"""
        if model_instance is None:
            return None

        from src.core.security.crypto import deep_decrypt

        data = model_instance.__dict__.copy()
        if decrypt:
            data = deep_decrypt(data)

        # Convert activations to base DTO to avoid circular reference
        if "activations" in data and data["activations"]:
            activations_data = []
            for activation in data["activations"]:
                activation_dict = activation.__dict__.copy()
                # Remove the back-reference to promocode to break the cycle
                activation_dict.pop("promocode", None)
                activations_data.append(activation_dict)
            data["activations"] = activations_data

        return cls.model_validate(data)

    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)

    @property
    def is_unlimited(self) -> bool:
        """Проверка, является ли промокод безлимитным по количеству активаций"""
        return self.max_activations == -1 or self.max_activations is None

    @property
    def is_depleted(self) -> bool:
        """Проверка, исчерпан ли лимит активаций промокода"""
        # -1 означает безлимитный
        if self.max_activations == -1 or self.max_activations is None:
            return False

        return len(self.activations) >= self.max_activations

    @property
    def is_available(self) -> bool:
        """Проверка, доступен ли промокод для активации"""
        return self.is_active and not self.is_expired and not self.is_depleted

    @property
    def is_unlimited_lifetime(self) -> bool:
        """Проверка, является ли промокод бессрочным"""
        return self.lifetime == -1 or self.lifetime is None

    @property
    def expires_at(self) -> Optional[datetime]:
        """Получение даты истечения срока действия промокода"""
        # -1 означает бессрочный
        if self.lifetime == -1 or self.lifetime is None:
            return None
        if self.created_at is None:
            return None
        return self.created_at + timedelta(days=self.lifetime)

    @property
    def is_expired(self) -> bool:
        """Проверка, истек ли срок действия промокода"""
        # Бессрочный промокод не может истечь
        if self.lifetime == -1 or self.lifetime is None:
            return False
        
        if self.expires_at is None:
            return False

        current_time = datetime_now()
        return current_time > self.expires_at

    @property
    def time_left(self) -> Optional[timedelta]:
        if self.expires_at is None:
            return None

        current_time = datetime_now()
        delta = self.expires_at - current_time
        return delta if delta.total_seconds() > 0 else timedelta(seconds=0)

    @staticmethod
    def generate_code(length: int = 10) -> str:
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))


class PromocodeActivationDto(PromocodeActivationBaseDto):
    """Full DTO for promocode activation with optional back-reference to promocode"""
    promocode: Optional["PromocodeDto"] = None
