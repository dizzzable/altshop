from aiogram import Router
from aiogram.filters import Command as FilterCommand
from aiogram.types import Message
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.keyboards import get_contact_support_keyboard
from src.core.config.app import AppConfig
from src.core.enums import Command
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService

router = Router(name=__name__)


@inject
@router.message(FilterCommand(Command.PAYSUPPORT.value.command))
async def on_paysupport_command(
    message: Message,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    notification_service: FromDishka[NotificationService],
) -> None:
    logger.info(f"{log(user)} Call 'paysupport' command")

    text = i18n.get("contact-support-paysupport")
    support_username = config.bot.support_username.get_secret_value()

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-command-paysupport",
            reply_markup=get_contact_support_keyboard(support_username, text),
        ),
    )


@inject
@router.message(FilterCommand(Command.HELP.value.command))
async def on_help_command(
    message: Message,
    user: UserDto,
    config: AppConfig,
    i18n: FromDishka[TranslatorRunner],
    notification_service: FromDishka[NotificationService],
) -> None:
    logger.info(f"{log(user)} Call 'help' command")

    text = i18n.get("contact-support-help")
    support_username = config.bot.support_username.get_secret_value()

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="ntf-command-help",
            reply_markup=get_contact_support_keyboard(support_username, text),
        ),
    )
