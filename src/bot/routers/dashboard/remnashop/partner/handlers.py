from uuid import UUID

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import RemnashopPartner
from src.core.constants import USER_KEY
from src.core.enums import WithdrawalStatus
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.settings import SettingsService
from src.services.user import UserService


@inject
async def on_enable_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Переключение статуса партнерской программы."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    settings = await settings_service.get()
    settings.partner.enabled = not settings.partner.enabled
    await settings_service.update(settings)

    logger.info(
        f"{log(user)} Toggled partner program status to '{settings.partner.enabled}'"
    )


@inject
async def on_level_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_level: int,
) -> None:
    """Выбор уровня для редактирования процента."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected partner level '{selected_level}' for editing")
    
    dialog_manager.dialog_data["selected_level"] = selected_level
    await dialog_manager.switch_to(state=RemnashopPartner.LEVEL_1_PERCENT)


@inject
async def on_level_percent_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода процента для уровня."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text
    
    level = dialog_manager.dialog_data.get("selected_level", 1)

    if not text or not text.replace(".", "", 1).isdigit():
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent"),
        )
        return

    value = float(text)
    
    if value < 0 or value > 100:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent"),
        )
        return

    settings = await settings_service.get()
    
    if level == 1:
        settings.partner.level1_percent = value
    elif level == 2:
        settings.partner.level2_percent = value
    elif level == 3:
        settings.partner.level3_percent = value
    
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated partner level {level} percent to '{value}'")
    await dialog_manager.switch_to(state=RemnashopPartner.LEVEL_PERCENTS)


@inject
async def on_tax_percent_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода процента налога."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.replace(".", "", 1).isdigit():
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent"),
        )
        return

    value = float(text)
    
    if value < 0 or value > 100:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent"),
        )
        return

    settings = await settings_service.get()
    settings.partner.tax_percent = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated partner tax percent to '{value}'")
    await dialog_manager.switch_to(state=RemnashopPartner.MAIN)


@inject
async def on_gateway_fee_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_gateway: str,
) -> None:
    """Выбор платежной системы для редактирования комиссии."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected gateway '{selected_gateway}' for fee editing")
    
    dialog_manager.dialog_data["selected_gateway"] = selected_gateway
    await dialog_manager.switch_to(state=RemnashopPartner.GATEWAY_FEE_EDIT)


@inject
async def on_gateway_fee_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода комиссии для платежной системы."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text
    
    gateway_key = dialog_manager.dialog_data.get("selected_gateway", "")

    if not text or not text.replace(".", "", 1).isdigit():
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent"),
        )
        return

    value = float(text)
    
    if value < 0 or value > 100:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent"),
        )
        return

    settings = await settings_service.get()
    
    gateway_attr_map = {
        "yookassa": "yookassa_commission",
        "telegram_stars": "telegram_stars_commission",
        "cryptopay": "cryptopay_commission",
        "heleket": "heleket_commission",
        "pal24": "pal24_commission",
        "wata": "wata_commission",
        "platega": "platega_commission",
    }
    
    attr_name = gateway_attr_map.get(gateway_key)
    if attr_name:
        setattr(settings.partner, attr_name, value)
        await settings_service.update(settings)
        logger.info(f"{log(user)} Updated gateway '{gateway_key}' fee to '{value}'")
    
    await dialog_manager.switch_to(state=RemnashopPartner.GATEWAY_FEES)


@inject
async def on_min_withdrawal_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода минимальной суммы вывода."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.replace(".", "", 1).isdigit():
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-amount"),
        )
        return

    value = float(text)
    
    if value < 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-amount"),
        )
        return

    settings = await settings_service.get()
    # Пользователь вводит в рублях, сохраняем в копейках
    settings.partner.min_withdrawal_amount = int(value * 100)
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated min withdrawal amount to '{value}' rubles")
    await dialog_manager.switch_to(state=RemnashopPartner.MAIN)


@inject
async def on_status_filter_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_status: str,
) -> None:
    """Выбор фильтра по статусу для списка выводов."""
    if selected_status == "all":
        dialog_manager.dialog_data["status_filter"] = None
    else:
        dialog_manager.dialog_data["status_filter"] = WithdrawalStatus(selected_status)


@inject
async def on_withdrawal_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_withdrawal: str,
) -> None:
    """Выбор запроса на вывод для просмотра деталей."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected withdrawal '{selected_withdrawal}' for details")
    
    dialog_manager.dialog_data["selected_withdrawal_id"] = selected_withdrawal
    await dialog_manager.switch_to(state=RemnashopPartner.WITHDRAWAL_DETAILS)


@inject
async def on_withdrawal_approve(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    user_service: FromDishka[UserService],
) -> None:
    """Одобрение запроса на вывод (✅ Выполнено)."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    withdrawal_id = dialog_manager.dialog_data.get("selected_withdrawal_id")
    
    if not withdrawal_id:
        return
    
    # Получаем информацию о выводе и партнере до одобрения
    withdrawal = await partner_service.get_withdrawal(UUID(withdrawal_id))
    if not withdrawal:
        return
    
    partner = await partner_service.get_partner(withdrawal.partner_id)
    
    success = await partner_service.approve_withdrawal(
        withdrawal_id=UUID(withdrawal_id),
        admin_telegram_id=user.telegram_id,
    )
    
    if success:
        # Уведомляем админа
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-withdrawal-approved"),
        )
        logger.info(f"{log(user)} Approved withdrawal '{withdrawal_id}'")
        
        # Уведомляем партнера о выполнении
        if partner:
            partner_user = await user_service.get(telegram_id=partner.user_telegram_id)
            if partner_user:
                await notification_service.notify_user(
                    user=partner_user,
                    payload=MessagePayload(
                        i18n_key="ntf-partner-withdrawal-completed",
                        i18n_kwargs={"amount": withdrawal.amount_rubles},
                    ),
                )
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-withdrawal-error"),
        )
    
    await dialog_manager.switch_to(state=RemnashopPartner.WITHDRAWALS_LIST)


@inject
async def on_withdrawal_pending(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    user_service: FromDishka[UserService],
) -> None:
    """Установка статуса 'На рассмотрении' (💭)."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    withdrawal_id = dialog_manager.dialog_data.get("selected_withdrawal_id")
    
    if not withdrawal_id:
        return
    
    # Получаем информацию о выводе и партнере
    withdrawal = await partner_service.get_withdrawal(UUID(withdrawal_id))
    if not withdrawal:
        return
    
    partner = await partner_service.get_partner(withdrawal.partner_id)
    
    # Уведомляем админа
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-partner-withdrawal-pending-set"),
    )
    logger.info(f"{log(user)} Set withdrawal '{withdrawal_id}' as pending review")
    
    # Уведомляем партнера о рассмотрении
    if partner:
        partner_user = await user_service.get(telegram_id=partner.user_telegram_id)
        if partner_user:
            await notification_service.notify_user(
                user=partner_user,
                payload=MessagePayload(
                    i18n_key="ntf-partner-withdrawal-under-review",
                    i18n_kwargs={"amount": withdrawal.amount_rubles},
                ),
            )
    
    await dialog_manager.switch_to(state=RemnashopPartner.WITHDRAWALS_LIST)


@inject
async def on_withdrawal_reject(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
    user_service: FromDishka[UserService],
) -> None:
    """Отклонение запроса на вывод (🚫 Отказано)."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    withdrawal_id = dialog_manager.dialog_data.get("selected_withdrawal_id")
    admin_comment = dialog_manager.dialog_data.get("admin_comment", "")
    
    if not withdrawal_id:
        return
    
    # Получаем информацию о выводе и партнере до отклонения
    withdrawal = await partner_service.get_withdrawal(UUID(withdrawal_id))
    if not withdrawal:
        return
    
    partner = await partner_service.get_partner(withdrawal.partner_id)
    
    success = await partner_service.reject_withdrawal(
        withdrawal_id=UUID(withdrawal_id),
        admin_telegram_id=user.telegram_id,
        reason=admin_comment or "Отклонено администратором",
    )
    
    if success:
        # Уведомляем админа
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-withdrawal-rejected"),
        )
        logger.info(f"{log(user)} Rejected withdrawal '{withdrawal_id}'")
        
        # Уведомляем партнера об отклонении
        if partner:
            partner_user = await user_service.get(telegram_id=partner.user_telegram_id)
            if partner_user:
                await notification_service.notify_user(
                    user=partner_user,
                    payload=MessagePayload(
                        i18n_key="ntf-partner-withdrawal-rejected-user",
                        i18n_kwargs={
                            "amount": withdrawal.amount_rubles,
                            "reason": admin_comment or "Отклонено администратором",
                        },
                    ),
                )
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-withdrawal-error"),
        )
    
    await dialog_manager.switch_to(state=RemnashopPartner.WITHDRAWALS_LIST)


@inject
async def on_admin_comment_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    """Сохранение комментария администратора."""
    dialog_manager.show_mode = ShowMode.EDIT
    dialog_manager.dialog_data["admin_comment"] = message.text or ""