import asyncio
from types import SimpleNamespace

from src.services.webhook import WebhookService


def run_async(coroutine):
    return asyncio.run(coroutine)


def _build_service(*, setup_webhook: bool, reset_webhook: bool = True) -> WebhookService:
    config = SimpleNamespace(
        bot=SimpleNamespace(setup_webhook=setup_webhook, reset_webhook=reset_webhook)
    )
    return WebhookService(
        config=config,
        bot=SimpleNamespace(),
        redis_client=SimpleNamespace(),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
    )


def test_setup_returns_none_when_webhook_setup_is_disabled() -> None:
    service = _build_service(setup_webhook=False)

    result = run_async(service.setup(["message"]))

    assert result is None


def test_delete_returns_early_when_webhook_setup_is_disabled() -> None:
    service = _build_service(setup_webhook=False)

    run_async(service.delete())
