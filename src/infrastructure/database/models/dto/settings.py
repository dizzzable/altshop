from typing import Optional

from pydantic import Field, SecretStr

from src.core.constants import T_ME
from src.core.enums import (
    AccessMode,
    Currency,
    PointsExchangeType,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
    SystemNotificationType,
    UserNotificationType,
)

from .base import BaseDto, TrackableDto


class SystemNotificationDto(TrackableDto):  # == SystemNotificationType
    bot_lifetime: bool = True
    bot_update: bool = True
    user_registered: bool = True
    subscription: bool = True
    promocode_activated: bool = True
    trial_getted: bool = True
    node_status: bool = True
    user_first_connected: bool = True
    user_hwid: bool = True
    # TODO: Add torrent_block
    # TODO: Add traffic_overuse

    def is_enabled(self, ntf_type: SystemNotificationType) -> bool:
        return getattr(self, ntf_type.value.lower(), False)


class UserNotificationDto(TrackableDto):  # == UserNotificationType
    expires_in_3_days: bool = True
    expires_in_2_days: bool = True
    expires_in_1_days: bool = True
    expired: bool = True
    limited: bool = True
    expired_1_day_ago: bool = True
    referral_attached: bool = True
    referral_reward: bool = True

    def is_enabled(self, ntf_type: UserNotificationType) -> bool:
        return getattr(self, ntf_type.value.lower(), False)


class ExchangeTypeSettingsDto(BaseDto):
    """Настройки для конкретного типа обмена баллов."""
    enabled: bool = True  # Включен ли этот тип обмена
    points_cost: int = 1  # Стоимость в баллах за единицу (день/ГБ/%)
    min_points: int = 1  # Минимальное количество баллов для обмена
    max_points: int = -1  # Максимальное количество баллов за раз (-1 = без лимита)
    
    # Для подарочной подписки - ID плана и длительность
    gift_plan_id: Optional[int] = None
    gift_duration_days: int = 30
    
    # Для скидки - максимальный процент скидки
    max_discount_percent: int = 50
    
    # Для трафика - максимальное количество ГБ
    max_traffic_gb: int = 100


class PointsExchangeSettingsDto(BaseDto):
    """Настройки обмена баллов."""
    exchange_enabled: bool = True  # Глобальный переключатель обмена баллов
    
    # Настройки для каждого типа обмена
    subscription_days: ExchangeTypeSettingsDto = Field(
        default_factory=lambda: ExchangeTypeSettingsDto(
            enabled=True,
            points_cost=1,  # 1 балл = 1 день
            min_points=1,
            max_points=-1,
        )
    )
    gift_subscription: ExchangeTypeSettingsDto = Field(
        default_factory=lambda: ExchangeTypeSettingsDto(
            enabled=False,
            points_cost=30,  # 30 баллов = подарочная подписка
            min_points=30,
            max_points=30,
            gift_duration_days=30,
        )
    )
    discount: ExchangeTypeSettingsDto = Field(
        default_factory=lambda: ExchangeTypeSettingsDto(
            enabled=False,
            points_cost=10,  # 10 баллов = 1% скидки
            min_points=10,
            max_points=500,  # Максимум 50% скидки
            max_discount_percent=50,
        )
    )
    traffic: ExchangeTypeSettingsDto = Field(
        default_factory=lambda: ExchangeTypeSettingsDto(
            enabled=False,
            points_cost=5,  # 5 баллов = 1 ГБ
            min_points=5,
            max_points=-1,
            max_traffic_gb=100,
        )
    )
    
    # Устаревшие поля для обратной совместимости
    points_per_day: int = 1
    min_exchange_points: int = 1
    max_exchange_points: int = -1

    def get_enabled_types(self) -> list[PointsExchangeType]:
        """Возвращает список включенных типов обмена."""
        enabled = []
        if self.subscription_days.enabled:
            enabled.append(PointsExchangeType.SUBSCRIPTION_DAYS)
        if self.gift_subscription.enabled:
            enabled.append(PointsExchangeType.GIFT_SUBSCRIPTION)
        if self.discount.enabled:
            enabled.append(PointsExchangeType.DISCOUNT)
        if self.traffic.enabled:
            enabled.append(PointsExchangeType.TRAFFIC)
        return enabled

    def get_settings_for_type(self, exchange_type: PointsExchangeType) -> ExchangeTypeSettingsDto:
        """Возвращает настройки для конкретного типа обмена."""
        mapping = {
            PointsExchangeType.SUBSCRIPTION_DAYS: self.subscription_days,
            PointsExchangeType.GIFT_SUBSCRIPTION: self.gift_subscription,
            PointsExchangeType.DISCOUNT: self.discount,
            PointsExchangeType.TRAFFIC: self.traffic,
        }
        return mapping[exchange_type]

    def is_type_enabled(self, exchange_type: PointsExchangeType) -> bool:
        """Проверяет, включен ли конкретный тип обмена."""
        return self.exchange_enabled and self.get_settings_for_type(exchange_type).enabled

    def calculate_days(self, points: int) -> int:
        """Рассчитывает количество дней за указанное количество баллов."""
        cost = self.subscription_days.points_cost or self.points_per_day
        if cost <= 0:
            return 0
        return points // cost

    def calculate_points_needed(self, days: int) -> int:
        """Рассчитывает количество баллов, необходимых для указанного количества дней."""
        cost = self.subscription_days.points_cost or self.points_per_day
        return days * cost
    
    def calculate_discount(self, points: int) -> int:
        """Рассчитывает процент скидки за указанное количество баллов."""
        if self.discount.points_cost <= 0:
            return 0
        discount = points // self.discount.points_cost
        return min(discount, self.discount.max_discount_percent)
    
    def calculate_traffic_gb(self, points: int) -> int:
        """Рассчитывает количество ГБ трафика за указанное количество баллов."""
        if self.traffic.points_cost <= 0:
            return 0
        traffic = points // self.traffic.points_cost
        return min(traffic, self.traffic.max_traffic_gb)


class ReferralRewardSettingsDto(BaseDto):
    type: ReferralRewardType = ReferralRewardType.EXTRA_DAYS
    strategy: ReferralRewardStrategy = ReferralRewardStrategy.AMOUNT
    config: dict[ReferralLevel, int] = {ReferralLevel.FIRST: 5}

    @property
    def is_identical(self) -> bool:
        values = list(self.config.values())
        return len(values) <= 1 or all(v == values[0] for v in values)

    @property
    def is_points(self) -> bool:
        return self.type == ReferralRewardType.POINTS

    @property
    def is_extra_days(self) -> bool:
        return self.type == ReferralRewardType.EXTRA_DAYS


class ReferralSettingsDto(TrackableDto):
    enable: bool = True
    level: ReferralLevel = ReferralLevel.FIRST
    accrual_strategy: ReferralAccrualStrategy = ReferralAccrualStrategy.ON_FIRST_PAYMENT
    reward: ReferralRewardSettingsDto = ReferralRewardSettingsDto()
    eligible_plan_ids: list[int] = []  # Пустой список = все планы
    points_exchange: PointsExchangeSettingsDto = PointsExchangeSettingsDto()  # Настройки обмена баллов

    @property
    def has_plan_filter(self) -> bool:
        """Проверяет, установлен ли фильтр по планам."""
        return len(self.eligible_plan_ids) > 0

    def is_plan_eligible(self, plan_id: int) -> bool:
        """Проверяет, подходит ли план для начисления реферальных наград."""
        if not self.has_plan_filter:
            return True
        return plan_id in self.eligible_plan_ids


class SettingsDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    rules_required: bool = False
    channel_required: bool = False

    rules_link: SecretStr = SecretStr("https://telegram.org/tos/")
    channel_id: Optional[int] = False
    channel_link: SecretStr = SecretStr("@remna_shop")

    access_mode: AccessMode = AccessMode.PUBLIC
    default_currency: Currency = Currency.XTR

    user_notifications: UserNotificationDto = UserNotificationDto()
    system_notifications: SystemNotificationDto = SystemNotificationDto()

    referral: ReferralSettingsDto = ReferralSettingsDto()

    @property
    def channel_has_username(self) -> bool:
        return self.channel_link.get_secret_value().startswith("@")

    @property
    def get_url_channel_link(self) -> str:
        if self.channel_has_username:
            return f"{T_ME}{self.channel_link.get_secret_value()[1:]}"
        else:
            return self.channel_link.get_secret_value()
