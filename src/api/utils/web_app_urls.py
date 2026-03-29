from __future__ import annotations

from urllib.parse import quote, urlencode

from src.core.config import AppConfig
from src.core.constants import REFERRAL_PREFIX


def build_web_app_base_url(config: AppConfig) -> str:
    base_url = config.web_app.url_str.rstrip("/")
    if not base_url:
        base_url = f"https://{config.domain.get_secret_value()}"

    if base_url.endswith("/webapp"):
        return base_url

    return f"{base_url}/webapp"


def build_web_referral_link(config: AppConfig, referral_code: str) -> str:
    referral_payload = quote(f"{REFERRAL_PREFIX}{referral_code}", safe="")
    return f"{build_web_app_base_url(config)}/?ref={referral_payload}"


def build_web_payment_redirect_urls(config: AppConfig) -> tuple[str, str]:
    web_base_url = build_web_app_base_url(config)
    success_url = f"{web_base_url}/dashboard/subscription?payment=success"
    fail_url = f"{web_base_url}/dashboard/subscription/purchase?payment=failed"
    return success_url, fail_url


def build_web_settings_url(
    config: AppConfig,
    *,
    telegram_link: str | None = None,
    telegram_id: int | None = None,
) -> str:
    web_base_url = build_web_app_base_url(config)
    params: dict[str, str] = {}
    if telegram_link:
        params["telegram_link"] = telegram_link
    if telegram_id is not None:
        params["telegram_id"] = str(telegram_id)

    query = urlencode(params)
    settings_url = f"{web_base_url}/dashboard/settings"
    return f"{settings_url}?{query}" if query else settings_url
