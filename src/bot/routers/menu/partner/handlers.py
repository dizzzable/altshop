from decimal import Decimal

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import UserPartner
from src.core.constants import USER_KEY
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.settings import SettingsService


@inject
async def on_partner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Открытие партнерской программы."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    # Проверяем включена ли партнерка
    partner_settings = await settings_service.get_partner_settings()
    if not partner_settings.is_enabled:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-disabled"),
        )
        return
    
    # Проверяем есть ли у пользователя партнерка
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return
    
    await dialog_manager.switch_to(state=UserPartner.MAIN)


@inject
async def on_withdraw(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переход к выводу средств."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return
    
    partner_settings = await settings_service.get_partner_settings()
    
    if partner.balance < partner_settings.min_withdrawal:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-withdraw-min-not-reached",
                i18n_kwargs={"min_withdrawal": float(partner_settings.min_withdrawal)},
            ),
        )
        return
    
    # Устанавливаем сумму вывода (всю доступную сумму)
    dialog_manager.dialog_data["withdraw_amount"] = float(partner.balance)
    await dialog_manager.switch_to(state=UserPartner.WITHDRAW)


@inject
async def on_withdraw_amount_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Обработка ввода суммы вывода."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if not partner:
        return
    
    partner_settings = await settings_service.get_partner_settings()
    
    try:
        amount = Decimal(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-amount"),
        )
        return
    
    if amount > partner.balance:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-withdraw-insufficient-balance"),
        )
        return
    
    if amount < partner_settings.min_withdrawal:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-withdraw-min-not-reached",
                i18n_kwargs={"min_withdrawal": float(partner_settings.min_withdrawal)},
            ),
        )
        return
    
    dialog_manager.dialog_data["withdraw_amount"] = float(amount)
    await dialog_manager.switch_to(state=UserPartner.WITHDRAW_CONFIRM)


@inject
async def on_withdraw_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение вывода средств."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return
    
    amount = dialog_manager.dialog_data.get("withdraw_amount", 0)
    if amount <= 0:
        return
    
    try:
        withdrawal = await partner_service.create_withdrawal_request(
            partner_id=partner.id,
            amount=Decimal(str(amount)),
        )
        
        if withdrawal:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(
                    i18n_key="ntf-partner-withdraw-request-created",
                ),
            )
            logger.info(
                f"{log(user)} Created withdrawal request for {amount}, "
                f"withdrawal_id={withdrawal.id}"
            )
            # TODO: Отправить уведомление администраторам
            await dialog_manager.switch_to(state=UserPartner.MAIN)
        else:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-partner-withdraw-insufficient-balance"),
            )
    except Exception as e:
        logger.exception(f"Error creating withdrawal request: {e}")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )


@inject
async def on_withdraw_all(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Вывести все доступные средства."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return
    
    partner_settings = await settings_service.get_partner_settings()
    
    if partner.balance < partner_settings.min_withdrawal:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-withdraw-min-not-reached",
                i18n_kwargs={"min_withdrawal": float(partner_settings.min_withdrawal)},
            ),
        )
        return
    
    dialog_manager.dialog_data["withdraw_amount"] = float(partner.balance)
    await dialog_manager.switch_to(state=UserPartner.WITHDRAW_CONFIRM)