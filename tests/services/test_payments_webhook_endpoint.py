from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Response

import src.api.endpoints.payments as payments_module
from src.core.enums import TransactionStatus
from src.core.observability import clear_metrics_registry, render_metrics_text
from src.services.payment_gateway import PaymentGatewayService
from src.services.payment_webhook_event import PaymentWebhookEventService


def run_async(coroutine):
    return asyncio.run(coroutine)


def setup_function() -> None:
    clear_metrics_registry()


def teardown_function() -> None:
    clear_metrics_registry()


class FakeDishkaContainer:
    def __init__(
        self,
        payment_gateway_service: object,
        payment_webhook_event_service: object,
    ) -> None:
        self.payment_gateway_service = payment_gateway_service
        self.payment_webhook_event_service = payment_webhook_event_service

    async def get(self, type_hint, *, component=None):
        del component
        if type_hint is PaymentGatewayService:
            return self.payment_gateway_service
        if type_hint is PaymentWebhookEventService:
            return self.payment_webhook_event_service
        raise AssertionError(f"Unexpected dependency request: {type_hint}")


class FakeRequest:
    def __init__(self, payload: bytes, container: FakeDishkaContainer) -> None:
        self._payload = payload
        self.headers = {}
        self.client = SimpleNamespace(host="127.0.0.1")
        self.app = SimpleNamespace(state=SimpleNamespace(config=None))
        self.state = SimpleNamespace(dishka_container=container)

    async def body(self) -> bytes:
        return self._payload


@pytest.mark.parametrize(
    ("already_processed", "already_in_flight"),
    [
        (True, False),
        (False, True),
    ],
)
def test_payments_webhook_short_circuits_duplicate_and_in_flight_events(
    monkeypatch: pytest.MonkeyPatch,
    already_processed: bool,
    already_in_flight: bool,
) -> None:
    payment_id = uuid4()
    gateway = SimpleNamespace(
        handle_webhook=AsyncMock(return_value=(payment_id, TransactionStatus.COMPLETED)),
        build_webhook_response=AsyncMock(return_value=Response(status_code=200)),
    )
    payment_gateway_service = SimpleNamespace(
        _get_gateway_instance=AsyncMock(return_value=gateway),
    )
    payment_webhook_event_service = SimpleNamespace(
        record_received=AsyncMock(
            return_value=SimpleNamespace(
                already_processed=already_processed,
                already_in_flight=already_in_flight,
            )
        )
    )
    queue_task = AsyncMock()
    monkeypatch.setattr(payments_module.handle_payment_transaction_task, "kiq", queue_task)
    request = FakeRequest(
        b'{"id":"abc"}',
        FakeDishkaContainer(
            payment_gateway_service=payment_gateway_service,
            payment_webhook_event_service=payment_webhook_event_service,
        ),
    )

    response = run_async(
        payments_module.payments_webhook(
            gateway_type="platega",
            request=request,
        )
    )

    assert response.status_code == 200
    payment_webhook_event_service.record_received.assert_awaited_once()
    queue_task.assert_not_awaited()
    gateway.build_webhook_response.assert_awaited_once()


def test_payments_webhook_emits_metric_when_queue_enqueue_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment_id = uuid4()
    gateway = SimpleNamespace(
        handle_webhook=AsyncMock(return_value=(payment_id, TransactionStatus.COMPLETED)),
        build_webhook_response=AsyncMock(return_value=Response(status_code=200)),
    )
    payment_gateway_service = SimpleNamespace(
        _get_gateway_instance=AsyncMock(return_value=gateway),
    )
    payment_webhook_event_service = SimpleNamespace(
        record_received=AsyncMock(
            return_value=SimpleNamespace(
                already_processed=False,
                already_in_flight=False,
            )
        ),
        mark_failed=AsyncMock(),
        mark_enqueued=AsyncMock(),
    )
    queue_task = AsyncMock(side_effect=RuntimeError("queue down"))
    monkeypatch.setattr(payments_module.handle_payment_transaction_task, "kiq", queue_task)
    request = FakeRequest(
        b'{"id":"abc"}',
        FakeDishkaContainer(
            payment_gateway_service=payment_gateway_service,
            payment_webhook_event_service=payment_webhook_event_service,
        ),
    )

    response = run_async(
        payments_module.payments_webhook(
            gateway_type="platega",
            request=request,
        )
    )

    assert response.status_code == 503
    payment_webhook_event_service.mark_failed.assert_awaited_once()
    payment_webhook_event_service.mark_enqueued.assert_not_awaited()
    rendered_metrics = render_metrics_text()
    assert (
        'payment_webhook_enqueue_failures_total{gateway_type="PLATEGA"} 1'
        in rendered_metrics
    )


def test_payments_webhook_returns_403_without_recording_event_when_gateway_denies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = SimpleNamespace(
        handle_webhook=AsyncMock(side_effect=PermissionError("Missing WATA webhook signature")),
        build_webhook_response=AsyncMock(return_value=Response(status_code=200)),
    )
    payment_gateway_service = SimpleNamespace(
        _get_gateway_instance=AsyncMock(return_value=gateway),
    )
    payment_webhook_event_service = SimpleNamespace(
        record_received=AsyncMock(),
    )
    queue_task = AsyncMock()
    monkeypatch.setattr(payments_module.handle_payment_transaction_task, "kiq", queue_task)
    request = FakeRequest(
        b'{"orderId":"abc"}',
        FakeDishkaContainer(
            payment_gateway_service=payment_gateway_service,
            payment_webhook_event_service=payment_webhook_event_service,
        ),
    )

    response = run_async(
        payments_module.payments_webhook(
            gateway_type="wata",
            request=request,
        )
    )

    assert response.status_code == 403
    payment_webhook_event_service.record_received.assert_not_awaited()
    queue_task.assert_not_awaited()
    gateway.build_webhook_response.assert_not_awaited()
