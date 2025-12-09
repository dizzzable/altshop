from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.config import AppConfig
from src.core.enums import UserRole
from src.infrastructure.database.models.dto import UserDto
from src.services.partner import PartnerService
from src.services.user import UserService


@inject
async def remnashop_main_getter(
    dialog_manager: DialogManager,
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    """Getter для главного окна RemnaShop."""
    # Получаем количество ожидающих запросов на вывод
    stats = await partner_service.get_partner_statistics()
    pending_withdrawals = stats.get("pending_withdrawals", 0)
    
    return {
        "pending_withdrawals": pending_withdrawals,
    }


@inject
async def admins_getter(
    dialog_manager: DialogManager,
    config: AppConfig,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    devs: list[UserDto] = await user_service.get_by_role(role=UserRole.DEV)
    admins: list[UserDto] = await user_service.get_by_role(role=UserRole.ADMIN)
    all_users = devs + admins

    users_dicts = [
        {
            "user_id": user.telegram_id,
            "user_name": user.name,
            "deletable": user.telegram_id not in config.bot.dev_id,
        }
        for user in all_users
    ]

    return {"admins": users_dicts}
