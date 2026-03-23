from dishka import Provider, Scope, provide

from src.services.access import AccessService
from src.services.access_policy import AccessModePolicyService
from src.services.auth_challenge import AuthChallengeService
from src.services.backup import BackupService
from src.services.broadcast import BroadcastService
from src.services.command import CommandService
from src.services.email_recovery import EmailRecoveryService
from src.services.email_sender import EmailSenderService
from src.services.importer import ImporterService
from src.services.market_quote import MarketQuoteService
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.partner_portal import PartnerPortalService
from src.services.payment_gateway import PaymentGatewayService
from src.services.payment_webhook_event import PaymentWebhookEventService
from src.services.plan import PlanService
from src.services.plan_catalog import PlanCatalogService
from src.services.pricing import PricingService
from src.services.promocode import PromocodeService
from src.services.promocode_portal import PromocodePortalService
from src.services.purchase_access import PurchaseAccessService
from src.services.referral import ReferralService
from src.services.referral_exchange import ReferralExchangeService
from src.services.referral_portal import ReferralPortalService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_device import SubscriptionDeviceService
from src.services.subscription_portal import SubscriptionPortalService
from src.services.subscription_purchase import SubscriptionPurchaseService
from src.services.subscription_purchase_policy import SubscriptionPurchasePolicyService
from src.services.subscription_runtime import SubscriptionRuntimeService
from src.services.subscription_trial import SubscriptionTrialService
from src.services.telegram_link import TelegramLinkService
from src.services.transaction import TransactionService
from src.services.user import UserService
from src.services.user_activity_portal import UserActivityPortalService
from src.services.user_notification_event import UserNotificationEventService
from src.services.user_profile import UserProfileService
from src.services.web_access_guard import WebAccessGuardService
from src.services.web_account import WebAccountService
from src.services.web_analytics_event import WebAnalyticsEventService
from src.services.webhook import WebhookService


class ServicesProvider(Provider):
    scope = Scope.APP

    command_service = provide(source=CommandService)
    access_mode_policy_service = provide(source=AccessModePolicyService)
    access_service = provide(source=AccessService, scope=Scope.REQUEST)
    backup_service = provide(source=BackupService)
    notification_service = provide(source=NotificationService, scope=Scope.REQUEST)
    gateway_service = provide(source=PaymentGatewayService, scope=Scope.REQUEST)
    payment_webhook_event_service = provide(source=PaymentWebhookEventService, scope=Scope.REQUEST)
    partner_service = provide(source=PartnerService, scope=Scope.REQUEST)
    partner_portal_service = provide(source=PartnerPortalService, scope=Scope.REQUEST)
    plan_service = provide(source=PlanService, scope=Scope.REQUEST)
    plan_catalog_service = provide(source=PlanCatalogService, scope=Scope.REQUEST)
    promocode_service = provide(source=PromocodeService, scope=Scope.REQUEST)
    promocode_portal_service = provide(source=PromocodePortalService, scope=Scope.REQUEST)
    purchase_access_service = provide(source=PurchaseAccessService, scope=Scope.REQUEST)
    remnawave_service = provide(source=RemnawaveService, scope=Scope.REQUEST)
    subscription_service = provide(source=SubscriptionService, scope=Scope.REQUEST)
    subscription_device_service = provide(source=SubscriptionDeviceService, scope=Scope.REQUEST)
    subscription_portal_service = provide(source=SubscriptionPortalService, scope=Scope.REQUEST)
    subscription_purchase_service = provide(source=SubscriptionPurchaseService, scope=Scope.REQUEST)
    subscription_purchase_policy_service = provide(
        source=SubscriptionPurchasePolicyService, scope=Scope.REQUEST
    )
    subscription_runtime_service = provide(source=SubscriptionRuntimeService, scope=Scope.REQUEST)
    subscription_trial_service = provide(source=SubscriptionTrialService, scope=Scope.REQUEST)
    transaction_service = provide(source=TransactionService, scope=Scope.REQUEST)
    user_service = provide(source=UserService, scope=Scope.REQUEST)
    user_activity_portal_service = provide(source=UserActivityPortalService, scope=Scope.REQUEST)
    user_profile_service = provide(source=UserProfileService, scope=Scope.REQUEST)
    web_account_service = provide(source=WebAccountService, scope=Scope.REQUEST)
    web_access_guard_service = provide(source=WebAccessGuardService, scope=Scope.REQUEST)
    auth_challenge_service = provide(source=AuthChallengeService, scope=Scope.REQUEST)
    telegram_link_service = provide(source=TelegramLinkService, scope=Scope.REQUEST)
    email_sender_service = provide(source=EmailSenderService)
    email_recovery_service = provide(source=EmailRecoveryService, scope=Scope.REQUEST)
    webhook_service = provide(source=WebhookService)
    settings_service = provide(source=SettingsService, scope=Scope.REQUEST)
    broadcast_service = provide(source=BroadcastService, scope=Scope.REQUEST)
    pricing_service = provide(source=PricingService)
    importer_service = provide(source=ImporterService)
    market_quote_service = provide(source=MarketQuoteService, scope=Scope.REQUEST)
    referral_service = provide(source=ReferralService, scope=Scope.REQUEST)
    referral_exchange_service = provide(source=ReferralExchangeService, scope=Scope.REQUEST)
    referral_portal_service = provide(source=ReferralPortalService, scope=Scope.REQUEST)
    user_notification_event_service = provide(
        source=UserNotificationEventService, scope=Scope.REQUEST
    )
    web_analytics_event_service = provide(source=WebAnalyticsEventService, scope=Scope.REQUEST)
