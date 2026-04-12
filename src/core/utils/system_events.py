# ruff: noqa: C901, E501

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from typing import Any

from src.__version__ import __version__
from src.core.enums import Locale
from src.core.utils.message_payload import MessagePayload

SYSTEM_EVENT_DEDUPE_TTL_SECONDS = 300

_AUTH_SOURCE_LABELS = {
    "WEB_PASSWORD": "Password",
    "WEB_TELEGRAM_WIDGET": "Telegram Widget",
    "WEB_TELEGRAM_WEBAPP": "Telegram Mini App",
    "ADMIN_BIND": "Admin Bind",
}
_ENTRY_SURFACE_LABELS = {
    "BOT": "Bot",
    "WEB": "Web",
    "MINI_APP": "Mini App",
    "BACKGROUND": "Background",
    "WEBHOOK": "Webhook",
    "API": "API",
}
_PURCHASE_CHANNEL_LABELS = {
    "TELEGRAM": "Bot / Mini App",
    "WEB": "Web",
}
_LINK_SOURCE_LABELS = {
    "WEB_TELEGRAM_WIDGET": "Telegram Widget",
    "WEB_TELEGRAM_WEBAPP": "Telegram Mini App",
    "WEB_CONFIRM": "Web Confirm",
    "ADMIN_BIND": "Admin Bind",
}
_EVENT_LABELS = {
    "en": {
        "impact": "Impact",
        "context": "Context",
        "build": "Build",
        "hint": "Next step",
        "source": "Source",
        "surface": "Surface",
        "operation": "Operation",
        "auth_source": "Auth source",
        "purchase_channel": "Purchase channel",
        "link_source": "Link source",
        "severity": "Severity",
        "version": "Version",
        "commit": "Commit",
        "branch": "Branch",
        "built_at": "Built at",
        "error_type": "Type",
        "error_message": "Message",
    },
    "ru": {
        "impact": "Почему это важно",
        "context": "Контекст",
        "build": "Информация о сборке",
        "hint": "Что проверить дальше",
        "source": "Источник",
        "surface": "Поверхность",
        "operation": "Операция",
        "auth_source": "Источник авторизации",
        "purchase_channel": "Канал покупки",
        "link_source": "Источник привязки",
        "severity": "Уровень",
        "version": "Версия",
        "commit": "Коммит",
        "branch": "Ветка",
        "built_at": "Время сборки",
        "error_type": "Тип",
        "error_message": "Сообщение",
    },
}


def _run_git_command(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            check=True,
            text=True,
            timeout=1.5,
        )
    except Exception:
        return None

    value = completed.stdout.strip()
    return value or None


@lru_cache(maxsize=1)
def get_build_context() -> dict[str, str]:
    commit = (
        os.getenv("APP_BUILD_COMMIT")
        or os.getenv("GIT_COMMIT")
        or os.getenv("GITHUB_SHA")
        or _run_git_command("rev-parse", "--short", "HEAD")
        or "unknown"
    )
    branch = (
        os.getenv("APP_BUILD_BRANCH")
        or os.getenv("GIT_BRANCH")
        or os.getenv("GITHUB_REF_NAME")
        or _run_git_command("branch", "--show-current")
        or "unknown"
    )
    built_at = (
        os.getenv("APP_BUILD_TIME")
        or os.getenv("BUILD_TIME")
        or os.getenv("GITHUB_RUN_ATTEMPT")
        or "unknown"
    )

    return {
        "build_version": __version__,
        "build_commit": commit,
        "build_branch": branch,
        "build_time": built_at,
    }


def _split_error(raw_error: str | None) -> tuple[str | None, str | None]:
    if not raw_error:
        return None, None
    if ":" not in raw_error:
        return raw_error.strip() or None, None

    raw_error_type, raw_error_message = raw_error.split(":", 1)
    normalized_error_type = raw_error_type.strip() or None
    normalized_error_message = raw_error_message.strip() or None
    return normalized_error_type, normalized_error_message


def _default_entry_surface(auth_source: str | None, purchase_channel: str | None) -> str | None:
    if auth_source == "WEB_TELEGRAM_WEBAPP":
        return "MINI_APP"
    if auth_source in {"WEB_TELEGRAM_WIDGET", "WEB_PASSWORD"}:
        return "WEB"
    if purchase_channel == "WEB":
        return "WEB"
    if purchase_channel == "TELEGRAM":
        return "BOT"
    return None


def normalize_system_event_kwargs(
    i18n_kwargs: dict[str, Any] | None = None,
    *,
    severity: str | None = None,
    event_source: str | None = None,
    entry_surface: str | None = None,
    operation: str | None = None,
    auth_source: str | None = None,
    purchase_channel: str | None = None,
    link_source: str | None = None,
    impact: str | None = None,
    operator_hint: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    kwargs = dict(i18n_kwargs or {})
    raw_error = kwargs.get("error")
    parsed_error_type, parsed_error_message = _split_error(
        raw_error if isinstance(raw_error, str) else None
    )

    auth_source_value = str(kwargs.get("auth_source") or auth_source or "").strip() or None
    purchase_channel_value = (
        str(kwargs.get("purchase_channel") or purchase_channel or "").strip() or None
    )
    entry_surface_value = (
        str(kwargs.get("entry_surface") or entry_surface or "").strip()
        or _default_entry_surface(auth_source_value, purchase_channel_value)
    )
    event_source_value = str(kwargs.get("event_source") or event_source or "").strip() or None
    operation_value = str(kwargs.get("operation") or operation or "").strip() or None
    link_source_value = str(kwargs.get("link_source") or link_source or "").strip() or None
    severity_value = str(kwargs.get("severity") or severity or "INFO").strip().upper()
    impact_value = str(kwargs.get("impact") or impact or "").strip() or None
    operator_hint_value = str(kwargs.get("operator_hint") or operator_hint or "").strip() or None
    resolved_error_type = (
        str(kwargs.get("error_type") or error_type or parsed_error_type or "").strip() or None
    )
    resolved_error_message = (
        str(kwargs.get("error_message") or error_message or parsed_error_message or "").strip()
        or None
    )

    build_context = get_build_context()
    kwargs.update(build_context)
    kwargs.update(
        {
            "severity": severity_value,
            "has_event_context": bool(
                event_source_value
                or entry_surface_value
                or operation_value
                or auth_source_value
                or purchase_channel_value
                or link_source_value
            ),
            "event_source": event_source_value or "",
            "has_event_source": bool(event_source_value),
            "entry_surface": entry_surface_value or "",
            "entry_surface_label": _ENTRY_SURFACE_LABELS.get(
                entry_surface_value or "", entry_surface_value or ""
            ),
            "has_entry_surface": bool(entry_surface_value),
            "operation": operation_value or "",
            "has_operation": bool(operation_value),
            "auth_source": auth_source_value or "",
            "auth_source_label": _AUTH_SOURCE_LABELS.get(
                auth_source_value or "", auth_source_value or ""
            ),
            "has_auth_source": bool(auth_source_value),
            "purchase_channel": purchase_channel_value or "",
            "purchase_channel_label": _PURCHASE_CHANNEL_LABELS.get(
                purchase_channel_value or "", purchase_channel_value or ""
            ),
            "has_purchase_channel": bool(purchase_channel_value),
            "link_source": link_source_value or "",
            "link_source_label": _LINK_SOURCE_LABELS.get(
                link_source_value or "", link_source_value or ""
            ),
            "has_link_source": bool(link_source_value),
            "impact": impact_value or "",
            "has_impact": bool(impact_value),
            "operator_hint": operator_hint_value or "",
            "has_operator_hint": bool(operator_hint_value),
            "error_type": resolved_error_type or "",
            "error_message": resolved_error_message or "",
            "has_structured_error": bool(resolved_error_type or resolved_error_message),
            "has_build_info": True,
            "event_context_block": "",
            "build_info_block": "",
            "impact_block": "",
            "operator_hint_block": "",
            "error_block": "",
        }
    )
    return kwargs


def build_system_event_payload(
    *,
    i18n_key: str,
    i18n_kwargs: dict[str, Any] | None = None,
    severity: str | None = None,
    event_source: str | None = None,
    entry_surface: str | None = None,
    operation: str | None = None,
    auth_source: str | None = None,
    purchase_channel: str | None = None,
    link_source: str | None = None,
    impact: str | None = None,
    operator_hint: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    reply_markup: Any = None,
    message_effect: Any = None,
    dedupe_ttl_seconds: int = SYSTEM_EVENT_DEDUPE_TTL_SECONDS,
) -> MessagePayload:
    normalized_kwargs = normalize_system_event_kwargs(
        i18n_kwargs,
        severity=severity,
        event_source=event_source,
        entry_surface=entry_surface,
        operation=operation,
        auth_source=auth_source,
        purchase_channel=purchase_channel,
        link_source=link_source,
        impact=impact,
        operator_hint=operator_hint,
        error_type=error_type,
        error_message=error_message,
    )

    dedupe_parts = [
        i18n_key,
        normalized_kwargs.get("severity") or "",
        normalized_kwargs.get("event_source") or "",
        normalized_kwargs.get("entry_surface") or "",
        normalized_kwargs.get("operation") or "",
        normalized_kwargs.get("error_type") or "",
        normalized_kwargs.get("error_message") or "",
        normalized_kwargs.get("auth_source") or "",
        normalized_kwargs.get("purchase_channel") or "",
        normalized_kwargs.get("link_source") or "",
    ]
    dedupe_key = "|".join(str(part) for part in dedupe_parts if part)

    return MessagePayload.not_deleted(
        i18n_key=i18n_key,
        i18n_kwargs=normalized_kwargs,
        reply_markup=reply_markup,
        message_effect=message_effect,
        dedupe_key=dedupe_key or None,
        dedupe_ttl_seconds=dedupe_ttl_seconds,
    )


def render_system_event_blocks(locale: Locale, i18n_kwargs: dict[str, Any]) -> dict[str, str]:
    labels = _EVENT_LABELS["en" if locale == Locale.EN else "ru"]

    def quote_block(title: str, lines: list[str]) -> str:
        body = "\n".join(lines)
        return f"\n<b>{title}:</b>\n<blockquote>\n{body}\n</blockquote>\n"

    impact_block = ""
    if i18n_kwargs.get("has_impact") and i18n_kwargs.get("impact"):
        impact_block = quote_block(labels["impact"], [str(i18n_kwargs["impact"])])

    context_lines: list[str] = []
    if i18n_kwargs.get("has_event_source"):
        context_lines.append(f"• <b>{labels['source']}</b>: <code>{i18n_kwargs['event_source']}</code>")
    if i18n_kwargs.get("has_entry_surface"):
        context_lines.append(f"• <b>{labels['surface']}</b>: {i18n_kwargs['entry_surface_label']}")
    if i18n_kwargs.get("has_operation"):
        context_lines.append(f"• <b>{labels['operation']}</b>: <code>{i18n_kwargs['operation']}</code>")
    context_lines.append(f"• <b>{labels['severity']}</b>: {i18n_kwargs['severity']}")
    if i18n_kwargs.get("has_auth_source"):
        context_lines.append(f"• <b>{labels['auth_source']}</b>: {i18n_kwargs['auth_source_label']}")
    if i18n_kwargs.get("has_purchase_channel"):
        context_lines.append(
            f"• <b>{labels['purchase_channel']}</b>: {i18n_kwargs['purchase_channel_label']}"
        )
    if i18n_kwargs.get("has_link_source"):
        context_lines.append(f"• <b>{labels['link_source']}</b>: {i18n_kwargs['link_source_label']}")
    event_context_block = quote_block(labels["context"], context_lines) if context_lines else ""

    build_lines = [
        f"• <b>{labels['version']}</b>: {i18n_kwargs['build_version']}",
        f"• <b>{labels['commit']}</b>: <code>{i18n_kwargs['build_commit']}</code>",
        f"• <b>{labels['branch']}</b>: <code>{i18n_kwargs['build_branch']}</code>",
    ]
    if i18n_kwargs.get("build_time") and i18n_kwargs["build_time"] != "unknown":
        build_lines.append(f"• <b>{labels['built_at']}</b>: {i18n_kwargs['build_time']}")
    build_info_block = quote_block(labels["build"], build_lines)

    error_block = ""
    if i18n_kwargs.get("has_structured_error"):
        error_lines: list[str] = []
        if i18n_kwargs.get("error_type"):
            error_lines.append(
                f"• <b>{labels['error_type']}</b>: <code>{i18n_kwargs['error_type']}</code>"
            )
        if i18n_kwargs.get("error_message"):
            error_lines.append(
                f"• <b>{labels['error_message']}</b>: {i18n_kwargs['error_message']}"
            )
        error_block = quote_block("⚠️ Error" if locale == Locale.EN else "⚠️ Ошибка", error_lines)
    elif i18n_kwargs.get("error"):
        error_block = quote_block(
            "⚠️ Error" if locale == Locale.EN else "⚠️ Ошибка",
            [str(i18n_kwargs["error"])],
        )

    operator_hint_block = ""
    if i18n_kwargs.get("has_operator_hint") and i18n_kwargs.get("operator_hint"):
        operator_hint_block = quote_block(labels["hint"], [str(i18n_kwargs["operator_hint"])])

    return {
        "impact_block": impact_block,
        "event_context_block": event_context_block,
        "build_info_block": build_info_block,
        "error_block": error_block,
        "operator_hint_block": operator_hint_block,
    }
