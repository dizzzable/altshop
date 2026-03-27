import asyncio
import traceback
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

from aiogram import Bot, Dispatcher
from aiogram.types import User, WebhookInfo
from aiogram.utils.formatting import Text
from dishka import AsyncContainer, Scope
from fastapi import FastAPI
from loguru import logger

from src.__version__ import __version__
from src.api.endpoints import TelegramWebhookEndpoint
from src.core.config import AppConfig
from src.core.enums import SystemNotificationType
from src.core.observability import emit_counter
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.taskiq.tasks.notifications import (
    send_error_notification_task,
    send_remnashop_notification_task,
    send_system_notification_task,
)
from src.infrastructure.taskiq.tasks.payments import recover_platega_webhooks_task
from src.infrastructure.taskiq.tasks.updates import check_bot_update
from src.services.backup import BackupService
from src.services.command import CommandService
from src.services.payment_gateway import PaymentGatewayService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.webhook import WebhookService


def _log_startup_summary(*, access_mode: str, bot_profile: User | None) -> None:
    lines = [f"Bot version: {__version__}"]

    if bot_profile is None:
        lines.append("Telegram profile check - skipped")
    else:
        states: dict[Optional[bool], str] = {True: "Enabled", False: "Disabled", None: "Unknown"}
        lines.extend(
            [
                "Groups Mode  - " + states[bot_profile.can_join_groups],
                "Privacy Mode - " + states[not bot_profile.can_read_all_group_messages],
                "Inline Mode  - " + states[bot_profile.supports_inline_queries],
            ]
        )

    lines.append(f"Bot in access mode: '{access_mode}'")
    logger.info("\n".join(lines))


@dataclass(slots=True)
class AppLifecycleCoordinator:
    config: AppConfig
    dispatcher: Dispatcher
    telegram_webhook_endpoint: TelegramWebhookEndpoint

    async def startup(self, container: AsyncContainer) -> None:
        async with container(scope=Scope.REQUEST) as scoped_container:
            webhook_service: WebhookService = await scoped_container.get(WebhookService)
            command_service: CommandService = await scoped_container.get(CommandService)
            settings_service: SettingsService = await scoped_container.get(SettingsService)
            gateway_service: PaymentGatewayService = await scoped_container.get(
                PaymentGatewayService
            )
            remnawave_service: RemnawaveService = await scoped_container.get(RemnawaveService)

            await gateway_service.create_default()
            await gateway_service.normalize_gateway_settings()
            access_mode = await settings_service.get_access_mode()

            backup_service: BackupService = await container.get(BackupService)
            await backup_service.start_auto_backup()

            webhook_info = await self._setup_webhook(webhook_service)
            await self._send_webhook_error_notification(
                webhook_service=webhook_service,
                webhook_info=webhook_info,
            )

            await command_service.setup()
            await self.telegram_webhook_endpoint.startup()

            bot_profile = await self._get_bot_profile(container)
            _log_startup_summary(access_mode=access_mode, bot_profile=bot_profile)

            await self._queue_startup_tasks(access_mode)
            await self._probe_remnawave(remnawave_service)

    async def shutdown(self, container: AsyncContainer) -> None:
        backup_service: BackupService = await container.get(BackupService)
        await backup_service.stop_auto_backup()

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.BOT_LIFETIME,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-bot-shutdown",
            ),
        )

        await self.telegram_webhook_endpoint.shutdown()

        async with container(scope=Scope.REQUEST) as scoped_container:
            command_service: CommandService = await scoped_container.get(CommandService)
            webhook_service: WebhookService = await scoped_container.get(WebhookService)
            await command_service.delete()
            await webhook_service.delete()

    async def _setup_webhook(self, webhook_service: WebhookService) -> WebhookInfo | None:
        allowed_updates = self.dispatcher.resolve_used_update_types()
        return await webhook_service.setup(allowed_updates)

    async def _send_webhook_error_notification(
        self,
        *,
        webhook_service: WebhookService,
        webhook_info: WebhookInfo | None,
    ) -> None:
        if webhook_info is None or not webhook_service.has_error(webhook_info):
            return

        logger.critical(f"Webhook has a last error message: '{webhook_info.last_error_message}'")
        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.BOT_LIFETIME,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error-webhook",
                i18n_kwargs={"error": webhook_info.last_error_message},
            ),
        )

    async def _get_bot_profile(self, container: AsyncContainer) -> User | None:
        if not self.config.bot.fetch_me_on_startup:
            logger.warning(
                "BOT_FETCH_ME_ON_STARTUP is disabled; skipping Telegram bot profile check"
            )
            return None

        bot_client: Bot = await container.get(Bot)
        return await bot_client.get_me()

    async def _queue_startup_tasks(self, access_mode: str) -> None:
        await check_bot_update.kiq()
        await recover_platega_webhooks_task.kiq()
        await send_remnashop_notification_task.kiq()
        await asyncio.sleep(2)
        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.BOT_LIFETIME,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-bot-startup",
                i18n_kwargs={"access_mode": access_mode},
            ),
        )

    async def _probe_remnawave(self, remnawave_service: RemnawaveService) -> None:
        try:
            await remnawave_service.try_connection()
        except Exception as exception:
            emit_counter(
                "remnawave_degraded_states_total",
                stage="startup",
                reason="connection_failed",
            )
            logger.exception(f"Remnawave connection failed: {exception}")
            error_type_name = type(exception).__name__
            error_message = Text(str(exception)[:512])

            await send_error_notification_task.kiq(
                error_id=str(uuid.uuid4()),
                traceback_str=traceback.format_exc(),
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-error-remnawave",
                    i18n_kwargs={
                        "error": f"{error_type_name}: {error_message.as_html()}",
                    },
                ),
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    container: AsyncContainer = app.state.dishka_container
    coordinator: AppLifecycleCoordinator = app.state.lifecycle_coordinator

    await coordinator.startup(container)
    try:
        yield
    finally:
        await coordinator.shutdown(container)
        await container.close()
