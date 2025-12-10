from decimal import Decimal
from typing import Optional

from pydantic import Field, SecretStr

from src.core.constants import T_ME
from src.core.enums import (
    AccessMode,
    Currency,
    PartnerLevel,
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


class PartnerSettingsDto(TrackableDto):
    """Настройки партнерской программы."""
    enabled: bool = False  # Включена ли партнерская программа
    
    # Проценты для каждого уровня
    level1_percent: Decimal = Decimal("10.0")  # 10% с прямых рефералов
    level2_percent: Decimal = Decimal("3.0")   # 3% с рефералов 2 уровня
    level3_percent: Decimal = Decimal("1.0")   # 1% с рефералов 3 уровня
    
    # Настройки комиссий и налогов
    tax_percent: Decimal = Decimal("6.0")  # НДС или налог (для самозанятых 6%)
    
    # Комиссии платежных систем (для информирования)
    yookassa_commission: Decimal = Decimal("3.5")  # Комиссия YooKassa
    telegram_stars_commission: Decimal = Decimal("30.0")  # Комиссия Telegram Stars
    cryptopay_commission: Decimal = Decimal("1.0")  # Комиссия CryptoPay
    heleket_commission: Decimal = Decimal("1.0")  # Комиссия Heleket
    pal24_commission: Decimal = Decimal("5.0")  # Комиссия Pal24
    wata_commission: Decimal = Decimal("3.0")  # Комиссия WATA
    platega_commission: Decimal = Decimal("3.5")  # Комиссия Platega
    
    # Минимальная сумма для вывода (в копейках)
    min_withdrawal_amount: int = 50000  # 500 рублей
    
    # Автоматический расчет или ручной
    auto_calculate_commission: bool = True
    
    @property
    def is_enabled(self) -> bool:
        """Алиас для enabled (для совместимости)."""
        return self.enabled
    
    @property
    def min_withdrawal(self) -> Decimal:
        """Минимальная сумма для вывода в рублях (конвертация из копеек)."""
        return Decimal(self.min_withdrawal_amount) / 100
    
    def get_level_percent(self, level: PartnerLevel) -> Decimal:
        """Получить процент для уровня."""
        match level:
            case PartnerLevel.LEVEL_1:
                return self.level1_percent
            case PartnerLevel.LEVEL_2:
                return self.level2_percent
            case PartnerLevel.LEVEL_3:
                return self.level3_percent
        return Decimal("0")
    
    def calculate_partner_earning(
        self,
        payment_amount: int,
        level: PartnerLevel,
        gateway_commission: Decimal = Decimal("0"),
    ) -> int:
        """
        Рассчитать заработок партнера с учетом комиссий.
        
        Args:
            payment_amount: Сумма оплаты в копейках
            level: Уровень партнера
            gateway_commission: Комиссия платежной системы в процентах
            
        Returns:
            Заработок партнера в копейках
        """
        percent = self.get_level_percent(level)
        
        if self.auto_calculate_commission:
            # Вычитаем комиссию платежной системы из суммы
            net_amount = Decimal(payment_amount) * (100 - gateway_commission) / 100
            # Вычитаем налог
            net_amount = net_amount * (100 - self.tax_percent) / 100
        else:
            net_amount = Decimal(payment_amount)
        
        # Считаем процент партнера
        earning = int(net_amount * percent / 100)
        return max(0, earning)
    
    def get_gateway_commission(self, gateway_type: str) -> Decimal:
        """Получить комиссию платежной системы."""
        commissions = {
            "YOOKASSA": self.yookassa_commission,
            "TELEGRAM_STARS": self.telegram_stars_commission,
            "CRYPTOPAY": self.cryptopay_commission,
            "HELEKET": self.heleket_commission,
            "PAL24": self.pal24_commission,
            "WATA": self.wata_commission,
            "PLATEGA": self.platega_commission,
        }
        return commissions.get(gateway_type, Decimal("0"))
    
    def calculate_net_earning_info(
        self,
        payment_amount: int,
        gateway_type: str,
    ) -> dict:
        """
        Рассчитать подробную информацию о чистом заработке.
        Полезно для отображения в админке.
        """
        gateway_commission = self.get_gateway_commission(gateway_type)
        amount_decimal = Decimal(payment_amount)
        
        gateway_fee = amount_decimal * gateway_commission / 100
        after_gateway = amount_decimal - gateway_fee
        
        tax_fee = after_gateway * self.tax_percent / 100
        net_amount = after_gateway - tax_fee
        
        level1_earning = int(net_amount * self.level1_percent / 100)
        level2_earning = int(net_amount * self.level2_percent / 100)
        level3_earning = int(net_amount * self.level3_percent / 100)
        total_partner_expense = level1_earning + level2_earning + level3_earning
        
        return {
            "payment_amount": payment_amount,
            "gateway_commission_percent": gateway_commission,
            "gateway_fee": int(gateway_fee),
            "tax_percent": self.tax_percent,
            "tax_fee": int(tax_fee),
            "net_amount": int(net_amount),
            "level1_percent": self.level1_percent,
            "level1_earning": level1_earning,
            "level2_percent": self.level2_percent,
            "level2_earning": level2_earning,
            "level3_percent": self.level3_percent,
            "level3_earning": level3_earning,
            "total_partner_expense": total_partner_expense,
            "owner_profit": int(net_amount) - total_partner_expense,
        }


class MultiSubscriptionSettingsDto(TrackableDto):
    """Настройки мультиподписок."""
    enabled: bool = True  # Глобально разрешены ли мультиподписки
    default_max_subscriptions: int = 5  # Максимум подписок по умолчанию (1 = только одна)
    
    @property
    def is_single_subscription_mode(self) -> bool:
        """Режим одной подписки (мультиподписки отключены и лимит = 1)."""
        return not self.enabled or self.default_max_subscriptions == 1


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
    partner: PartnerSettingsDto = PartnerSettingsDto()
    multi_subscription: MultiSubscriptionSettingsDto = MultiSubscriptionSettingsDto()

    @property
    def channel_has_username(self) -> bool:
        return self.channel_link.get_secret_value().startswith("@")

    @property
    def get_url_channel_link(self) -> str:
        if self.channel_has_username:
            return f"{T_ME}{self.channel_link.get_secret_value()[1:]}"
        else:
            return self.channel_link.get_secret_value()
