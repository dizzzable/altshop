from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from loguru import logger
from remnawave.exceptions import ConflictError
from remnawave.models import CreateUserRequestDto, DeleteUserResponseDto, UpdateUserRequestDto

from src.core.constants import MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import SubscriptionStatus
from src.core.utils.formatters import (
    format_days_to_datetime,
    format_device_count,
    format_gb_to_bytes,
)
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto, UserDto


async def create_user(
    service: Any,
    user: UserDto,
    plan: PlanSnapshotDto,
    subscription_index: int = 0,
) -> Any:
    existing_subscriptions = await service.subscription_service.get_all_by_user(user.telegram_id)
    active_subscriptions_count = len(
        [
            subscription
            for subscription in existing_subscriptions
            if subscription.status != SubscriptionStatus.DELETED
        ]
    )

    effective_max_subscriptions = await service.settings_service.get_max_subscriptions_for_user(
        user
    )
    if effective_max_subscriptions < 1:
        logger.warning(
            f"Invalid effective max subscriptions '{effective_max_subscriptions}' "
            f"for user '{user.telegram_id}', falling back to 1"
        )
        effective_max_subscriptions = 1

    total_after_creation = active_subscriptions_count + subscription_index + 1
    if total_after_creation > effective_max_subscriptions:
        raise ValueError(
            f"User '{user.telegram_id}' would exceed maximum subscriptions limit "
            f"({effective_max_subscriptions}). Current: {active_subscriptions_count}, "
            f"Requested index: {subscription_index}"
        )

    if total_after_creation > MAX_SUBSCRIPTIONS_PER_USER:
        raise ValueError(
            f"User '{user.telegram_id}' would exceed hard ceiling "
            f"({MAX_SUBSCRIPTIONS_PER_USER}). Current: {active_subscriptions_count}, "
            f"Requested index: {subscription_index}"
        )

    base_index = active_subscriptions_count + subscription_index
    max_retries = 10
    for retry in range(max_retries):
        current_index = base_index + retry
        username = (
            f"{user.remna_name}_sub"
            if current_index == 0
            else f"{user.remna_name}_sub{current_index}"
        )

        logger.info(
            f"Creating RemnaUser '{username}' for plan '{plan.name}' "
            f"(index: {current_index}, retry: {retry})"
        )

        try:
            created_user = await service.remnawave.users.create_user(
                CreateUserRequestDto(
                    expire_at=format_days_to_datetime(plan.duration),
                    username=username,
                    traffic_limit_bytes=format_gb_to_bytes(plan.traffic_limit),
                    traffic_limit_strategy=plan.traffic_limit_strategy,
                    description=user.remna_description,
                    tag=plan.tag,
                    telegram_id=user.telegram_id,
                    hwid_device_limit=format_device_count(plan.device_limit),
                    active_internal_squads=plan.internal_squads,
                    external_squad_uuid=plan.external_squad,
                )
            )

            from remnawave.models import UserResponseDto  # noqa: PLC0415

            if not isinstance(created_user, UserResponseDto):
                raise ValueError("Failed to create RemnaUser: unexpected response")

            logger.info(
                f"RemnaUser '{created_user.telegram_id}' created successfully "
                f"with username '{username}'"
            )
            return created_user

        except ConflictError as exception:
            if "username already exists" in str(exception).lower():
                logger.warning(
                    f"Username '{username}' already exists on panel, trying next index..."
                )
                continue
            raise

    raise ValueError(
        f"Failed to create RemnaUser for '{user.telegram_id}' after {max_retries} retries - "
        "all usernames are taken"
    )


async def updated_user(
    service: Any,
    user: UserDto,
    uuid: UUID,
    plan: Optional[PlanSnapshotDto] = None,
    subscription: Optional[SubscriptionDto] = None,
    reset_traffic: bool = False,
) -> Any:
    if subscription:
        logger.info(
            f"Updating RemnaUser '{user.telegram_id}' from subscription '{subscription.id}'"
        )
        status = (
            SubscriptionStatus.DISABLED
            if subscription.status == SubscriptionStatus.DISABLED
            else SubscriptionStatus.ACTIVE
        )
        traffic_limit = subscription.traffic_limit
        device_limit = subscription.device_limit
        internal_squads = subscription.internal_squads
        external_squad = subscription.external_squad
        expire_at = subscription.expire_at
        tag = subscription.plan.tag
        strategy = subscription.plan.traffic_limit_strategy
    elif plan:
        logger.info(f"Updating RemnaUser '{user.telegram_id}' from plan '{plan.name}'")
        status = SubscriptionStatus.ACTIVE
        traffic_limit = plan.traffic_limit
        device_limit = plan.device_limit
        internal_squads = plan.internal_squads
        external_squad = plan.external_squad
        expire_at = format_days_to_datetime(plan.duration)
        tag = plan.tag
        strategy = plan.traffic_limit_strategy
    else:
        raise ValueError("Either 'plan' or 'subscription' must be provided")

    updated_user_response = await service.remnawave.users.update_user(
        UpdateUserRequestDto(
            uuid=uuid,
            active_internal_squads=internal_squads,
            external_squad_uuid=external_squad,
            description=user.remna_description,
            tag=tag,
            expire_at=expire_at,
            hwid_device_limit=format_device_count(device_limit),
            status=status,
            telegram_id=user.telegram_id,
            traffic_limit_bytes=format_gb_to_bytes(traffic_limit),
            traffic_limit_strategy=strategy,
        )
    )

    if reset_traffic:
        await service.remnawave.users.reset_user_traffic(str(uuid))
        logger.info(f"Traffic reset for RemnaUser '{user.telegram_id}'")

    from remnawave.models import UserResponseDto  # noqa: PLC0415

    if not isinstance(updated_user_response, UserResponseDto):
        raise ValueError("Failed to update RemnaUser: unexpected response")

    logger.info(f"RemnaUser '{user.telegram_id}' updated successfully")
    return updated_user_response


async def delete_user(
    service: Any,
    user: UserDto,
    uuid: Optional[UUID] = None,
) -> bool:
    logger.info(f"Deleting RemnaUser '{user.telegram_id}'")

    target_uuid = uuid
    if target_uuid is None:
        if user.current_subscription:
            target_uuid = user.current_subscription.user_remna_id
        else:
            users_result = await service.remnawave.users.get_users_by_telegram_id(
                telegram_id=str(user.telegram_id)
            )

            from remnawave.models import TelegramUserResponseDto  # noqa: PLC0415

            if not isinstance(users_result, TelegramUserResponseDto) or not users_result:
                logger.warning(f"No RemnaUser found in panel for '{user.telegram_id}'")
                return False

            target_uuid = users_result[0].uuid

    result = await service.remnawave.users.delete_user(uuid=str(target_uuid))
    if not isinstance(result, DeleteUserResponseDto):
        raise ValueError("Failed to delete RemnaUser: unexpected response")

    if result.is_deleted:
        logger.info(f"RemnaUser '{user.telegram_id}' deleted successfully")
    else:
        logger.warning(f"RemnaUser '{user.telegram_id}' deletion failed")

    return result.is_deleted
