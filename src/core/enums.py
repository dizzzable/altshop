from enum import Enum, IntEnum, StrEnum, auto
from typing import Any, Callable, Union

from aiogram import Bot
from aiogram.types import BotCommand, ContentType


class UpperStrEnum(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name


class ReferralRewardType(UpperStrEnum):
    POINTS = auto()
    EXTRA_DAYS = auto()


class ReferralLevel(IntEnum):
    FIRST = auto()
    SECOND = auto()
    THIRD = auto()


class PartnerLevel(IntEnum):
    """Уровни партнерской программы (3 уровня)."""
    LEVEL_1 = 1  # Прямой реферал
    LEVEL_2 = 2  # Реферал реферала
    LEVEL_3 = 3  # Реферал реферала реферала


class PartnerAccrualStrategy(UpperStrEnum):
    """Стратегия начисления партнерских вознаграждений."""
    ON_FIRST_PAYMENT = auto()  # Только при первой оплате реферала
    ON_EACH_PAYMENT = auto()   # С каждой оплаты реферала


class PartnerRewardType(UpperStrEnum):
    """Тип вознаграждения партнера."""
    PERCENT = auto()       # Процент с оплаты (по умолчанию)
    FIXED_AMOUNT = auto()  # Фиксированная сумма


class WithdrawalStatus(UpperStrEnum):
    """Статусы запросов на вывод средств партнера."""
    PENDING = auto()    # Ожидает обработки
    COMPLETED = auto()  # Завершён
    REJECTED = auto()   # Отклонён
    CANCELED = auto()   # Отменён


class ReferralAccrualStrategy(UpperStrEnum):
    ON_FIRST_PAYMENT = auto()
    ON_EACH_PAYMENT = auto()


class ReferralRewardStrategy(UpperStrEnum):
    AMOUNT = auto()
    PERCENT = auto()


class PointsExchangeType(UpperStrEnum):
    """Типы обмена баллов."""
    SUBSCRIPTION_DAYS = auto()  # Дни подписки
    GIFT_SUBSCRIPTION = auto()  # Подарочная подписка (промокод)
    DISCOUNT = auto()  # Скидка на следующую покупку
    TRAFFIC = auto()  # Дополнительный трафик


class BroadcastStatus(UpperStrEnum):
    PROCESSING = auto()
    COMPLETED = auto()
    CANCELED = auto()
    DELETED = auto()
    ERROR = auto()


class BroadcastMessageStatus(UpperStrEnum):
    SENT = auto()
    FAILED = auto()
    EDITED = auto()
    DELETED = auto()
    PENDING = auto()


class BroadcastAudience(UpperStrEnum):
    ALL = auto()
    PLAN = auto()
    SUBSCRIBED = auto()
    UNSUBSCRIBED = auto()
    EXPIRED = auto()
    TRIAL = auto()


class PurchaseType(UpperStrEnum):
    NEW = auto()
    RENEW = auto()
    ADDITIONAL = auto()


class TransactionStatus(UpperStrEnum):
    PENDING = auto()
    COMPLETED = auto()
    CANCELED = auto()
    REFUNDED = auto()
    FAILED = auto()


class SubscriptionStatus(UpperStrEnum):
    ACTIVE = auto()
    DISABLED = auto()
    LIMITED = auto()
    EXPIRED = auto()
    DELETED = auto()


class MessageEffect(UpperStrEnum):
    FIRE = "5104841245755180586"  #     🔥
    LIKE = "5107584321108051014"  #     👍
    DISLIKE = "5104858069142078462"  #  👎
    LOVE = "5159385139981059251"  #     ❤️
    CONFETTI = "5046509860389126442"  # 🎉
    POOP = "5046589136895476101"  #     💩


class BannerName(StrEnum):
    DEFAULT = auto()
    MENU = auto()
    DASHBOARD = auto()
    SUBSCRIPTION = auto()
    PROMOCODE = auto()
    REFERRAL = auto()


class BannerFormat(StrEnum):
    JPG = auto()
    JPEG = auto()
    PNG = auto()
    GIF = auto()
    WEBP = auto()

    @property
    def content_type(self) -> ContentType:
        match self:
            case BannerFormat.JPG | BannerFormat.JPEG | BannerFormat.PNG | BannerFormat.WEBP:
                return ContentType.PHOTO
            case BannerFormat.GIF:
                return ContentType.ANIMATION


class MediaType(UpperStrEnum):
    PHOTO = auto()
    VIDEO = auto()
    DOCUMENT = auto()

    def get_function(self, bot_instance: Bot) -> Callable[..., Any]:
        match self:
            case MediaType.PHOTO:
                return bot_instance.send_photo
            case MediaType.VIDEO:
                return bot_instance.send_video
            case MediaType.DOCUMENT:
                return bot_instance.send_document


class SystemNotificationType(UpperStrEnum):  # == SystemNotificationDto
    BOT_LIFETIME = auto()
    BOT_UPDATE = auto()
    #
    USER_REGISTERED = auto()
    SUBSCRIPTION = auto()
    PROMOCODE_ACTIVATED = auto()
    TRIAL_GETTED = auto()
    #
    NODE_STATUS = auto()
    USER_FIRST_CONNECTED = auto()
    USER_HWID = auto()


class UserNotificationType(UpperStrEnum):  # == UserNotificationDto
    EXPIRES_IN_3_DAYS = auto()
    EXPIRES_IN_2_DAYS = auto()
    EXPIRES_IN_1_DAYS = auto()
    EXPIRED = auto()
    LIMITED = auto()
    EXPIRED_1_DAY_AGO = auto()
    #
    REFERRAL_ATTACHED = auto()
    REFERRAL_REWARD = auto()


class UserRoleHierarchy(Enum):
    DEV = 3
    ADMIN = 2
    USER = 1


class UserRole(UpperStrEnum):
    DEV = auto()
    ADMIN = auto()
    USER = auto()

    def __le__(self, other: Union["UserRole", str]) -> bool:
        if isinstance(other, UserRole):
            other_name = other.name
        elif isinstance(other, str):
            other_name = other
        else:
            raise TypeError(f"Cannot compare UserRole with '{type(other)}'")
        return UserRoleHierarchy[self.name].value <= UserRoleHierarchy[other_name].value

    def __lt__(self, other: Union["UserRole", str]) -> bool:
        if isinstance(other, UserRole):
            other_name = other.name
        elif isinstance(other, str):
            other_name = other
        else:
            raise TypeError(f"Cannot compare UserRole with '{type(other)}'")
        return UserRoleHierarchy[self.name].value < UserRoleHierarchy[other_name].value


class PromocodeRewardType(UpperStrEnum):
    DURATION = auto()
    TRAFFIC = auto()
    DEVICES = auto()
    SUBSCRIPTION = auto()
    PERSONAL_DISCOUNT = auto()
    PURCHASE_DISCOUNT = auto()


class DeviceType(UpperStrEnum):
    ANDROID = auto()
    IPHONE = auto()
    WINDOWS = auto()
    MAC = auto()


class PlanType(UpperStrEnum):
    TRAFFIC = auto()
    DEVICES = auto()
    BOTH = auto()
    UNLIMITED = auto()


class PlanAvailability(UpperStrEnum):
    ALL = auto()
    NEW = auto()
    EXISTING = auto()
    INVITED = auto()
    ALLOWED = auto()
    TRIAL = auto()


class PromocodeAvailability(UpperStrEnum):
    ALL = auto()
    NEW = auto()
    EXISTING = auto()
    INVITED = auto()
    ALLOWED = auto()


class PaymentGatewayType(UpperStrEnum):
    TELEGRAM_STARS = auto()
    YOOKASSA = auto()
    YOOMONEY = auto()
    CRYPTOMUS = auto()
    HELEKET = auto()
    CRYPTOPAY = auto()
    ROBOKASSA = auto()
    PAL24 = auto()
    WATA = auto()
    PLATEGA = auto()


class Currency(UpperStrEnum):
    USD = auto()
    XTR = auto()
    RUB = auto()
    USDT = auto()
    TON = auto()
    BTC = auto()
    ETH = auto()
    LTC = auto()

    @property
    def symbol(self) -> str:
        symbols = {
            "USD": "$",
            "XTR": "★",
            "RUB": "₽",
            "USDT": "₮",
            "TON": "💎",
            "BTC": "₿",
            "ETH": "Ξ",
            "LTC": "Ł",
        }
        return symbols[self.value]

    @classmethod
    def from_code(cls, code: str) -> "Currency":
        return cls(code)

    @classmethod
    def from_gateway_type(cls, gateway_type: PaymentGatewayType) -> "Currency":
        mapping = {
            PaymentGatewayType.TELEGRAM_STARS: cls.XTR,
            PaymentGatewayType.YOOKASSA: cls.RUB,
            PaymentGatewayType.YOOMONEY: cls.RUB,
            PaymentGatewayType.ROBOKASSA: cls.RUB,
            PaymentGatewayType.CRYPTOMUS: cls.USD,
            PaymentGatewayType.HELEKET: cls.USD,
            PaymentGatewayType.CRYPTOPAY: cls.USDT,
            PaymentGatewayType.PAL24: cls.RUB,
            PaymentGatewayType.WATA: cls.RUB,
            PaymentGatewayType.PLATEGA: cls.RUB,
        }

        try:
            return mapping[gateway_type]
        except KeyError:
            raise ValueError(f"Unknown payment gateway type: '{gateway_type}'")


class AccessMode(UpperStrEnum):
    PUBLIC = auto()  # Access is allowed for everyone
    INVITED = auto()  # Invited users only
    PURCHASE_BLOCKED = auto()  # Purchases are forbidden
    REG_BLOCKED = auto()  # Registration is forbidden
    RESTRICTED = auto()  # All actions are completely forbidden


class Command(Enum):
    START = BotCommand(command="start", description="cmd-start")
    PAYSUPPORT = BotCommand(command="paysupport", description="cmd-paysupport")
    HELP = BotCommand(command="help", description="cmd-help")


class Locale(StrEnum):
    AR = auto()  # Arabic
    AZ = auto()  # Azerbaijani
    BE = auto()  # Belarusian
    CS = auto()  # Czech
    DE = auto()  # German
    EN = auto()  # English
    ES = auto()  # Spanish
    FA = auto()  # Persian
    FR = auto()  # French
    HE = auto()  # Hebrew
    HI = auto()  # Hindi
    ID = auto()  # Indonesian
    IT = auto()  # Italian
    JA = auto()  # Japanese
    KK = auto()  # Kazakh
    KO = auto()  # Korean
    MS = auto()  # Malay
    NL = auto()  # Dutch
    PL = auto()  # Polish
    PT = auto()  # Portuguese
    RO = auto()  # Romanian
    RU = auto()  # Russian
    SR = auto()  # Serbian
    TR = auto()  # Turkish
    UK = auto()  # Ukrainian
    UZ = auto()  # Uzbek
    VI = auto()  # Vietnamese


# https://docs.aiogram.dev/en/latest/api/types/update.html
class MiddlewareEventType(StrEnum):
    AIOGD_UPDATE = auto()  # AIOGRAM DIALOGS
    UPDATE = auto()
    MESSAGE = auto()
    EDITED_MESSAGE = auto()
    CHANNEL_POST = auto()
    EDITED_CHANNEL_POST = auto()
    BUSINESS_CONNECTION = auto()
    BUSINESS_MESSAGE = auto()
    EDITED_BUSINESS_MESSAGE = auto()
    DELETED_BUSINESS_MESSAGES = auto()
    MESSAGE_REACTION = auto()
    MESSAGE_REACTION_COUNT = auto()
    INLINE_QUERY = auto()
    CHOSEN_INLINE_RESULT = auto()
    CALLBACK_QUERY = auto()
    SHIPPING_QUERY = auto()
    PRE_CHECKOUT_QUERY = auto()
    PURCHASED_PAID_MEDIA = auto()
    POLL = auto()
    POLL_ANSWER = auto()
    MY_CHAT_MEMBER = auto()
    CHAT_MEMBER = auto()
    CHAT_JOIN_REQUEST = auto()
    CHAT_BOOST = auto()
    REMOVED_CHAT_BOOST = auto()
    ERROR = auto()


class RemnaUserEvent(StrEnum):
    CREATED = "user.created"
    MODIFIED = "user.modified"
    DELETED = "user.deleted"
    REVOKED = "user.revoked"
    DISABLED = "user.disabled"
    ENABLED = "user.enabled"
    LIMITED = "user.limited"
    EXPIRED = "user.expired"
    TRAFFIC_RESET = "user.traffic_reset"
    FIRST_CONNECTED = "user.first_connected"
    BANDWIDTH_USAGE_THRESHOLD_REACHED = "user.bandwidth_usage_threshold_reached"

    EXPIRES_IN_72_HOURS = "user.expires_in_72_hours"
    EXPIRES_IN_48_HOURS = "user.expires_in_48_hours"
    EXPIRES_IN_24_HOURS = "user.expires_in_24_hours"
    EXPIRED_24_HOURS_AGO = "user.expired_24_hours_ago"


class RemnaUserHwidDevicesEvent(StrEnum):
    ADDED = "user_hwid_devices.added"
    DELETED = "user_hwid_devices.deleted"


class RemnaNodeEvent(StrEnum):
    CREATED = "node.created"
    MODIFIED = "node.modified"
    DISABLED = "node.disabled"
    ENABLED = "node.enabled"
    DELETED = "node.deleted"
    CONNECTION_LOST = "node.connection_lost"
    CONNECTION_RESTORED = "node.connection_restored"
    TRAFFIC_NOTIFY = "node.traffic_notify"


# https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values#vat-codes
class YookassaVatCode(IntEnum):
    VAT_CODE_01 = auto()  # Without VAT
    VAT_CODE_02 = auto()  # VAT at 0% rate
    VAT_CODE_03 = auto()  # VAT at 10% rate
    VAT_CODE_04 = auto()  # VAT at 20% rate
    VAT_CODE_05 = auto()  # VAT at calculated rate 10/110
    VAT_CODE_06 = auto()  # VAT at calculated rate 20/120
    VAT_CODE_07 = auto()  # VAT at 5% rate
    VAT_CODE_08 = auto()  # VAT at 7% rate
    VAT_CODE_09 = auto()  # VAT at calculated rate 5/105
    VAT_CODE_10 = auto()  # VAT at calculated rate 7/107
