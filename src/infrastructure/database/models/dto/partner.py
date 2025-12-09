from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

if TYPE_CHECKING:
    from .user import BaseUserDto

from datetime import datetime

from pydantic import Field, field_validator

from src.core.enums import PartnerAccrualStrategy, PartnerLevel, PartnerRewardType

from .base import BaseDto, TrackableDto


class PartnerIndividualSettingsDto(BaseDto):
    """Индивидуальные настройки партнера.
    
    Позволяет назначить каждому партнеру свои условия начисления:
    - Стратегия начисления (при первой оплате реферала или с каждой оплаты)
    - Тип вознаграждения (процент или фиксированная сумма)
    - Индивидуальные проценты для каждого уровня
    - Индивидуальные фиксированные суммы для каждого уровня
    """
    
    # Использовать глобальные настройки (если True - все остальные поля игнорируются)
    use_global_settings: bool = True
    
    # Стратегия начисления
    accrual_strategy: PartnerAccrualStrategy = PartnerAccrualStrategy.ON_EACH_PAYMENT
    
    # Тип вознаграждения
    reward_type: PartnerRewardType = PartnerRewardType.PERCENT
    
    # Индивидуальные проценты для каждого уровня (None = использовать глобальное значение)
    level1_percent: Optional[Decimal] = None
    level2_percent: Optional[Decimal] = None
    level3_percent: Optional[Decimal] = None
    
    # Фиксированные суммы для каждого уровня (в копейках)
    # Используются только когда reward_type = FIXED_AMOUNT
    level1_fixed_amount: Optional[int] = None  # Копейки
    level2_fixed_amount: Optional[int] = None
    level3_fixed_amount: Optional[int] = None
    
    def get_level_percent(self, level: PartnerLevel) -> Optional[Decimal]:
        """Получить индивидуальный процент для уровня."""
        match level:
            case PartnerLevel.LEVEL_1:
                return self.level1_percent
            case PartnerLevel.LEVEL_2:
                return self.level2_percent
            case PartnerLevel.LEVEL_3:
                return self.level3_percent
        return None
    
    def get_level_fixed_amount(self, level: PartnerLevel) -> Optional[int]:
        """Получить индивидуальную фиксированную сумму для уровня."""
        match level:
            case PartnerLevel.LEVEL_1:
                return self.level1_fixed_amount
            case PartnerLevel.LEVEL_2:
                return self.level2_fixed_amount
            case PartnerLevel.LEVEL_3:
                return self.level3_fixed_amount
        return None
    
    @property
    def is_first_payment_only(self) -> bool:
        """Начислять только при первой оплате."""
        return self.accrual_strategy == PartnerAccrualStrategy.ON_FIRST_PAYMENT
    
    @property
    def is_fixed_amount(self) -> bool:
        """Использовать фиксированную сумму вместо процента."""
        return self.reward_type == PartnerRewardType.FIXED_AMOUNT


class PartnerDto(TrackableDto):
    """DTO партнера."""
    id: Optional[int] = Field(default=None, frozen=True)
    user_telegram_id: int
    
    # Баланс (в копейках/центах)
    balance: int = 0
    total_earned: int = 0
    total_withdrawn: int = 0
    
    # Статистика рефералов
    referrals_count: int = 0
    level2_referrals_count: int = 0
    level3_referrals_count: int = 0
    
    # Активность
    is_active: bool = True
    
    # Индивидуальные настройки партнера
    individual_settings: PartnerIndividualSettingsDto = Field(
        default_factory=PartnerIndividualSettingsDto
    )
    
    @field_validator("individual_settings", mode="before")
    @classmethod
    def parse_individual_settings(
        cls, value: Union[Dict[str, Any], PartnerIndividualSettingsDto, None]
    ) -> PartnerIndividualSettingsDto:
        """Преобразовать JSON словарь из БД в DTO."""
        if value is None:
            return PartnerIndividualSettingsDto()
        
        if isinstance(value, PartnerIndividualSettingsDto):
            return value
        
        if isinstance(value, dict):
            # Преобразуем строковые значения для Decimal
            parsed = {}
            
            parsed["use_global_settings"] = value.get("use_global_settings", True)
            
            # Преобразуем accrual_strategy
            accrual_str = value.get("accrual_strategy", "ON_EACH_PAYMENT")
            if isinstance(accrual_str, str):
                parsed["accrual_strategy"] = PartnerAccrualStrategy(accrual_str)
            else:
                parsed["accrual_strategy"] = accrual_str
            
            # Преобразуем reward_type
            reward_str = value.get("reward_type", "PERCENT")
            if isinstance(reward_str, str):
                parsed["reward_type"] = PartnerRewardType(reward_str)
            else:
                parsed["reward_type"] = reward_str
            
            # Преобразуем проценты (хранятся как строки или None)
            for level_key in ["level1_percent", "level2_percent", "level3_percent"]:
                val = value.get(level_key)
                if val is not None:
                    parsed[level_key] = Decimal(str(val))
                else:
                    parsed[level_key] = None
            
            # Копируем фиксированные суммы
            for level_key in ["level1_fixed_amount", "level2_fixed_amount", "level3_fixed_amount"]:
                parsed[level_key] = value.get(level_key)
            
            return PartnerIndividualSettingsDto(**parsed)
        
        return PartnerIndividualSettingsDto()
    
    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)
    
    # Связь с пользователем
    user: Optional["BaseUserDto"] = None
    
    @property
    def balance_rub(self) -> Decimal:
        """Баланс в рублях."""
        return Decimal(self.balance) / 100
    
    @property
    def total_earned_rub(self) -> Decimal:
        """Всего заработано в рублях."""
        return Decimal(self.total_earned) / 100
    
    @property
    def total_withdrawn_rub(self) -> Decimal:
        """Всего выведено в рублях."""
        return Decimal(self.total_withdrawn) / 100
    
    @property
    def total_referrals(self) -> int:
        """Общее количество рефералов на всех уровнях."""
        return self.referrals_count + self.level2_referrals_count + self.level3_referrals_count


class PartnerTransactionDto(TrackableDto):
    """DTO транзакции партнера."""
    id: Optional[int] = Field(default=None, frozen=True)
    partner_id: int
    referral_telegram_id: int
    
    level: PartnerLevel
    payment_amount: int  # в копейках
    percent: Decimal
    earned_amount: int  # в копейках
    
    source_transaction_id: Optional[int] = None
    description: Optional[str] = None
    
    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)
    
    # Связи
    referral: Optional["BaseUserDto"] = None
    
    @property
    def payment_amount_rub(self) -> Decimal:
        """Сумма оплаты в рублях."""
        return Decimal(self.payment_amount) / 100
    
    @property
    def earned_amount_rub(self) -> Decimal:
        """Заработано в рублях."""
        return Decimal(self.earned_amount) / 100


class PartnerWithdrawalDto(TrackableDto):
    """DTO вывода средств партнера."""
    id: Optional[int] = Field(default=None, frozen=True)
    partner_id: int
    
    amount: int  # в копейках
    status: str = "pending"
    method: str
    requisites: str
    
    admin_comment: Optional[str] = None
    processed_by: Optional[int] = None
    
    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)
    
    @property
    def amount_rub(self) -> Decimal:
        """Сумма вывода в рублях."""
        return Decimal(self.amount) / 100
    
    @property
    def is_pending(self) -> bool:
        return self.status == "pending"
    
    @property
    def is_completed(self) -> bool:
        return self.status == "completed"
    
    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"


class PartnerReferralDto(TrackableDto):
    """DTO связи партнер -> реферал."""
    id: Optional[int] = Field(default=None, frozen=True)
    partner_id: int
    referral_telegram_id: int
    level: PartnerLevel
    parent_partner_id: Optional[int] = None
    
    created_at: Optional[datetime] = Field(default=None, frozen=True)
    updated_at: Optional[datetime] = Field(default=None, frozen=True)
    
    # Связи
    referral: Optional["BaseUserDto"] = None