from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Optional, cast

from loguru import logger

from src.core.enums import PromocodeRewardType, SubscriptionStatus
from src.core.utils.formatters import format_gb_to_bytes
from src.infrastructure.database.models.dto import (
    PromocodeDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)

if TYPE_CHECKING:
    from .promocode import PromocodeService
    from .subscription import SubscriptionService
    from .user import UserService
else:
    PromocodeService = Any
    SubscriptionService = Any
    UserService = Any


async def sync_subscription_with_panel(
    service: PromocodeService,
    *,
    user: UserDto,
    subscription: SubscriptionDto,
    subscription_service: SubscriptionService,
) -> None:
    panel_user = await service.remnawave_service.updated_user(
        user=user,
        uuid=subscription.user_remna_id,
        subscription=subscription,
    )
    panel_user_data: dict[str, Any]
    if hasattr(panel_user, "model_dump"):
        panel_user_data = cast(Any, panel_user).model_dump()
    else:
        panel_user_data = {
            "uuid": getattr(panel_user, "uuid", subscription.user_remna_id),
            "status": getattr(panel_user, "status", subscription.status),
            "expire_at": getattr(panel_user, "expire_at", subscription.expire_at),
            "subscription_url": getattr(panel_user, "subscription_url", subscription.url),
            "traffic_limit_bytes": getattr(
                panel_user,
                "traffic_limit_bytes",
                format_gb_to_bytes(subscription.traffic_limit),
            ),
            "hwid_device_limit": getattr(
                panel_user,
                "hwid_device_limit",
                subscription.device_limit,
            ),
            "active_internal_squads": getattr(
                panel_user,
                "active_internal_squads",
                subscription.internal_squads,
            ),
            "external_squad_uuid": getattr(
                panel_user,
                "external_squad_uuid",
                subscription.external_squad,
            ),
            "tag": getattr(panel_user, "tag", subscription.plan.tag),
        }

    panel_subscription = RemnaSubscriptionDto.from_remna_user(panel_user_data)
    subscription.expire_at = panel_subscription.expire_at
    subscription.status = panel_subscription.status
    if panel_subscription.url:
        subscription.url = panel_subscription.url

    await subscription_service.update(subscription, auto_commit=False)


async def apply_user_discount_reward(
    _service: PromocodeService,
    *,
    reward_type: PromocodeRewardType,
    reward: Optional[int],
    user: UserDto,
    user_service: UserService,
) -> bool:
    if reward_type == PromocodeRewardType.PERSONAL_DISCOUNT:
        user.personal_discount = reward or 0
        await user_service.update(user)
        logger.info(f"Applied personal discount {reward}% to user '{user.telegram_id}'")
        return True

    if reward_type == PromocodeRewardType.PURCHASE_DISCOUNT:
        user.purchase_discount = reward or 0
        await user_service.update(user)
        logger.info(f"Applied purchase discount {reward}% to user '{user.telegram_id}'")
        return True

    return False


async def apply_subscription_reward(
    service: PromocodeService,
    *,
    promocode: PromocodeDto,
    user: UserDto,
    subscription_service: SubscriptionService,
    target_subscription_id: Optional[int],
) -> bool:
    plan = promocode.plan
    if plan is None:
        logger.warning(
            "Cannot apply subscription reward: subscription_service or plan not available"
        )
        return False

    if target_subscription_id:
        target_subscription = await subscription_service.get(target_subscription_id)
        if not target_subscription:
            logger.warning(f"Target subscription '{target_subscription_id}' not found")
            return False

        days_to_add = plan.duration
        if days_to_add and target_subscription.expire_at:
            target_subscription.expire_at = target_subscription.expire_at + timedelta(
                days=days_to_add
            )
            await service._sync_subscription_with_panel(
                user=user,
                subscription=target_subscription,
                subscription_service=subscription_service,
            )
            logger.info(
                f"Added {days_to_add} days to subscription '{target_subscription_id}' "
                f"for user '{user.telegram_id}' from promocode"
            )
            return True

        logger.warning(
            "Cannot add days: duration={}, expire_at={}",
            days_to_add,
            target_subscription.expire_at,
        )
        return False

    created_user = await service.remnawave_service.create_user(user, plan)
    subscription_url = (
        created_user.subscription_url
        or await service.remnawave_service.get_subscription_url(created_user.uuid)
    )
    if not subscription_url:
        logger.warning(
            f"Cannot apply subscription promocode for user '{user.telegram_id}': "
            f"missing subscription URL for remna user '{created_user.uuid}'"
        )
        return False

    subscription = SubscriptionDto(
        user_remna_id=created_user.uuid,
        status=created_user.status or SubscriptionStatus.ACTIVE,
        is_trial=False,
        traffic_limit=plan.traffic_limit if plan.traffic_limit else 0,
        device_limit=plan.device_limit if plan.device_limit else 0,
        internal_squads=plan.internal_squads if plan.internal_squads else [],
        external_squad=plan.external_squad,
        expire_at=created_user.expire_at,
        url=subscription_url,
        plan=plan,
    )
    await subscription_service.create(user, subscription, auto_commit=False)
    logger.info(
        "Applied subscription promocode by creating a new subscription for "
        f"user '{user.telegram_id}'"
    )
    return True


async def resolve_target_subscription_for_reward(
    _service: PromocodeService,
    *,
    reward_type: PromocodeRewardType,
    user: UserDto,
    subscription_service: SubscriptionService,
    target_subscription_id: Optional[int],
) -> tuple[Optional[int], Optional[SubscriptionDto]]:
    target_id = target_subscription_id
    if target_id is None:
        if not user.current_subscription or not user.current_subscription.id:
            logger.warning(
                f"Cannot apply {reward_type} reward to user '{user.telegram_id}': "
                "no target or current subscription"
            )
            return None, None
        target_id = user.current_subscription.id

    subscription = await subscription_service.get(target_id)
    if not subscription:
        logger.warning(f"Cannot find subscription '{target_id}' for user '{user.telegram_id}'")
        return None, None

    return target_id, subscription


async def apply_subscription_mutation_reward(
    service: PromocodeService,
    *,
    reward_type: PromocodeRewardType,
    reward: Optional[int],
    target_id: int,
    user: UserDto,
    subscription: SubscriptionDto,
    subscription_service: SubscriptionService,
) -> bool:
    if reward_type == PromocodeRewardType.DURATION:
        if reward and subscription.expire_at:
            subscription.expire_at = subscription.expire_at + timedelta(days=reward)
            await service._sync_subscription_with_panel(
                user=user,
                subscription=subscription,
                subscription_service=subscription_service,
            )
            logger.info(
                f"Added {reward} days to subscription '{target_id}' "
                f"for user '{user.telegram_id}' from DURATION promocode"
            )
            return True
        return False

    if reward_type == PromocodeRewardType.TRAFFIC:
        if reward:
            current_limit = subscription.plan.traffic_limit or 0
            subscription.plan.traffic_limit = current_limit + reward
            subscription.traffic_limit = current_limit + reward
            await service._sync_subscription_with_panel(
                user=user,
                subscription=subscription,
                subscription_service=subscription_service,
            )
            logger.info(
                f"Added {reward} GB traffic to subscription '{target_id}' "
                f"for user '{user.telegram_id}'"
            )
            return True
        return False

    if reward_type == PromocodeRewardType.DEVICES:
        if reward:
            current_limit = subscription.plan.device_limit or 0
            subscription.plan.device_limit = current_limit + reward
            subscription.device_limit = current_limit + reward
            await service._sync_subscription_with_panel(
                user=user,
                subscription=subscription,
                subscription_service=subscription_service,
            )
            logger.info(
                f"Added {reward} devices to subscription '{target_id}' "
                f"for user '{user.telegram_id}'"
            )
            return True
        return False

    return False


async def apply_reward(
    service: PromocodeService,
    promocode: PromocodeDto,
    user: UserDto,
    user_service: UserService,
    subscription_service: Optional[SubscriptionService] = None,
    target_subscription_id: Optional[int] = None,
) -> bool:
    """
    Apply promocode reward to user.

    Args:
        promocode: Promocode DTO
        user: User DTO
        user_service: User service
        subscription_service: Subscription service
        target_subscription_id: Target subscription for reward application
    """
    reward_type = promocode.reward_type
    reward = promocode.reward

    if await service._apply_user_discount_reward(
        reward_type=reward_type,
        reward=reward,
        user=user,
        user_service=user_service,
    ):
        return True

    if reward_type == PromocodeRewardType.SUBSCRIPTION:
        if not subscription_service or not promocode.plan:
            logger.warning(
                "Cannot apply subscription reward: subscription_service or plan not available"
            )
            return False
        return await service._apply_subscription_reward(
            promocode=promocode,
            user=user,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )

    if reward_type not in (
        PromocodeRewardType.DURATION,
        PromocodeRewardType.TRAFFIC,
        PromocodeRewardType.DEVICES,
    ):
        return False

    if not subscription_service:
        logger.warning(f"Cannot apply {reward_type} reward: subscription_service not available")
        return False

    target_id, subscription = await service._resolve_target_subscription_for_reward(
        reward_type=reward_type,
        user=user,
        subscription_service=subscription_service,
        target_subscription_id=target_subscription_id,
    )
    if target_id is None or subscription is None:
        return False

    return await service._apply_subscription_mutation_reward(
        reward_type=reward_type,
        reward=reward,
        target_id=target_id,
        user=user,
        subscription=subscription,
        subscription_service=subscription_service,
    )


def get_success_message_key(
    _service: PromocodeService,
    reward_type: PromocodeRewardType,
) -> str:
    """Return success i18n key for applied promocode reward."""
    message_keys = {
        PromocodeRewardType.DURATION: "ntf-promocode-activated-duration",
        PromocodeRewardType.TRAFFIC: "ntf-promocode-activated-traffic",
        PromocodeRewardType.DEVICES: "ntf-promocode-activated-devices",
        PromocodeRewardType.SUBSCRIPTION: "ntf-promocode-activated-subscription",
        PromocodeRewardType.PERSONAL_DISCOUNT: "ntf-promocode-activated-personal-discount",
        PromocodeRewardType.PURCHASE_DISCOUNT: "ntf-promocode-activated-purchase-discount",
    }
    return message_keys.get(reward_type, "ntf-promocode-activated")
