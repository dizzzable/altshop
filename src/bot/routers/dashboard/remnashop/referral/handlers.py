from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.bot.states import RemnashopReferral
from src.core.constants import USER_KEY
from src.core.enums import (
    PointsExchangeType,
    ReferralAccrualStrategy,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.plan import PlanService
from src.services.settings import SettingsService


@inject
async def on_enable_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    settings = await settings_service.get()
    settings.referral.enable = not settings.referral.enable
    await settings_service.update(settings)

    logger.info(
        f"{log(user)} Successfully toggled referral system status to '{settings.referral.enable}'"
    )


@inject
async def on_level_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_level: int,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected referral level '{selected_level}'")

    settings = await settings_service.get()
    settings.referral.level = ReferralLevel(selected_level)
    config: dict[ReferralLevel, int] = settings.referral.reward.config

    for lvl in ReferralLevel:
        if lvl.value <= selected_level and lvl not in config:
            prev_value = config.get(ReferralLevel(lvl.value - 1), 0)
            config[lvl] = prev_value

    settings.referral.reward.config = config
    await settings_service.update(settings)

    logger.info(f"{log(user)} Successfully updated referral level to '{selected_level}'")
    await dialog_manager.switch_to(state=RemnashopReferral.MAIN)


@inject
async def on_reward_select(
    callback: CallbackQuery,
    widget: Select[ReferralRewardType],
    dialog_manager: DialogManager,
    selected_reward: ReferralRewardType,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected referral reward '{selected_reward}'")

    settings = await settings_service.get()
    settings.referral.reward.type = selected_reward
    await settings_service.update(settings)

    logger.info(f"{log(user)} Successfully updated referral reward to '{selected_reward}'")
    await dialog_manager.switch_to(state=RemnashopReferral.MAIN)


@inject
async def on_accrual_strategy_select(
    callback: CallbackQuery,
    widget: Select[ReferralAccrualStrategy],
    dialog_manager: DialogManager,
    selected_strategy: ReferralAccrualStrategy,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected referral accrual strategy '{selected_strategy}'")

    settings = await settings_service.get()
    settings.referral.accrual_strategy = selected_strategy
    await settings_service.update(settings)

    logger.info(
        f"{log(user)} Successfully updated referral accrual strategy to '{selected_strategy}'"
    )
    await dialog_manager.switch_to(state=RemnashopReferral.MAIN)


@inject
async def on_reward_strategy_select(
    callback: CallbackQuery,
    widget: Select[ReferralRewardStrategy],
    dialog_manager: DialogManager,
    selected_strategy: ReferralRewardStrategy,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected referral reward strategy '{selected_strategy}'")

    settings = await settings_service.get()
    settings.referral.reward.strategy = selected_strategy
    await settings_service.update(settings)

    logger.info(
        f"{log(user)} Successfully updated referral reward strategy to '{selected_strategy}'"
    )
    await dialog_manager.switch_to(state=RemnashopReferral.MAIN)


@inject
async def on_reward_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-referral-invalid-reward"),
        )
        return

    settings = await settings_service.get()
    config: dict[ReferralLevel, int] = settings.referral.reward.config

    if text.isdigit():
        value = int(text)
        config[ReferralLevel.FIRST] = value
    else:
        try:
            for pair in text.split():
                lvl_str, val_str = pair.split("=")
                lvl = ReferralLevel(int(lvl_str.strip()))
                val = int(val_str.strip())
                config[lvl] = val
        except Exception:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-referral-invalid-reward"),
            )
            return

    settings.referral.reward.config = config
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated referral reward: {settings.referral.reward}")


@inject
async def on_eligible_plan_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
    settings_service: FromDishka[SettingsService],
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Toggled eligible plan '{selected_plan_id}'")

    settings = await settings_service.get()
    eligible_plan_ids: list[int] = settings.referral.eligible_plan_ids.copy()

    if selected_plan_id in eligible_plan_ids:
        eligible_plan_ids.remove(selected_plan_id)
        logger.info(f"{log(user)} Removed plan '{selected_plan_id}' from eligible plans")
    else:
        eligible_plan_ids.append(selected_plan_id)
        logger.info(f"{log(user)} Added plan '{selected_plan_id}' to eligible plans")

    settings.referral.eligible_plan_ids = eligible_plan_ids
    await settings_service.update(settings)


@inject
async def on_clear_eligible_plans(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Clearing eligible plans filter")

    settings = await settings_service.get()
    settings.referral.eligible_plan_ids = []
    await settings_service.update(settings)

    logger.info(f"{log(user)} Cleared eligible plans filter - rewards now apply to all plans")


@inject
async def on_exchange_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Переключение статуса обмена баллов."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    settings = await settings_service.get()
    settings.referral.points_exchange.exchange_enabled = not settings.referral.points_exchange.exchange_enabled
    await settings_service.update(settings)

    logger.info(
        f"{log(user)} Toggled points exchange status to "
        f"'{settings.referral.points_exchange.exchange_enabled}'"
    )


@inject
async def on_points_per_day_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода курса обмена баллов."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    value = int(text)
    settings = await settings_service.get()
    settings.referral.points_exchange.points_per_day = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated points per day to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.POINTS_EXCHANGE)


@inject
async def on_min_exchange_points_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода минимального количества баллов для обмена."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) < 1:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    value = int(text)
    settings = await settings_service.get()
    settings.referral.points_exchange.min_exchange_points = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated min exchange points to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.POINTS_EXCHANGE)


@inject
async def on_max_exchange_points_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода максимального количества баллов для обмена."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    # Поддержка -1 для отключения лимита
    try:
        value = int(text)
        if value < -1 or value == 0:
            raise ValueError("Invalid value")
    except ValueError:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    settings = await settings_service.get()
    settings.referral.points_exchange.max_exchange_points = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated max exchange points to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.POINTS_EXCHANGE)


@inject
async def on_exchange_type_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_type: str,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Выбор типа обмена для настройки."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected exchange type '{selected_type}'")
    
    dialog_manager.dialog_data["selected_exchange_type"] = selected_type
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_exchange_type_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Переключение статуса типа обмена."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    exchange_type_str = dialog_manager.dialog_data.get("selected_exchange_type")
    if not exchange_type_str:
        return
    
    exchange_type = PointsExchangeType(exchange_type_str)
    settings = await settings_service.get()
    exchange = settings.referral.points_exchange
    
    # Получаем настройки для типа и переключаем
    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        exchange.subscription_days.enabled = not exchange.subscription_days.enabled
        new_status = exchange.subscription_days.enabled
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        exchange.gift_subscription.enabled = not exchange.gift_subscription.enabled
        new_status = exchange.gift_subscription.enabled
    elif exchange_type == PointsExchangeType.DISCOUNT:
        exchange.discount.enabled = not exchange.discount.enabled
        new_status = exchange.discount.enabled
    elif exchange_type == PointsExchangeType.TRAFFIC:
        exchange.traffic.enabled = not exchange.traffic.enabled
        new_status = exchange.traffic.enabled
    else:
        return
    
    await settings_service.update(settings)
    logger.info(f"{log(user)} Toggled exchange type '{exchange_type}' to '{new_status}'")


@inject
async def on_exchange_type_cost_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода стоимости в баллах для типа обмена."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    value = int(text)
    exchange_type_str = dialog_manager.dialog_data.get("selected_exchange_type")
    if not exchange_type_str:
        return
    
    exchange_type = PointsExchangeType(exchange_type_str)
    settings = await settings_service.get()
    exchange = settings.referral.points_exchange
    
    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        exchange.subscription_days.points_cost = value
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        exchange.gift_subscription.points_cost = value
    elif exchange_type == PointsExchangeType.DISCOUNT:
        exchange.discount.points_cost = value
    elif exchange_type == PointsExchangeType.TRAFFIC:
        exchange.traffic.points_cost = value
    
    await settings_service.update(settings)
    logger.info(f"{log(user)} Updated exchange type '{exchange_type}' cost to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_exchange_type_min_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода минимального количества баллов для типа обмена."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) < 1:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    value = int(text)
    exchange_type_str = dialog_manager.dialog_data.get("selected_exchange_type")
    if not exchange_type_str:
        return
    
    exchange_type = PointsExchangeType(exchange_type_str)
    settings = await settings_service.get()
    exchange = settings.referral.points_exchange
    
    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        exchange.subscription_days.min_points = value
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        exchange.gift_subscription.min_points = value
    elif exchange_type == PointsExchangeType.DISCOUNT:
        exchange.discount.min_points = value
    elif exchange_type == PointsExchangeType.TRAFFIC:
        exchange.traffic.min_points = value
    
    await settings_service.update(settings)
    logger.info(f"{log(user)} Updated exchange type '{exchange_type}' min points to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_exchange_type_max_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода максимального количества баллов для типа обмена."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    try:
        value = int(text)
        if value < -1 or value == 0:
            raise ValueError("Invalid value")
    except ValueError:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    exchange_type_str = dialog_manager.dialog_data.get("selected_exchange_type")
    if not exchange_type_str:
        return
    
    exchange_type = PointsExchangeType(exchange_type_str)
    settings = await settings_service.get()
    exchange = settings.referral.points_exchange
    
    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        exchange.subscription_days.max_points = value
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        exchange.gift_subscription.max_points = value
    elif exchange_type == PointsExchangeType.DISCOUNT:
        exchange.discount.max_points = value
    elif exchange_type == PointsExchangeType.TRAFFIC:
        exchange.traffic.max_points = value
    
    await settings_service.update(settings)
    logger.info(f"{log(user)} Updated exchange type '{exchange_type}' max points to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_gift_plan_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
    settings_service: FromDishka[SettingsService],
) -> None:
    """Выбор плана для подарочной подписки."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected gift plan '{selected_plan_id}'")

    settings = await settings_service.get()
    settings.referral.points_exchange.gift_subscription.gift_plan_id = selected_plan_id
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated gift subscription plan to '{selected_plan_id}'")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_gift_duration_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода длительности подарочной подписки."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    value = int(text)
    settings = await settings_service.get()
    settings.referral.points_exchange.gift_subscription.gift_duration_days = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated gift subscription duration to '{value}' days")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_discount_max_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода максимального процента скидки."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) <= 0 or int(text) > 100:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-percent"),
        )
        return

    value = int(text)
    settings = await settings_service.get()
    settings.referral.points_exchange.discount.max_discount_percent = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated max discount percent to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)


@inject
async def on_traffic_max_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Обработка ввода максимального количества ГБ трафика."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    text = message.text

    if not text or not text.isdigit() or int(text) <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-points-exchange-invalid-value"),
        )
        return

    value = int(text)
    settings = await settings_service.get()
    settings.referral.points_exchange.traffic.max_traffic_gb = value
    await settings_service.update(settings)

    logger.info(f"{log(user)} Updated max traffic GB to '{value}'")
    await dialog_manager.switch_to(state=RemnashopReferral.EXCHANGE_TYPE_SETTINGS)
