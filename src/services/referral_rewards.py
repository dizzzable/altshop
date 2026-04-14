from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.core.enums import (
    MessageEffect,
    PurchaseChannel,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralInviteSource,
    ReferralLevel,
    ReferralRewardStrategy,
    ReferralRewardType,
    UserNotificationType,
)
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    ReferralDto,
    ReferralRewardDto,
    ReferralSettingsDto,
    TransactionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.user import BaseUserDto
from src.infrastructure.database.models.sql import ReferralReward
from src.infrastructure.taskiq.tasks.notifications import send_user_notification_task
from src.services.referral_models import ReferralManualAttachResult

if TYPE_CHECKING:
    from .referral import ReferralService


async def create_reward(
    service: ReferralService,
    referral_id: int,
    user_telegram_id: int,
    type: ReferralRewardType,
    amount: int,
) -> ReferralRewardDto:
    reward = await service.uow.repository.referrals.create_reward(
        ReferralReward(
            referral_id=referral_id,
            user_telegram_id=user_telegram_id,
            type=type,
            amount=amount,
            is_issued=False,
        )
    )
    logger.info(f"ReferralReward '{referral_id} created, user '{user_telegram_id}'")
    return ReferralRewardDto.from_model(reward)  # type: ignore[return-value]


async def get_rewards_by_user(
    service: ReferralService,
    telegram_id: int,
) -> list[ReferralRewardDto]:
    rewards = await service.uow.repository.referrals.get_rewards_by_user(telegram_id)
    return ReferralRewardDto.from_model_list(rewards)


async def get_rewards_by_referral(
    service: ReferralService,
    referral_id: int,
) -> list[ReferralRewardDto]:
    rewards = await service.uow.repository.referrals.get_rewards_by_referral(referral_id)
    return ReferralRewardDto.from_model_list(rewards)


async def mark_reward_as_issued(service: ReferralService, reward_id: int) -> None:
    await service.uow.repository.referrals.update_reward(reward_id, is_issued=True)
    logger.info(f"Marked reward '{reward_id}' as issued")


async def handle_referral(
    service: ReferralService,
    user: UserDto,
    code: str,
    source: ReferralInviteSource = ReferralInviteSource.UNKNOWN,
) -> None:
    invite, invite_referrer, invite_block_reason = await service.resolve_invite_token(
        code,
        user_telegram_id=user.telegram_id,
    )

    if invite_referrer and invite_block_reason is None:
        await service._attach_referral(
            user=user,
            referrer=invite_referrer,
            source=source,
            enforce_slot_capacity=True,
        )
        return

    partner_referrer = await service.get_partner_referrer_by_code(
        code,
        user_telegram_id=user.telegram_id,
    )
    if partner_referrer:
        await service._attach_referral(
            user=user,
            referrer=partner_referrer,
            source=source,
            enforce_slot_capacity=False,
        )
        return

    normalized_code = service._normalize_referral_payload(code)
    logger.warning(
        "Referral skipped for user '{}' with code '{}': invite='{}', reason='{}'",
        user.telegram_id,
        normalized_code,
        invite.token if invite else None,
        invite_block_reason,
    )


async def _attach_referral(
    service: ReferralService,
    *,
    user: UserDto,
    referrer: UserDto,
    source: ReferralInviteSource,
    enforce_slot_capacity: bool,
) -> None:
    if referrer.telegram_id == user.telegram_id:
        logger.warning("Referral skipped: self-referral for user '{}'", user.telegram_id)
        return

    existing_referral = await service.get_referral_by_referred(user.telegram_id)
    if existing_referral:
        logger.warning(
            "Referral skipped: user '{}' is already referred by '{}'",
            user.telegram_id,
            existing_referral.referrer.telegram_id,
        )
        return

    if enforce_slot_capacity:
        capacity = await service.get_invite_capacity_snapshot(referrer)
        if capacity.remaining_slots is not None and capacity.remaining_slots <= 0:
            logger.warning(
                "Referral skipped: inviter '{}' has no remaining invite slots",
                referrer.telegram_id,
            )
            return

    parent = await service.get_referral_by_referred(referrer.telegram_id)
    parent_level = parent.level if parent else None
    level = service._define_referral_level(parent_level)

    logger.info(
        "Referral detected '{}' -> '{}' level '{}'",
        referrer.telegram_id,
        user.telegram_id,
        level.name,
    )

    await service.create_referral(
        referrer=referrer,
        referred=user,
        level=level,
        invite_source=source,
    )

    if await service.settings_service.is_referral_enable():
        await send_user_notification_task.kiq(
            user=referrer,
            ntf_type=UserNotificationType.REFERRAL_ATTACHED,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-user-referral-attached",
                i18n_kwargs={"name": user.name},
                message_effect=MessageEffect.CONFETTI,
            ),
        )  # type: ignore[call-overload]


async def attach_referrer_manually(
    service: ReferralService,
    *,
    user: UserDto,
    referrer: UserDto,
    partner_service: Any,
    transaction_service: Any,
) -> ReferralManualAttachResult:
    if referrer.telegram_id == user.telegram_id:
        raise ValueError("Cannot attach a user as their own referrer")

    if await service.has_referral_attribution(user.telegram_id):
        raise ValueError("User already has referral attribution")

    if await partner_service.has_partner_attribution(user.telegram_id):
        raise ValueError("User already has partner attribution")

    await service._attach_referral(
        user=user,
        referrer=referrer,
        source=ReferralInviteSource.UNKNOWN,
        enforce_slot_capacity=False,
    )
    partner_chain_attached = await partner_service.attach_partner_referral_chain(
        user=user,
        referrer=referrer,
    )

    historical_payments_processed = 0
    historical_transactions = await transaction_service.get_completed_by_user_chronological(
        user.telegram_id
    )
    for historical_transaction in historical_transactions:
        if historical_transaction.pricing.is_free:
            continue

        transaction = historical_transaction
        if transaction.user is None:
            transaction = historical_transaction.model_copy(update={"user": user})

        await service.assign_referral_rewards(transaction)
        await partner_service.process_partner_earning(
            payer_user_id=user.telegram_id,
            payment_amount=transaction.pricing.final_amount,
            gateway_type=transaction.gateway_type,
            source_transaction_id=transaction.id,
        )
        historical_payments_processed += 1

    logger.info(
        "Manual referral attach completed: referrer '{}' -> user '{}', "
        "historical_payments_processed='{}', partner_chain_attached='{}'",
        referrer.telegram_id,
        user.telegram_id,
        historical_payments_processed,
        partner_chain_attached,
    )

    return ReferralManualAttachResult(
        historical_payments_processed=historical_payments_processed,
        partner_chain_attached=partner_chain_attached,
    )


async def assign_referral_rewards(service: ReferralService, transaction: TransactionDto) -> None:
    from src.infrastructure.taskiq.tasks.referrals import give_referrer_reward_task  # noqa: PLC0415

    settings = await service.settings_service.get_referral_settings()
    if service._should_skip_reward_assignment(settings=settings, transaction=transaction):
        return

    user = transaction.user
    if not user:
        raise ValueError(
            f"Transaction '{transaction.id}' has no associated user, "
            "cannot assign referral rewards"
        )

    referral = await service.get_referral_by_referred(user.telegram_id)
    if not referral:
        logger.info(
            f"User '{user.telegram_id}' is not a referred user, skipping reward assignment"
        )
        return

    await service._mark_referral_as_qualified(referral=referral, transaction=transaction)

    reward_chain = await service._build_reward_chain(referral.referrer)
    for current_level, referrer in reward_chain.items():
        await service._issue_referral_reward_for_level(
            settings=settings,
            transaction=transaction,
            referral=referral,
            referred_user=user,
            level=current_level,
            referrer=referrer,
            task=give_referrer_reward_task,
        )


def _should_skip_reward_assignment(
    _service: ReferralService,
    *,
    settings: ReferralSettingsDto,
    transaction: TransactionDto,
) -> bool:
    if transaction.plan and settings.has_plan_filter and not settings.is_plan_eligible(
        transaction.plan.id
    ):
        logger.info(
            f"Skipping referral reward for transaction '{transaction.id}' "
            f"because plan '{transaction.plan.id}' ({transaction.plan.name}) "
            f"is not in eligible plans list: {settings.eligible_plan_ids}"
        )
        return True

    if (
        settings.accrual_strategy == ReferralAccrualStrategy.ON_FIRST_PAYMENT
        and transaction.purchase_type != PurchaseType.NEW
    ):
        logger.info(
            f"Skipping referral reward for transaction '{transaction.id}' "
            f"because purchase type '{transaction.purchase_type}' is not NEW"
        )
        return True

    return False


async def _build_reward_chain(
    service: ReferralService,
    current_referrer: BaseUserDto,
) -> dict[ReferralLevel, BaseUserDto]:
    reward_chain = {ReferralLevel.FIRST: current_referrer}
    parent_referral = await service.get_referral_by_referred(current_referrer.telegram_id)
    if parent_referral:
        reward_chain[ReferralLevel.SECOND] = parent_referral.referrer
    return reward_chain


async def _issue_referral_reward_for_level(
    service: ReferralService,
    *,
    settings: ReferralSettingsDto,
    transaction: TransactionDto,
    referral: ReferralDto,
    referred_user: BaseUserDto,
    level: ReferralLevel,
    referrer: BaseUserDto,
    task: Any,
) -> None:
    active_partner = await service.uow.repository.partners.get_partner_by_user(
        referrer.telegram_id
    )
    if active_partner and active_partner.is_active:
        logger.info(
            f"Skipping referral reward for active partner '{referrer.telegram_id}' "
            f"at level '{level.name}'"
        )
        return

    config_value = settings.reward.config.get(level)
    if config_value is None:
        logger.info(f"Reward configuration not found for level '{level.name}'")
        return

    reward_amount = service._calculate_reward_amount(
        settings=settings,
        transaction=transaction,
        config_value=config_value,
    )
    if reward_amount is None or reward_amount <= 0:
        logger.warning(
            "Calculated reward amount is 0 or less, or calculation failed "
            f"for referrer '{referrer.telegram_id}' at level '{level.name}'"
        )
        return

    if referral.id is None:
        logger.warning(
            f"Skipping referral reward for referrer '{referrer.telegram_id}': "
            "referral id is missing"
        )
        return

    reward = await service.create_reward(
        referral_id=referral.id,
        user_telegram_id=referrer.telegram_id,
        type=settings.reward.type,
        amount=reward_amount,
    )

    await task.kiq(
        user_telegram_id=referrer.telegram_id,
        reward=reward,
        referred_name=referred_user.name,
    )

    logger.info(
        f"Created '{settings.reward.type}' reward of '{reward_amount}' for referrer "
        f"'{referrer.telegram_id}' using level '{level.name}' "
        f"and strategy '{settings.reward.strategy}'"
    )


def _calculate_reward_amount(
    _service: ReferralService,
    settings: ReferralSettingsDto,
    transaction: TransactionDto,
    config_value: int,
) -> Optional[int]:
    reward_strategy = settings.reward.strategy
    reward_type = settings.reward.type
    reward_amount: int

    if reward_strategy == ReferralRewardStrategy.AMOUNT:
        reward_amount = config_value
    elif reward_strategy == ReferralRewardStrategy.PERCENT:
        percentage = Decimal(config_value) / Decimal(100)

        if reward_type == ReferralRewardType.POINTS:
            base_amount = transaction.pricing.final_amount
            reward_amount = max(1, int(base_amount * percentage))
        elif reward_type == ReferralRewardType.EXTRA_DAYS:
            if transaction.plan and transaction.plan.duration:
                base_amount = Decimal(transaction.plan.duration)
                reward_amount = max(1, int(base_amount * percentage))
            else:
                logger.warning(
                    f"Cannot calculate extra days reward, plan duration is missing "
                    f"for transaction '{transaction.id}'"
                )
                return None
        else:
            logger.warning(f"Unsupported reward type '{reward_type}' for PERCENT strategy")
            return None
    else:
        logger.warning(f"Unsupported reward strategy '{reward_strategy}'")
        return None

    return reward_amount


async def _mark_referral_as_qualified(
    service: ReferralService,
    *,
    referral: ReferralDto,
    transaction: TransactionDto,
) -> None:
    if referral.id is None or referral.qualified_at is not None:
        return

    qualified_data: dict[str, object] = {
        "qualified_at": datetime_now(),
        "qualified_transaction_id": transaction.id,
    }
    if transaction.channel in (PurchaseChannel.WEB, PurchaseChannel.TELEGRAM):
        qualified_data["qualified_purchase_channel"] = transaction.channel

    await service.uow.repository.referrals.update_referral(
        referral_id=referral.id,
        **qualified_data,
    )

    try:
        await service.notification_service.notify_user(
            user=referral.referrer,
            payload=MessagePayload.not_deleted(
                i18n_key="ntf-event-user-referral-qualified",
                i18n_kwargs={
                    "name": transaction.user.name
                    if transaction.user
                    else str(referral.referred.telegram_id),
                },
                message_effect=MessageEffect.CONFETTI,
            ),
            ntf_type=UserNotificationType.REFERRAL_QUALIFIED,
        )
    except Exception as exception:
        logger.warning(
            f"Failed to send referral qualified notification for "
            f"referral '{referral.id}': {exception}"
        )
