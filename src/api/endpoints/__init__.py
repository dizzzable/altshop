from fastapi import APIRouter

from .analytics import router as analytics_router
from .payments import router as payments_router
from .remnawave import router as remnawave_router
from .telegram import TelegramWebhookEndpoint
from .user_account import router as user_account_router
from .user_portal import router as user_portal_router
from .user_subscription import router as user_subscription_router
from .web_auth import router as web_auth_router

user_router = APIRouter()
user_router.include_router(user_account_router)
user_router.include_router(user_subscription_router)
user_router.include_router(user_portal_router)

__all__ = [
    "analytics_router",
    "payments_router",
    "remnawave_router",
    "TelegramWebhookEndpoint",
    "user_router",
    "web_auth_router",
]
