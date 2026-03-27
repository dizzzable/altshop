from decimal import Decimal
from typing import Optional
from uuid import UUID

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager, ShowMode, StartMode, SubManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger
from remnawave.enums.users import TrafficLimitStrategy

from src.bot.states import RemnashopPlans
from src.core.constants import TAG_REGEX, USER_KEY
from src.core.enums import ArchivedPlanRenewMode, Currency, PlanAvailability, PlanType
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import format_user_log as log
from src.core.utils.message_payload import MessagePayload
from src.core.utils.validators import is_double_click, parse_int
from src.infrastructure.database.models.dto import PlanDto, PlanDurationDto, PlanPriceDto, UserDto
from src.services.notification import NotificationService
from src.services.plan import PlanDeletionBlockedError, PlanService, PlanValidationError
from src.services.pricing import PricingService
from src.services.remnawave import RemnawaveService
from src.services.subscription import SubscriptionService
from src.services.user import UserService


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    plan: Optional[PlanDto] = await plan_service.get(plan_id=int(sub_manager.item_id))

    if not plan:
        raise ValueError(f"Attempted to select non-existent plan '{sub_manager.item_id}'")

    logger.info(f"{log(user)} Selected plan ID '{plan.id}'")

    adapter = DialogDataAdapter(sub_manager.manager)
    adapter.save(plan)

    sub_manager.manager.dialog_data["is_edit"] = True
    await sub_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


@inject
async def on_plan_move(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    plan_service: FromDishka[PlanService],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    plan_id = int(sub_manager.item_id)

    moved = await plan_service.move_plan_up(plan_id)
    if moved:
        logger.info(f"{log(user)} Moved plan '{plan_id}' up successfully")
    else:
        logger.warning(f"{log(user)} Failed to move plan '{plan_id}' up")


@inject
async def on_plan_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: SubManager,
    notification_service: FromDishka[NotificationService],
    plan_service: FromDishka[PlanService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if is_double_click(dialog_manager, key=f"delete_confirm_{plan.id}", cooldown=10):
        try:
            await plan_service.delete(plan.id)
        except PlanDeletionBlockedError:
            await notification_service.notify_user(
                user=user,
                payload=MessagePayload(i18n_key="ntf-plan-delete-blocked"),
            )
            logger.warning(f"{log(user)} Deletion blocked for plan ID '{plan.id}'")
            return
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-deleted-success"),
        )
        logger.info(f"{log(user)} Deleted plan ID '{plan.id}'")
        await dialog_manager.start(state=RemnashopPlans.MAIN, mode=StartMode.RESET_STACK)
        return

    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key="ntf-double-click-confirm"),
    )
    logger.debug(f"{log(user)} Clicked delete for plan ID '{plan.id}' (awaiting confirmation)")


@inject
async def on_name_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    plan_service: FromDishka[PlanService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set plan name")

    if message.text is None:
        logger.warning(f"{log(user)} Provided empty plan name input")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-name"),
        )
        return

    if await plan_service.get_by_name(plan_name=message.text):
        logger.warning(f"{log(user)} Tried to set duplicate plan name '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-name"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.name = message.text
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully set plan name to '{plan.name}'")
    await dialog_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


@inject
async def on_description_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set plan description")

    if message.text is None:
        logger.warning(f"{log(user)} Provided empty plan description input")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-description"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.description = message.text
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully set plan description to '{plan.description}'")


async def on_description_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.description = None
    adapter.save(plan)
    logger.info(f"{log(user)} Successfully removed plan description")


@inject
async def on_tag_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set plan tag")

    if message.text is None:
        logger.warning(f"{log(user)} Provided empty plan tag input")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-tag"),
        )
        return

    tag = message.text.strip()

    if not TAG_REGEX.fullmatch(tag):
        logger.warning(f"{log(user)} Invalid plan tag input: '{tag}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-tag"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.tag = message.text
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully set plan tag to '{plan.tag}'")


async def on_tag_delete(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.tag = None
    adapter.save(plan)
    logger.info(f"{log(user)} Successfully removed plan tag")


async def on_type_select(
    callback: CallbackQuery,
    widget: Select[PlanType],
    dialog_manager: DialogManager,
    selected_type: PlanType,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Selected plan type '{selected_type}'")
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if selected_type == PlanType.DEVICES and plan.device_limit == -1:
        plan.device_limit = 1
    elif selected_type == PlanType.TRAFFIC and plan.traffic_limit == -1:
        plan.traffic_limit = 100
    elif selected_type == PlanType.BOTH:
        if plan.traffic_limit == -1:
            plan.traffic_limit = 100
        if plan.device_limit == -1:
            plan.device_limit = 1

    plan.type = selected_type
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully updated plan type to '{plan.type.name}'")
    await dialog_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


async def on_availability_select(
    callback: CallbackQuery,
    widget: Select[PlanAvailability],
    dialog_manager: DialogManager,
    selected_availability: PlanAvailability,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    logger.debug(f"{log(user)} Selected plan availability '{selected_availability}'")

    plan.availability = selected_availability
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully updated plan availability to '{plan.availability}'")
    await dialog_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


async def on_archived_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.is_archived = not plan.is_archived
    if not plan.is_archived:
        plan.archived_renew_mode = ArchivedPlanRenewMode.SELF_RENEW
        plan.replacement_plan_ids = []

    adapter.save(plan)
    logger.info(f"{log(user)} Successfully toggled archived status to '{plan.is_archived}'")


async def on_archived_renew_mode_select(
    callback: CallbackQuery,
    widget: Select[ArchivedPlanRenewMode],
    dialog_manager: DialogManager,
    selected_mode: ArchivedPlanRenewMode,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.archived_renew_mode = selected_mode
    if selected_mode != ArchivedPlanRenewMode.REPLACE_ON_RENEW:
        plan.replacement_plan_ids = []

    adapter.save(plan)
    logger.info(f"{log(user)} Successfully updated archived renew mode to '{selected_mode}'")
    await dialog_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    logger.debug(f"{log(user)} Attempted to toggle plan active status")

    plan.is_active = not plan.is_active
    adapter.save(plan)
    logger.info(f"{log(user)} Successfully toggled plan active status to '{plan.is_active}'")


async def on_replacement_plan_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if selected_plan_id in plan.replacement_plan_ids:
        plan.replacement_plan_ids.remove(selected_plan_id)
        logger.info(f"{log(user)} Removed replacement plan '{selected_plan_id}'")
    else:
        plan.replacement_plan_ids.append(selected_plan_id)
        logger.info(f"{log(user)} Added replacement plan '{selected_plan_id}'")

    adapter.save(plan)


async def on_upgrade_target_select(
    callback: CallbackQuery,
    widget: Select[int],
    dialog_manager: DialogManager,
    selected_plan_id: int,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if selected_plan_id in plan.upgrade_to_plan_ids:
        plan.upgrade_to_plan_ids.remove(selected_plan_id)
        logger.info(f"{log(user)} Removed upgrade target '{selected_plan_id}'")
    else:
        plan.upgrade_to_plan_ids.append(selected_plan_id)
        logger.info(f"{log(user)} Added upgrade target '{selected_plan_id}'")

    adapter.save(plan)


@inject
async def on_traffic_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set plan traffic limit")

    if message.text is None or not (message.text.isdigit() and int(message.text) > 0):
        logger.warning(f"{log(user)} Invalid traffic limit input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-number"),
        )
        return

    number = int(message.text)
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.traffic_limit = number
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully set plan traffic limit to '{plan.traffic_limit}'")
    await dialog_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


async def on_strategy_select(
    callback: CallbackQuery,
    widget: Select[TrafficLimitStrategy],
    dialog_manager: DialogManager,
    selected_strategy: TrafficLimitStrategy,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    logger.debug(f"{log(user)} Selected plan traffic strategy '{selected_strategy}'")

    plan.traffic_limit_strategy = selected_strategy
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully updated plan traffic strategy to '{plan.availability}'")


@inject
async def on_devices_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set plan device limit")

    if message.text is None or not (message.text.isdigit() and int(message.text) > 0):
        logger.warning(f"{log(user)} Invalid device limit input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-number"),
        )
        return

    number = int(message.text)
    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    plan.device_limit = number
    adapter.save(plan)

    logger.info(f"{log(user)} Successfully set plan device limit to '{plan.device_limit}'")
    await dialog_manager.switch_to(state=RemnashopPlans.CONFIGURATOR)


async def on_duration_select(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    sub_manager.dialog_data["selected_duration"] = int(sub_manager.item_id)
    logger.debug(f"{log(user)} Selected duration '{sub_manager.item_id}' days")
    await sub_manager.switch_to(state=RemnashopPlans.PRICES)


@inject
async def on_duration_remove(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    await sub_manager.load_data()
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to remove duration")

    adapter = DialogDataAdapter(sub_manager.manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if len(plan.durations) <= 1:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-duration-last"),
        )
        return

    duration_to_remove = int(sub_manager.item_id)
    new_durations = [d for d in plan.durations if d.days != duration_to_remove]
    plan.durations = new_durations
    adapter.save(plan)
    logger.info(f"{log(user)} Successfully removed duration '{duration_to_remove}' days from plan")


@inject
async def on_duration_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to add new plan duration")

    number = parse_int(message.text)

    if number is None or not (number > 0 or number == -1):
        logger.warning(f"{log(user)} Provided invalid duration input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-number"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if plan.get_duration(number):
        logger.warning(f"{log(user)} Provided already existing duration")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-duration-already-exists"),
        )
        return

    plan.durations.append(
        PlanDurationDto(
            days=number,
            prices=[
                PlanPriceDto(
                    currency=currency,
                    price=100,
                )
                for currency in (Currency.USD, Currency.XTR, Currency.RUB)
            ],
        )
    )
    adapter.save(plan)

    logger.info(f"{log(user)} New duration '{number}' days added to plan")
    await dialog_manager.switch_to(state=RemnashopPlans.DURATIONS)


async def on_currency_select(
    callback: CallbackQuery,
    widget: Select[Currency],
    dialog_manager: DialogManager,
    selected_currency: Currency,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.info(f"{log(user)} Selected currency '{selected_currency}'")
    dialog_manager.dialog_data["selected_currency"] = selected_currency.value
    await dialog_manager.switch_to(state=RemnashopPlans.PRICE)


@inject
async def on_price_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    pricing_service: FromDishka[PricingService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set plan price")

    if message.text is None:
        logger.warning(f"{log(user)} Provided empty price input")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-number"),
        )
        return

    selected_duration = dialog_manager.dialog_data.get("selected_duration")
    selected_currency = dialog_manager.dialog_data.get("selected_currency")

    if not selected_duration or not selected_currency:
        raise ValueError("Missing duration or currency selection for price input")

    try:
        new_price = pricing_service.parse_price(message.text, selected_currency)
    except ValueError:
        logger.warning(f"{log(user)} Provided invalid price input: '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-number"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    for duration in plan.durations:
        if duration.days == selected_duration:
            for price in duration.prices:
                if price.currency == selected_currency:
                    price.price = new_price
                    logger.info(
                        f"{log(user)} Updated price for duration '{duration.days}' "
                        f"and currency '{selected_currency}' to '{new_price}'"
                    )
                    break
            break

    adapter.save(plan)
    await dialog_manager.switch_to(state=RemnashopPlans.PRICES)


@inject
async def on_allowed_user_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    notification_service: FromDishka[NotificationService],
) -> None:
    dialog_manager.show_mode = ShowMode.EDIT
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to set allowed id for plan")

    if message.text is None or not message.text.isdigit():
        logger.warning(f"{log(user)} Provided non-numeric user ID")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-invalid-user-id"),
        )
        return

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    allowed_user = await user_service.get(telegram_id=int(message.text))

    if not allowed_user:
        logger.warning(f"{log(user)} No user found with Telegram ID '{message.text}'")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-no-user-found"),
        )
        return  # NOTE: Allow adding non-existent users to the list?

    if allowed_user.telegram_id in plan.allowed_user_ids:
        logger.warning(f"{log(user)} User '{allowed_user.telegram_id}' is already allowed for plan")
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-plan-user-already-allowed"),
        )
        return

    plan.allowed_user_ids.append(allowed_user.telegram_id)
    adapter.save(plan)


@inject
async def on_allowed_user_remove(
    callback: CallbackQuery,
    widget: Button,
    sub_manager: SubManager,
) -> None:
    user: UserDto = sub_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to remove allowed user from plan")
    await sub_manager.load_data()
    user_id = int(sub_manager.item_id)

    adapter = DialogDataAdapter(sub_manager.manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    logger.info(f"{log(user)} Removed allowed user ID '{user_id}' from plan")
    plan.allowed_user_ids.remove(user_id)
    adapter.save(plan)


@inject
async def on_squads(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    remnawave_service: FromDishka[RemnawaveService],
    notification_service: FromDishka[NotificationService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    response = await remnawave_service.get_internal_squads()
    if not response.internal_squads:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(i18n_key="ntf-squads-empty"),
        )
        return

    await dialog_manager.switch_to(state=RemnashopPlans.SQUADS)


@inject
async def on_internal_squad_select(
    callback: CallbackQuery,
    widget: Select[UUID],
    dialog_manager: DialogManager,
    selected_squad: UUID,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if selected_squad in plan.internal_squads:
        plan.internal_squads.remove(selected_squad)
        logger.info(f"{log(user)} Unset squad '{selected_squad}'")
    else:
        plan.internal_squads.append(selected_squad)
        logger.info(f"{log(user)} Set squad '{selected_squad}'")

    adapter.save(plan)


@inject
async def on_external_squad_select(
    callback: CallbackQuery,
    widget: Select[UUID],
    dialog_manager: DialogManager,
    selected_squad: UUID,
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]

    adapter = DialogDataAdapter(dialog_manager)
    plan = adapter.load(PlanDto)

    if not plan:
        raise ValueError("PlanDto not found in dialog data")

    if selected_squad == plan.external_squad:
        plan.external_squad = None
        logger.info(f"{log(user)} Unset squad '{selected_squad}'")
    else:
        plan.external_squad = selected_squad
        logger.info(f"{log(user)} Set squad '{selected_squad}'")

    adapter.save(plan)


async def _notify_plan_message(
    *,
    user: UserDto,
    notification_service: NotificationService,
    i18n_key: str,
) -> None:
    await notification_service.notify_user(
        user=user,
        payload=MessagePayload(i18n_key=i18n_key),
    )


def _normalize_plan_limits(plan_dto: PlanDto) -> None:
    if plan_dto.type == PlanType.DEVICES:
        plan_dto.traffic_limit = -1
    elif plan_dto.type == PlanType.TRAFFIC:
        plan_dto.device_limit = -1
    elif plan_dto.type == PlanType.UNLIMITED:
        plan_dto.traffic_limit = -1
        plan_dto.device_limit = -1

    if plan_dto.availability != PlanAvailability.ALLOWED:
        plan_dto.allowed_user_ids = []

    if not plan_dto.is_archived:
        plan_dto.archived_renew_mode = ArchivedPlanRenewMode.SELF_RENEW
        plan_dto.replacement_plan_ids = []


async def _prepare_trial_plan(
    *,
    user: UserDto,
    plan_dto: PlanDto,
    notification_service: NotificationService,
    plan_service: PlanService,
) -> bool:
    if plan_dto.availability != PlanAvailability.TRIAL:
        return True

    existing_trial = await plan_service.get_trial_plan()
    if existing_trial and existing_trial.id != plan_dto.id:
        await _notify_plan_message(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-plan-trial-already-exists",
        )
        return False

    if len(plan_dto.durations) > 1:
        await _notify_plan_message(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-plan-trial-once-duration",
        )
        return False

    for duration in plan_dto.durations:
        for price in duration.prices:
            price.price = Decimal("0")
    return True


async def _load_plan_for_confirmation(
    *,
    dialog_manager: DialogManager,
    user: UserDto,
    notification_service: NotificationService,
) -> PlanDto:
    adapter = DialogDataAdapter(dialog_manager)
    plan_dto = adapter.load(PlanDto)
    if plan_dto:
        return plan_dto

    await _notify_plan_message(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-plan-save-error",
    )
    raise ValueError("PlanDto not found in dialog data")


async def _persist_existing_plan(
    *,
    user: UserDto,
    plan_dto: PlanDto,
    notification_service: NotificationService,
    plan_service: PlanService,
    subscription_service: SubscriptionService,
) -> bool:
    logger.info(f"{log(user)} Updating existing plan with ID '{plan_dto.id}'")
    try:
        updated_plan = await plan_service.update(plan_dto)
    except PlanValidationError as exception:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-plan-validation-error",
                i18n_kwargs={"error": str(exception)},
            ),
        )
        logger.warning(f"{log(user)} Plan validation failed: {exception}")
        return False
    if not updated_plan:
        await _notify_plan_message(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-plan-save-error",
        )
        return False

    updated_subscriptions = await subscription_service.sync_plan_snapshot_metadata(updated_plan)
    logger.info(f"{log(user)} Plan '{plan_dto.name}' updated successfully")
    logger.info(
        f"{log(user)} Plan snapshot metadata propagated to "
        f"'{updated_subscriptions}' subscription(s)"
    )
    await _notify_plan_message(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-plan-updated-success",
    )
    return True


async def _persist_new_plan(
    *,
    user: UserDto,
    plan_dto: PlanDto,
    notification_service: NotificationService,
    plan_service: PlanService,
) -> bool:
    existing_plan: Optional[PlanDto] = await plan_service.get_by_name(plan_name=plan_dto.name)
    if existing_plan:
        logger.warning(f"{log(user)} Plan with name '{plan_dto.name}' already exists. Aborting")
        await _notify_plan_message(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-plan-name-already-exists",
        )
        return False

    logger.info(f"{log(user)} Creating new plan with name '{plan_dto.name}'")
    try:
        plan = await plan_service.create(plan_dto)
    except PlanValidationError as exception:
        await notification_service.notify_user(
            user=user,
            payload=MessagePayload(
                i18n_key="ntf-plan-validation-error",
                i18n_kwargs={"error": str(exception)},
            ),
        )
        logger.warning(f"{log(user)} Plan validation failed: {exception}")
        return False
    logger.info(f"{log(user)} Plan '{plan.name}' created successfully")
    await _notify_plan_message(
        user=user,
        notification_service=notification_service,
        i18n_key="ntf-plan-created-success",
    )
    return True


@inject
async def on_confirm_plan(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    notification_service: FromDishka[NotificationService],
    plan_service: FromDishka[PlanService],
    subscription_service: FromDishka[SubscriptionService],
) -> None:
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    logger.debug(f"{log(user)} Attempted to confirm plan")

    plan_dto = await _load_plan_for_confirmation(
        dialog_manager=dialog_manager,
        user=user,
        notification_service=notification_service,
    )
    if not plan_dto.internal_squads:
        await _notify_plan_message(
            user=user,
            notification_service=notification_service,
            i18n_key="ntf-plan-internal-squads-empty",
        )
        return

    _normalize_plan_limits(plan_dto)
    if not await _prepare_trial_plan(
        user=user,
        plan_dto=plan_dto,
        notification_service=notification_service,
        plan_service=plan_service,
    ):
        return

    if plan_dto.id:
        saved = await _persist_existing_plan(
            user=user,
            plan_dto=plan_dto,
            notification_service=notification_service,
            plan_service=plan_service,
            subscription_service=subscription_service,
        )
    else:
        saved = await _persist_new_plan(
            user=user,
            plan_dto=plan_dto,
            notification_service=notification_service,
            plan_service=plan_service,
        )

    if not saved:
        return

    await dialog_manager.reset_stack()
    await dialog_manager.start(state=RemnashopPlans.MAIN)
