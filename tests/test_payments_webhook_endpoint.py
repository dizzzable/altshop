from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from fastapi import Request
from fastapi.responses import PlainTextResponse

from src.api.endpoints.payments import payments_webhook
from src.core.enums import TransactionStatus


def _unwrap_callable(func):
    closure = getattr(func, "__closure__", None) or ()
    for cell in closure:
        cell_value = getattr(cell, "cell_contents", None)
        if callable(cell_value) and getattr(cell_value, "__name__", "") == func.__name__:
            return _unwrap_callable(cell_value)

    target = func
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__  # type: ignore[attr-defined]
    return target


_PAYMENTS_WEBHOOK_IMPL = _unwrap_callable(payments_webhook)


def _build_request() -> Request:
    body = b"InvId=demo"
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/payments/robokassa",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "query_string": b"",
        "scheme": "https",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "http_version": "1.1",
        "app": SimpleNamespace(state=SimpleNamespace(config=None)),
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


class _GatewayStub:
    async def handle_webhook(self, request: Request) -> tuple[UUID, TransactionStatus]:
        return UUID("00000000-0000-0000-0000-000000000123"), TransactionStatus.COMPLETED

    async def build_webhook_response(self, request: Request) -> PlainTextResponse:
        return PlainTextResponse("OKdemo")


def test_payments_webhook_returns_gateway_ack_for_duplicates(monkeypatch) -> None:
    gateway = _GatewayStub()
    payment_gateway_service = SimpleNamespace(_get_gateway_instance=AsyncMock(return_value=gateway))
    payment_webhook_event_service = SimpleNamespace(
        record_received=AsyncMock(return_value=SimpleNamespace(already_processed=True)),
        mark_enqueued=AsyncMock(),
        mark_failed=AsyncMock(),
    )

    response = asyncio.run(
        _PAYMENTS_WEBHOOK_IMPL(
            gateway_type="robokassa",
            request=_build_request(),
            payment_gateway_service=payment_gateway_service,
            payment_webhook_event_service=payment_webhook_event_service,
        )
    )

    assert response.body == b"OKdemo"
    payment_webhook_event_service.mark_enqueued.assert_not_awaited()


def test_payments_webhook_returns_gateway_ack_after_enqueue(monkeypatch) -> None:
    gateway = _GatewayStub()
    payment_gateway_service = SimpleNamespace(_get_gateway_instance=AsyncMock(return_value=gateway))
    payment_webhook_event_service = SimpleNamespace(
        record_received=AsyncMock(return_value=SimpleNamespace(already_processed=False)),
        mark_enqueued=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    monkeypatch.setattr(
        "src.api.endpoints.payments.handle_payment_transaction_task.kiq",
        AsyncMock(return_value=None),
    )

    response = asyncio.run(
        _PAYMENTS_WEBHOOK_IMPL(
            gateway_type="robokassa",
            request=_build_request(),
            payment_gateway_service=payment_gateway_service,
            payment_webhook_event_service=payment_webhook_event_service,
        )
    )

    assert response.body == b"OKdemo"
    payment_webhook_event_service.mark_enqueued.assert_awaited_once()
