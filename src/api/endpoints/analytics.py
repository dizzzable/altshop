from __future__ import annotations

from typing import Any, Literal, Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field

from src.core.security.jwt_handler import verify_access_token
from src.services.web_analytics_event import WebAnalyticsEventService

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])
security = HTTPBearer(auto_error=False)

AnalyticsEventName = Literal[
    "miniapp_landing_view",
    "miniapp_open_panel_click",
    "miniapp_open_panel_blocked_non_telegram",
    "miniapp_credentials_bootstrap_shown",
    "miniapp_credentials_bootstrap_completed",
    "miniapp_credentials_bootstrap_rejected",
    "web_landing_view_in_telegram",
    "web_landing_miniapp_cta_click",
    "telegram_auth_attempt",
    "telegram_auth_success",
    "telegram_auth_failed",
    "post_login_route_resolved",
    "auth_refresh_singleflight_waiter",
]

AnalyticsDeviceMode = Literal["telegram-mobile", "telegram-desktop", "web"]


class WebAnalyticsEventRequest(BaseModel):
    event_name: AnalyticsEventName
    source_path: str = Field(min_length=1, max_length=255)
    session_id: str = Field(min_length=1, max_length=64)
    device_mode: AnalyticsDeviceMode
    is_in_telegram: bool
    has_init_data: bool
    start_param: Optional[str] = Field(default=None, max_length=128)
    has_query_id: bool = False
    chat_type: Optional[str] = Field(default=None, max_length=64)
    meta: dict[str, Any] = Field(default_factory=dict)


class OkResponse(BaseModel):
    ok: bool = True


def _resolve_optional_user_telegram_id(
    *,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[int]:
    if not credentials:
        return None

    token = credentials.credentials

    web_payload = verify_access_token(token)
    if web_payload and web_payload.get("sub") is not None:
        try:
            return int(web_payload["sub"])
        except (TypeError, ValueError):
            return None

    return None


@router.post("/web-events", response_model=OkResponse)
@inject
async def create_web_event(
    payload: WebAnalyticsEventRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    web_analytics_event_service: FromDishka[WebAnalyticsEventService] = None,  # type: ignore[assignment]
) -> OkResponse:
    if web_analytics_event_service is None:
        return OkResponse(ok=True)

    user_telegram_id = _resolve_optional_user_telegram_id(credentials=credentials)

    try:
        await web_analytics_event_service.create_event(
            event_name=payload.event_name,
            source_path=payload.source_path,
            session_id=payload.session_id,
            user_telegram_id=user_telegram_id,
            device_mode=payload.device_mode,
            is_in_telegram=payload.is_in_telegram,
            has_init_data=payload.has_init_data,
            start_param=payload.start_param,
            has_query_id=payload.has_query_id,
            chat_type=payload.chat_type,
            meta=payload.meta,
        )
    except Exception as exc:
        logger.warning("Failed to persist analytics event '{}': {}", payload.event_name, exc)

    return OkResponse(ok=True)
