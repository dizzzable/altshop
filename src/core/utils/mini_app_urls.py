from __future__ import annotations

from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.core.constants import T_ME

PaymentReturnStatus = Literal["success", "failed"]

PAYMENT_RETURN_STATUS_QUERY_KEY = "payment_return_status"
_TELEGRAM_MINI_APP_START_PARAMS: dict[PaymentReturnStatus, str] = {
    "success": "payment-success",
    "failed": "payment-failed",
}
_TELEGRAM_HOSTS = {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}


def build_telegram_payment_return_url(
    *,
    status: PaymentReturnStatus,
    mini_app_url: str | None,
    bot_username: str | None,
) -> str | None:
    normalized_mini_app_url = _normalize_url(mini_app_url)
    if normalized_mini_app_url:
        return _apply_payment_return_payload(url=normalized_mini_app_url, status=status)

    normalized_bot_username = _normalize_bot_username(bot_username)
    if not normalized_bot_username:
        return None

    return f"{T_ME}{normalized_bot_username}?startapp={_TELEGRAM_MINI_APP_START_PARAMS[status]}"


def _apply_payment_return_payload(*, url: str, status: PaymentReturnStatus) -> str:
    parsed = urlsplit(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if parsed.netloc.lower() in _TELEGRAM_HOSTS:
        params["startapp"] = _TELEGRAM_MINI_APP_START_PARAMS[status]
    else:
        params[PAYMENT_RETURN_STATUS_QUERY_KEY] = status
        if parsed.path.rstrip("/").endswith("/miniapp"):
            params.setdefault("tg_open", "1")

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(params, doseq=True),
            parsed.fragment,
        )
    )


def _normalize_bot_username(value: str | None) -> str | None:
    normalized = str(value or "").strip().lstrip("@")
    return normalized or None


def _normalize_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


__all__ = [
    "PAYMENT_RETURN_STATUS_QUERY_KEY",
    "PaymentReturnStatus",
    "build_telegram_payment_return_url",
]
