from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Optional, cast

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import PromocodeAvailability, PromocodeRewardType, SubscriptionStatus
from src.core.utils.formatters import format_gb_to_bytes
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    PromocodeDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.database.models.dto.promocode import (
    PromocodeActivationBaseDto,
)
from src.infrastructure.database.models.sql import Promocode, PromocodeActivation
from src.infrastructure.redis import RedisRepository

from .base import BaseService
from .remnawave import RemnawaveService

if TYPE_CHECKING:
    from .subscription import SubscriptionService
    from .user import UserService


class ActivationError(StrEnum):
    """РћС€РёР±РєРё Р°РєС‚РёРІР°С†РёРё РїСЂРѕРјРѕРєРѕРґР°"""

    NOT_FOUND = auto()
    INACTIVE = auto()
    EXPIRED = auto()
    DEPLETED = auto()
    ALREADY_ACTIVATED = auto()
    NOT_AVAILABLE_FOR_USER = auto()


@dataclass
class ActivationResult:
    """Р РµР·СѓР»СЊС‚Р°С‚ Р°РєС‚РёРІР°С†РёРё РїСЂРѕРјРѕРєРѕРґР°"""

    success: bool
    error: Optional[ActivationError] = None
    promocode: Optional[PromocodeDto] = None
    message_key: Optional[str] = None


class PromocodeService(BaseService):
    uow: UnitOfWork
    remnawave_service: RemnawaveService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        remnawave_service: RemnawaveService,
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.remnawave_service = remnawave_service
        self.uow = uow

    async def create(
        self,
        promocode: PromocodeDto,
        *,
        auto_commit: bool = True,
    ) -> PromocodeDto:
        """РЎРѕР·РґР°РЅРёРµ РЅРѕРІРѕРіРѕ РїСЂРѕРјРѕРєРѕРґР°"""
        # РџСЂРѕРІРµСЂРєР° СѓРЅРёРєР°Р»СЊРЅРѕСЃС‚Рё РєРѕРґР° РїСЂРѕРјРѕРєРѕРґР°
        existing_promocode = await self.get_by_code(promocode.code)
        if existing_promocode:
            raise ValueError(f"Promocode with code '{promocode.code}' already exists")

        data = promocode.model_dump(exclude={"id", "activations", "created_at", "updated_at"})

        if promocode.plan:
            data["plan"] = promocode.plan.model_dump(mode="json")

        db_promocode = Promocode(**data)
        db_created_promocode = await self.uow.repository.promocodes.create(db_promocode)
        if auto_commit:
            await self.uow.commit()

        logger.info(f"Created promocode '{promocode.code}' with type '{promocode.reward_type}'")
        return PromocodeDto.from_model(db_created_promocode)  # type: ignore[return-value]

    async def get(self, promocode_id: int) -> Optional[PromocodeDto]:
        db_promocode = await self.uow.repository.promocodes.get(promocode_id)

        if db_promocode:
            logger.debug(f"Retrieved promocode '{promocode_id}'")
        else:
            logger.warning(f"Promocode '{promocode_id}' not found")

        return PromocodeDto.from_model(db_promocode)

    async def get_by_code(self, promocode_code: str) -> Optional[PromocodeDto]:
        db_promocode = await self.uow.repository.promocodes.get_by_code(promocode_code)

        if db_promocode:
            logger.debug(f"Retrieved promocode by code '{promocode_code}'")
        else:
            logger.warning(f"Promocode with code '{promocode_code}' not found")

        return PromocodeDto.from_model(db_promocode)

    async def get_all(self) -> list[PromocodeDto]:
        db_promocodes = await self.uow.repository.promocodes.get_all()
        logger.debug(f"Retrieved '{len(db_promocodes)}' promocodes")
        return PromocodeDto.from_model_list(db_promocodes)

    async def update(self, promocode: PromocodeDto) -> Optional[PromocodeDto]:
        db_updated_promocode = await self.uow.repository.promocodes.update(
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

    async def delete(self, promocode_id: int) -> bool:
        result = await self.uow.repository.promocodes.delete(promocode_id)

        if result:
            logger.info(f"Promocode '{promocode_id}' deleted successfully")
        else:
            logger.warning(
                f"Failed to delete promocode '{promocode_id}'. "
                f"Promocode not found or deletion failed"
            )

        return result

    async def filter_by_type(self, promocode_type: PromocodeRewardType) -> list[PromocodeDto]:
        db_promocodes = await self.uow.repository.promocodes.filter_by_type(promocode_type)
        logger.debug(
            f"Filtered promocodes by type '{promocode_type}', found '{len(db_promocodes)}'"
        )
        return PromocodeDto.from_model_list(db_promocodes)

    async def filter_active(self, is_active: bool = True) -> list[PromocodeDto]:
        db_promocodes = await self.uow.repository.promocodes.filter_active(is_active)
        logger.debug(f"Filtered active promocodes: '{is_active}', found '{len(db_promocodes)}'")
        return PromocodeDto.from_model_list(db_promocodes)

    async def check_user_activation(self, promocode_id: int, user_telegram_id: int) -> bool:
        """Return whether user has already activated this promocode."""
        db_promocode = await self.uow.repository.promocodes.get(promocode_id)
        if not db_promocode:
            return False

        for activation in db_promocode.activations:
            if activation.user_telegram_id == user_telegram_id:
                return True
        return False

    async def _check_availability(self, promocode: PromocodeDto, user: UserDto) -> bool:
        """Check whether promocode is available for the user."""
        if promocode.availability == PromocodeAvailability.ALL:
            return True

        if promocode.availability == PromocodeAvailability.NEW:
            # Р”Р»СЏ РЅРѕРІС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ (Р±РµР· РїРѕРґРїРёСЃРѕРє)
            has_subscriptions = user.current_subscription is not None or (
                hasattr(user, "subscriptions") and len(user.subscriptions) > 0
            )
            return not has_subscriptions

        if promocode.availability == PromocodeAvailability.EXISTING:
            # Р”Р»СЏ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёС… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ (СЃ РїРѕРґРїРёСЃРєР°РјРё)
            has_subscriptions = user.current_subscription is not None or (
                hasattr(user, "subscriptions") and len(user.subscriptions) > 0
            )
            return has_subscriptions

        if promocode.availability == PromocodeAvailability.INVITED:
            # Р”Р»СЏ РїСЂРёРіР»Р°С€РµРЅРЅС‹С… РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
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

    async def validate_promocode(self, code: str, user: UserDto) -> ActivationResult:
        """Р’Р°Р»РёРґР°С†РёСЏ РїСЂРѕРјРѕРєРѕРґР° РїРµСЂРµРґ Р°РєС‚РёРІР°С†РёРµР№"""
        normalized_code = code.strip().upper()
        if not normalized_code:
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_FOUND,
                message_key="ntf-promocode-not-found",
            )

        promocode = await self.get_by_code(normalized_code)

        if not promocode:
            logger.warning(f"Promocode '{normalized_code}' not found for user '{user.telegram_id}'")
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_FOUND,
                message_key="ntf-promocode-not-found",
            )

        if not promocode.is_active:
            logger.warning(f"Promocode '{normalized_code}' is inactive")
            return ActivationResult(
                success=False, error=ActivationError.INACTIVE, message_key="ntf-promocode-inactive"
            )

        if promocode.is_expired:
            logger.warning(f"Promocode '{normalized_code}' has expired")
            return ActivationResult(
                success=False, error=ActivationError.EXPIRED, message_key="ntf-promocode-expired"
            )

        if promocode.is_depleted:
            logger.warning(f"Promocode '{normalized_code}' has reached activation limit")
            return ActivationResult(
                success=False, error=ActivationError.DEPLETED, message_key="ntf-promocode-depleted"
            )

        # Check whether user already activated this promocode.
        already_activated = await self.check_user_activation(promocode.id, user.telegram_id)  # type: ignore
        if already_activated:
            logger.warning(
                f"User '{user.telegram_id}' already activated promocode '{normalized_code}'"
            )
            return ActivationResult(
                success=False,
                error=ActivationError.ALREADY_ACTIVATED,
                message_key="ntf-promocode-already-activated",
            )

        # РџСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё РґР»СЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        is_available = await self._check_availability(promocode, user)
        if not is_available:
            logger.warning(
                f"Promocode '{normalized_code}' is not available for user '{user.telegram_id}'"
            )
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_AVAILABLE_FOR_USER,
                message_key="ntf-promocode-not-available",
            )

        return ActivationResult(
            success=True, promocode=promocode, message_key="ntf-promocode-valid"
        )

    async def activate(
        self,
        code: str,
        user: UserDto,
        user_service: "UserService",
        subscription_service: Optional["SubscriptionService"] = None,
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
        # Р’Р°Р»РёРґР°С†РёСЏ РїСЂРѕРјРѕРєРѕРґР°
        normalized_code = code.strip().upper()
        validation_result = await self.validate_promocode(normalized_code, user)
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
            # РЎРѕР·РґР°РЅРёРµ Р·Р°РїРёСЃРё Р°РєС‚РёРІР°С†РёРё
            activation = PromocodeActivation(
                promocode_id=promocode.id,
                user_telegram_id=user.telegram_id,
                promocode_code=promocode.code,
                reward_type=promocode.reward_type,
                reward_value=reward_value,
                target_subscription_id=target_subscription_id,
            )
            self.uow.repository.promocodes.session.add(activation)
            await self.uow.repository.promocodes.session.flush()

            # РџСЂРёРјРµРЅРµРЅРёРµ РЅР°РіСЂР°РґС‹
            reward_applied = await self._apply_reward(
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
                await self.uow.rollback()
                return ActivationResult(
                    success=False,
                    error=ActivationError.NOT_AVAILABLE_FOR_USER,
                    message_key="ntf-promocode-reward-failed",
                )

            await self.uow.commit()
        except Exception as e:
            logger.error(
                f"Error activating promocode '{normalized_code}' for user '{user.telegram_id}': {e}"
            )
            await self.uow.rollback()
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
            message_key=self._get_success_message_key(promocode.reward_type),
        )

    async def _sync_subscription_with_panel(
        self,
        *,
        user: UserDto,
        subscription: SubscriptionDto,
        subscription_service: "SubscriptionService",
    ) -> None:
        panel_user = await self.remnawave_service.updated_user(
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

    async def _apply_user_discount_reward(
        self,
        *,
        reward_type: PromocodeRewardType,
        reward: Optional[int],
        user: UserDto,
        user_service: "UserService",
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

    async def _apply_subscription_reward(
        self,
        *,
        promocode: PromocodeDto,
        user: UserDto,
        subscription_service: "SubscriptionService",
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
                await self._sync_subscription_with_panel(
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

        created_user = await self.remnawave_service.create_user(user, plan)
        subscription_url = (
            created_user.subscription_url
            or await self.remnawave_service.get_subscription_url(created_user.uuid)
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

    async def _resolve_target_subscription_for_reward(
        self,
        *,
        reward_type: PromocodeRewardType,
        user: UserDto,
        subscription_service: "SubscriptionService",
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

    async def _apply_subscription_mutation_reward(
        self,
        *,
        reward_type: PromocodeRewardType,
        reward: Optional[int],
        target_id: int,
        user: UserDto,
        subscription: SubscriptionDto,
        subscription_service: "SubscriptionService",
    ) -> bool:
        if reward_type == PromocodeRewardType.DURATION:
            if reward and subscription.expire_at:
                subscription.expire_at = subscription.expire_at + timedelta(days=reward)
                await self._sync_subscription_with_panel(
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
                await self._sync_subscription_with_panel(
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
                await self._sync_subscription_with_panel(
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

    async def _apply_reward(
        self,
        promocode: PromocodeDto,
        user: UserDto,
        user_service: "UserService",
        subscription_service: Optional["SubscriptionService"] = None,
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

        if await self._apply_user_discount_reward(
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
            return await self._apply_subscription_reward(
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

        target_id, subscription = await self._resolve_target_subscription_for_reward(
            reward_type=reward_type,
            user=user,
            subscription_service=subscription_service,
            target_subscription_id=target_subscription_id,
        )
        if target_id is None or subscription is None:
            return False

        return await self._apply_subscription_mutation_reward(
            reward_type=reward_type,
            reward=reward,
            target_id=target_id,
            user=user,
            subscription=subscription,
            subscription_service=subscription_service,
        )

    def _get_success_message_key(self, reward_type: PromocodeRewardType) -> str:
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

    async def get_activations_count(self, promocode_id: int) -> int:
        """РџРѕР»СѓС‡РµРЅРёРµ РєРѕР»РёС‡РµСЃС‚РІР° Р°РєС‚РёРІР°С†РёР№ РїСЂРѕРјРѕРєРѕРґР°"""
        promocode = await self.get(promocode_id)
        if promocode:
            return len(promocode.activations)
        return 0

    async def get_user_activations(self, user_telegram_id: int) -> list[PromocodeActivationBaseDto]:
        """Return all promocode activations for a user."""
        total = await self.uow.repository.promocodes.count_activations_by_user(user_telegram_id)
        if total == 0:
            return []

        db_activations = await self.uow.repository.promocodes.get_activations_by_user(
            user_telegram_id,
            limit=total,
            offset=0,
        )
        return PromocodeActivationBaseDto.from_model_list(db_activations)

    async def get_user_activation_history(
        self,
        user_telegram_id: int,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[PromocodeActivationBaseDto], int]:
        safe_page = max(page, 1)
        safe_limit = min(max(limit, 1), 100)
        offset = (safe_page - 1) * safe_limit

        total = await self.uow.repository.promocodes.count_activations_by_user(user_telegram_id)
        if total == 0:
            return [], 0

        db_activations = await self.uow.repository.promocodes.get_activations_by_user(
            user_telegram_id,
            limit=safe_limit,
            offset=offset,
        )
        activations = PromocodeActivationBaseDto.from_model_list(db_activations)
        return activations, total
