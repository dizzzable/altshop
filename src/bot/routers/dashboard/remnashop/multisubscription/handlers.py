from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import RemnashopMultiSubscription
from src.core.constants import USER_KEY
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.settings import SettingsService


@inject
async def on_multi_subscription_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Переключение статуса мультиподписок (включено/выключено)."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    settings = await settings_service.get()
    settings.multi_subscription.enabled = not settings.multi_subscription.enabled
    await settings_service.update(settings)
    
    status = "enabled" if settings.multi_subscription.enabled else "disabled"
    logger.info(f"{log(user)} Multi-subscription {status}")


@inject
async def on_max_subscriptions_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_max: int,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Выбор максимального количества подписок."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    settings = await settings_service.get()
    settings.multi_subscription.default_max_subscriptions = selected_max
    await settings_service.update(settings)
    
    logger.info(f"{log(user)} Set default max subscriptions to {selected_max}")
    await dialog_manager.switch_to(state=RemnashopMultiSubscription.MAIN)


@inject
async def on_max_subscriptions_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Обработка ввода максимального количества подписок вручную."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    if not message.text:
        return
    
    try:
        value = int(message.text.strip())
        
        # Проверяем валидность значения
        if value < -1 or value == 0:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-multi-subscription-invalid-value"),
            )
            return
        
        settings = await settings_service.get()
        settings.multi_subscription.default_max_subscriptions = value
        await settings_service.update(settings)
        
        logger.info(f"{log(user)} Set default max subscriptions to {value}")
        await dialog_manager.switch_to(state=RemnashopMultiSubscription.MAIN)
        
    except ValueError:
        logger.warning(f"{log(user)} Invalid max subscriptions input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )