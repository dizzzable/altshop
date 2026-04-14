from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_dialog import DialogManager, ShowMode, StartMode
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram import inject as aiogram_inject
from dishka.integrations.aiogram_dialog import inject as dialog_inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.api.utils.web_app_urls import build_web_app_route_url, build_web_settings_url
from src.bot.keyboards import CALLBACK_CHANNEL_CONFIRM, CALLBACK_RULES_ACCEPT
from src.bot.states import MainMenu, UserPartner
from src.core.config import AppConfig
from src.core.constants import REFERRAL_PREFIX, USER_KEY
from src.core.enums import MediaType, PointsExchangeType, PurchaseChannel, ReferralInviteSource
from src.core.utils.bot_menu import (
    BOT_MENU_URL_KIND_WEB_APP,
    resolve_bot_menu_launch_target,
)
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.taskiq.tasks.subscriptions import trial_subscription_task
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.plan import PlanService
from src.services.purchase_access import PurchaseAccessError
from src.services.referral import INVITE_BLOCK_REASON_EXHAUSTED, ReferralService
from src.services.referral_exchange import (
    ReferralExchangeError,
    ReferralExchangeService,
)
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.subscription_trial import SubscriptionTrialService
from src.services.telegram_link import TelegramLinkError, TelegramLinkService
from src.services.user import UserService

router = Router(name=__name__)

_TG_LINK_START_PREFIX = "tglink_"
_TG_LINK_START_MINIAPP_PREFIX = "tglinkapp_"
_TG_LINK_CONFIRM_PREFIX = "tglnk_ok:"
_TG_LINK_CONFIRM_MINIAPP_PREFIX = "tglnk_ok_app:"
_TG_LINK_CANCEL_PREFIX = "tglnk_no:"
_TG_LINK_CANCEL_MINIAPP_PREFIX = "tglnk_no_app:"


def _is_russian_user(user: UserDto) -> bool:
    return str(getattr(user.language, "value", user.language) or "").lower().startswith("ru")


def _tg_link_copy(user: UserDto, key: str) -> str:
    is_ru = _is_russian_user(user)
    translations = {
        "prompt": (
            "Подтвердить привязку этого Telegram-аккаунта к веб-профилю?\n\n"
            "Нажмите «Привязать», чтобы завершить подтверждение."
            if is_ru
            else "Link this Telegram account to your web profile?\n\n"
            "Press “Link account” to finish confirmation."
        ),
        "confirm": "Привязать" if is_ru else "Link account",
        "cancel": "Отмена" if is_ru else "Cancel",
        "success": (
            "Telegram-аккаунт успешно привязан. Вернитесь в настройки, профиль уже можно обновить."
            if is_ru
            else "Telegram account linked successfully. Return to settings to refresh the profile."
        ),
        "cancelled": (
            "Подтверждение привязки отменено."
            if is_ru
            else "Link confirmation was cancelled."
        ),
        "invalid": (
            "Ссылка подтверждения недействительна или уже использована."
            if is_ru
            else "Confirmation link is invalid or already used."
        ),
        "merge_conflict": (
            "Автоматически завершить привязку не удалось. "
            "Откройте настройки и повторите привязку через веб-профиль."
            if is_ru
            else "Automatic linking could not be completed. "
            "Open settings and retry the link flow from the web profile."
        ),
        "return": "Открыть настройки" if is_ru else "Open settings",
    }
    return translations[key]


def _extract_tg_link_token_and_mode(value: str) -> tuple[str, bool]:
    if value.startswith(_TG_LINK_START_MINIAPP_PREFIX):
        return value.removeprefix(_TG_LINK_START_MINIAPP_PREFIX).strip(), True
    if value.startswith(_TG_LINK_CONFIRM_MINIAPP_PREFIX):
        return value.removeprefix(_TG_LINK_CONFIRM_MINIAPP_PREFIX).strip(), True
    if value.startswith(_TG_LINK_CANCEL_MINIAPP_PREFIX):
        return value.removeprefix(_TG_LINK_CANCEL_MINIAPP_PREFIX).strip(), True
    if value.startswith(_TG_LINK_START_PREFIX):
        return value.removeprefix(_TG_LINK_START_PREFIX).strip(), False
    if value.startswith(_TG_LINK_CONFIRM_PREFIX):
        return value.removeprefix(_TG_LINK_CONFIRM_PREFIX).strip(), False
    if value.startswith(_TG_LINK_CANCEL_PREFIX):
        return value.removeprefix(_TG_LINK_CANCEL_PREFIX).strip(), False
    return value.strip(), False


async def _build_telegram_link_return_url(
    config: AppConfig,
    settings_service: SettingsService,
    *,
    telegram_link: str,
    telegram_id: int,
    return_to_miniapp: bool,
) -> tuple[str, bool]:
    if return_to_miniapp:
        settings = await settings_service.get()
        mini_app_url, _source, launch_kind = resolve_bot_menu_launch_target(
            bot_menu=settings.bot_menu,
            config=config,
        )
        if mini_app_url and launch_kind == BOT_MENU_URL_KIND_WEB_APP:
            return (
                build_web_app_route_url(
                    mini_app_url,
                    f"/dashboard/settings?telegram_link={telegram_link}&telegram_id={telegram_id}",
                ),
                True,
            )

    return (
        build_web_settings_url(
        config,
        telegram_link=telegram_link,
        telegram_id=telegram_id,
        ),
        False,
    )


def _build_tg_link_confirmation_keyboard(
    user: UserDto,
    token: str,
    *,
    return_to_miniapp: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    confirm_prefix = (
        _TG_LINK_CONFIRM_MINIAPP_PREFIX if return_to_miniapp else _TG_LINK_CONFIRM_PREFIX
    )
    cancel_prefix = (
        _TG_LINK_CANCEL_MINIAPP_PREFIX if return_to_miniapp else _TG_LINK_CANCEL_PREFIX
    )
    builder.row(
        InlineKeyboardButton(
            text=_tg_link_copy(user, "confirm"),
            callback_data=f"{confirm_prefix}{token}",
        ),
        InlineKeyboardButton(
            text=_tg_link_copy(user, "cancel"),
            callback_data=f"{cancel_prefix}{token}",
        ),
    )
    return builder.as_markup()


def _build_tg_link_result_keyboard(
    user: UserDto,
    return_url: str | None,
    *,
    use_web_app_button: bool = False,
) -> InlineKeyboardMarkup | None:
    if not return_url:
        return None

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_tg_link_copy(user, "return"),
            web_app=WebAppInfo(url=return_url) if use_web_app_button else None,
            url=return_url if not use_web_app_button else None,
        ),
    )
    return builder.as_markup()


async def _notify_exchange_error(
    *,
    user: UserDto,
    notification_service: NotificationService,
    error: ReferralExchangeError,
) -> None:
    if error.code in {"EXCHANGE_DISABLED", "EXCHANGE_TYPE_DISABLED"}:
        payload = MessagePayload(i18n_key="ntf-exchange-points-disabled")
    elif error.code in {"PLAN_REQUIRED", "PLAN_NOT_FOUND"}:
        payload = MessagePayload(i18n_key="ntf-exchange-gift-no-plan")
    elif error.code in {
        "SUBSCRIPTION_REQUIRED",
        "SUBSCRIPTION_NOT_FOUND",
        "SUBSCRIPTION_NOT_ELIGIBLE",
    }:
        payload = MessagePayload(i18n_key="ntf-user-subscription-empty")
    elif error.code in {"NOT_ENOUGH_POINTS", "INVALID_POINTS_COST"}:
        payload = MessagePayload(i18n_key="ntf-exchange-points-no-points")
    else:
        payload = MessagePayload(i18n_key="ntf-error")

    await notification_service.notify_user(user=user, payload=payload)


def _resolve_trial_notification_key(reason_code: str | None) -> str:
    mapping = {
        "TRIAL_ALREADY_USED": "ntf-trial-already-used",
        "TRIAL_NOT_FIRST_SUBSCRIPTION": "ntf-trial-existing-subscription",
        "TRIAL_TELEGRAM_LINK_REQUIRED": "ntf-trial-telegram-link-required",
        "TRIAL_PLAN_NOT_CONFIGURED": "ntf-trial-plan-not-configured",
        "TRIAL_PLAN_NOT_FOUND": "ntf-trial-plan-not-found",
        "TRIAL_PLAN_NOT_TRIAL": "ntf-trial-plan-not-trial",
        "TRIAL_PLAN_INACTIVE": "ntf-trial-plan-inactive",
        "TRIAL_PLAN_NO_DURATION": "ntf-trial-plan-no-duration",
    }
    return mapping.get(reason_code, "ntf-trial-unavailable")


async def on_start_dialog(
    user: UserDto,
    dialog_manager: DialogManager,
    user_service: UserService,
) -> None:
    logger.info(f"{log(user)} Started dialog")
    if user.is_bot_blocked:
        logger.debug(
            "Skip direct MainMenu start for '{}': bot already blocked",
            user.telegram_id,
        )
        return

    try:
        await dialog_manager.start(
            state=MainMenu.MAIN,
            mode=StartMode.RESET_STACK,
            show_mode=ShowMode.DELETE_AND_SEND,
        )
    except TelegramForbiddenError:
        logger.info(
            "Skip direct MainMenu start for '{}': bot was blocked by the user",
            user.telegram_id,
        )
        if not user.is_bot_blocked:
            await user_service.set_bot_blocked(user=user, blocked=True)


@router.message(CommandStart(ignore_case=True))
@aiogram_inject
async def on_start_command(
    message: Message,
    command: CommandObject,
    user: UserDto,
    is_new_user: bool,
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    user_service: FromDishka[UserService],
) -> None:
    del is_new_user

    if command.args and (
        command.args.startswith(_TG_LINK_START_PREFIX)
        or command.args.startswith(_TG_LINK_START_MINIAPP_PREFIX)
    ):
        token, return_to_miniapp = _extract_tg_link_token_and_mode(command.args)
        if not token:
            await message.answer(_tg_link_copy(user, "invalid"))
            return

        await message.answer(
            _tg_link_copy(user, "prompt"),
            reply_markup=_build_tg_link_confirmation_keyboard(
                user,
                token,
                return_to_miniapp=return_to_miniapp,
            ),
        )
        return

    if command.args and command.args.startswith(REFERRAL_PREFIX) and not user.is_invited_user:
        referral_code = command.args
        logger.info(f"Start with referral code: '{referral_code}'")
        await referral_service.handle_referral(
            user,
            referral_code,
            source=ReferralInviteSource.BOT,
        )

    await on_start_dialog(user, dialog_manager, user_service)


@router.callback_query(F.data.startswith("tglnk_ok"))
@aiogram_inject
async def on_telegram_link_confirm_click(
    callback: CallbackQuery,
    user: UserDto,
    telegram_link_service: FromDishka[TelegramLinkService],
    config: FromDishka[AppConfig],
    settings_service: FromDishka[SettingsService],
) -> None:
    token, return_to_miniapp = _extract_tg_link_token_and_mode(str(callback.data or ""))
    try:
        await telegram_link_service.confirm_token(
            telegram_id=user.telegram_id,
            token=token,
        )
    except TelegramLinkError as exception:
        result_key = (
            "merge_conflict"
            if exception.code in {"MANUAL_MERGE_REQUIRED", "LINK_UPDATE_FAILED"}
            else "invalid"
        )
        result_marker = "merge_conflict" if result_key == "merge_conflict" else "invalid"
        return_url, use_web_app_button = await _build_telegram_link_return_url(
            config,
            settings_service,
            telegram_link=result_marker,
            telegram_id=user.telegram_id,
            return_to_miniapp=return_to_miniapp,
        )
        await callback.message.edit_text(
            _tg_link_copy(user, result_key),
            reply_markup=_build_tg_link_result_keyboard(
                user,
                return_url,
                use_web_app_button=use_web_app_button,
            ),
        )
        await callback.answer()
        return

    return_url, use_web_app_button = await _build_telegram_link_return_url(
        config,
        settings_service,
        telegram_link="success",
        telegram_id=user.telegram_id,
        return_to_miniapp=return_to_miniapp,
    )
    await callback.message.edit_text(
        _tg_link_copy(user, "success"),
        reply_markup=_build_tg_link_result_keyboard(
            user,
            return_url,
            use_web_app_button=use_web_app_button,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tglnk_no"))
@aiogram_inject
async def on_telegram_link_cancel_click(
    callback: CallbackQuery,
    user: UserDto,
    config: FromDishka[AppConfig],
    settings_service: FromDishka[SettingsService],
) -> None:
    _token, return_to_miniapp = _extract_tg_link_token_and_mode(str(callback.data or ""))
    return_url, use_web_app_button = await _build_telegram_link_return_url(
        config,
        settings_service,
        telegram_link="cancelled",
        telegram_id=user.telegram_id,
        return_to_miniapp=return_to_miniapp,
    )
    await callback.message.edit_text(
        _tg_link_copy(user, "cancelled"),
        reply_markup=_build_tg_link_result_keyboard(
            user,
            return_url,
            use_web_app_button=use_web_app_button,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == CALLBACK_RULES_ACCEPT)
@aiogram_inject
async def on_rules_accept(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    logger.info(f"{log(user)} Accepted rules")
    await on_start_dialog(user, dialog_manager, user_service)


@router.callback_query(F.data == CALLBACK_CHANNEL_CONFIRM)
@aiogram_inject
async def on_channel_confirm(
    callback: CallbackQuery,
    user: UserDto,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    logger.info(f"{log(user)} Cofirmed join channel")
    await on_start_dialog(user, dialog_manager, user_service)


@dialog_inject
async def on_get_trial(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    subscription_trial_service: FromDishka[SubscriptionTrialService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    try:
        snapshot = await subscription_trial_service.get_eligibility(
            user,
            channel=PurchaseChannel.TELEGRAM,
        )
    except PurchaseAccessError:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-trial-unavailable"),
        )
        return

    if not snapshot.eligible:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key=_resolve_trial_notification_key(snapshot.reason_code),
            ),
        )
        return

    await trial_subscription_task.kiq(user)


@dialog_inject
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


@dialog_inject
async def on_show_qr(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    invite_state = await referral_service.get_invite_state(user, create_if_missing=True)
    if (
        not invite_state.invite
        or invite_state.invite_block_reason is not None
    ):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-referral-invite-link-unavailable"),
        )
        return

    ref_link = await referral_service.get_ref_link(invite_state.invite.token)
    ref_qr = referral_service.get_ref_qr(ref_link)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload.not_deleted(
            i18n_key="",
            media=ref_qr,
            media_type=MediaType.PHOTO,
        ),
    )


@dialog_inject
async def on_regenerate_invite(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    invite_state = await referral_service.regenerate_invite(user)

    if invite_state.invite and invite_state.invite_block_reason is None:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-referral-invite-regenerated"),
        )
        await dialog_manager.switch_to(state=MainMenu.INVITE)
        return

    error_key = (
        "ntf-referral-invite-regenerate-blocked"
        if invite_state.invite_block_reason == INVITE_BLOCK_REASON_EXHAUSTED
        else "ntf-referral-invite-link-unavailable"
    )
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key=error_key),
    )
    await dialog_manager.switch_to(state=MainMenu.INVITE)


@dialog_inject
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


@dialog_inject
async def on_go_to_exchange(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Open the points exchange screen."""
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE)


@dialog_inject
async def on_exchange_points(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    """Open subscription-days exchange selection."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    # Guard against users without points to exchange.
    if user.points <= 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-points-no-points"),
        )
        return

    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_POINTS)


@dialog_inject
async def on_exchange_points_select_subscription(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Select a subscription for points exchange."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    subscription = await subscription_service.get(selected_subscription)
    if not subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return

    # Store the selected subscription.
    dialog_manager.dialog_data["exchange_subscription_id"] = selected_subscription
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_POINTS_CONFIRM)


@dialog_inject
async def on_exchange_points_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
) -> None:
    """Confirm exchanging points for subscription days."""

    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("exchange_subscription_id")

    if not subscription_id:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return

    try:
        result = await referral_exchange_service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.SUBSCRIPTION_DAYS,
            subscription_id=int(subscription_id),
        )
    except ReferralExchangeError as error:
        logger.warning(f"{log(user)} Subscription-days exchange failed: {error.code}")
        await _notify_exchange_error(
            user=user,
            notification_service=notification_service,
            error=error,
        )
        return

    days_to_add = result.result.days_added or 0
    points_to_exchange = result.points_spent
    user.points = result.points_balance_after

    logger.info(
        f"{log(user)} Exchanged {points_to_exchange} points for {days_to_add} days "
        f"on subscription {subscription_id} via ReferralExchangeService"
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

    # Return to the exchange screen.
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE)


@dialog_inject
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

    # Route to the matching exchange flow.
    if exchange_type == PointsExchangeType.SUBSCRIPTION_DAYS:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_POINTS)
    elif exchange_type == PointsExchangeType.GIFT_SUBSCRIPTION:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_GIFT)
    elif exchange_type == PointsExchangeType.DISCOUNT:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_DISCOUNT)
    elif exchange_type == PointsExchangeType.TRAFFIC:
        await dialog_manager.switch_to(state=MainMenu.EXCHANGE_TRAFFIC)


@dialog_inject
async def on_exchange_gift_select_plan(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan_id: int,
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Select a plan for a gift subscription."""
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

    logger.info(
        f"{log(user)} Selected plan for gift subscription: {plan.name} (id={selected_plan_id})"
    )

    # Move to the gift confirmation step.
    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_GIFT_CONFIRM)


@dialog_inject
async def on_exchange_gift_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
) -> None:
    """Confirm points exchange into a gift subscription promocode."""

    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    # Load the selected plan from dialog data.
    selected_plan_id = dialog_manager.dialog_data.get("gift_selected_plan_id")

    # Проверяем, что план выбран
    if not selected_plan_id:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-exchange-gift-no-plan"),
        )
        return

    try:
        result = await referral_exchange_service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.GIFT_SUBSCRIPTION,
            gift_plan_id=int(selected_plan_id),
        )
    except ReferralExchangeError as error:
        logger.warning(f"{log(user)} Gift exchange failed: {error.code}")
        await _notify_exchange_error(
            user=user,
            notification_service=notification_service,
            error=error,
        )
        return

    promocode_code = result.result.gift_promocode
    if not promocode_code:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return

    user.points = result.points_balance_after
    plan_name = result.result.gift_plan_name or "—"
    gift_duration_days = result.result.gift_duration_days or 0
    logger.info(f"{log(user)} Created gift exchange promocode '{promocode_code}'")

    # Persist values for the result screen.
    dialog_manager.dialog_data["gift_promocode"] = promocode_code
    dialog_manager.dialog_data["gift_plan_name"] = plan_name
    dialog_manager.dialog_data["gift_duration_days"] = gift_duration_days

    await dialog_manager.switch_to(state=MainMenu.EXCHANGE_GIFT_SUCCESS)


@dialog_inject
async def on_exchange_discount_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
) -> None:
    """Confirm points exchange into a discount."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    try:
        result = await referral_exchange_service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.DISCOUNT,
        )
    except ReferralExchangeError as error:
        logger.warning(f"{log(user)} Discount exchange failed: {error.code}")
        await _notify_exchange_error(
            user=user,
            notification_service=notification_service,
            error=error,
        )
        return

    discount_percent = result.result.discount_percent_added or 0
    points_to_spend = result.points_spent
    user.points = result.points_balance_after

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


@dialog_inject
async def on_exchange_traffic_select_subscription(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_subscription: int,
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Select a subscription for traffic top-up."""
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


@dialog_inject
async def on_exchange_traffic_confirm(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    referral_exchange_service: FromDishka[ReferralExchangeService],
) -> None:
    """Confirm points exchange into traffic."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    subscription_id = dialog_manager.dialog_data.get("traffic_subscription_id")

    if not subscription_id:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return

    try:
        result = await referral_exchange_service.execute(
            user_telegram_id=user.telegram_id,
            exchange_type=PointsExchangeType.TRAFFIC,
            subscription_id=int(subscription_id),
        )
    except ReferralExchangeError as error:
        logger.warning(f"{log(user)} Traffic exchange failed: {error.code}")
        await _notify_exchange_error(
            user=user,
            notification_service=notification_service,
            error=error,
        )
        return

    traffic_gb = result.result.traffic_gb_added or 0
    points_to_spend = result.points_spent
    user.points = result.points_balance_after

    logger.info(
        f"{log(user)} Exchanged {points_to_spend} points for {traffic_gb} GB traffic "
        f"on subscription {subscription_id} via ReferralExchangeService"
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


@dialog_inject
async def on_invite(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    settings_service: FromDishka[SettingsService],
    partner_service: FromDishka[PartnerService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    partner = await partner_service.get_partner_by_user(user.telegram_id)
    if partner and partner.is_active:
        await dialog_manager.start(state=UserPartner.MAIN, mode=StartMode.RESET_STACK)
        return

    if await settings_service.is_referral_enable():
        await dialog_manager.switch_to(state=MainMenu.INVITE)


@dialog_inject
async def on_invite_referral_item_click(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_item: str,
) -> None:
    await callback.answer()


@dialog_inject
async def on_connect_device_selected(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
    subscription_service: FromDishka[SubscriptionService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Handle subscription item click and open its URL."""



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
    dialog_manager.dialog_data["selected_subscription_plan_name"] = (
        subscription.plan.name if subscription.plan else i18n.get("msg-common-plan-fallback")
    )

    logger.info(f"{log(user)} Selected device for connection: subscription_id={subscription_id}")

    # Switch to URL window
    await dialog_manager.switch_to(state=MainMenu.CONNECT_DEVICE_URL)
