from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery
from dishka import FromDishka
from loguru import logger

from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import UserDto
from src.services.payment_gateway import PaymentGatewayService

router = Router(name=__name__)


@router.pre_checkout_query()
async def on_pre_checkout(pre_checkout_query: PreCheckoutQuery, user: UserDto) -> None:
    logger.info(f"{log(user)} Initiated a pre-checkout query")
    if pre_checkout_query.invoice_payload:
        await pre_checkout_query.answer(ok=True)
    else:
        logger.warning(f"{log(user)} Pre-checkout query rejected: empty payload")
        await pre_checkout_query.answer(ok=False)


@router.message(F.successful_payment)
async def on_successful_payment(
    message: Message,
    user: UserDto,
    bot: Bot,
    payment_gateway_service: FromDishka[PaymentGatewayService],
) -> None:
    payment = message.successful_payment

    if not payment:
        return

    if user.is_dev:
        logger.info(f"{log(user)} Refunding test payment '{payment.telegram_payment_charge_id}'")
        await bot.refund_star_payment(
            user_id=user.telegram_id,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
        )

    await payment_gateway_service.handle_payment_succeeded(payment_id=UUID(payment.invoice_payload))
