from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src import lifespan as lifespan_module


def run_async(coroutine):
    return asyncio.run(coroutine)


class _FakeScopedContainer:
    def __init__(self, mapping):
        self.mapping = mapping

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, dependency):
        return self.mapping[dependency]

    async def close(self):
        return None


class _FakeContainer:
    def __init__(self, startup_mapping, runtime_mapping):
        self.startup_mapping = startup_mapping
        self.runtime_mapping = runtime_mapping

    def __call__(self, scope=None):
        del scope
        return _FakeScopedContainer(self.startup_mapping)

    async def get(self, dependency):
        return self.runtime_mapping[dependency]

    async def close(self):
        return None


def _build_lifespan_app(
    *,
    container,
    dispatcher,
    telegram_webhook_endpoint,
    config,
):
    coordinator = lifespan_module.AppLifecycleCoordinator(
        config=config,
        dispatcher=dispatcher,
        telegram_webhook_endpoint=telegram_webhook_endpoint,
    )
    return SimpleNamespace(
        state=SimpleNamespace(
            dispatcher=dispatcher,
            telegram_webhook_endpoint=telegram_webhook_endpoint,
            dishka_container=container,
            config=config,
            lifecycle_coordinator=coordinator,
        )
    )


def test_lifespan_queues_check_bot_update_on_startup(monkeypatch) -> None:
    webhook_service = SimpleNamespace(
        setup=AsyncMock(return_value=SimpleNamespace(last_error_message=None)),
        has_error=MagicMock(return_value=False),
        delete=AsyncMock(),
    )
    command_service = SimpleNamespace(setup=AsyncMock(), delete=AsyncMock())
    settings_service = SimpleNamespace(get_access_mode=AsyncMock(return_value="PUBLIC"))
    gateway_service = SimpleNamespace(
        create_default=AsyncMock(),
        normalize_gateway_settings=AsyncMock(),
    )
    remnawave_service = SimpleNamespace(try_connection=AsyncMock())
    backup_service = SimpleNamespace(
        start_auto_backup=AsyncMock(),
        stop_auto_backup=AsyncMock(),
    )
    bot = SimpleNamespace(
        get_me=AsyncMock(
            return_value=SimpleNamespace(
                can_join_groups=False,
                can_read_all_group_messages=False,
                supports_inline_queries=False,
            )
        )
    )
    telegram_webhook_endpoint = SimpleNamespace(startup=AsyncMock(), shutdown=AsyncMock())
    dispatcher = SimpleNamespace(resolve_used_update_types=MagicMock(return_value=[]))

    startup_mapping = {
        lifespan_module.WebhookService: webhook_service,
        lifespan_module.CommandService: command_service,
        lifespan_module.SettingsService: settings_service,
        lifespan_module.PaymentGatewayService: gateway_service,
        lifespan_module.RemnawaveService: remnawave_service,
    }
    runtime_mapping = {
        lifespan_module.BackupService: backup_service,
        lifespan_module.Bot: bot,
    }
    container = _FakeContainer(startup_mapping=startup_mapping, runtime_mapping=runtime_mapping)
    app = _build_lifespan_app(
        container=container,
        dispatcher=dispatcher,
        telegram_webhook_endpoint=telegram_webhook_endpoint,
        config=SimpleNamespace(bot=SimpleNamespace(fetch_me_on_startup=True)),
    )

    check_bot_update_mock = AsyncMock()
    recover_platega_mock = AsyncMock()
    send_remnashop_mock = AsyncMock()
    send_system_mock = AsyncMock()

    monkeypatch.setattr(lifespan_module.check_bot_update, "kiq", check_bot_update_mock)
    monkeypatch.setattr(
        lifespan_module.recover_platega_webhooks_task,
        "kiq",
        recover_platega_mock,
    )
    monkeypatch.setattr(
        lifespan_module.send_remnashop_notification_task,
        "kiq",
        send_remnashop_mock,
    )
    monkeypatch.setattr(
        lifespan_module.send_system_notification_task,
        "kiq",
        send_system_mock,
    )
    monkeypatch.setattr(lifespan_module.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        lifespan_module,
        "logger",
        SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            critical=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        ),
    )

    async def _exercise_lifespan():
        async with lifespan_module.lifespan(app):
            check_bot_update_mock.assert_awaited_once()

    run_async(_exercise_lifespan())

    recover_platega_mock.assert_awaited_once()
    send_remnashop_mock.assert_awaited_once()
    backup_service.start_auto_backup.assert_awaited_once()
    backup_service.stop_auto_backup.assert_awaited_once()
    command_service.setup.assert_awaited_once()
    command_service.delete.assert_awaited_once()
    webhook_service.delete.assert_awaited_once()
    bot.get_me.assert_awaited_once()


def test_lifespan_skips_profile_fetch_when_startup_profile_check_is_disabled(monkeypatch) -> None:
    webhook_service = SimpleNamespace(
        setup=AsyncMock(return_value=None),
        has_error=MagicMock(return_value=False),
        delete=AsyncMock(),
    )
    command_service = SimpleNamespace(setup=AsyncMock(), delete=AsyncMock())
    settings_service = SimpleNamespace(get_access_mode=AsyncMock(return_value="PUBLIC"))
    gateway_service = SimpleNamespace(
        create_default=AsyncMock(),
        normalize_gateway_settings=AsyncMock(),
    )
    remnawave_service = SimpleNamespace(try_connection=AsyncMock())
    backup_service = SimpleNamespace(
        start_auto_backup=AsyncMock(),
        stop_auto_backup=AsyncMock(),
    )
    bot = SimpleNamespace(get_me=AsyncMock())
    telegram_webhook_endpoint = SimpleNamespace(startup=AsyncMock(), shutdown=AsyncMock())
    dispatcher = SimpleNamespace(resolve_used_update_types=MagicMock(return_value=[]))

    startup_mapping = {
        lifespan_module.WebhookService: webhook_service,
        lifespan_module.CommandService: command_service,
        lifespan_module.SettingsService: settings_service,
        lifespan_module.PaymentGatewayService: gateway_service,
        lifespan_module.RemnawaveService: remnawave_service,
    }
    runtime_mapping = {
        lifespan_module.BackupService: backup_service,
        lifespan_module.Bot: bot,
    }
    container = _FakeContainer(startup_mapping=startup_mapping, runtime_mapping=runtime_mapping)
    app = _build_lifespan_app(
        container=container,
        dispatcher=dispatcher,
        telegram_webhook_endpoint=telegram_webhook_endpoint,
        config=SimpleNamespace(bot=SimpleNamespace(fetch_me_on_startup=False)),
    )

    monkeypatch.setattr(lifespan_module.check_bot_update, "kiq", AsyncMock())
    monkeypatch.setattr(
        lifespan_module.recover_platega_webhooks_task,
        "kiq",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lifespan_module.send_remnashop_notification_task,
        "kiq",
        AsyncMock(),
    )
    monkeypatch.setattr(
        lifespan_module.send_system_notification_task,
        "kiq",
        AsyncMock(),
    )
    monkeypatch.setattr(lifespan_module.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(
        lifespan_module,
        "logger",
        SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            critical=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        ),
    )

    async def _exercise_lifespan():
        async with lifespan_module.lifespan(app):
            return None

    run_async(_exercise_lifespan())

    bot.get_me.assert_not_awaited()
    webhook_service.has_error.assert_not_called()
