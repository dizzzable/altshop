from typing import Any, cast

from aiogram import F, Router
from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager, ShowMode, StartMode
from dishka import FromDishka
from dishka.integrations.aiogram import inject as aiogram_inject
from loguru import logger

from src.bot.routers.subscription.handlers import on_purchase_type_select
from src.bot.states import DashboardUser, Subscription, state_from_string
from src.core.constants import GOTO_PREFIX, PURCHASE_PREFIX
from src.core.enums import PurchaseType
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto
from src.services.notification import NotificationService
from src.services.payment_gateway import PaymentGatewayService
from src.services.plan import PlanService
from src.services.subscription_purchase import SubscriptionPurchaseService

router = Router(name=__name__)


async def _start_purchase_flow(
    *,
    dialog_manager: DialogManager,
    purchase_type: PurchaseType,
    plan_service: PlanService,
    payment_gateway_service: PaymentGatewayService,
    notification_service: NotificationService,
    subscription_purchase_service: SubscriptionPurchaseService,
) -> None:
    await dialog_manager.start(
        state=Subscription.MAIN,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
    await cast(Any, on_purchase_type_select)(
        purchase_type=purchase_type,
        dialog_manager=dialog_manager,
        plan_service=plan_service,
        payment_gateway_service=payment_gateway_service,
        notification_service=notification_service,
        subscription_purchase_service=subscription_purchase_service,
    )


async def _handle_goto(
    callback: CallbackQuery,
    dialog_manager: DialogManager,
    user: UserDto,
    plan_service: PlanService,
    payment_gateway_service: PaymentGatewayService,
    notification_service: NotificationService,
    subscription_purchase_service: SubscriptionPurchaseService,
) -> None:
    logger.info(f"{log(user)} Go to '{callback.data}'")
    data = callback.data.removeprefix(GOTO_PREFIX)

    if data.startswith(PURCHASE_PREFIX):
        try:
            purchase_type = PurchaseType(data.removeprefix(PURCHASE_PREFIX))
        except ValueError:
            logger.warning(f"{log(user)} Trying go to invalid purchase type '{data}'")
            await callback.answer()
            return

        await _start_purchase_flow(
            dialog_manager=dialog_manager,
            purchase_type=purchase_type,
            plan_service=plan_service,
            payment_gateway_service=payment_gateway_service,
            notification_service=notification_service,
            subscription_purchase_service=subscription_purchase_service,
        )
        await callback.answer()
        return

    state = state_from_string(data)

    if not state:
        logger.warning(f"{log(user)} Trying go to not exist state '{data}'")
        await callback.answer()
        return

    if state == DashboardUser.MAIN:
        parts = data.split(":")

        try:
            target_telegram_id = int(parts[2])
        except ValueError:
            logger.warning(f"{log(user)} Invalid target_telegram_id in callback: {parts[2]}")

        await dialog_manager.bg(
            user_id=user.telegram_id,
            chat_id=user.telegram_id,
        ).start(
            state=DashboardUser.MAIN,
            data={"target_telegram_id": target_telegram_id},
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
        logger.debug(f"{log(user)} Redirected to user '{target_telegram_id}'")
        await callback.answer()
        return

    logger.debug(f"{log(user)} Redirected to '{state}'")
    await dialog_manager.bg(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
    ).start(
        state=state,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(GOTO_PREFIX))
@aiogram_inject
async def on_goto(
    callback: CallbackQuery,
    dialog_manager: DialogManager,
    user: UserDto,
    plan_service: FromDishka[PlanService],
    payment_gateway_service: FromDishka[PaymentGatewayService],
    notification_service: FromDishka[NotificationService],
    subscription_purchase_service: FromDishka[SubscriptionPurchaseService],
) -> None:
    await _handle_goto(
        callback=callback,
        dialog_manager=dialog_manager,
        user=user,
        plan_service=plan_service,
        payment_gateway_service=payment_gateway_service,
        notification_service=notification_service,
        subscription_purchase_service=subscription_purchase_service,
    )
