from __future__ import annotations

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject

from src.core.constants import DATETIME_FORMAT
from src.core.enums import UserRole
from src.core.utils.formatters import (
    i18n_format_days,
    i18n_format_device_limit,
    i18n_format_traffic_limit,
)
from src.services.plan import PlanService
from src.services.transaction import TransactionService
from src.services.user import UserService


async def discount_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"percentages": [0, 5, 10, 25, 40, 50, 70, 80, 100]}


async def purchase_discount_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"percentages": [0, 5, 10, 25, 40, 50, 70, 80, 100]}


@inject
async def points_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_points_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
    )


async def _build_points_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    formatted_points = [
        {
            "operation": "+" if value > 0 else "",
            "points": value,
        }
        for value in [5, -5, 25, -25, 50, -50, 100, -100]
    ]

    return {
        "current_points": target_user.points,
        "points": formatted_points,
    }


async def traffic_limit_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    formatted_traffic = [
        {
            "traffic_limit": i18n_format_traffic_limit(value),
            "traffic": value,
        }
        for value in [100, 200, 300, 500, 1024, 2048, -1]
    ]

    return {"traffic_count": formatted_traffic}


async def device_limit_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    return {"devices_count": [1, 2, 3, 4, 5, 10, -1]}


@inject
async def transactions_getter(
    dialog_manager: DialogManager,
    transaction_service: FromDishka[TransactionService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_transactions_getter_payload(
        dialog_manager=dialog_manager,
        transaction_service=transaction_service,
    )


async def _build_transactions_getter_payload(
    *,
    dialog_manager: DialogManager,
    transaction_service: TransactionService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    transactions = await transaction_service.get_by_user(target_telegram_id)

    if not transactions:
        raise ValueError(f"Transactions not found for user '{target_telegram_id}'")

    formatted_transactions = [
        {
            "payment_id": transaction.payment_id,
            "status": transaction.status,
            "created_at": transaction.created_at.strftime(DATETIME_FORMAT),
        }
        for transaction in transactions
    ]

    return {"transactions": list(reversed(formatted_transactions))}


@inject
async def transaction_getter(
    dialog_manager: DialogManager,
    transaction_service: FromDishka[TransactionService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_transaction_getter_payload(
        dialog_manager=dialog_manager,
        transaction_service=transaction_service,
    )


async def _build_transaction_getter_payload(
    *,
    dialog_manager: DialogManager,
    transaction_service: TransactionService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    selected_transaction = dialog_manager.dialog_data["selected_transaction"]
    transaction = await transaction_service.get(selected_transaction)

    if not transaction:
        raise ValueError(
            f"Transaction '{selected_transaction}' not found for user '{target_telegram_id}'"
        )

    return {
        "is_test": transaction.is_test,
        "payment_id": str(transaction.payment_id),
        "purchase_type": transaction.purchase_type,
        "transaction_status": transaction.status,
        "gateway_type": transaction.gateway_type,
        "final_amount": transaction.pricing.final_amount,
        "currency": transaction.currency.symbol,
        "discount_percent": transaction.pricing.discount_percent,
        "original_amount": transaction.pricing.original_amount,
        "created_at": transaction.created_at.strftime(DATETIME_FORMAT),
        "plan_name": transaction.plan.name,
        "plan_type": transaction.plan.type,
        "plan_traffic_limit": i18n_format_traffic_limit(transaction.plan.traffic_limit),
        "plan_device_limit": i18n_format_device_limit(transaction.plan.device_limit),
        "plan_duration": i18n_format_days(transaction.plan.duration),
    }


@inject
async def give_access_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    plan_service: FromDishka[PlanService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_give_access_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        plan_service=plan_service,
    )


async def _build_give_access_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    plan_service: PlanService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    plans = await plan_service.get_allowed_plans()
    if not plans:
        raise ValueError("Allowed plans not found")

    formatted_plans = [
        {
            "plan_name": plan.name,
            "plan_id": plan.id,
            "selected": target_telegram_id in plan.allowed_user_ids,
        }
        for plan in plans
    ]

    return {"plans": formatted_plans}


@inject
async def role_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_role_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
    )


async def _build_role_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    roles = [role for role in UserRole if role != target_user.role]
    return {"roles": roles}
