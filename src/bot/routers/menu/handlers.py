from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode, SubManager
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.keyboards import CALLBACK_CHANNEL_CONFIRM, CALLBACK_RULES_ACCEPT
from src.bot.states import MainMenu
from src.core.constants import REFERRAL_PREFIX, USER_KEY
from src.core.enums import MediaType, PointsExchangeType
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PlanSnapshotDto, UserDto
from src.infrastructure.taskiq.tasks.subscriptions import trial_subscription_task
from src.services.notification import NotificationService
from src.services.plan import PlanService
from src.services.promocode import PromocodeService
from src.services.referral import ReferralService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

router = Router(name=__name__)


async def on_start_dialog(
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    logger.info(f"{log(user)} Started dialog")
    await dialog_manager.start(
        state=MainMenu.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@inject
@router.message(CommandStart(ignore_case=True))
async def on_start_command(
    message: Message,
    command: CommandObject,
    user: UserDto,
    is_new_user: bool,
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
) -> None:
    if command.args and command.args.startswith(REFERRAL_PREFIX) and is_new_user:
        referral_code = command.args
        logger.info(f"Start with referral code: '{referral_code}'")
        await referral_service.handle_referral(user, referral_code)

    await on_start_dialog(user, dialog_manager)


@router.callback_query(F.data == CALLBACK_RULES_ACCEPT)
async def on_rules_accept(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    logger.info(f"{log(user)} Accepted rules")
    await on_start_dialog(user, dialog_manager)


@router.callback_query(F.data == CALLBACK_CHANNEL_CONFIRM)
async def on_channel_confirm(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
) -> None:
    logger.info(f"{log(user)} Cofirmed join channel")
    await on_start_dialog(user, dialog_manager)


@inject
async def on_get_trial(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plan = await plan_service.get_trial_plan()

    if not plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-trial-unavailable"),
        )
        raise ValueError("Trial plan not exist")

    trial = PlanSnapshotDto.from_plan(plan, plan.durations[0].days)
    await trial_subscription_task.kiq(user, trial)




@inject
async def show_reason(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    status = user.current_subscription.status if user.current_subscription else False

    await callback.answer(
        text=i18n.get("ntf-connect-not-available", status=status),
        show_alert=True,
    )


@inject
async def on_show_qr(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    ref_link = await referral_service.get_ref_link(user.referral_code)
    ref_qr = referral_service.get_ref_qr(ref_link)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="",
            media=ref_qr,
            media_type=MediaType.PHOTO,
        ),
    )


@inject
async def on_withdraw_points(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    await callback.answer(
        text=i18n.get("ntf-invite-withdraw-points-error"),
        show_alert=True,
    )


@inject
async def on_go_to_exchange(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переход на экран обмена с главного меню"""
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE)


@inject
async def on_exchange_points(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переход к выбору подписки для обмена баллов"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    # Проверяем, что у пользователя есть баллы
    if user.points <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_POINTS)


@inject
async def on_exchange_points_select_subscription(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор подписки для обмена баллов"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    subscription = await subscription_service.get(selected_subscription)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    # Сохраняем выбранную подписку
    dialog_manager.dialog_data["exchange_subscription_id"] = selected_subscription
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_POINTS_CONFIRM)


@inject
async def on_exchange_points_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    user_service: FromDishka[UserService],
    remnawave_service: FromDishka[RemnawaveService],
    notification_service: FromDishka[NotificationService],
    settings_service: FromDishka[SettingsService],
) -> None:
    """Подтверждение обмена баллов на дни подписки"""
    from datetime import timedelta
    from src.core.utils.time import datetime_now
    
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("exchange_subscription_id")
    
    if not subscription_id:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return
    
    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    # Получаем настройки обмена баллов
    referral_settings = await settings_service.get_referral_settings()
    exchange_settings = referral_settings.points_exchange
    
    # Проверяем, включен ли обмен
    if not exchange_settings.exchange_enabled:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-disabled"),
        )
        return
    
    points_to_exchange = user.points
    
    # Проверяем минимальное количество баллов
    if points_to_exchange < exchange_settings.min_exchange_points:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-exchange-points-min",
                i18n_kwargs={"min_points": str(exchange_settings.min_exchange_points)},
            ),
        )
        return
    
    # Применяем максимальный лимит, если установлен
    if exchange_settings.max_exchange_points > 0:
        points_to_exchange = min(points_to_exchange, exchange_settings.max_exchange_points)
    
    # Рассчитываем количество дней по курсу обмена
    days_to_add = exchange_settings.calculate_days(points_to_exchange)
    
    # Пересчитываем фактическое количество баллов для списания (кратное курсу)
    points_to_exchange = exchange_settings.calculate_points_needed(days_to_add)
    
    if days_to_add <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    # Добавляем дни к подписке
    base_expire_at = max(subscription.expire_at, datetime_now())
    new_expire = base_expire_at + timedelta(days=days_to_add)
    subscription.expire_at = new_expire
    
    await subscription_service.update(subscription)
    
    # Обновляем в Remnawave
    await remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )
    
    # Списываем баллы
    await user_service.add_points(user=user, points=-points_to_exchange)
    
    logger.info(
        f"{log(user)} Exchanged {points_to_exchange} points for {days_to_add} days "
        f"on subscription {subscription_id} (rate: {exchange_settings.points_per_day} points/day)"
    )
    
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-exchange-points-success",
            i18n_kwargs={
                "points": str(points_to_exchange),
                "days": str(days_to_add),
            },
        ),
    )
    
    # Возвращаемся в экран обмена
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE)


@inject
async def on_exchange_select_type(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: str,
) -> None:
    """Выбор типа обмена баллов."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    exchange_type = PointsExchangeType(selected_type)
    dialog_manager.dialog_data["selected_exchange_type"] = selected_type
    
    logger.info(f"{log(user)} Selected exchange type: {exchange_type}")
    
    # Переходим к соответствующему экрану
    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_POINTS)
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_GIFT)
    elif exchange_type == PointsExchangeType.DISCOUNT:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_DISCOUNT)
    elif exchange_type == PointsExchangeType.TRAFFIC:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_TRAFFIC)


@inject
async def on_exchange_gift_select_plan(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan_id: int,
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор плана для подарочной подписки."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    plan = await plan_service.get(selected_plan_id)
    if not plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-gift-no-plan"),
        )
        return
    
    # Сохраняем выбранный план
    dialog_manager.dialog_data["gift_selected_plan_id"] = selected_plan_id
    dialog_manager.dialog_data["gift_selected_plan_name"] = plan.name
    
    logger.info(f"{log(user)} Selected plan for gift subscription: {plan.name} (id={selected_plan_id})")
    
    # Переходим к подтверждению
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_GIFT_CONFIRM)


@inject
async def on_exchange_gift_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение обмена баллов на подарочную подписку (промокод)."""
    from src.core.enums import PromocodeRewardType, PromocodeAvailability
    import secrets
    import string
    
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    # Получаем настройки
    referral_settings = await settings_service.get_referral_settings()
    gift_settings = referral_settings.points_exchange.gift_subscription
    
    # Проверяем, что у пользователя достаточно баллов
    if user.points < gift_settings.min_points:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    # Получаем выбранный план из dialog_data
    selected_plan_id = dialog_manager.dialog_data.get("gift_selected_plan_id")
    
    # Проверяем, что план выбран
    if not selected_plan_id:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-gift-no-plan"),
        )
        return
    
    plan = await plan_service.get(selected_plan_id)
    if not plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-gift-no-plan"),
        )
        return
    
    # Генерируем уникальный код промокода
    code_chars = string.ascii_uppercase + string.digits
    promocode_code = "GIFT_" + "".join(secrets.choice(code_chars) for _ in range(8))
    
    # Создаем промокод типа SUBSCRIPTION
    from src.infrastructure.database.models.dto import PromocodeDto
    
    promocode = PromocodeDto(
        code=promocode_code,
        reward_type=PromocodeRewardType.SUBSCRIPTION,
        availability=PromocodeAvailability.ALL,
        reward=gift_settings.gift_duration_days,
        lifetime=-1,  # Бессрочный
        max_activations=1,  # Одноразовый
        is_active=True,
        plan_id=selected_plan_id,  # Используем выбранный план
        plan_duration_days=gift_settings.gift_duration_days,
    )
    
    # Сохраняем промокод
    created_promocode = await promocode_service.create(promocode)
    
    # Списываем баллы
    await user_service.add_points(user=user, points=-gift_settings.points_cost)
    
    logger.info(
        f"{log(user)} Exchanged {gift_settings.points_cost} points for gift subscription promocode: {promocode_code} (plan: {plan.name})"
    )
    
    # Сохраняем данные для отображения
    dialog_manager.dialog_data["gift_promocode"] = promocode_code
    dialog_manager.dialog_data["gift_plan_name"] = plan.name
    dialog_manager.dialog_data["gift_duration_days"] = gift_settings.gift_duration_days
    
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_GIFT_SUCCESS)


@inject
async def on_exchange_discount_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение обмена баллов на скидку."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    # Получаем настройки
    referral_settings = await settings_service.get_referral_settings()
    discount_settings = referral_settings.points_exchange.discount
    
    # Проверяем, что у пользователя достаточно баллов
    if user.points < discount_settings.min_points:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    # Рассчитываем скидку
    discount_percent = referral_settings.points_exchange.calculate_discount(user.points)
    points_to_spend = discount_percent * discount_settings.points_cost
    
    if discount_percent <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    # Добавляем скидку на следующую покупку
    # Используем purchase_discount поле пользователя
    current_discount = user.purchase_discount or 0
    new_discount = min(current_discount + discount_percent, 100)  # Максимум 100%
    
    await user_service.set_purchase_discount(user=user, discount=new_discount)
    
    # Списываем баллы
    await user_service.add_points(user=user, points=-points_to_spend)
    
    logger.info(
        f"{log(user)} Exchanged {points_to_spend} points for {discount_percent}% discount"
    )
    
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-exchange-discount-success",
            i18n_kwargs={
                "points": str(points_to_spend),
                "discount": str(discount_percent),
            },
        ),
    )
    
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE)


@inject
async def on_exchange_traffic_select_subscription(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор подписки для добавления трафика."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    subscription = await subscription_service.get(selected_subscription)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    dialog_manager.dialog_data["traffic_subscription_id"] = selected_subscription
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_TRAFFIC_CONFIRM)


@inject
async def on_exchange_traffic_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    user_service: FromDishka[UserService],
    remnawave_service: FromDishka[RemnawaveService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение обмена баллов на трафик."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("traffic_subscription_id")
    
    if not subscription_id:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return
    
    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    # Получаем настройки
    referral_settings = await settings_service.get_referral_settings()
    traffic_settings = referral_settings.points_exchange.traffic
    
    # Проверяем, что у пользователя достаточно баллов
    if user.points < traffic_settings.min_points:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    # Рассчитываем трафик
    traffic_gb = referral_settings.points_exchange.calculate_traffic_gb(user.points)
    points_to_spend = traffic_gb * traffic_settings.points_cost
    
    if traffic_gb <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return
    
    # Добавляем трафик к подписке (в байтах)
    traffic_bytes = traffic_gb * 1024 * 1024 * 1024  # ГБ в байты
    current_limit = subscription.traffic_limit or 0
    new_limit = current_limit + traffic_bytes
    
    subscription.traffic_limit = new_limit
    await subscription_service.update(subscription)
    
    # Обновляем в Remnawave
    await remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )
    
    # Списываем баллы
    await user_service.add_points(user=user, points=-points_to_spend)
    
    logger.info(
        f"{log(user)} Exchanged {points_to_spend} points for {traffic_gb} GB traffic "
        f"on subscription {subscription_id}"
    )
    
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-exchange-traffic-success",
            i18n_kwargs={
                "points": str(points_to_spend),
                "traffic": str(traffic_gb),
            },
        ),
    )
    
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE)


@inject
async def on_invite(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
) -> None:
    if await settings_service.is_referral_enable():
        await dialog_manager.switch_to(state=MainMenu.INVITE)
    else:
        return


@inject
async def on_connect_device_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
    subscription_service: FromDishka[SubscriptionService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """
    Обработчик выбора устройства для подключения.
    Сохраняет данные и переключается на окно с URL.
    """
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    # Get subscription by ID
    subscription_id = int(item_id)
    subscription = await subscription_service.get(subscription_id)
    
    if not subscription:
        await callback.answer(
            text=i18n.get("ntf-subscription-not-found"),
            show_alert=True,
        )
        return
    
    # Save subscription data for the URL window
    dialog_manager.dialog_data["selected_subscription_id"] = subscription_id
    dialog_manager.dialog_data["selected_subscription_url"] = subscription.url
    dialog_manager.dialog_data["selected_subscription_plan_name"] = subscription.plan.name if subscription.plan else "Подписка"
    
    logger.info(f"{log(user)} Selected device for connection: subscription_id={subscription_id}")
    
    # Switch to URL window
    await dialog_manager.switch_to(state=MainMenu.CONNECT_DEVICE_URL)
