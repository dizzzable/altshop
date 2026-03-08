from sqlalchemy.ext.asyncio import AsyncSession

from .broadcast import BroadcastRepository
from .partner import PartnerRepository
from .payment_gateway import PaymentGatewayRepository
from .payment_webhook_event import PaymentWebhookEventRepository
from .plan import PlanRepository
from .promocode import PromocodeRepository
from .referral import ReferralRepository
from .settings import SettingsRepository
from .subscription import SubscriptionRepository
from .transaction import TransactionRepository
from .user import UserRepository
from .user_notification_event import UserNotificationEventRepository
from .web_account import AuthChallengeRepository, WebAccountRepository
from .web_analytics_event import WebAnalyticsEventRepository


class RepositoriesFacade:
    session: AsyncSession

    gateways: PaymentGatewayRepository
    payment_webhook_events: PaymentWebhookEventRepository
    partners: PartnerRepository
    plans: PlanRepository
    promocodes: PromocodeRepository
    subscriptions: SubscriptionRepository
    transactions: TransactionRepository
    users: UserRepository
    settings: SettingsRepository
    broadcasts: BroadcastRepository
    referrals: ReferralRepository
    user_notification_events: UserNotificationEventRepository
    web_analytics_events: WebAnalyticsEventRepository
    web_accounts: WebAccountRepository
    auth_challenges: AuthChallengeRepository

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self.gateways = PaymentGatewayRepository(session)
        self.payment_webhook_events = PaymentWebhookEventRepository(session)
        self.partners = PartnerRepository(session)
        self.plans = PlanRepository(session)
        self.promocodes = PromocodeRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.transactions = TransactionRepository(session)
        self.users = UserRepository(session)
        self.settings = SettingsRepository(session)
        self.broadcasts = BroadcastRepository(session)
        self.referrals = ReferralRepository(session)
        self.user_notification_events = UserNotificationEventRepository(session)
        self.web_analytics_events = WebAnalyticsEventRepository(session)
        self.web_accounts = WebAccountRepository(session)
        self.auth_challenges = AuthChallengeRepository(session)
