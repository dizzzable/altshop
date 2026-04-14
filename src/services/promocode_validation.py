from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.core.enums import PromocodeAvailability
from src.infrastructure.database.models.dto import PromocodeDto, UserDto

if TYPE_CHECKING:
    from .promocode import PromocodeService
else:
    PromocodeService = Any


class ActivationError(StrEnum):
    """Ошибки активации промокода."""

    NOT_FOUND = auto()
    INACTIVE = auto()
    EXPIRED = auto()
    DEPLETED = auto()
    ALREADY_ACTIVATED = auto()
    NOT_AVAILABLE_FOR_USER = auto()


@dataclass
class ActivationResult:
    """Результат активации промокода."""

    success: bool
    error: Optional[ActivationError] = None
    promocode: Optional[PromocodeDto] = None
    message_key: Optional[str] = None


async def check_user_activation(
    service: PromocodeService,
    promocode_id: int,
    user_telegram_id: int,
) -> bool:
    """Return whether user has already activated this promocode."""
    db_promocode = await service.uow.repository.promocodes.get(promocode_id)
    if not db_promocode:
        return False

    for activation in db_promocode.activations:
        if activation.user_telegram_id == user_telegram_id:
            return True
    return False


async def check_availability(
    service: PromocodeService,
    promocode: PromocodeDto,
    user: UserDto,
) -> bool:
    """Check whether promocode is available for the user."""
    if promocode.availability == PromocodeAvailability.ALL:
        return True

    if promocode.availability == PromocodeAvailability.NEW:
        # Для новых пользователей (без подписок)
        has_subscriptions = user.current_subscription is not None or (
            hasattr(user, "subscriptions") and len(user.subscriptions) > 0
        )
        return not has_subscriptions

    if promocode.availability == PromocodeAvailability.EXISTING:
        # Для существующих пользователей (с подписками)
        has_subscriptions = user.current_subscription is not None or (
            hasattr(user, "subscriptions") and len(user.subscriptions) > 0
        )
        return has_subscriptions

    if promocode.availability == PromocodeAvailability.INVITED:
        # Для приглашенных пользователей
        return user.is_invited_user

    if promocode.availability == PromocodeAvailability.ALLOWED:
        # For explicitly allowed users from allowed_user_ids.
        if not promocode.allowed_user_ids:
            logger.warning(
                f"Promocode '{promocode.code}' has ALLOWED availability but no allowed_user_ids"
            )
            return False
        return user.telegram_id in promocode.allowed_user_ids

    return False


async def validate_promocode(
    service: PromocodeService,
    code: str,
    user: UserDto,
) -> ActivationResult:
    """Валидация промокода перед активацией."""
    normalized_code = code.strip().upper()
    if not normalized_code:
        return ActivationResult(
            success=False,
            error=ActivationError.NOT_FOUND,
            message_key="ntf-promocode-not-found",
        )

    promocode = await service.get_by_code(normalized_code)

    if not promocode:
        return ActivationResult(
            success=False,
            error=ActivationError.NOT_FOUND,
            message_key="ntf-promocode-not-found",
        )

    if not promocode.is_active:
        return ActivationResult(
            success=False,
            error=ActivationError.INACTIVE,
            message_key="ntf-promocode-inactive",
        )

    if promocode.is_expired:
        return ActivationResult(
            success=False,
            error=ActivationError.EXPIRED,
            message_key="ntf-promocode-expired",
        )

    if promocode.is_depleted:
        return ActivationResult(
            success=False,
            error=ActivationError.DEPLETED,
            message_key="ntf-promocode-depleted",
        )

    already_activated = await service.check_user_activation(promocode.id, user.telegram_id)  # type: ignore[arg-type]
    if already_activated:
        return ActivationResult(
            success=False,
            error=ActivationError.ALREADY_ACTIVATED,
            message_key="ntf-promocode-already-activated",
        )

    is_available = await service._check_availability(promocode, user)
    if not is_available:
        return ActivationResult(
            success=False,
            error=ActivationError.NOT_AVAILABLE_FOR_USER,
            message_key="ntf-promocode-not-available",
        )

    return ActivationResult(
        success=True,
        promocode=promocode,
        message_key="ntf-promocode-valid",
    )
