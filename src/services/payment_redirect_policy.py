from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.api.utils.web_app_urls import build_web_payment_redirect_urls
from src.core.config import AppConfig
from src.core.enums import PurchaseChannel
from src.core.utils.mini_app_urls import (
    PaymentReturnStatus,
    build_telegram_payment_return_url,
)

_DEFAULT_PORTS = {"http": 80, "https": 443}
_TELEGRAM_HOST_ALIASES = {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}
_PAYMENT_RETURN_STATUSES: tuple[PaymentReturnStatus, PaymentReturnStatus] = (
    "success",
    "failed",
)


def sanitize_payment_redirect_urls_for_channel(
    *,
    channel: PurchaseChannel,
    config: AppConfig,
    success_redirect_url: str | None,
    fail_redirect_url: str | None,
    mini_app_url: str | None = None,
    bot_username: str | None = None,
) -> tuple[str | None, str | None]:
    allowed_urls = _build_allowed_redirect_urls(
        channel=channel,
        config=config,
        mini_app_url=mini_app_url,
        bot_username=bot_username,
    )
    return (
        _sanitize_redirect_url(success_redirect_url, allowed_urls=allowed_urls),
        _sanitize_redirect_url(fail_redirect_url, allowed_urls=allowed_urls),
    )


def build_allowed_redirect_urls_for_channel(
    *,
    channel: PurchaseChannel,
    config: AppConfig,
    mini_app_url: str | None = None,
    bot_username: str | None = None,
) -> tuple[str, ...]:
    allowed_urls = _build_allowed_redirect_urls(
        channel=channel,
        config=config,
        mini_app_url=mini_app_url,
        bot_username=bot_username,
    )
    return tuple(sorted(allowed_urls))


def _build_allowed_redirect_urls(
    *,
    channel: PurchaseChannel,
    config: AppConfig,
    mini_app_url: str | None,
    bot_username: str | None,
) -> set[str]:
    if channel == PurchaseChannel.WEB:
        return {
            canonical
            for canonical in (
                _canonicalize_redirect_url(url)
                for url in build_web_payment_redirect_urls(config)
            )
            if canonical
        }

    if channel != PurchaseChannel.TELEGRAM:
        return set()

    return {
        canonical
        for canonical in (
            _canonicalize_redirect_url(
                build_telegram_payment_return_url(
                    status=status,
                    mini_app_url=mini_app_url,
                    bot_username=bot_username,
                )
            )
            for status in _PAYMENT_RETURN_STATUSES
        )
        if canonical
    }


def _sanitize_redirect_url(
    value: str | None,
    *,
    allowed_urls: set[str],
) -> str | None:
    canonical = _canonicalize_redirect_url(value)
    if canonical and canonical in allowed_urls:
        return canonical
    return None


def _canonicalize_redirect_url(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None

    parsed = urlsplit(normalized)
    scheme = parsed.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not parsed.hostname or parsed.username or parsed.password:
        return None

    host = parsed.hostname.lower()
    if host in _TELEGRAM_HOST_ALIASES:
        host = "t.me"

    port = parsed.port
    netloc = host
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        netloc = f"{host}:{port}"

    path = parsed.path or ""
    if path not in {"", "/"}:
        path = path.rstrip("/")

    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)

    return urlunsplit((scheme, netloc, path, query, parsed.fragment))


__all__ = [
    "build_allowed_redirect_urls_for_channel",
    "sanitize_payment_redirect_urls_for_channel",
]
