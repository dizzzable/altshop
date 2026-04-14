from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.core.enums import PromocodeRewardType
from src.infrastructure.database.models.dto import PromocodeDto
from src.infrastructure.database.models.dto.promocode import PromocodeActivationBaseDto
from src.infrastructure.database.models.sql import Promocode, PromocodeActivation

from .promocode_validation import ActivationError, ActivationResult

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import UserDto

    from .promocode import PromocodeService
    from .subscription import SubscriptionService
    from .user import UserService
else:
    PromocodeService = Any
    SubscriptionService = Any
    UserService = Any
    UserDto = Any


async def create(
    service: PromocodeService,
    promocode: PromocodeDto,
    *,
    auto_commit: bool = True,
) -> PromocodeDto:
    """Создание нового промокода."""
    existing_promocode = await service.get_by_code(promocode.code)
    if existing_promocode:
        raise ValueError(f"Promocode with code '{promocode.code}' already exists")

    data = promocode.model_dump(exclude={"id", "activations", "created_at", "updated_at"})

    if promocode.plan:
        data["plan"] = promocode.plan.model_dump(mode="json")

    db_promocode = Promocode(**data)
    db_created_promocode = await service.uow.repository.promocodes.create(db_promocode)
    if auto_commit:
        await service.uow.commit()

    logger.info(f"Created promocode '{promocode.code}' with type '{promocode.reward_type}'")
    return PromocodeDto.from_model(db_created_promocode)  # type: ignore[return-value]


async def get(service: PromocodeService, promocode_id: int) -> Optional[PromocodeDto]:
    db_promocode = await service.uow.repository.promocodes.get(promocode_id)

    if db_promocode:
        logger.debug(f"Retrieved promocode '{promocode_id}'")
    else:
        logger.warning(f"Promocode '{promocode_id}' not found")

    return PromocodeDto.from_model(db_promocode)


async def get_by_code(
    service: PromocodeService,
    promocode_code: str,
) -> Optional[PromocodeDto]:
    db_promocode = await service.uow.repository.promocodes.get_by_code(promocode_code)

    if db_promocode:
        logger.debug(f"Retrieved promocode by code '{promocode_code}'")
    else:
        logger.warning(f"Promocode with code '{promocode_code}' not found")

    return PromocodeDto.from_model(db_promocode)


async def get_all(service: PromocodeService) -> list[PromocodeDto]:
    db_promocodes = await service.uow.repository.promocodes.get_all()
    logger.debug(f"Retrieved '{len(db_promocodes)}' promocodes")
    return PromocodeDto.from_model_list(db_promocodes)


async def update(
    service: PromocodeService,
    promocode: PromocodeDto,
) -> Optional[PromocodeDto]:
    db_updated_promocode = await service.uow.repository.promocodes.update(
        promocode_id=promocode.id,  # type: ignore[arg-type]
        **promocode.changed_data,
    )

    if db_updated_promocode:
        logger.info(f"Updated promocode '{promocode.code}' successfully")
    else:
        logger.warning(
            f"Attempted to update promocode '{promocode.code}' "
            f"(ID: '{promocode.id}'), but promocode was not found or update failed"
        )

    return PromocodeDto.from_model(db_updated_promocode)


async def delete(service: PromocodeService, promocode_id: int) -> bool:
    result = await service.uow.repository.promocodes.delete(promocode_id)

    if result:
        logger.info(f"Promocode '{promocode_id}' deleted successfully")
    else:
        logger.warning(
            f"Failed to delete promocode '{promocode_id}'. "
            f"Promocode not found or deletion failed"
        )

    return result


async def filter_by_type(
    service: PromocodeService,
    promocode_type: PromocodeRewardType,
) -> list[PromocodeDto]:
    db_promocodes = await service.uow.repository.promocodes.filter_by_type(promocode_type)
    logger.debug(
        f"Filtered promocodes by type '{promocode_type}', found '{len(db_promocodes)}'"
    )
    return PromocodeDto.from_model_list(db_promocodes)


async def filter_active(
    service: PromocodeService,
    is_active: bool = True,
) -> list[PromocodeDto]:
    db_promocodes = await service.uow.repository.promocodes.filter_active(is_active)
    logger.debug(f"Filtered active promocodes: '{is_active}', found '{len(db_promocodes)}'")
    return PromocodeDto.from_model_list(db_promocodes)


async def activate(
    service: PromocodeService,
    code: str,
    user: UserDto,
    user_service: UserService,
    subscription_service: Optional[SubscriptionService] = None,
    target_subscription_id: Optional[int] = None,
) -> ActivationResult:
    """
    Activate a promocode for user and apply reward by reward type.

    Supported reward types:
    - DURATION, TRAFFIC, DEVICES
    - SUBSCRIPTION (new or target subscription extension)
    - PERSONAL_DISCOUNT, PURCHASE_DISCOUNT

    Args:
        code: Promocode string.
        user: Current user.
        user_service: User service.
        subscription_service: Subscription service.
        target_subscription_id: Optional target subscription for SUBSCRIPTION reward.
    """
    normalized_code = code.strip().upper()
    validation_result = await service.validate_promocode(normalized_code, user)
    if not validation_result.success:
        return validation_result

    promocode = validation_result.promocode
    if not promocode:
        return ActivationResult(
            success=False,
            error=ActivationError.NOT_FOUND,
            message_key="ntf-promocode-not-found",
        )

    try:
        reward_value = promocode.reward if promocode.reward is not None else 0
        if (
            reward_value == 0
            and promocode.reward_type == PromocodeRewardType.SUBSCRIPTION
            and promocode.plan
            and promocode.plan.duration
        ):
            reward_value = promocode.plan.duration

        activation = PromocodeActivation(
            promocode_id=promocode.id,
            user_telegram_id=user.telegram_id,
            promocode_code=promocode.code,
            reward_type=promocode.reward_type,
            reward_value=reward_value,
            target_subscription_id=target_subscription_id,
        )
        service.uow.repository.promocodes.session.add(activation)
        await service.uow.repository.promocodes.session.flush()

        reward_applied = await service._apply_reward(
            promocode=promocode,
            user=user,
            user_service=user_service,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )

        if not reward_applied:
            logger.error(
                f"Failed to apply reward for promocode '{normalized_code}' "
                f"to user '{user.telegram_id}'"
            )
            await service.uow.rollback()
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_AVAILABLE_FOR_USER,
                message_key="ntf-promocode-reward-failed",
            )

        await service.uow.commit()
    except Exception as exception:
        logger.error(
            f"Error activating promocode '{normalized_code}' "
            f"for user '{user.telegram_id}': {exception}"
        )
        await service.uow.rollback()
        return ActivationResult(
            success=False,
            error=ActivationError.NOT_AVAILABLE_FOR_USER,
            message_key="ntf-promocode-activation-error",
        )

    logger.info(
        f"User '{user.telegram_id}' activated promocode '{normalized_code}' "
        f"(type: {promocode.reward_type}, reward: {promocode.reward})"
    )

    return ActivationResult(
        success=True,
        promocode=promocode,
        message_key=service._get_success_message_key(promocode.reward_type),
    )


async def get_activations_count(
    service: PromocodeService,
    promocode_id: int,
) -> int:
    """Получение количества активаций промокода."""
    promocode = await service.get(promocode_id)
    if promocode:
        return len(promocode.activations)
    return 0


async def get_user_activations(
    service: PromocodeService,
    user_telegram_id: int,
) -> list[PromocodeActivationBaseDto]:
    """Return all promocode activations for a user."""
    total = await service.uow.repository.promocodes.count_activations_by_user(user_telegram_id)
    if total == 0:
        return []

    db_activations = await service.uow.repository.promocodes.get_activations_by_user(
        user_telegram_id,
        limit=total,
        offset=0,
    )
    return PromocodeActivationBaseDto.from_model_list(db_activations)


async def get_user_activation_history(
    service: PromocodeService,
    user_telegram_id: int,
    *,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[PromocodeActivationBaseDto], int]:
    safe_page = max(page, 1)
    safe_limit = min(max(limit, 1), 100)
    offset = (safe_page - 1) * safe_limit

    total = await service.uow.repository.promocodes.count_activations_by_user(user_telegram_id)
    if total == 0:
        return [], 0

    db_activations = await service.uow.repository.promocodes.get_activations_by_user(
        user_telegram_id,
        limit=safe_limit,
        offset=offset,
    )
    activations = PromocodeActivationBaseDto.from_model_list(db_activations)
    return activations, total
