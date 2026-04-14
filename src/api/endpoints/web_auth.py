from __future__ import annotations

from fastapi import APIRouter

from .web_auth_recovery import router as recovery_router
from .web_auth_sessions import router as sessions_router
from .web_auth_support import (
    _enforce_rate_limit,
    _has_valid_cookie_session,
    _notify_web_account_linked,
    _notify_web_user_registered,
    _resolve_trusted_telegram_id_for_auto_link,
    _resolve_web_auth_message,
)
from .web_auth_telegram import router as telegram_router

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
router.include_router(sessions_router)
router.include_router(telegram_router)
router.include_router(recovery_router)

__all__ = [
    "router",
    "_enforce_rate_limit",
    "_has_valid_cookie_session",
    "_notify_web_account_linked",
    "_notify_web_user_registered",
    "_resolve_trusted_telegram_id_for_auto_link",
    "_resolve_web_auth_message",
]
