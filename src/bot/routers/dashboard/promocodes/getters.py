from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.enums import PlanType, PromocodeAvailability, PromocodeRewardType
from src.core.utils.adapter import DialogDataAdapter
from src.core.utils.formatters import i18n_format_days, i18n_format_limit, i18n_format_traffic_limit
from src.infrastructure.database.models.dto import PromocodeDto
from src.services.plan import PlanService
from src.services.promocode import PromocodeService


async def configurator_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)

    if promocode is None:
        promocode = PromocodeDto()
        adapter.save(promocode)

    data = promocode.model_dump()

    if promocode.reward:
        if promocode.reward_type == PromocodeRewardType.DURATION:
            reward = i18n_format_days(promocode.reward)
            data.update({"reward": reward})
        elif promocode.reward_type == PromocodeRewardType.TRAFFIC:
            reward = i18n_format_traffic_limit(promocode.reward)
            data.update({"reward": reward})

    helpers = {
        "promocode_type": promocode.reward_type,
        "reward_type": promocode.reward_type,
        "availability_type": promocode.availability,
        "availability": promocode.availability,
        "max_activations": i18n_format_limit(promocode.max_activations),
        "lifetime": i18n_format_days(promocode.lifetime),
    }

    if promocode.plan:
        plan = {
            "plan_name": promocode.plan.name,
            "plan_type": promocode.plan.type,
            "plan_traffic_limit": promocode.plan.traffic_limit,
            "plan_device_limit": promocode.plan.device_limit,
            "plan_duration": promocode.plan.duration,
        }
        data.update(plan)
    else:
        # Provide default values for plan fields to avoid FluentNone errors
        data.update({
            "plan_name": "-",
            "plan_type": PlanType.UNLIMITED,
            "plan_traffic_limit": 0,
            "plan_device_limit": 0,
            "plan_duration": 0,
        })

    data.update(helpers)

    return data


@inject
async def list_getter(
    dialog_manager: DialogManager,
    promocode_service: FromDishka[PromocodeService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для списка промокодов"""
    promocodes = await promocode_service.get_all()
    
    promocodes_data = []
    for promo in promocodes:
        status = "🟢" if promo.is_active else "🔴"
        activations = len(promo.activations)
        max_act = promo.max_activations if promo.max_activations != -1 else "∞"
        display_name = f"{status} {promo.code} ({activations}/{max_act})"
        
        promocodes_data.append({
            "id": promo.id,
            "code": promo.code,
            "display_name": display_name,
            "is_active": promo.is_active,
            "reward_type": promo.reward_type,
            "activations_count": activations,
        })
    
    return {"promocodes": promocodes_data}


async def type_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    """Геттер для выбора типа награды промокода"""
    types = [
        {"type": PromocodeRewardType.DURATION.value},
        {"type": PromocodeRewardType.TRAFFIC.value},
        {"type": PromocodeRewardType.DEVICES.value},
        {"type": PromocodeRewardType.SUBSCRIPTION.value},
        {"type": PromocodeRewardType.PERSONAL_DISCOUNT.value},
        {"type": PromocodeRewardType.PURCHASE_DISCOUNT.value},
    ]
    return {"types": types}


async def availability_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    """Геттер для выбора доступности промокода"""
    availabilities = [
        {"type": PromocodeAvailability.ALL.value},
        {"type": PromocodeAvailability.NEW.value},
        {"type": PromocodeAvailability.EXISTING.value},
        {"type": PromocodeAvailability.INVITED.value},
        {"type": PromocodeAvailability.ALLOWED.value},
    ]
    return {"availabilities": availabilities}


async def reward_getter(dialog_manager: DialogManager, **kwargs: Any) -> dict[str, Any]:
    """Геттер для ввода награды"""
    adapter = DialogDataAdapter(dialog_manager)
    promocode = adapter.load(PromocodeDto)
    
    if promocode:
        return {
            "reward_type": promocode.reward_type,
            "current_reward": promocode.reward,
        }
    
    return {
        "reward_type": PromocodeRewardType.DURATION,
        "current_reward": None,
    }


@inject
async def plan_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для выбора плана для промокода типа Подписка"""
    plans = await plan_service.get_all()
    
    plans_data = []
    for plan in plans:
        status = "🟢" if plan.is_active else "🔴"
        plans_data.append({
            "id": plan.id,
            "name": plan.name,
            "display_name": f"{status} {plan.name}",
        })
    
    return {"plans": plans_data}


@inject
async def duration_getter(
    dialog_manager: DialogManager,
    plan_service: FromDishka[PlanService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    """Геттер для выбора длительности плана для промокода"""
    # Получаем план из dialog_data (сохранен в on_plan_select)
    plan_id = dialog_manager.dialog_data.get("selected_plan_id")
    
    if not plan_id:
        return {"durations": [], "plan_name": "-"}
    
    plan = await plan_service.get(plan_id)
    if not plan:
        return {"durations": [], "plan_name": "-"}
    
    durations_data = []
    
    # Получаем длительности из плана
    if plan.durations:
        for duration in plan.durations:
            key, kw = i18n_format_days(duration.days)
            durations_data.append({
                "days": duration.days,
                "display_name": i18n.get(key, **kw),
            })
    else:
        # Если длительности не заданы, используем стандартные
        for days in [7, 30, 90, 180, 365, -1]:
            key, kw = i18n_format_days(days)
            durations_data.append({
                "days": days,
                "display_name": i18n.get(key, **kw),
            })
    
    return {
        "durations": durations_data,
        "plan_name": plan.name,
    }
