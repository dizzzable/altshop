from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.state import State
from aiogram_dialog import BgManagerFactory, ShowMode, StartMode
from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from src.bot.states import MainMenu, Subscription
from src.core.enums import PurchaseType
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.broker import broker
from src.services.user import UserService


async def _mark_user_as_bot_blocked(
    *,
    telegram_id: int,
    user: UserDto | None,
    user_service: UserService,
) -> None:
    if user and not user.is_bot_blocked:
        await user_service.set_bot_blocked(user=user, blocked=True)
        return

    db_user = await user_service.get(telegram_id)
    if db_user and not db_user.is_bot_blocked:
        await user_service.set_bot_blocked(user=db_user, blocked=True)


async def run_dialog_redirect(
    *,
    telegram_id: int,
    state: State,
    bot: Bot,
    bg_manager_factory: BgManagerFactory,
    user_service: UserService,
    data: dict[str, object] | None = None,
) -> None:
    user = await user_service.get(telegram_id)
    if user and user.is_bot_blocked:
        logger.debug(
            "Skip dialog redirect for '{}' to '{}': bot already blocked",
            telegram_id,
            state,
        )
        return

    bg_manager = bg_manager_factory.bg(
        bot=bot,
        user_id=telegram_id,
        chat_id=telegram_id,
    )
    try:
        await bg_manager.start(
            state=state,
            data=data,
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
    except TelegramForbiddenError:
        logger.info(
            "Skip dialog redirect for '{}' to '{}': bot was blocked by the user",
            telegram_id,
            state,
        )
        await _mark_user_as_bot_blocked(
            telegram_id=telegram_id,
            user=user,
            user_service=user_service,
        )


async def run_redirect_to_main_menu(
    *,
    telegram_id: int,
    bot: Bot,
    bg_manager_factory: BgManagerFactory,
    user_service: UserService,
) -> None:
    await run_dialog_redirect(
        telegram_id=telegram_id,
        state=MainMenu.MAIN,
        bot=bot,
        bg_manager_factory=bg_manager_factory,
        user_service=user_service,
    )


@broker.task
@inject(patch_module=True)
async def redirect_to_main_menu_task(
    telegram_id: int,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
    user_service: FromDishka[UserService],
) -> None:
    await run_redirect_to_main_menu(
        telegram_id=telegram_id,
        bot=bot,
        bg_manager_factory=bg_manager_factory,
        user_service=user_service,
    )


@broker.task
@inject(patch_module=True)
async def redirect_to_successed_trial_task(
    user: UserDto,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
    user_service: FromDishka[UserService],
) -> None:
    await run_dialog_redirect(
        telegram_id=user.telegram_id,
        state=Subscription.TRIAL,
        bot=bot,
        bg_manager_factory=bg_manager_factory,
        user_service=user_service,
    )


@broker.task
@inject(patch_module=True)
async def redirect_to_successed_payment_task(
    user: UserDto,
    purchase_type: PurchaseType,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
    user_service: FromDishka[UserService],
) -> None:
    await run_dialog_redirect(
        telegram_id=user.telegram_id,
        state=Subscription.SUCCESS,
        data={"purchase_type": purchase_type},
        bot=bot,
        bg_manager_factory=bg_manager_factory,
        user_service=user_service,
    )


@broker.task
@inject(patch_module=True)
async def redirect_to_failed_subscription_task(
    user: UserDto,
    bot: FromDishka[Bot],
    bg_manager_factory: FromDishka[BgManagerFactory],
    user_service: FromDishka[UserService],
) -> None:
    await run_dialog_redirect(
        telegram_id=user.telegram_id,
        state=Subscription.FAILED,
        bot=bot,
        bg_manager_factory=bg_manager_factory,
        user_service=user_service,
    )
