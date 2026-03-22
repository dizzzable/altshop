from datetime import timedelta
from decimal import Decimal
from typing import Union
from uuid import UUID

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode, SubManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger
from remnawave import RemnawaveSDK
from remnawave.exceptions import NotFoundError
from remnawave.models import TelegramUserResponseDto

from src.bot.keyboards import get_contact_support_keyboard
from src.bot.states import DashboardUser
from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT, USER_KEY
from src.core.enums import PartnerAccrualStrategy, PartnerRewardType, SubscriptionStatus, UserRole
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now
from src.core.utils.validators import is_double_click, parse_int
from src.infrastructure.database.models.dto import UserDto
from src.infrastructure.database.models.dto.partner import PartnerIndividualSettingsDto
from src.infrastructure.database.models.dto.plan import PlanSnapshotDto
from src.infrastructure.database.models.dto.subscription import SubscriptionDto
from src.infrastructure.database.models.dto.user import ReferralInviteIndividualSettingsDto
from src.infrastructure.taskiq.tasks.redirects import redirect_to_main_menu_task
from src.services.email_recovery import EmailRecoveryService
from src.services.notification import NotificationService
from src.services.partner import PartnerService
from src.services.plan import PlanService
from src.services.remnawave import RemnawaveService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.transaction import TransactionService
from src.services.user import UserService

from .subscription_selection import (
    clear_selected_subscription,
    get_visible_subscriptions,
    resolve_selected_subscription,
    set_selected_subscription,
)

ASSIGN_PLAN_FROM_MULTI_KEY = "assign_plan_from_multi_subscriptions"


async def start_user_window(
    manager: Union[DialogManager, SubManager],
    target_telegram_id: int,
) -> None:
    await manager.start(
        state=DashboardUser.MAIN,
        data={"target_telegram_id": target_telegram_id},
        mode=StartMode.RESET_STACK,
    )


async def _get_target_user_subscription_context(
    dialog_manager: Union[DialogManager, SubManager],
    user_service: UserService,
    subscription_service: SubscriptionService,
) -> tuple[UserDto, list[SubscriptionDto], SubscriptionDto]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    visible_subscriptions, subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not subscription:
        raise ValueError(f"Selected subscription for user '{target_telegram_id}' not found")

    return target_user, visible_subscriptions, subscription


@inject
async def on_block_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    blocked = not target_user.is_blocked
    await user_service.set_block(user=target_user, blocked=blocked)
    await redirect_to_main_menu_task.kiq(target_user.telegram_id)
    logger.info(f"{log(user)} {'Blocked' if blocked else 'Unblocked'} {log(target_user)}")


@inject
async def on_reset_web_password(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    email_recovery_service: FromDishka[EmailRecoveryService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    is_dev = user.role == UserRole.DEV or user.telegram_id in config.bot.dev_id

    if not is_dev:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-error"),
        )
        return

    if not is_double_click(dialog_manager, key="web_password_reset_confirm", cooldown=10):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
        )
        logger.debug(
            f"{log(user)} Waiting for confirmation to reset web password for "
            f"user '{target_telegram_id}'"
        )
        return

    try:
        (
            username,
            temp_password,
            expires_at,
        ) = await email_recovery_service.issue_temporary_password_for_dev(
            target_telegram_id=target_telegram_id,
            ttl_seconds=24 * 60 * 60,
        )
    except ValueError as exc:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-user-web-password-reset-failed",
                i18n_kwargs={"error": str(exc)},
            ),
        )
        logger.warning(
            f"{log(user)} Failed to issue temporary web password for user "
            f"'{target_telegram_id}': {exc}"
        )
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-user-web-password-reset-issued",
            i18n_kwargs={
                "username": username,
                "temp_password": temp_password,
                "expires_at": expires_at.strftime(DATETIME_FORMAT),
            },
        ),
    )
    logger.info(
        f"{log(user)} Issued temporary web password for user '{target_telegram_id}' "
        f"(username='{username}', expires_at='{expires_at.isoformat()}')"
    )


@inject
async def on_role_select(
    callback: CallbackQuery,
    widget: Select[UserRole],
    dialog_manager: DialogManager,
    selected_role: UserRole,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    await user_service.set_role(user=target_user, role=selected_role)
    await redirect_to_main_menu_task.kiq(target_user.telegram_id)
    logger.info(f"{log(user)} Changed role to '{selected_role} for {log(target_user)}")


@inject
async def on_current_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    visible_subscriptions, selected_subscription = resolve_selected_subscription(
        dialog_manager,
        all_subscriptions,
        target_user.current_subscription.id if target_user.current_subscription else None,
    )

    if not visible_subscriptions or not selected_subscription:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return

    if len(visible_subscriptions) > 1:
        await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTIONS)
        return

    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_user_subscription_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_subscription_id: int,
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected user subscription '{selected_subscription_id}'")

    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    set_selected_subscription(dialog_manager, selected_subscription_id, subscriptions)
    logger.info(
        f"{log(user)} Opened selected subscription '{selected_subscription_id}' "
        f"for user '{target_telegram_id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_subscription_back(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    visible_subscriptions, _ = resolve_selected_subscription(dialog_manager, subscriptions)

    if len(visible_subscriptions) > 1:
        await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTIONS)
        return

    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    new_status = (
        SubscriptionStatus.DISABLED if subscription.is_active else SubscriptionStatus.ACTIVE
    )

    remnawave_toggle_status = (
        remnawave.users.disable_user if subscription.is_active else remnawave.users.enable_user
    )

    await remnawave_toggle_status(uuid=str(subscription.user_remna_id))
    subscription.status = new_status
    await subscription_service.update(subscription)
    logger.info(
        f"{log(user)} Toggled subscription '{subscription.id}' status "
        f"to '{new_status}' for '{target_user.telegram_id}'"
    )


@inject
async def on_subscription_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, visible_subscriptions, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )
    target_telegram_id = target_user.telegram_id

    if is_double_click(dialog_manager, key="subscription_delete_confirm", cooldown=10):
        subscription.status = SubscriptionStatus.DELETED
        await subscription_service.update(subscription)

        # Delete exactly the subscription user in panel (multi-subscriptions safe).
        if subscription.user_remna_id:
            try:
                await remnawave_service.delete_user(target_user, uuid=subscription.user_remna_id)
            except Exception as exception:
                logger.exception(
                    f"{log(user)} Failed to delete RemnaUser '{subscription.user_remna_id}' "
                    f"for user '{target_telegram_id}' exception: {exception}"
                )

        # If deleted subscription is current — switch to another non-deleted subscription.
        active_subs = [
            candidate
            for candidate in visible_subscriptions
            if candidate.id != subscription.id and candidate.status != SubscriptionStatus.DELETED
        ]

        if active_subs and active_subs[0].id:
            await user_service.set_current_subscription(target_telegram_id, active_subs[0].id)
        else:
            await user_service.delete_current_subscription(target_telegram_id)

        if active_subs and active_subs[0].id:
            set_selected_subscription(dialog_manager, active_subs[0].id, active_subs)
        else:
            clear_selected_subscription(dialog_manager)

        logger.info(
            f"{log(user)} Deleted subscription '{subscription.id}' for user '{target_telegram_id}'"
        )
        if len(active_subs) > 1:
            await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTIONS)
        elif active_subs:
            await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)
        else:
            await dialog_manager.switch_to(state=DashboardUser.MAIN)
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )
    logger.debug(
        f"{log(user)} Waiting for confirmation to delete "
        f"subscription for user '{target_telegram_id}'"
    )


@inject
async def on_devices(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    devices = await remnawave_service.get_devices_by_subscription_uuid(subscription.user_remna_id)

    if not devices:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-devices-empty"),
        )
        return

    await dialog_manager.switch_to(state=DashboardUser.DEVICES_LIST)


@inject
async def on_device_delete(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    await sub_manager.load_data()
    selected_device = sub_manager.item_id

    user: UserDto = sub_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        sub_manager,
        user_service,
        subscription_service,
    )

    devices = await remnawave_service.delete_device_by_subscription_uuid(
        user_remna_id=subscription.user_remna_id,
        hwid=selected_device,
    )
    logger.info(
        f"{log(user)} Deleted device '{selected_device}' "
        f"for subscription '{subscription.id}' and user '{target_user.telegram_id}'"
    )

    if devices:
        return

    await sub_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_reset_traffic(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave: FromDishka[RemnawaveSDK],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    await remnawave.users.reset_user_traffic(uuid=str(subscription.user_remna_id))
    logger.info(
        f"{log(user)} Reset traffic for subscription '{subscription.id}' "
        f"for user '{target_user.telegram_id}'"
    )


@inject
async def on_discount_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_discount: int,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected discount '{selected_discount}'")
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    target_user.personal_discount = selected_discount
    await user_service.update(user=target_user)
    logger.info(f"{log(user)} Changed discount to '{selected_discount}' for '{target_telegram_id}'")
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_discount_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    if message.text is None or not (message.text.isdigit() and 0 <= int(message.text) <= 100):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    number = int(message.text)
    target_user.personal_discount = number
    await user_service.update(user=target_user)
    logger.info(f"{log(user)} Changed discount to '{number}' for '{target_telegram_id}'")
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_purchase_discount_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_discount: int,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected next-purchase discount '{selected_discount}'")
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    target_user.purchase_discount = selected_discount
    await user_service.update(user=target_user)
    logger.info(
        f"{log(user)} Changed next-purchase discount to '{selected_discount}' "
        f"for '{target_telegram_id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_purchase_discount_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    if message.text is None or not (message.text.isdigit() and 0 <= int(message.text) <= 100):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    number = int(message.text)
    target_user.purchase_discount = number
    await user_service.update(user=target_user)
    logger.info(
        f"{log(user)} Changed next-purchase discount to '{number}' for '{target_telegram_id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_points_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    number = parse_int(message.text)

    if number is None:
        logger.warning(f"{log(user)} Invalid points input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    new_points = target_user.points + number

    if new_points < 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-user-invalid-points",
                i18n_kwargs={"operation": "ADD" if number > 0 else "SUB"},
            ),
        )
        return

    target_user.points = new_points
    await user_service.update(user=target_user)

    logger.info(
        f"{log(user)} {'Added' if number > 0 else 'Subtracted'} "
        f"'{abs(number)}' points for '{target_telegram_id}'"
    )


@inject
async def on_points_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_points: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected points '{selected_points}'")
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    new_points = target_user.points + selected_points

    if new_points < 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-user-invalid-points",
                i18n_kwargs={"operation": "ADD" if selected_points > 0 else "SUB"},
            ),
        )
        return

    target_user.points = new_points
    await user_service.update(target_user)

    logger.info(
        f"{log(user)} {'Added' if selected_points > 0 else 'Subtracted'} "
        f"'{abs(selected_points)}' points for '{target_telegram_id}'"
    )


@inject
async def on_traffic_limit_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_traffic: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected traffic '{selected_traffic}'")
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    subscription.traffic_limit = selected_traffic
    await subscription_service.update(subscription)

    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    logger.info(
        f"{log(user)} Changed traffic limit to '{selected_traffic}' "
        f"for subscription '{subscription.id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_traffic_limit_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    if message.text is None or not (message.text.isdigit() and int(message.text) > 0):
        logger.warning(f"{log(user)} Invalid traffic limit input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    number = int(message.text)
    subscription.traffic_limit = number
    await subscription_service.update(subscription)

    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    logger.info(
        f"{log(user)} Changed traffic limit to '{number}' for subscription '{subscription.id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_device_limit_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_device: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected device limit '{selected_device}'")
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    subscription.device_limit = selected_device
    await subscription_service.update(subscription)

    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    logger.info(
        f"{log(user)} Changed device limit to '{selected_device}' "
        f"for subscription '{subscription.id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_device_limit_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    if message.text is None or not (message.text.isdigit() and int(message.text) > 0):
        logger.warning(f"{log(user)} Invalid device limit input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    number = int(message.text)
    subscription.device_limit = number
    await subscription_service.update(subscription)

    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )

    logger.info(
        f"{log(user)} Changed device limit to '{number}' for subscription '{subscription.id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION)


@inject
async def on_internal_squad_select(
    callback: CallbackQuery,
    widget: Select[UUID],
    dialog_manager: DialogManager,
    selected_squad: UUID,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    if selected_squad in subscription.internal_squads:
        updated_internal_squads = [s for s in subscription.internal_squads if s != selected_squad]
        logger.info(f"{log(user)} Unset internal squad '{selected_squad}'")
    else:
        updated_internal_squads = [*subscription.internal_squads, selected_squad]
        logger.info(f"{log(user)} Set internal squad '{selected_squad}'")

    subscription.internal_squads = updated_internal_squads
    await subscription_service.update(subscription)
    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )


@inject
async def on_external_squad_select(
    callback: CallbackQuery,
    widget: Select[UUID],
    dialog_manager: DialogManager,
    selected_squad: UUID,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    if selected_squad == subscription.external_squad:
        subscription.external_squad = None
        logger.info(f"{log(user)} Unset external squad '{selected_squad}'")
    else:
        subscription.external_squad = selected_squad
        logger.info(f"{log(user)} Set external squad '{selected_squad}'")

    await subscription_service.update(subscription)
    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )


@inject
async def on_transactions(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    transaction_service: FromDishka[TransactionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    transactions = await transaction_service.get_by_user(target_telegram_id)

    if not transactions:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-transactions-empty"),
        )
        return

    await dialog_manager.switch_to(state=DashboardUser.TRANSACTIONS_LIST)


@inject
async def on_referrals(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(state=DashboardUser.REFERRALS)


async def on_referral_user_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_user: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected referral user '{selected_user}'")
    await start_user_window(manager=dialog_manager, target_telegram_id=selected_user)


async def on_transaction_select(
    callback: CallbackQuery,
    widget: Select[UUID],
    dialog_manager: DialogManager,
    selected_transaction: UUID,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected transaction '{selected_transaction}'")
    dialog_manager.dialog_data["selected_transaction"] = selected_transaction
    await dialog_manager.switch_to(state=DashboardUser.TRANSACTION)


@inject
async def on_give_access(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    plans = await plan_service.get_allowed_plans()

    if not plans:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-allowed-plans-empty"),
        )
        return

    await dialog_manager.switch_to(state=DashboardUser.GIVE_ACCESS)


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected plan '{selected_plan_id}'")
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    plan = await plan_service.get(selected_plan_id)

    if not plan:
        raise ValueError(f"Plan '{selected_plan_id}' not found")

    if target_telegram_id not in plan.allowed_user_ids:
        plan.allowed_user_ids.append(target_telegram_id)
    else:
        plan.allowed_user_ids.remove(target_telegram_id)

    await plan_service.update(plan)
    logger.info(
        f"{log(user)} Given access to plan '{selected_plan_id}' for user '{target_telegram_id}'"
    )


@inject
async def on_duration_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_duration: int,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected duration '{selected_duration}'")
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    new_expire = subscription.expire_at + timedelta(days=selected_duration)

    if new_expire < datetime_now():
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-user-invalid-expire-time",
                i18n_kwargs={"operation": "ADD" if selected_duration > 0 else "SUB"},
            ),
        )
        return

    subscription.expire_at = new_expire
    await subscription_service.update(subscription)
    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )
    logger.info(
        f"{log(user)} {'Added' if selected_duration > 0 else 'Subtracted'} "
        f"'{abs(selected_duration)}' days to subscription '{subscription.id}'"
    )


@inject
async def on_duration_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    number = parse_int(message.text)

    if number is None:
        logger.warning(f"{log(user)} Invalid duration input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    new_expire = subscription.expire_at + timedelta(days=number)

    if new_expire < datetime_now():
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-user-invalid-expire-time",
                i18n_kwargs={"operation": "ADD" if number > 0 else "SUB"},
            ),
        )
        return

    subscription.expire_at = new_expire
    await subscription_service.update(subscription)
    await remnawave_service.updated_user(
        user=target_user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )
    logger.info(
        f"{log(user)} {'Added' if number > 0 else 'Subtracted'} "
        f"'{abs(number)}' days to subscription '{subscription.id}'"
    )


@inject
async def on_send(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    config: FromDishka[AppConfig],
    i18n: FromDishka[TranslatorRunner],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    payload = dialog_manager.dialog_data.get("payload")

    if not payload:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-broadcast-empty-content"),
        )
        return

    if is_double_click(dialog_manager, key="message_confirm", cooldown=5):
        text = i18n.get("contact-support-help")
        support_username = config.bot.support_username.get_secret_value()
        payload["reply_markup"] = get_contact_support_keyboard(support_username, text)

        message = await notification_service.notify_user(
            user=target_user,
            payload=MessagePayload(**payload),
        )
        await dialog_manager.switch_to(state=DashboardUser.MAIN)

        if message:
            i18n_key = "ntf-user-message-success"
        else:
            i18n_key = "ntf-user-message-not-sent"

        await notification_service.notify_user(user=user, payload=MessagePayload(i18n_key=i18n_key))
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )
    logger.debug(f"{log(user)} Awaiting confirmation for message send")


@inject
async def on_sync(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    remnawave: FromDishka[RemnawaveSDK],
    remnawave_service: FromDishka[RemnawaveService],
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    try:
        result = await remnawave.users.get_users_by_telegram_id(telegram_id=str(target_telegram_id))

        if not isinstance(result, TelegramUserResponseDto):
            raise ValueError("Unexpected response TelegramUserResponseDto")
    except NotFoundError:
        result = None
    except Exception as exception:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-sync-failed"),
        )
        logger.exception(
            f"Error syncing RemnaUser '{target_user.telegram_id}' exception: {exception}"
        )
        return

    if not result:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-sync-failed"),
        )
        return

    profiles = list(result)
    stats = await remnawave_service.sync_profiles_by_telegram_id(
        telegram_id=target_telegram_id,
        remna_users=profiles,
        preserve_current=True,
    )
    processed_profiles = stats.subscriptions_created + stats.subscriptions_updated

    if processed_profiles == 0:
        logger.warning(
            f"{log(user)} Manual sync for '{target_telegram_id}' finished without successful "
            f"profile processing (errors={stats.errors})"
        )
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-sync-failed"),
        )
        return

    logger.info(
        f"{log(user)} Manual sync summary for '{target_telegram_id}': "
        f"created={stats.subscriptions_created}, "
        f"updated={stats.subscriptions_updated}, "
        f"errors={stats.errors}"
    )
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-user-sync-success"),
    )


@inject
async def on_assign_plan(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    subscription_service: FromDishka[SubscriptionService],
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    all_subscriptions = await subscription_service.get_all_by_user(target_telegram_id)
    visible_subscriptions = get_visible_subscriptions(all_subscriptions)

    if not visible_subscriptions:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-subscription-empty"),
        )
        return

    active_plans = [plan for plan in await plan_service.get_all() if plan.is_active and plan.id]
    if not active_plans:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-assign-plans-empty"),
        )
        return

    if len(visible_subscriptions) > 1:
        dialog_manager.dialog_data[ASSIGN_PLAN_FROM_MULTI_KEY] = True
        await dialog_manager.switch_to(state=DashboardUser.ASSIGN_PLAN_SUBSCRIPTIONS)
        return

    subscription = visible_subscriptions[0]
    if subscription.id is None:
        raise ValueError(f"Subscription for user '{target_telegram_id}' has no id")

    set_selected_subscription(dialog_manager, subscription.id, visible_subscriptions)
    dialog_manager.dialog_data[ASSIGN_PLAN_FROM_MULTI_KEY] = False
    await dialog_manager.switch_to(state=DashboardUser.ASSIGN_PLAN)


@inject
async def on_assign_plan_subscription_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_subscription_id: int,
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    subscriptions = await subscription_service.get_all_by_user(target_telegram_id)

    set_selected_subscription(dialog_manager, selected_subscription_id, subscriptions)
    dialog_manager.dialog_data[ASSIGN_PLAN_FROM_MULTI_KEY] = True
    logger.info(
        f"{log(user)} Selected subscription '{selected_subscription_id}' "
        f"for plan assignment to user '{target_telegram_id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.ASSIGN_PLAN)


@inject
async def on_assign_plan_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
    plan_service: FromDishka[PlanService],
    user_service: FromDishka[UserService],
    subscription_service: FromDishka[SubscriptionService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_user, _, subscription = await _get_target_user_subscription_context(
        dialog_manager,
        user_service,
        subscription_service,
    )

    plan = await plan_service.get(selected_plan_id)
    if not plan or not plan.is_active:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-assign-plans-empty"),
        )
        return

    current_duration = subscription.plan.duration if subscription.plan else 30
    if plan.durations and not any(duration.days == current_duration for duration in plan.durations):
        current_duration = plan.durations[0].days

    subscription.plan = PlanSnapshotDto.from_plan(plan, current_duration)
    await subscription_service.update(subscription)

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(
            i18n_key="ntf-user-plan-assigned",
            i18n_kwargs={"plan_name": plan.name},
        ),
    )
    dialog_manager.dialog_data.pop(ASSIGN_PLAN_FROM_MULTI_KEY, None)
    logger.info(
        f"{log(user)} Assigned plan '{selected_plan_id}' "
        f"to subscription '{subscription.id}' for user '{target_user.telegram_id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_assign_plan_back(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    if dialog_manager.dialog_data.get(ASSIGN_PLAN_FROM_MULTI_KEY):
        await dialog_manager.switch_to(state=DashboardUser.ASSIGN_PLAN_SUBSCRIPTIONS)
        return

    dialog_manager.dialog_data.pop(ASSIGN_PLAN_FROM_MULTI_KEY, None)
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


@inject
async def on_give_subscription(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await plan_service.get_available_plans(target_user)

    if not plans:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-plans-empty"),
        )
        return

    await dialog_manager.switch_to(state=DashboardUser.GIVE_SUBSCRIPTION)


@inject
async def on_subscription_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected plan '{selected_plan_id}'")
    dialog_manager.dialog_data["selected_plan_id"] = selected_plan_id
    await dialog_manager.switch_to(state=DashboardUser.SUBSCRIPTION_DURATION)


@inject
async def on_subscription_duration_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_duration: int,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
    remnawave_service: FromDishka[RemnawaveService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected duration '{selected_duration}'")
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)
    selected_plan_id = dialog_manager.dialog_data["selected_plan_id"]
    plan = await plan_service.get(selected_plan_id)

    if not plan:
        raise ValueError(f"Plan '{selected_plan_id}' not found")

    plan_snapshot = PlanSnapshotDto.from_plan(plan, selected_duration)
    subscription = await subscription_service.get_current(target_telegram_id)

    if subscription:
        remna_user = await remnawave_service.updated_user(
            user=target_user,
            uuid=subscription.user_remna_id,
            plan=plan_snapshot,
            reset_traffic=True,
        )
    else:
        remna_user = await remnawave_service.create_user(target_user, plan_snapshot)

    subscription_url = remna_user.subscription_url

    if not subscription_url:
        subscription_url = await remnawave_service.get_subscription_url(remna_user.uuid)

    new_subscription = SubscriptionDto(
        user_remna_id=remna_user.uuid,
        status=remna_user.status,
        traffic_limit=plan.traffic_limit,
        device_limit=plan.device_limit,
        internal_squads=plan.internal_squads,
        external_squad=plan.external_squad,
        expire_at=remna_user.expire_at,
        url=subscription_url,
        plan=plan_snapshot,
    )
    await subscription_service.create(target_user, new_subscription)

    logger.info(f"{log(user)} Set plan '{selected_plan_id}' for user '{target_telegram_id}'")
    await dialog_manager.switch_to(state=DashboardUser.MAIN)


# ==================
# PARTNER HANDLERS
# ==================


@inject
async def on_partner(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переход к управлению партнеркой пользователя."""
    await dialog_manager.switch_to(state=DashboardUser.PARTNER)


@inject
async def on_partner_create(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Создание партнера для пользователя."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    if is_double_click(dialog_manager, key="partner_create_confirm", cooldown=5):
        await partner_service.create_partner(target_user)

        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-created"),
        )
        logger.info(f"{log(user)} Created partner for user '{target_telegram_id}'")
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )


@inject
async def on_partner_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переключение статуса партнера."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    updated = await partner_service.toggle_partner_status(partner.id)

    if updated:
        status = "activated" if updated.is_active else "deactivated"
        logger.info(f"{log(user)} Partner for user '{target_telegram_id}' {status}")


@inject
async def on_partner_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Удаление партнера (деактивация)."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    if is_double_click(dialog_manager, key="partner_delete_confirm", cooldown=10):
        await partner_service.deactivate_partner(partner.id)

        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-deactivated"),
        )
        logger.info(f"{log(user)} Deactivated partner for user '{target_telegram_id}'")
        await dialog_manager.switch_to(state=DashboardUser.MAIN)
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )


@inject
async def on_partner_balance(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переход к управлению балансом партнера."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    await dialog_manager.switch_to(state=DashboardUser.PARTNER_BALANCE)


@inject
async def on_partner_balance_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_amount: int,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Изменение баланса партнера по выбору из списка."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Сумма в копейках (selected_amount в рублях * 100)
    amount_kopecks = selected_amount * 100

    new_balance = partner.balance + amount_kopecks

    if new_balance < 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-balance-insufficient",
                i18n_kwargs={"operation": "SUB"},
            ),
        )
        return

    updated = await partner_service.adjust_partner_balance(
        partner_id=partner.id,
        amount=amount_kopecks,
        admin_telegram_id=user.telegram_id,
        reason="Admin adjustment via dashboard",
    )

    if updated:
        operation = "added" if selected_amount > 0 else "subtracted"
        logger.info(
            f"{log(user)} {operation.capitalize()} {abs(selected_amount)} RUB "
            f"to partner balance for user '{target_telegram_id}'"
        )


@inject
async def on_partner_balance_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Обработка ввода суммы для изменения баланса партнера."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    number = parse_int(message.text)

    if number is None:
        logger.warning(f"{log(user)} Invalid partner balance input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-user-invalid-number"),
        )
        return

    # Сумма в копейках (number в рублях * 100)
    amount_kopecks = number * 100

    new_balance = partner.balance + amount_kopecks

    if new_balance < 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-partner-balance-insufficient",
                i18n_kwargs={"operation": "SUB"},
            ),
        )
        return

    updated = await partner_service.adjust_partner_balance(
        partner_id=partner.id,
        amount=amount_kopecks,
        admin_telegram_id=user.telegram_id,
        reason="Admin adjustment via dashboard",
    )

    if updated:
        operation = "added" if number > 0 else "subtracted"
        logger.info(
            f"{log(user)} {operation.capitalize()} {abs(number)} RUB "
            f"to partner balance for user '{target_telegram_id}'"
        )


@inject
async def on_partner_settings(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переход к индивидуальным настройкам партнера."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    await dialog_manager.switch_to(state=DashboardUser.PARTNER_SETTINGS)


@inject
async def on_partner_use_global_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переключить использование глобальных настроек."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Переключаем use_global_settings
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=not partner.individual_settings.use_global_settings,
        accrual_strategy=partner.individual_settings.accrual_strategy,
        reward_type=partner.individual_settings.reward_type,
        level1_percent=partner.individual_settings.level1_percent,
        level2_percent=partner.individual_settings.level2_percent,
        level3_percent=partner.individual_settings.level3_percent,
        level1_fixed_amount=partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        status = "disabled" if new_settings.use_global_settings else "enabled"
        logger.info(f"{log(user)} Partner '{partner.id}' individual settings {status}")


@inject
async def on_partner_accrual_strategy_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_strategy: str,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор стратегии начисления."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Обновляем стратегию начисления
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=False,  # При выборе стратегии отключаем глобальные
        accrual_strategy=PartnerAccrualStrategy(selected_strategy),
        reward_type=partner.individual_settings.reward_type,
        level1_percent=partner.individual_settings.level1_percent,
        level2_percent=partner.individual_settings.level2_percent,
        level3_percent=partner.individual_settings.level3_percent,
        level1_fixed_amount=partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        logger.info(
            f"{log(user)} Partner '{partner.id}' accrual strategy changed to '{selected_strategy}'"
        )

    await dialog_manager.switch_to(state=DashboardUser.PARTNER_SETTINGS)


@inject
async def on_partner_reward_type_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_type: str,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор типа вознаграждения."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Обновляем тип вознаграждения
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=False,  # При выборе типа отключаем глобальные
        accrual_strategy=partner.individual_settings.accrual_strategy,
        reward_type=PartnerRewardType(selected_type),
        level1_percent=partner.individual_settings.level1_percent,
        level2_percent=partner.individual_settings.level2_percent,
        level3_percent=partner.individual_settings.level3_percent,
        level1_fixed_amount=partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        logger.info(f"{log(user)} Partner '{partner.id}' reward type changed to '{selected_type}'")

    await dialog_manager.switch_to(state=DashboardUser.PARTNER_SETTINGS)


@inject
async def on_partner_percent_level_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_item: str,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор процента для уровня."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Формат: "level:percent" например "1:10"
    level_str, percent_str = selected_item.split(":")
    level = int(level_str)
    percent = Decimal(percent_str)

    # Обновляем процент для конкретного уровня
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=False,
        accrual_strategy=partner.individual_settings.accrual_strategy,
        reward_type=partner.individual_settings.reward_type,
        level1_percent=percent if level == 1 else partner.individual_settings.level1_percent,
        level2_percent=percent if level == 2 else partner.individual_settings.level2_percent,
        level3_percent=percent if level == 3 else partner.individual_settings.level3_percent,
        level1_fixed_amount=partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        logger.info(
            f"{log(user)} Partner '{partner.id}' level {level} percent changed to {percent}%"
        )


@inject
async def on_partner_percent_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Ввод процента вручную (формат: уровень процент, например '1 15')."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Парсим ввод: "уровень процент"
    parts = message.text.split() if message.text else []

    if len(parts) != 2:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent-format"),
        )
        return

    try:
        level = int(parts[0])
        percent = Decimal(parts[1])

        if level not in [1, 2, 3]:
            raise ValueError("Invalid level")

        if percent < 0 or percent > 100:
            raise ValueError("Invalid percent")
    except (ValueError, TypeError):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-percent-format"),
        )
        return

    # Обновляем процент для конкретного уровня
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=False,
        accrual_strategy=partner.individual_settings.accrual_strategy,
        reward_type=partner.individual_settings.reward_type,
        level1_percent=percent if level == 1 else partner.individual_settings.level1_percent,
        level2_percent=percent if level == 2 else partner.individual_settings.level2_percent,
        level3_percent=percent if level == 3 else partner.individual_settings.level3_percent,
        level1_fixed_amount=partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        logger.info(
            f"{log(user)} Partner '{partner.id}' level {level} percent changed to {percent}%"
        )


@inject
async def on_partner_fixed_level_select(
    callback: CallbackQuery,
    widget: Select[str],
    dialog_manager: DialogManager,
    selected_item: str,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Выбор фиксированной суммы для уровня."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Формат: "level:amount" например "1:100" (amount в рублях)
    level_str, amount_str = selected_item.split(":")
    level = int(level_str)
    amount_rub = int(amount_str)
    amount_kopecks = amount_rub * 100

    # Обновляем фиксированную сумму для конкретного уровня
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=False,
        accrual_strategy=partner.individual_settings.accrual_strategy,
        reward_type=partner.individual_settings.reward_type,
        level1_percent=partner.individual_settings.level1_percent,
        level2_percent=partner.individual_settings.level2_percent,
        level3_percent=partner.individual_settings.level3_percent,
        level1_fixed_amount=amount_kopecks
        if level == 1
        else partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=amount_kopecks
        if level == 2
        else partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=amount_kopecks
        if level == 3
        else partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        logger.info(
            f"{log(user)} Partner '{partner.id}' level {level} "
            f"fixed amount changed to {amount_rub} RUB"
        )


@inject
async def on_partner_fixed_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Ввод фиксированной суммы вручную (формат: уровень сумма, например '1 150')."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]

    partner = await partner_service.get_partner_by_user(target_telegram_id)

    if not partner:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-not-found"),
        )
        return

    # Парсим ввод: "уровень сумма"
    parts = message.text.split() if message.text else []

    if len(parts) != 2:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-amount-format"),
        )
        return

    try:
        level = int(parts[0])
        amount_rub = int(parts[1])

        if level not in [1, 2, 3]:
            raise ValueError("Invalid level")

        if amount_rub < 0:
            raise ValueError("Invalid amount")
    except (ValueError, TypeError):
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-partner-invalid-amount-format"),
        )
        return

    amount_kopecks = amount_rub * 100

    # Обновляем фиксированную сумму для конкретного уровня
    new_settings = PartnerIndividualSettingsDto(
        use_global_settings=False,
        accrual_strategy=partner.individual_settings.accrual_strategy,
        reward_type=partner.individual_settings.reward_type,
        level1_percent=partner.individual_settings.level1_percent,
        level2_percent=partner.individual_settings.level2_percent,
        level3_percent=partner.individual_settings.level3_percent,
        level1_fixed_amount=amount_kopecks
        if level == 1
        else partner.individual_settings.level1_fixed_amount,
        level2_fixed_amount=amount_kopecks
        if level == 2
        else partner.individual_settings.level2_fixed_amount,
        level3_fixed_amount=amount_kopecks
        if level == 3
        else partner.individual_settings.level3_fixed_amount,
    )

    updated = await partner_service.update_partner_individual_settings(
        partner_id=partner.id,
        settings=new_settings,
    )

    if updated:
        logger.info(
            f"{log(user)} Partner '{partner.id}' level {level} "
            f"fixed amount changed to {amount_rub} RUB"
        )


def _build_referral_invite_individual_settings(
    target_user: UserDto,
    **updates: object,
) -> ReferralInviteIndividualSettingsDto:
    current = target_user.referral_invite_settings
    return ReferralInviteIndividualSettingsDto(
        use_global_settings=bool(updates.get("use_global_settings", current.use_global_settings)),
        link_ttl_enabled=bool(updates.get("link_ttl_enabled", current.link_ttl_enabled)),
        link_ttl_seconds=updates.get("link_ttl_seconds", current.link_ttl_seconds),
        slots_enabled=bool(updates.get("slots_enabled", current.slots_enabled)),
        initial_slots=updates.get("initial_slots", current.initial_slots),
        refill_threshold_qualified=updates.get(
            "refill_threshold_qualified",
            current.refill_threshold_qualified,
        ),
        refill_amount=updates.get("refill_amount", current.refill_amount),
    )


async def _update_referral_invite_settings(
    *,
    user_service: UserService,
    target_user: UserDto,
    settings: ReferralInviteIndividualSettingsDto,
) -> None:
    target_user.referral_invite_settings = settings
    await user_service.update(user=target_user)


@inject
async def on_referral_invite_settings(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    await dialog_manager.switch_to(state=DashboardUser.REFERRAL_INVITE_SETTINGS)


@inject
async def on_referral_invite_use_global_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    new_settings = _build_referral_invite_individual_settings(
        target_user,
        use_global_settings=not target_user.referral_invite_settings.use_global_settings,
    )
    await _update_referral_invite_settings(
        user_service=user_service,
        target_user=target_user,
        settings=new_settings,
    )
    logger.info(
        f"{log(user)} Toggled referral invite use_global_settings to "
        f"'{new_settings.use_global_settings}' for user '{target_telegram_id}'"
    )


@inject
async def on_referral_invite_ttl_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    new_settings = _build_referral_invite_individual_settings(
        target_user,
        use_global_settings=False,
        link_ttl_enabled=not target_user.referral_invite_settings.link_ttl_enabled,
    )
    await _update_referral_invite_settings(
        user_service=user_service,
        target_user=target_user,
        settings=new_settings,
    )
    logger.info(
        f"{log(user)} Toggled referral invite TTL to "
        f"'{new_settings.link_ttl_enabled}' for user '{target_telegram_id}'"
    )


@inject
async def on_referral_invite_slots_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    new_settings = _build_referral_invite_individual_settings(
        target_user,
        use_global_settings=False,
        slots_enabled=not target_user.referral_invite_settings.slots_enabled,
    )
    await _update_referral_invite_settings(
        user_service=user_service,
        target_user=target_user,
        settings=new_settings,
    )
    logger.info(
        f"{log(user)} Toggled referral invite slots to "
        f"'{new_settings.slots_enabled}' for user '{target_telegram_id}'"
    )


async def _update_referral_invite_numeric_field(
    *,
    dialog_manager: DialogManager,
    message: Message,
    user_service: UserService,
    notification_service: NotificationService,
    field_name: str,
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    number = parse_int(message.text)
    if number is None or number < 0:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-invalid-value"),
        )
        return

    new_settings = _build_referral_invite_individual_settings(
        target_user,
        use_global_settings=False,
        **{field_name: number if number > 0 else None},
    )
    await _update_referral_invite_settings(
        user_service=user_service,
        target_user=target_user,
        settings=new_settings,
    )
    logger.info(
        f"{log(user)} Updated referral invite field '{field_name}' "
        f"to '{number}' for user '{target_telegram_id}'"
    )
    await dialog_manager.switch_to(state=DashboardUser.REFERRAL_INVITE_SETTINGS)


@inject
async def on_referral_invite_ttl_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await _update_referral_invite_numeric_field(
        dialog_manager=dialog_manager,
        message=message,
        user_service=user_service,
        notification_service=notification_service,
        field_name="link_ttl_seconds",
    )


@inject
async def on_referral_invite_initial_slots_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await _update_referral_invite_numeric_field(
        dialog_manager=dialog_manager,
        message=message,
        user_service=user_service,
        notification_service=notification_service,
        field_name="initial_slots",
    )


@inject
async def on_referral_invite_refill_threshold_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await _update_referral_invite_numeric_field(
        dialog_manager=dialog_manager,
        message=message,
        user_service=user_service,
        notification_service=notification_service,
        field_name="refill_threshold_qualified",
    )


@inject
async def on_referral_invite_refill_amount_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    await _update_referral_invite_numeric_field(
        dialog_manager=dialog_manager,
        message=message,
        user_service=user_service,
        notification_service=notification_service,
        field_name="refill_amount",
    )


# ==================
# MAX SUBSCRIPTIONS HANDLERS
# ==================


@inject
async def on_max_subscriptions(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переход к настройке индивидуального лимита подписок.

    Индивидуальная настройка позволяет переопределить глобальный лимит для конкретного пользователя.
    Работает независимо от того, включена ли мультиподписка глобально.
    """
    await dialog_manager.switch_to(state=DashboardUser.MAX_SUBSCRIPTIONS)


@inject
async def on_max_subscriptions_use_global_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Переключение между индивидуальным и глобальным лимитом подписок."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    if target_user.max_subscriptions is not None:
        # Переключаем на глобальные настройки (устанавливаем None)
        target_user.max_subscriptions = None
        await user_service.update(user=target_user)
        logger.info(
            f"{log(user)} Reset max_subscriptions to global for user '{target_telegram_id}'"
        )
    else:
        # Переключаем на индивидуальные настройки (устанавливаем текущее глобальное значение)
        settings = await settings_service.get()
        target_user.max_subscriptions = settings.multi_subscription.default_max_subscriptions
        await user_service.update(user=target_user)
        logger.info(
            f"{log(user)} Set individual max_subscriptions to "
            f"{target_user.max_subscriptions} for user '{target_telegram_id}'"
        )


@inject
async def on_max_subscriptions_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_limit: int,
    user_service: FromDishka[UserService],
) -> None:
    """Выбор индивидуального лимита подписок."""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    target_user.max_subscriptions = selected_limit
    await user_service.update(user=target_user)

    limit_display = "∞" if selected_limit == -1 else str(selected_limit)
    logger.info(
        f"{log(user)} Set max_subscriptions to {limit_display} for user '{target_telegram_id}'"
    )


@inject
async def on_max_subscriptions_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    """Ручной ввод индивидуального лимита подписок."""
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    number = parse_int(message.text)

    if number is None or (number < 1 and number != -1):
        logger.warning(f"{log(user)} Invalid max_subscriptions input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-multi-subscription-invalid-value"),
        )
        return

    target_user.max_subscriptions = number
    await user_service.update(user=target_user)

    limit_display = "∞" if number == -1 else str(number)
    logger.info(
        f"{log(user)} Set max_subscriptions to {limit_display} for user '{target_telegram_id}'"
    )
