from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Button, Select
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner
from loguru import logger

from src.bot.states import DashboardPromocodes
from src.core.constants import USER_KEY
from src.core.enums import PromocodeAvailability, PromocodeRewardType
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import format_user_log as log
from src.infrastructure.database.models.dto import PlanDto, PlanSnapshotDto, PromocodeDto, UserDto
from src.services.plan import PlanService
from src.services.promocode import PromocodeService


@inject
async def on_active_toggle(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Переключение статуса активности промокода"""
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.is_active = not promocode.is_active
        adapter.save(promocode)
        logger.debug(f"Toggled promocode active status to {promocode.is_active}")


@inject
async def on_code_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка ввода кода промокода"""
    if not message.text:
        return
    
    code = message.text.strip().upper()
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.code = code
        adapter.save(promocode)
        logger.debug(f"Set promocode code to '{code}'")
    
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_type_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_type: str,
) -> None:
    """Выбор типа награды промокода"""
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.reward_type = PromocodeRewardType(selected_type)
        # Сброс награды при смене типа
        if promocode.reward_type == PromocodeRewardType.SUBSCRIPTION:
            promocode.reward = None
        else:
            promocode.reward = 1
            promocode.plan = None
        adapter.save(promocode)
        logger.debug(f"Set promocode type to '{selected_type}'")
    
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_availability_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_availability: str,
) -> None:
    """Выбор доступности промокода"""
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.availability = PromocodeAvailability(selected_availability)
        adapter.save(promocode)
        logger.debug(f"Set promocode availability to '{selected_availability}'")
    
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_reward_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка ввода награды промокода"""
    if not message.text:
        return
    
    try:
        reward = int(message.text.strip())
        if reward <= 0:
            await message.answer(i18n.get("ntf-invalid-value"))
            return
    except ValueError:
        await message.answer(i18n.get("ntf-invalid-value"))
        return
    
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.reward = reward
        adapter.save(promocode)
        logger.debug(f"Set promocode reward to '{reward}'")
    
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_lifetime_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка ввода срока действия промокода"""
    if not message.text:
        return
    
    try:
        lifetime = int(message.text.strip())
        # -1 означает бессрочный
        if lifetime < -1 or lifetime == 0:
            await message.answer(i18n.get("ntf-invalid-value"))
            return
    except ValueError:
        await message.answer(i18n.get("ntf-invalid-value"))
        return
    
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.lifetime = lifetime
        adapter.save(promocode)
        logger.debug(f"Set promocode lifetime to '{lifetime}'")
    
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_max_activations_input(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Обработка ввода лимита активаций"""
    if not message.text:
        return
    
    try:
        max_activations = int(message.text.strip())
        # -1 означает безлимитный
        if max_activations < -1 or max_activations == 0:
            await message.answer(i18n.get("ntf-invalid-value"))
            return
    except ValueError:
        await message.answer(i18n.get("ntf-invalid-value"))
        return
    
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.max_activations = max_activations
        adapter.save(promocode)
        logger.debug(f"Set promocode max_activations to '{max_activations}'")
    
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_confirm_promocode(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Подтверждение создания/обновления промокода"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if not promocode:
        await callback.answer(i18n.get("ntf-error"), show_alert=True)
        return
    
    # Валидация
    if not promocode.code:
        await callback.answer(i18n.get("ntf-promocode-code-required"), show_alert=True)
        return
    
    if promocode.reward_type == PromocodeRewardType.SUBSCRIPTION and not promocode.plan:
        await callback.answer(i18n.get("ntf-promocode-plan-required"), show_alert=True)
        return
    
    if promocode.reward_type != PromocodeRewardType.SUBSCRIPTION and not promocode.reward:
        await callback.answer(i18n.get("ntf-promocode-reward-required"), show_alert=True)
        return
    
    try:
        if promocode.id:
            # Обновление существующего промокода
            updated_promocode = await promocode_service.update(promocode)
            if updated_promocode:
                logger.info(f"{log(user)} Updated promocode '{promocode.code}'")
                await callback.answer(i18n.get("ntf-promocode-updated"), show_alert=True)
            else:
                await callback.answer(i18n.get("ntf-error"), show_alert=True)
                return
        else:
            # Создание нового промокода
            # Проверка уникальности кода
            existing = await promocode_service.get_by_code(promocode.code)
            if existing:
                await callback.answer(i18n.get("ntf-promocode-code-exists"), show_alert=True)
                return
            
            created_promocode = await promocode_service.create(promocode)
            logger.info(f"{log(user)} Created promocode '{created_promocode.code}'")
            await callback.answer(i18n.get("ntf-promocode-created"), show_alert=True)
        
        # Очистка данных и возврат к списку
        adapter.clear()
        await dialog_manager.switch_to(DashboardPromocodes.MAIN)
        
    except Exception as e:
        logger.error(f"Error saving promocode: {e}")
        await callback.answer(i18n.get("ntf-error"), show_alert=True)


@inject
async def on_promocode_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_promocode_id: int,
    promocode_service: FromDishka[PromocodeService],
) -> None:
    """Выбор промокода из списка для редактирования"""
    promocode = await promocode_service.get(selected_promocode_id)
    
    if promocode:
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(promocode)
        await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)


@inject
async def on_delete_promocode(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Удаление промокода"""
    user: UserDto = dialog_manager.middleware_data[USER_KEY]
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if not promocode or not promocode.id:
        await callback.answer(i18n.get("ntf-error"), show_alert=True)
        return
    
    try:
        result = await promocode_service.delete(promocode.id)
        if result:
            logger.info(f"{log(user)} Deleted promocode '{promocode.code}'")
            await callback.answer(i18n.get("ntf-promocode-deleted"), show_alert=True)
            adapter.clear()
            await dialog_manager.switch_to(DashboardPromocodes.MAIN)
        else:
            await callback.answer(i18n.get("ntf-error"), show_alert=True)
    except Exception as e:
        logger.error(f"Error deleting promocode: {e}")
        await callback.answer(i18n.get("ntf-error"), show_alert=True)


@inject
async def on_search_promocode(
    message: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    i18n: FromDishka[TranslatorRunner],
) -> None:
    """Поиск промокода по коду"""
    if not message.text:
        return
    
    code = message.text.strip().upper()
    promocode = await promocode_service.get_by_code(code)
    
    if promocode:
        adapter = DialogDataAdapter(dialog_manager)
        adapter.save(promocode)
        await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)
    else:
        await message.answer(i18n.get("ntf-promocode-not-found"))


@inject
async def on_generate_code(
    callback: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    """Генерация нового случайного кода"""
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        promocode.code = PromocodeDto.generate_code()
        adapter.save(promocode)
        logger.debug(f"Generated new promocode code: '{promocode.code}'")


@inject
async def on_plan_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_plan_id: int,
    plan_service: FromDishka[PlanService],
) -> None:
    """Выбор плана для промокода типа Подписка"""
    plan = await plan_service.get(selected_plan_id)
    
    if plan:
        adapter = DialogDataAdapter(dialog_manager)
        promocode = adapter.load(PromocodeDto)
        
        if promocode:
            # Сохраняем план в dialog_data для выбора длительности
            dialog_manager.dialog_data["selected_plan"] = plan.model_dump_json()
            dialog_manager.dialog_data["selected_plan_id"] = plan.id
            logger.debug(f"Selected plan '{plan.name}' for promocode")
        
        await dialog_manager.switch_to(DashboardPromocodes.DURATION)


@inject
async def on_duration_select(
    callback: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    selected_duration: int,
    plan_service: FromDishka[PlanService],
) -> None:
    """Выбор длительности плана для промокода"""
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if not promocode:
        return
    
    # Получаем план из dialog_data
    plan_id = dialog_manager.dialog_data.get("selected_plan_id")
    if not plan_id:
        return
    
    plan = await plan_service.get(plan_id)
    if not plan:
        return
    
    # Создаем снимок плана с выбранной длительностью
    plan_snapshot = PlanSnapshotDto.from_plan(plan, selected_duration)
    
    promocode.plan = plan_snapshot
    promocode.reward = None  # Для типа SUBSCRIPTION reward не используется
    adapter.save(promocode)
    
    # Очищаем временные данные
    dialog_manager.dialog_data.pop("selected_plan", None)
    dialog_manager.dialog_data.pop("selected_plan_id", None)
    
    logger.debug(f"Set promocode plan to '{plan.name}' with duration {selected_duration} days")
    await dialog_manager.switch_to(DashboardPromocodes.CONFIGURATOR)