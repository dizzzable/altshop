from typing import Optional

from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    MAIN = State()
    DEVICES = State()
    CONNECT_DEVICE = State()  # Выбор устройства для подключения
    CONNECT_DEVICE_URL = State()  # Показ URL выбранного устройства
    INVITE = State()
    INVITE_ABOUT = State()
    EXCHANGE = State()  # Экран обмена - показывает баллы и доступные типы обмена
    EXCHANGE_SELECT_TYPE = State()  # Выбор типа обмена
    EXCHANGE_POINTS = State()  # Выбор подписки для обмена баллов на дни
    EXCHANGE_POINTS_CONFIRM = State()  # Подтверждение обмена баллов на дни
    EXCHANGE_GIFT = State()  # Обмен на подарочную подписку
    EXCHANGE_GIFT_SELECT_PLAN = State()  # Выбор плана для подарочной подписки
    EXCHANGE_GIFT_CONFIRM = State()  # Подтверждение обмена на подарочную подписку
    EXCHANGE_GIFT_SUCCESS = State()  # Успешный обмен - показ промокода
    EXCHANGE_DISCOUNT = State()  # Обмен на скидку
    EXCHANGE_DISCOUNT_CONFIRM = State()  # Подтверждение обмена на скидку
    EXCHANGE_TRAFFIC = State()  # Обмен на трафик - выбор подписки
    EXCHANGE_TRAFFIC_CONFIRM = State()  # Подтверждение обмена на трафик


class Notification(StatesGroup):
    CLOSE = State()


class Subscription(StatesGroup):
    MAIN = State()
    MY_SUBSCRIPTIONS = State()
    SUBSCRIPTION_DETAILS = State()
    CONFIRM_DELETE = State()
    PROMOCODE = State()
    PROMOCODE_SELECT_SUBSCRIPTION = State()  # Выбор подписки для добавления дней от промокода
    PROMOCODE_CONFIRM_NEW = State()  # Подтверждение создания новой подписки от промокода
    SELECT_SUBSCRIPTION_FOR_RENEW = State()  # Выбор подписки для продления (множественный выбор)
    CONFIRM_RENEW_SELECTION = State()  # Подтверждение выбранных подписок для продления
    PLANS = State()
    DURATION = State()
    DEVICE_TYPE = State()
    PAYMENT_METHOD = State()
    CONFIRM = State()
    SUCCESS = State()
    FAILED = State()
    TRIAL = State()


class Dashboard(StatesGroup):
    MAIN = State()


class DashboardStatistics(StatesGroup):
    MAIN = State()


class DashboardBroadcast(StatesGroup):
    MAIN = State()
    LIST = State()
    VIEW = State()
    PLAN = State()
    SEND = State()
    CONTENT = State()
    BUTTONS = State()


class DashboardPromocodes(StatesGroup):
    MAIN = State()
    LIST = State()
    CONFIGURATOR = State()
    CODE = State()
    TYPE = State()
    AVAILABILITY = State()
    REWARD = State()
    LIFETIME = State()
    ALLOWED = State()
    PLAN = State()  # Выбор плана для промокода типа "Подписка"
    DURATION = State()  # Выбор длительности плана для промокода


class DashboardAccess(StatesGroup):
    MAIN = State()
    CONDITIONS = State()
    RULES = State()
    CHANNEL = State()


class DashboardUsers(StatesGroup):
    MAIN = State()
    SEARCH = State()
    SEARCH_RESULTS = State()
    RECENT_REGISTERED = State()
    RECENT_ACTIVITY = State()
    BLACKLIST = State()


class DashboardUser(StatesGroup):
    MAIN = State()
    SUBSCRIPTION = State()
    TRAFFIC_LIMIT = State()
    DEVICE_LIMIT = State()
    EXPIRE_TIME = State()
    SQUADS = State()
    INTERNAL_SQUADS = State()
    EXTERNAL_SQUADS = State()
    DEVICES_LIST = State()
    DISCOUNT = State()
    POINTS = State()
    STATISTICS = State()
    ROLE = State()
    TRANSACTIONS_LIST = State()
    TRANSACTION = State()
    GIVE_ACCESS = State()
    MESSAGE = State()
    GIVE_SUBSCRIPTION = State()
    SUBSCRIPTION_DURATION = State()


class DashboardRemnashop(StatesGroup):
    MAIN = State()
    ADMINS = State()
    ADVERTISING = State()


class RemnashopBanners(StatesGroup):
    MAIN = State()
    SELECT_BANNER = State()
    UPLOAD_BANNER = State()
    CONFIRM_DELETE = State()


class RemnashopReferral(StatesGroup):
    MAIN = State()
    LEVEL = State()
    REWARD = State()
    REWARD_TYPE = State()
    ACCRUAL_STRATEGY = State()
    REWARD_STRATEGY = State()
    ELIGIBLE_PLANS = State()
    # Настройки обмена баллов
    POINTS_EXCHANGE = State()
    POINTS_PER_DAY = State()
    MIN_EXCHANGE_POINTS = State()
    MAX_EXCHANGE_POINTS = State()
    # Настройки типов обмена
    EXCHANGE_TYPES = State()  # Список типов обмена с переключателями
    EXCHANGE_TYPE_SETTINGS = State()  # Настройки конкретного типа обмена
    EXCHANGE_TYPE_COST = State()  # Стоимость в баллах
    EXCHANGE_TYPE_MIN = State()  # Минимум баллов
    EXCHANGE_TYPE_MAX = State()  # Максимум баллов
    EXCHANGE_GIFT_PLAN = State()  # Выбор плана для подарочной подписки
    EXCHANGE_GIFT_DURATION = State()  # Длительность подарочной подписки
    EXCHANGE_DISCOUNT_MAX = State()  # Максимальный процент скидки
    EXCHANGE_TRAFFIC_MAX = State()  # Максимум ГБ трафика


class RemnashopGateways(StatesGroup):
    MAIN = State()
    SETTINGS = State()
    FIELD = State()
    CURRENCY = State()
    PLACEMENT = State()


class RemnashopNotifications(StatesGroup):
    MAIN = State()
    USER = State()
    SYSTEM = State()


class RemnashopPlans(StatesGroup):
    MAIN = State()
    CONFIGURATOR = State()
    NAME = State()
    DESCRIPTION = State()
    TAG = State()
    TYPE = State()
    AVAILABILITY = State()
    TRAFFIC = State()
    DEVICES = State()
    SUBSCRIPTION_COUNT = State()
    DURATIONS = State()
    DURATION_ADD = State()
    PRICES = State()
    PRICE = State()
    ALLOWED = State()
    SQUADS = State()
    INTERNAL_SQUADS = State()
    EXTERNAL_SQUADS = State()


class DashboardRemnawave(StatesGroup):
    MAIN = State()
    USERS = State()
    HOSTS = State()
    NODES = State()
    INBOUNDS = State()


class DashboardImporter(StatesGroup):
    MAIN = State()
    FROM_XUI = State()
    SYNC = State()
    SQUADS = State()
    IMPORT_COMPLETED = State()
    SYNC_COMPLETED = State()


def state_from_string(state_str: str, sep: Optional[str] = ":") -> Optional[State]:
    try:
        group_name, state_name = state_str.split(":")[:2]
        group_cls = globals().get(group_name)
        if group_cls is None:
            return None
        state_obj = getattr(group_cls, state_name, None)
        if not isinstance(state_obj, State):
            return None
        return state_obj
    except (ValueError, AttributeError):
        return None
