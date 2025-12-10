import traceback
from typing import Optional, TypedDict, cast

from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Text
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.keyboards import get_user_keyboard
from src.bot.states import Subscription
from src.core.constants import PURCHASE_PREFIX, USER_KEY
from src.core.enums import DeviceType, PaymentGatewayType, PromocodeRewardType, PurchaseType, SubscriptionStatus
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, UserDto
from src.infrastructure.taskiq.tasks.notifications import send_error_notification_task
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.pricing import PricingService
from src.services.promocode import PromocodeService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

PAYMENT_CACHE_KEY = "payment_cache"
CURRENT_DURATION_KEY = "selected_duration"
CURRENT_METHOD_KEY = "selected_payment_method"
CURRENT_DEVICE_TYPE_KEY = "selected_device_type"
SELECTED_DEVICE_TYPES_KEY = "selected_device_types"
SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY = "selected_subscriptions_for_renew"


class CachedPaymentData(TypedDict):
    payment_id: str
    payment_url: Optional[str]
    final_pricing: str


def _get_cache_key(duration: int, gateway_type: PaymentGatewayType) -> str:
    return f"{duration}:{gateway_type.value}"


def _load_payment_data(dialog_manager: DialogManager) -> dict[str, CachedPaymentData]:
    if PAYMENT_CACHE_KEY not in dialog_manager.dialog_data:
        dialog_manager.dialog_data[PAYMENT_CACHE_KEY] = {}
    return cast(dict[str, CachedPaymentData], dialog_manager.dialog_data[PAYMENT_CACHE_KEY])


def _save_payment_data(dialog_manager: DialogManager, payment_data: CachedPaymentData) -> None:
    dialog_manager.dialog_data["payment_id"] = payment_data["payment_id"]
    dialog_manager.dialog_data["payment_url"] = payment_data["payment_url"]
    dialog_manager.dialog_data["final_pricing"] = payment_data["final_pricing"]


async def _create_payment_and_get_data(
    dialog_manager: DialogManager,
    plan: PlanDto,
    duration_days: int,
    gateway_type: PaymentGatewayType,
    payment_gateway_service: PaymentGatewayService,
    notification_service: NotificationService,
    pricing_service: PricingService,
    subscription_service: Optional[SubscriptionService] = None,
    plan_service: Optional["PlanService"] = None,
    device_types: Optional[list[DeviceType]] = None,
) -> Optional[CachedPaymentData]:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    duration = plan.get_duration(duration_days)
    payment_gateway = await payment_gateway_service.get_by_type(gateway_type)
    purchase_type: PurchaseType = dialog_manager.dialog_data["purchase_type"]
    renew_subscription_id: Optional[int] = dialog_manager.dialog_data.get("renew_subscription_id")
    renew_subscription_ids: Optional[list[int]] = dialog_manager.dialog_data.get("renew_subscription_ids")

    if not duration or not payment_gateway:
        logger.error(f"{log(user)} Failed to find duration or gateway for payment creation")
        return None

    # Check subscription limit for NEW purchases
    if purchase_type == PurchaseType.NEW and subscription_service:
        from src.core.enums import SubscriptionStatus
        from src.services.settings import SettingsService  # noqa: PLC0415
        from dishka import AsyncContainer  # noqa: PLC0415
        
        existing_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
        active_count = len([
            s for s in existing_subscriptions
            if s.status != SubscriptionStatus.DELETED
        ])
        
        # Получаем лимит подписок для пользователя
        container: AsyncContainer = dialog_manager.middleware_data["dishka_container"]
        settings_service = await container.get(SettingsService)
        max_subscriptions = await settings_service.get_max_subscriptions_for_user(user)
        
        # -1 означает безлимит
        if max_subscriptions != -1:
            # Check if adding new subscriptions would exceed the limit
            subscription_count = plan.subscription_count
            if active_count + subscription_count > max_subscriptions:
                logger.warning(
                    f"{log(user)} Would exceed max subscriptions limit. "
                    f"Current: {active_count}, Requested: {subscription_count}, Max: {max_subscriptions}"
                )
                await notification_service.notify_user(
                    user=user,
                    payload=MessagePayload(
                        i18n_key="ntf-subscription-limit-exceeded",
                        i18n_kwargs={
                            "current": str(active_count),
                            "max": str(max_subscriptions),
                        },
                    ),
                )
                return None

    transaction_plan = PlanSnapshotDto.from_plan(plan, duration.days)
    
    # Для множественного продления с разными планами - суммируем цены
    if purchase_type == PurchaseType.RENEW and renew_subscription_ids and len(renew_subscription_ids) > 1 and subscription_service and plan_service:
        total_price = 0
        plans = await plan_service.get_available_plans(user)
        
        for sub_id in renew_subscription_ids:
            subscription = await subscription_service.get(sub_id)
            if subscription:
                matched_plan = subscription.find_matching_plan(plans)
                if matched_plan:
                    sub_duration = matched_plan.get_duration(duration_days)
                    if sub_duration:
                        total_price += sub_duration.get_price(payment_gateway.currency)
        
        pricing = pricing_service.calculate(user, total_price, payment_gateway.currency)
        logger.info(f"{log(user)} Calculated total price for {len(renew_subscription_ids)} subscriptions: {total_price}")
    else:
        price = duration.get_price(payment_gateway.currency)
        pricing = pricing_service.calculate(user, price, payment_gateway.currency)

    try:
        result = await payment_gateway_service.create_payment(
            user=user,
            plan=transaction_plan,
            pricing=pricing,
            purchase_type=purchase_type,
            gateway_type=gateway_type,
            renew_subscription_id=renew_subscription_id,
            renew_subscription_ids=renew_subscription_ids,
            device_types=device_types,
        )

        return CachedPaymentData(
            payment_id=str(result.id),
            payment_url=result.url,
            final_pricing=pricing.model_dump_json(),
        )

    except Exception as exception:
        logger.error(f"{log(user)} Failed to create payment: {exception}")
        traceback_str = traceback.format_exc()
        error_type_name = type(exception).__name__
        error_message = Text(str(exception)[:512])

        await send_error_notification_task.kiq(
            error_id=user.telegram_id,
            traceback_str=traceback_str,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-error",
                i18n_kwargs={
                    "user": True,
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "error": f"{error_type_name}: Failed to create payment "
                    + f"check due to error: {error_message.as_html()}",
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )

        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-payment-creation-failed"),
        )
        return None


@inject
async def on_purchase_type_select(
    purchase_type: PurchaseType,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = await payment_gateway_service.filter_active()
    dialog_manager.dialog_data["purchase_type"] = purchase_type
    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)

    if not plans:
        logger.warning(f"{log(user)} No available subscription plans")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-plans-not-available"),
        )
        return

    if not gateways:
        logger.warning(f"{log(user)} No active payment gateways")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-gateways-not-available"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)

    if purchase_type == PurchaseType.RENEW:
        if user.current_subscription:
            matched_plan = user.current_subscription.find_matching_plan(plans)
            logger.debug(f"Matched plan for renewal: '{matched_plan}'")

            if matched_plan:
                adapter.save(matched_plan)
                dialog_manager.dialog_data["only_single_plan"] = True
                await dialog_manager.switch_to(state=Subscription.DURATION)
                return
            else:
                logger.warning(f"{log(user)} Tried to renew, but no matching plan found")
                await notification_service.notify_user(
                    user=user,
                    payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
                )
                return

    if len(plans) == 1:
        logger.info(f"{log(user)} Auto-selected single plan '{plans[0].id}'")
        adapter.save(plans[0])
        dialog_manager.dialog_data["only_single_plan"] = True
        await dialog_manager.switch_to(state=Subscription.DURATION)
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_subscription_plans(  # noqa: C901
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Opened subscription plans menu")

    plans: list[PlanDto] = await plan_service.get_available_plans(user)
    gateways = await payment_gateway_service.filter_active()

    if not callback.data:
        raise ValueError("Callback data is empty")

    purchase_type = PurchaseType(callback.data.removeprefix(PURCHASE_PREFIX))
    dialog_manager.dialog_data["purchase_type"] = purchase_type

    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)

    if not plans:
        logger.warning(f"{log(user)} No available subscription plans")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-plans-not-available"),
        )
        return

    if not gateways:
        logger.warning(f"{log(user)} No active payment gateways")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-gateways-not-available"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)

    if purchase_type == PurchaseType.RENEW:
        # Получаем все подписки пользователя, которые можно продлить
        all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
        renewable_subscriptions = []
        
        for sub in all_subscriptions:
            if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED):
                matched_plan = sub.find_matching_plan(plans)
                if matched_plan and not sub.is_unlimited:
                    renewable_subscriptions.append((sub, matched_plan))
        
        if not renewable_subscriptions:
            logger.warning(f"{log(user)} No renewable subscriptions found")
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
            )
            return
        
        # Если только одна подписка для продления - сразу переходим к выбору длительности
        if len(renewable_subscriptions) == 1:
            sub, matched_plan = renewable_subscriptions[0]
            adapter.save(matched_plan)
            dialog_manager.dialog_data["only_single_plan"] = True
            dialog_manager.dialog_data["renew_subscription_id"] = sub.id
            # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
            dialog_manager.dialog_data["renew_subscription_ids"] = None
            dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [sub.id]
            # Очищаем кэш платежей для новой подписки
            dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
            await dialog_manager.switch_to(state=Subscription.DURATION)
            return
        
        # Если несколько подписок - показываем экран выбора подписок для продления
        # Сбрасываем ранее выбранные подписки
        dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = []
        # Сбрасываем renew_subscription_ids и renew_subscription_id чтобы избежать использования старых данных
        dialog_manager.dialog_data["renew_subscription_ids"] = None
        dialog_manager.dialog_data["renew_subscription_id"] = None
        # Очищаем кэш платежей
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
        # Устанавливаем режим множественного выбора (корзина)
        dialog_manager.dialog_data["renew_single_select_mode"] = False
        await dialog_manager.switch_to(state=Subscription.SELECT_SUBSCRIPTION_FOR_RENEW)
        return

    if len(plans) == 1:
        logger.info(f"{log(user)} Auto-selected single plan '{plans[0].id}'")
        adapter.save(plans[0])
        dialog_manager.dialog_data["only_single_plan"] = True

        if len(plans[0].durations) == 1:
            logger.info(f"{log(user)} Auto-selected duration '{plans[0].durations[0].days}'")
            dialog_manager.dialog_data["selected_duration"] = plans[0].durations[0].days
            dialog_manager.dialog_data["only_single_duration"] = True

            # Для новых и дополнительных подписок переходим к выбору устройства
            if purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
                # Сбрасываем ранее выбранные устройства
                dialog_manager.dialog_data.pop("selected_device_types", None)
                await dialog_manager.switch_to(state=Subscription.DEVICE_TYPE)
                return

            if len(gateways) == 1:
                logger.info(f"{log(user)} Auto-selected payment method '{gateways[0].type}'")
                dialog_manager.dialog_data["selected_payment_method"] = gateways[0].type
                dialog_manager.dialog_data["only_single_payment_method"] = True

                payment_data = await _create_payment_and_get_data(
                    dialog_manager=dialog_manager,
                    plan=plans[0],
                    duration_days=plans[0].durations[0].days,
                    gateway_type=gateways[0].type,
                    payment_gateway_service=payment_gateway_service,
                    notification_service=notification_service,
                    pricing_service=pricing_service,
                    subscription_service=subscription_service,
                )

                if payment_data:
                    _save_payment_data(dialog_manager, payment_data)

                await dialog_manager.switch_to(state=Subscription.CONFIRM)
                return

            await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)
            return

        await dialog_manager.switch_to(state=Subscription.DURATION)
        return

    dialog_manager.dialog_data["only_single_plan"] = False
    dialog_manager.dialog_data["only_single_duration"] = False
    await dialog_manager.switch_to(state=Subscription.PLANS)


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan: int,
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plan = await plan_service.get(plan_id=selected_plan)

    if not plan:
        raise ValueError(f"Selected plan '{selected_plan}' not found")

    logger.info(f"{log(user)} Selected plan '{plan.id}'")
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(plan)

    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
    dialog_manager.dialog_data.pop(CURRENT_DURATION_KEY, None)
    dialog_manager.dialog_data.pop(CURRENT_METHOD_KEY, None)

    if len(plan.durations) == 1:
        logger.info(f"{log(user)} Auto-selected single duration '{plan.durations[0].days}'")
        dialog_manager.dialog_data["only_single_duration"] = True
        await on_duration_select(callback, widget, dialog_manager, plan.durations[0].days)
        return

    await dialog_manager.switch_to(state=Subscription.DURATION)


@inject
async def on_duration_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_duration: int,
    settings_service: FromDishka[SettingsService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription duration '{selected_duration}' days")
    dialog_manager.dialog_data[CURRENT_DURATION_KEY] = selected_duration

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    gateways = await payment_gateway_service.filter_active()
    currency = await settings_service.get_default_currency()
    
    # Для множественного продления с разными планами - суммируем цены
    purchase_type = dialog_manager.dialog_data.get("purchase_type")
    renew_subscription_ids = dialog_manager.dialog_data.get("renew_subscription_ids")
    
    if purchase_type == PurchaseType.RENEW and renew_subscription_ids and len(renew_subscription_ids) > 1:
        total_price = 0
        plans = await plan_service.get_available_plans(user)
        
        for sub_id in renew_subscription_ids:
            subscription = await subscription_service.get(sub_id)
            if subscription:
                matched_plan = subscription.find_matching_plan(plans)
                if matched_plan:
                    sub_duration = matched_plan.get_duration(selected_duration)
                    if sub_duration:
                        total_price += sub_duration.get_price(currency)
        
        price = pricing_service.calculate(user, total_price, currency)
        logger.info(f"{log(user)} Calculated total price for {len(renew_subscription_ids)} subscriptions: {total_price}")
    else:
        price = pricing_service.calculate(
            user=user,
            price=plan.get_duration(selected_duration).get_price(currency),  # type: ignore[union-attr]
            currency=currency,
        )
    dialog_manager.dialog_data["is_free"] = price.is_free

    # Для новых и дополнительных подписок переходим к выбору устройства
    if purchase_type in (PurchaseType.NEW, PurchaseType.ADDITIONAL):
        # Сбрасываем ранее выбранные устройства
        dialog_manager.dialog_data.pop(SELECTED_DEVICE_TYPES_KEY, None)
        await dialog_manager.switch_to(state=Subscription.DEVICE_TYPE)
        return

    # Для продления и изменения - сразу к оплате
    if len(gateways) == 1 or price.is_free:
        selected_payment_method = gateways[0].type
        dialog_manager.dialog_data[CURRENT_METHOD_KEY] = selected_payment_method

        cache = _load_payment_data(dialog_manager)
        cache_key = _get_cache_key(selected_duration, selected_payment_method)

        if cache_key in cache:
            logger.info(f"{log(user)} Re-selected same duration and single gateway")
            _save_payment_data(dialog_manager, cache[cache_key])
            await dialog_manager.switch_to(state=Subscription.CONFIRM)
            return

        logger.info(f"{log(user)} Auto-selected single gateway '{selected_payment_method}'")

        payment_data = await _create_payment_and_get_data(
            dialog_manager=dialog_manager,
            plan=plan,
            duration_days=selected_duration,
            gateway_type=selected_payment_method,
            payment_gateway_service=payment_gateway_service,
            notification_service=notification_service,
            pricing_service=pricing_service,
            subscription_service=subscription_service,
            plan_service=plan_service,
        )

        if payment_data:
            cache[cache_key] = payment_data
            _save_payment_data(dialog_manager, payment_data)
            await dialog_manager.switch_to(state=Subscription.CONFIRM)
            return

    dialog_manager.dialog_data.pop(CURRENT_METHOD_KEY, None)
    await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)


@inject
async def on_payment_method_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_payment_method: PaymentGatewayType,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected payment method '{selected_payment_method}'")

    selected_duration = dialog_manager.dialog_data[CURRENT_DURATION_KEY]
    dialog_manager.dialog_data[CURRENT_METHOD_KEY] = selected_payment_method
    cache = _load_payment_data(dialog_manager)
    cache_key = _get_cache_key(selected_duration, selected_payment_method)

    if cache_key in cache:
        logger.info(f"{log(user)} Re-selected same method and duration")
        _save_payment_data(dialog_manager, cache[cache_key])
        await dialog_manager.switch_to(state=Subscription.CONFIRM)
        return

    logger.info(f"{log(user)} New combination. Creating new payment")

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    # Получаем выбранные устройства для новых подписок
    selected_devices = dialog_manager.dialog_data.get(SELECTED_DEVICE_TYPES_KEY, [])
    device_types_for_payment = [DeviceType(dt) for dt in selected_devices] if selected_devices else None
    
    payment_data = await _create_payment_and_get_data(
        dialog_manager=dialog_manager,
        plan=plan,
        duration_days=selected_duration,
        gateway_type=selected_payment_method,
        payment_gateway_service=payment_gateway_service,
        notification_service=notification_service,
        pricing_service=pricing_service,
        subscription_service=subscription_service,
        plan_service=plan_service,
        device_types=device_types_for_payment,
    )

    if payment_data:
        cache[cache_key] = payment_data
        _save_payment_data(dialog_manager, payment_data)

    # Переходим к подтверждению (выбор устройства уже был сделан ранее для NEW)
    await dialog_manager.switch_to(state=Subscription.CONFIRM)


@inject
async def on_get_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    payment_id = dialog_manager.dialog_data["payment_id"]
    logger.info(f"{log(user)} Getted free subscription '{payment_id}'")
    await payment_gateway_service.handle_payment_succeeded(payment_id)


@inject
async def on_promocode_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка ввода промокода пользователем"""
    if not message.text:
        return
    
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    code = message.text.strip().upper()
    
    logger.info(f"{log(user)} Attempting to activate promocode '{code}'")
    
    # Сначала валидируем промокод без активации
    validation_result = await promocode_service.validate_promocode(code, user)
    
    if not validation_result.success:
        # Ошибка валидации
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=validation_result.message_key or "ntf-promocode-error",
            ),
        )
        return
    
    promocode = validation_result.promocode
    if not promocode:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-promocode-not-found"),
        )
        return
    
    # Для промокодов типа SUBSCRIPTION проверяем активные подписки
    if promocode.reward_type == PromocodeRewardType.SUBSCRIPTION:
        # Получаем все активные подписки пользователя
        all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
        active_subscriptions = [
            s for s in all_subscriptions
            if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
            and not s.is_unlimited
        ]
        
        if active_subscriptions:
            # Есть активные подписки - сохраняем промокод и переходим к выбору
            dialog_manager.dialog_data["pending_promocode_code"] = code
            dialog_manager.dialog_data["pending_promocode_days"] = promocode.plan.duration if promocode.plan else 30
            dialog_manager.dialog_data["pending_promocode_reward_type"] = promocode.reward_type.value
            await dialog_manager.switch_to(Subscription.PROMOCODE_SELECT_SUBSCRIPTION)
            return
        else:
            # Нет активных подписок - сохраняем промокод и переходим к подтверждению создания новой
            dialog_manager.dialog_data["pending_promocode_code"] = code
            dialog_manager.dialog_data["pending_promocode_plan_name"] = promocode.plan.name if promocode.plan else "Подписка"
            dialog_manager.dialog_data["pending_promocode_days"] = promocode.plan.duration if promocode.plan else 30
            await dialog_manager.switch_to(Subscription.PROMOCODE_CONFIRM_NEW)
            return
    
    # Для промокодов типа DURATION проверяем активные подписки
    if promocode.reward_type == PromocodeRewardType.DURATION:
        # Получаем все активные подписки пользователя
        all_subscriptions = await subscription_service.get_all_by_user(user.telegram_id)
        active_subscriptions = [
            s for s in all_subscriptions
            if s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED, SubscriptionStatus.LIMITED)
            and not s.is_unlimited
        ]
        
        if not active_subscriptions:
            # Нет активных подписок - нельзя применить промокод на дни
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-promocode-no-subscription-for-duration"),
            )
            return
        
        if len(active_subscriptions) > 1:
            # Несколько подписок - даём выбор
            dialog_manager.dialog_data["pending_promocode_code"] = code
            dialog_manager.dialog_data["pending_promocode_days"] = promocode.reward or 0
            dialog_manager.dialog_data["pending_promocode_reward_type"] = promocode.reward_type.value
            await dialog_manager.switch_to(Subscription.PROMOCODE_SELECT_SUBSCRIPTION)
            return
        # Если только одна подписка - активируем сразу на неё
        # (продолжаем выполнение ниже)
    
    # Для остальных типов промокодов - активируем сразу
    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
    )
    
    if result.success and result.promocode:
        # Успешная активация
        activated_promocode = result.promocode
        
        # Формируем сообщение об успехе в зависимости от типа награды
        reward_info = ""
        if activated_promocode.reward_type == PromocodeRewardType.DURATION:
            reward_info = f"{activated_promocode.reward} дней"
        elif activated_promocode.reward_type == PromocodeRewardType.TRAFFIC:
            reward_info = f"{activated_promocode.reward} ГБ трафика"
        elif activated_promocode.reward_type == PromocodeRewardType.DEVICES:
            reward_info = f"{activated_promocode.reward} устройств"
        elif activated_promocode.reward_type == PromocodeRewardType.PERSONAL_DISCOUNT:
            reward_info = f"{activated_promocode.reward}% персональная скидка"
        elif activated_promocode.reward_type == PromocodeRewardType.PURCHASE_DISCOUNT:
            reward_info = f"{activated_promocode.reward}% скидка на покупку"
        
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=result.message_key or "ntf-promocode-activated",
                i18n_kwargs={
                    "code": activated_promocode.code,
                    "reward_type": activated_promocode.reward_type.value,
                    "reward": reward_info,
                },
            ),
        )
        
        await dialog_manager.switch_to(Subscription.MAIN)
    else:
        # Ошибка активации
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=result.message_key or "ntf-promocode-error",
            ),
        )


@inject
async def on_promocode_select_subscription(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка выбора подписки для добавления дней от промокода (SUBSCRIPTION или DURATION)"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    code = dialog_manager.dialog_data.get("pending_promocode_code")
    reward_type_str = dialog_manager.dialog_data.get("pending_promocode_reward_type")
    
    if not code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        await dialog_manager.switch_to(Subscription.MAIN)
        return
    
    logger.info(f"{log(user)} Selected subscription '{selected_subscription}' for promocode '{code}' (type: {reward_type_str})")
    
    # Активируем промокод с указанием подписки для добавления дней
    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
        target_subscription_id=selected_subscription,
    )
    
    # Очищаем временные данные
    dialog_manager.dialog_data.pop("pending_promocode_code", None)
    dialog_manager.dialog_data.pop("pending_promocode_days", None)
    dialog_manager.dialog_data.pop("pending_promocode_reward_type", None)
    
    if result.success and result.promocode:
        promocode = result.promocode
        
        # Определяем количество дней в зависимости от типа промокода
        if promocode.reward_type == PromocodeRewardType.DURATION:
            days = promocode.reward or 0
        else:
            # SUBSCRIPTION type
            days = promocode.plan.duration if promocode.plan else 0
        
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-promocode-activated-subscription-extended",
                i18n_kwargs={
                    "code": promocode.code,
                    "days": str(days),
                },
            ),
        )
        
        await dialog_manager.switch_to(Subscription.MAIN)
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=result.message_key or "ntf-promocode-error",
            ),
        )


@inject
async def on_promocode_create_new_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Подтверждение создания новой подписки от промокода"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    code = dialog_manager.dialog_data.get("pending_promocode_code")
    
    if not code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        await dialog_manager.switch_to(Subscription.MAIN)
        return
    
    logger.info(f"{log(user)} Confirmed creating new subscription from promocode '{code}'")
    
    # Активируем промокод (создаст новую подписку)
    result = await promocode_service.activate(
        code=code,
        user=user,
        user_service=user_service,
        subscription_service=subscription_service,
    )
    
    # Очищаем временные данные
    dialog_manager.dialog_data.pop("pending_promocode_code", None)
    dialog_manager.dialog_data.pop("pending_promocode_plan_name", None)
    dialog_manager.dialog_data.pop("pending_promocode_days", None)
    
    if result.success and result.promocode:
        promocode = result.promocode
        
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-promocode-activated-subscription",
                i18n_kwargs={
                    "code": promocode.code,
                    "plan_name": promocode.plan.name if promocode.plan else "Подписка",
                },
            ),
        )
        
        await dialog_manager.switch_to(Subscription.SUCCESS)
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=result.message_key or "ntf-promocode-error",
            ),
        )


@inject
async def on_subscription_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
) -> None:
    """Обработка выбора подписки из списка"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription '{selected_subscription}'")
    
    # Get the index from items
    items = dialog_manager.dialog_data.get("_subscriptions_items", [])
    subscription_index = 1
    for idx, item in enumerate(items):
        if item.get("id") == selected_subscription:
            subscription_index = idx + 1
            break
    
    dialog_manager.dialog_data["selected_subscription_id"] = selected_subscription
    dialog_manager.dialog_data["selected_subscription_index"] = subscription_index
    await dialog_manager.switch_to(Subscription.SUBSCRIPTION_DETAILS)


@inject
async def on_renew_selected_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    """Продление выбранной подписки"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("selected_subscription_id")
    
    if not subscription_id:
        return
    
    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    # Найти план для продления
    plans = await plan_service.get_available_plans(user)
    matched_plan = subscription.find_matching_plan(plans)
    
    if not matched_plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
        )
        return
    
    # Сохраняем план и переходим к выбору длительности
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(matched_plan)
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data["only_single_plan"] = True
    dialog_manager.dialog_data["renew_subscription_id"] = subscription_id
    # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [subscription_id]
    # Очищаем кэш платежей для новой подписки
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
    
    await dialog_manager.switch_to(Subscription.DURATION)


@inject
async def on_delete_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переход на окно подтверждения удаления подписки"""
    await dialog_manager.switch_to(Subscription.CONFIRM_DELETE)


@inject
async def on_confirm_delete_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение удаления подписки"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("selected_subscription_id")
    
    if not subscription_id:
        return
    
    from src.services.remnawave import RemnawaveService  # noqa: PLC0415
    from dishka import AsyncContainer  # noqa: PLC0415
    
    container: AsyncContainer = dialog_manager.middleware_data["dishka_container"]
    remnawave_service = await container.get(RemnawaveService)
    
    subscription = await subscription_service.get(subscription_id)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    # Удаляем пользователя из Remnawave
    if subscription.user_remna_id:
        try:
            await remnawave_service.remnawave.users.delete_user(
                uuid=str(subscription.user_remna_id)
            )
            logger.info(f"{log(user)} Deleted RemnaUser '{subscription.user_remna_id}' from panel")
        except Exception as e:
            logger.error(f"{log(user)} Failed to delete RemnaUser from panel: {e}")
    
    # Помечаем подписку как удаленную
    result = await subscription_service.delete_subscription(subscription_id)
    
    if result:
        logger.info(f"{log(user)} Deleted subscription '{subscription_id}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-deleted"),
        )
        
        # Если это была текущая подписка, нужно обновить current_subscription
        if user.current_subscription and user.current_subscription.id == subscription_id:
            # Найти другую активную подписку
            all_subs = await subscription_service.get_all_by_user(user.telegram_id)
            active_subs = [s for s in all_subs if s.status != SubscriptionStatus.DELETED and s.id != subscription_id]
            
            from src.services.user import UserService  # noqa: PLC0415
            user_service = await container.get(UserService)
            
            if active_subs:
                await user_service.set_current_subscription(user.telegram_id, active_subs[0].id)
            else:
                await user_service.set_current_subscription(user.telegram_id, None)
    else:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
    
    # Возвращаемся к списку подписок
    await dialog_manager.switch_to(Subscription.MY_SUBSCRIPTIONS)


@inject
async def on_cancel_delete_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Отмена удаления подписки - возврат к деталям"""
    await dialog_manager.switch_to(Subscription.SUBSCRIPTION_DETAILS)


@inject
async def on_subscription_for_renew_toggle(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    plan_service: FromDishka[PlanService],
) -> None:
    """Обработка переключения выбора подписки для продления (множественный или одиночный выбор)"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    
    # Проверяем режим одиночного выбора
    single_select_mode = dialog_manager.dialog_data.get("renew_single_select_mode", False)
    
    if single_select_mode:
        # Режим одиночного выбора - сразу переходим к продлению выбранной подписки
        logger.info(f"{log(user)} Selected single subscription for renewal '{selected_subscription}'")
        
        subscription = await subscription_service.get(selected_subscription)
        if not subscription:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
            )
            return
        
        # Найти план для продления
        plans = await plan_service.get_available_plans(user)
        matched_plan = subscription.find_matching_plan(plans)
        
        if not matched_plan:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
            )
            return
        
        # Сохраняем план и переходим к выбору длительности
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(matched_plan)
        dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
        dialog_manager.dialog_data["only_single_plan"] = True
        dialog_manager.dialog_data["renew_subscription_id"] = selected_subscription
        # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
        dialog_manager.dialog_data["renew_subscription_ids"] = None
        dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [selected_subscription]
        # Очищаем кэш платежей, так как выбрана новая подписка для продления
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
        
        await dialog_manager.switch_to(Subscription.DURATION)
        return
    
    # Режим множественного выбора (toggle)
    # Получаем текущий список выбранных подписок
    selected_subscriptions = dialog_manager.dialog_data.get(SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY, [])
    
    if selected_subscription in selected_subscriptions:
        # Убираем из выбора
        selected_subscriptions.remove(selected_subscription)
        logger.info(f"{log(user)} Deselected subscription for renewal '{selected_subscription}'")
    else:
        # Добавляем в выбор
        selected_subscriptions.append(selected_subscription)
        logger.info(f"{log(user)} Selected subscription for renewal '{selected_subscription}'")
    
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = selected_subscriptions


@inject
async def on_confirm_renew_selection(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Подтверждение выбора подписок для продления"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    selected_subscriptions = dialog_manager.dialog_data.get(SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY, [])
    
    if not selected_subscriptions:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-select-at-least-one"),
        )
        return
    
    logger.info(f"{log(user)} Confirmed renewal for subscriptions: {selected_subscriptions}")
    
    # Получаем все выбранные подписки и их планы
    plans = await plan_service.get_available_plans(user)
    subscriptions_with_plans = []
    
    for sub_id in selected_subscriptions:
        subscription = await subscription_service.get(sub_id)
        if subscription:
            matched_plan = subscription.find_matching_plan(plans)
            if matched_plan:
                subscriptions_with_plans.append((subscription, matched_plan))
    
    if not subscriptions_with_plans:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
        )
        return
    
    # Сохраняем информацию о выбранных подписках
    dialog_manager.dialog_data["subscriptions_for_renew"] = [
        {"id": sub.id, "plan_id": plan.id} for sub, plan in subscriptions_with_plans
    ]
    
    # Если все подписки имеют одинаковый план, используем его
    # Иначе нужно будет обрабатывать каждую подписку отдельно
    unique_plans = list(set(plan.id for _, plan in subscriptions_with_plans))
    
    if len(unique_plans) == 1:
        # Все подписки имеют одинаковый план
        _, matched_plan = subscriptions_with_plans[0]
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(matched_plan)
        dialog_manager.dialog_data["only_single_plan"] = True
        dialog_manager.dialog_data["renew_subscription_ids"] = selected_subscriptions
        # Для обратной совместимости сохраняем первую подписку
        dialog_manager.dialog_data["renew_subscription_id"] = selected_subscriptions[0]
        # Очищаем кэш платежей для новых подписок
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
        await dialog_manager.switch_to(Subscription.DURATION)
    else:
        # Разные планы - используем первый план как базовый, но цена будет суммироваться
        # при создании платежа на основе плана каждой подписки
        _, first_plan = subscriptions_with_plans[0]
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(first_plan)
        dialog_manager.dialog_data["only_single_plan"] = True  # Скрываем выбор плана
        dialog_manager.dialog_data["renew_subscription_ids"] = selected_subscriptions
        dialog_manager.dialog_data["renew_subscription_id"] = selected_subscriptions[0]
        # Очищаем кэш платежей для новых подписок
        dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
        # Переходим к выбору длительности - цена будет рассчитана с учётом всех планов
        await dialog_manager.switch_to(Subscription.DURATION)


@inject
async def on_subscription_for_renew_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Обработка выбора подписки для продления (одиночный выбор - для обратной совместимости)"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected subscription for renewal '{selected_subscription}'")
    
    subscription = await subscription_service.get(selected_subscription)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return
    
    # Найти план для продления
    plans = await plan_service.get_available_plans(user)
    matched_plan = subscription.find_matching_plan(plans)
    
    if not matched_plan:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-subscription-renew-plan-unavailable"),
        )
        return
    
    # Сохраняем план и переходим к выбору длительности
    adapter = DialogDataAdapter(dialog_manager)
    adapter.save(matched_plan)
    dialog_manager.dialog_data["purchase_type"] = PurchaseType.RENEW
    dialog_manager.dialog_data["only_single_plan"] = True
    dialog_manager.dialog_data["renew_subscription_id"] = selected_subscription
    # Очищаем renew_subscription_ids чтобы использовалось одиночное продление
    dialog_manager.dialog_data["renew_subscription_ids"] = None
    dialog_manager.dialog_data[SELECTED_SUBSCRIPTIONS_FOR_RENEW_KEY] = [selected_subscription]
    # Очищаем кэш платежей для новой подписки
    dialog_manager.dialog_data.pop(PAYMENT_CACHE_KEY, None)
    
    await dialog_manager.switch_to(Subscription.DURATION)


@inject
async def on_device_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_device_type: DeviceType,
    settings_service: FromDishka[SettingsService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    """Обработка выбора типа устройства"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected device type '{selected_device_type}'")
    
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)
    
    if not plan:
        raise ValueError("PlanDto not found in dialog data")
    
    subscription_count = plan.subscription_count
    
    # Получаем или инициализируем список выбранных устройств
    selected_devices = dialog_manager.dialog_data.get(SELECTED_DEVICE_TYPES_KEY, [])
    
    # Добавляем выбранное устройство
    selected_devices.append(selected_device_type.value)
    dialog_manager.dialog_data[SELECTED_DEVICE_TYPES_KEY] = selected_devices
    
    # Если выбрано достаточно устройств, переходим к выбору метода оплаты
    if len(selected_devices) >= subscription_count:
        selected_duration = dialog_manager.dialog_data[CURRENT_DURATION_KEY]
        gateways = await payment_gateway_service.filter_active()
        currency = await settings_service.get_default_currency()
        price = pricing_service.calculate(
            user=user,
            price=plan.get_duration(selected_duration).get_price(currency),  # type: ignore[union-attr]
            currency=currency,
        )
        is_free = price.is_free
        dialog_manager.dialog_data["is_free"] = is_free
        
        # Если только один шлюз или бесплатно - автовыбор и переход к подтверждению
        if len(gateways) == 1 or is_free:
            selected_payment_method = gateways[0].type
            dialog_manager.dialog_data[CURRENT_METHOD_KEY] = selected_payment_method
            
            cache = _load_payment_data(dialog_manager)
            cache_key = _get_cache_key(selected_duration, selected_payment_method)
            
            if cache_key in cache:
                logger.info(f"{log(user)} Re-selected same duration and single gateway")
                _save_payment_data(dialog_manager, cache[cache_key])
                await dialog_manager.switch_to(state=Subscription.CONFIRM)
                return
            
            logger.info(f"{log(user)} Auto-selected single gateway '{selected_payment_method}'")
            
            # Преобразуем строки в DeviceType для передачи в платёж
            device_types_for_payment = [DeviceType(dt) for dt in selected_devices]
            
            payment_data = await _create_payment_and_get_data(
                dialog_manager=dialog_manager,
                plan=plan,
                duration_days=selected_duration,
                gateway_type=selected_payment_method,
                payment_gateway_service=payment_gateway_service,
                notification_service=notification_service,
                pricing_service=pricing_service,
                subscription_service=subscription_service,
                device_types=device_types_for_payment,
            )
            
            if payment_data:
                cache[cache_key] = payment_data
                _save_payment_data(dialog_manager, payment_data)
                await dialog_manager.switch_to(state=Subscription.CONFIRM)
                return
        
        # Иначе переходим к выбору метода оплаты
        await dialog_manager.switch_to(state=Subscription.PAYMENT_METHOD)
    # Иначе остаемся на экране выбора устройства для следующей подписки
