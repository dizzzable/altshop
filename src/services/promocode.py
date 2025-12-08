from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import PromocodeAvailability, PromocodeRewardType
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PromocodeDto, UserDto
from src.infrastructure.database.models.dto.promocode import PromocodeActivationDto
from src.infrastructure.database.models.sql import Promocode, PromocodeActivation
from src.infrastructure.redis import RedisRepository

from .base import BaseService

if TYPE_CHECKING:
    from .subscription import SubscriptionService
    from .user import UserService


class ActivationError(StrEnum):
    """Ошибки активации промокода"""
    NOT_FOUND = auto()
    INACTIVE = auto()
    EXPIRED = auto()
    DEPLETED = auto()
    ALREADY_ACTIVATED = auto()
    NOT_AVAILABLE_FOR_USER = auto()


@dataclass
class ActivationResult:
    """Результат активации промокода"""
    success: bool
    error: Optional[ActivationError] = None
    promocode: Optional[PromocodeDto] = None
    message_key: Optional[str] = None


class PromocodeService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    async def create(self, promocode: PromocodeDto) -> PromocodeDto:
        """Создание нового промокода"""
        # Проверка уникальности кода промокода
        existing_promocode = await self.get_by_code(promocode.code)
        if existing_promocode:
            raise ValueError(f"Promocode with code '{promocode.code}' already exists")
        
        data = promocode.model_dump(exclude={"id", "activations", "created_at", "updated_at"})
        
        if promocode.plan:
            data["plan"] = promocode.plan.model_dump(mode="json")
        
        db_promocode = Promocode(**data)
        db_created_promocode = await self.uow.repository.promocodes.create(db_promocode)
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
        """Проверка, активировал ли пользователь данный промокод"""
        db_promocode = await self.uow.repository.promocodes.get(promocode_id)
        if not db_promocode:
            return False
        
        for activation in db_promocode.activations:
            if activation.user_telegram_id == user_telegram_id:
                return True
        return False

    async def _check_availability(self, promocode: PromocodeDto, user: UserDto) -> bool:
        """Проверка доступности промокода для пользователя"""
        if promocode.availability == PromocodeAvailability.ALL:
            return True
        
        if promocode.availability == PromocodeAvailability.NEW:
            # Для новых пользователей (без подписок)
            has_subscriptions = (
                user.current_subscription is not None or
                (hasattr(user, 'subscriptions') and len(user.subscriptions) > 0)
            )
            return not has_subscriptions
        
        if promocode.availability == PromocodeAvailability.EXISTING:
            # Для существующих пользователей (с подписками)
            has_subscriptions = (
                user.current_subscription is not None or
                (hasattr(user, 'subscriptions') and len(user.subscriptions) > 0)
            )
            return has_subscriptions
        
        if promocode.availability == PromocodeAvailability.INVITED:
            # Для приглашенных пользователей
            return user.invited_by is not None
        
        if promocode.availability == PromocodeAvailability.ALLOWED:
            # Для разрешенных пользователей (проверка по списку allowed_user_ids)
            if not promocode.allowed_user_ids:
                logger.warning(
                    f"Promocode '{promocode.code}' has ALLOWED availability but no allowed_user_ids"
                )
                return False
            return user.telegram_id in promocode.allowed_user_ids
        
        return False

    async def validate_promocode(
        self,
        code: str,
        user: UserDto
    ) -> ActivationResult:
        """Валидация промокода перед активацией"""
        promocode = await self.get_by_code(code)
        
        if not promocode:
            logger.warning(f"Promocode '{code}' not found for user '{user.telegram_id}'")
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_FOUND,
                message_key="ntf-promocode-not-found"
            )
        
        if not promocode.is_active:
            logger.warning(f"Promocode '{code}' is inactive")
            return ActivationResult(
                success=False,
                error=ActivationError.INACTIVE,
                message_key="ntf-promocode-inactive"
            )
        
        if promocode.is_expired:
            logger.warning(f"Promocode '{code}' has expired")
            return ActivationResult(
                success=False,
                error=ActivationError.EXPIRED,
                message_key="ntf-promocode-expired"
            )
        
        if promocode.is_depleted:
            logger.warning(f"Promocode '{code}' has reached activation limit")
            return ActivationResult(
                success=False,
                error=ActivationError.DEPLETED,
                message_key="ntf-promocode-depleted"
            )
        
        # Проверка, не активировал ли пользователь уже этот промокод
        already_activated = await self.check_user_activation(promocode.id, user.telegram_id)  # type: ignore
        if already_activated:
            logger.warning(f"User '{user.telegram_id}' already activated promocode '{code}'")
            return ActivationResult(
                success=False,
                error=ActivationError.ALREADY_ACTIVATED,
                message_key="ntf-promocode-already-activated"
            )
        
        # Проверка доступности для пользователя
        is_available = await self._check_availability(promocode, user)
        if not is_available:
            logger.warning(f"Promocode '{code}' is not available for user '{user.telegram_id}'")
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_AVAILABLE_FOR_USER,
                message_key="ntf-promocode-not-available"
            )
        
        return ActivationResult(
            success=True,
            promocode=promocode,
            message_key="ntf-promocode-valid"
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
        Активация промокода пользователем.
        
        Применяет награду в зависимости от типа промокода:
        - DURATION: добавляет дни к текущей подписке
        - TRAFFIC: добавляет трафик к текущей подписке
        - DEVICES: добавляет устройства к текущей подписке
        - SUBSCRIPTION: выдает новую подписку или добавляет дни к существующей (если указан target_subscription_id)
        - PERSONAL_DISCOUNT: устанавливает персональную скидку
        - PURCHASE_DISCOUNT: устанавливает скидку на следующую покупку
        
        Args:
            code: Код промокода
            user: Пользователь
            user_service: Сервис пользователей
            subscription_service: Сервис подписок
            target_subscription_id: ID подписки для добавления дней (для типа SUBSCRIPTION)
        """
        # Валидация промокода
        validation_result = await self.validate_promocode(code, user)
        if not validation_result.success:
            return validation_result
        
        promocode = validation_result.promocode
        if not promocode:
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_FOUND,
                message_key="ntf-promocode-not-found"
            )
        
        try:
            # Создание записи активации
            activation = PromocodeActivation(
                promocode_id=promocode.id,
                user_telegram_id=user.telegram_id,
            )
            self.uow.repository.promocodes.session.add(activation)
            await self.uow.repository.promocodes.session.flush()
            
            # Применение награды
            reward_applied = await self._apply_reward(
                promocode=promocode,
                user=user,
                user_service=user_service,
                subscription_service=subscription_service,
                target_subscription_id=target_subscription_id,
            )
            
            if not reward_applied:
                logger.error(f"Failed to apply reward for promocode '{code}' to user '{user.telegram_id}'")
                await self.uow.rollback()
                return ActivationResult(
                    success=False,
                    error=ActivationError.NOT_AVAILABLE_FOR_USER,
                    message_key="ntf-promocode-reward-failed"
                )
            
            await self.uow.commit()
        except Exception as e:
            logger.error(f"Error activating promocode '{code}' for user '{user.telegram_id}': {e}")
            await self.uow.rollback()
            return ActivationResult(
                success=False,
                error=ActivationError.NOT_AVAILABLE_FOR_USER,
                message_key="ntf-promocode-activation-error"
            )
        
        logger.info(
            f"User '{user.telegram_id}' activated promocode '{code}' "
            f"(type: {promocode.reward_type}, reward: {promocode.reward})"
        )
        
        return ActivationResult(
            success=True,
            promocode=promocode,
            message_key=self._get_success_message_key(promocode.reward_type)
        )

    async def _apply_reward(
        self,
        promocode: PromocodeDto,
        user: UserDto,
        user_service: "UserService",
        subscription_service: Optional["SubscriptionService"] = None,
        target_subscription_id: Optional[int] = None,
    ) -> bool:
        """
        Применение награды промокода к пользователю.
        
        Args:
            promocode: Промокод
            user: Пользователь
            user_service: Сервис пользователей
            subscription_service: Сервис подписок
            target_subscription_id: ID подписки для добавления дней (для типа SUBSCRIPTION)
        """
        reward_type = promocode.reward_type
        reward = promocode.reward
        
        if reward_type == PromocodeRewardType.PERSONAL_DISCOUNT:
            # Установка персональной скидки
            user.personal_discount = reward or 0
            await user_service.update(user)
            logger.info(f"Applied personal discount {reward}% to user '{user.telegram_id}'")
            return True
        
        if reward_type == PromocodeRewardType.PURCHASE_DISCOUNT:
            # Установка скидки на следующую покупку
            user.purchase_discount = reward or 0
            await user_service.update(user)
            logger.info(f"Applied purchase discount {reward}% to user '{user.telegram_id}'")
            return True
        
        # Для остальных типов наград требуется активная подписка или subscription_service
        if reward_type == PromocodeRewardType.SUBSCRIPTION:
            if not subscription_service or not promocode.plan:
                logger.warning(f"Cannot apply subscription reward: subscription_service or plan not available")
                return False
            
            # Если указан target_subscription_id - добавляем дни к существующей подписке
            if target_subscription_id:
                target_subscription = await subscription_service.get(target_subscription_id)
                if not target_subscription:
                    logger.warning(f"Target subscription '{target_subscription_id}' not found")
                    return False
                
                # Добавляем дни к существующей подписке
                from datetime import timedelta
                days_to_add = promocode.plan.duration
                if days_to_add and target_subscription.expire_at:
                    target_subscription.expire_at = target_subscription.expire_at + timedelta(days=days_to_add)
                    await subscription_service.update(target_subscription)
                    logger.info(
                        f"Added {days_to_add} days to subscription '{target_subscription_id}' "
                        f"for user '{user.telegram_id}' from promocode"
                    )
                    return True
                logger.warning(f"Cannot add days: duration={days_to_add}, expire_at={target_subscription.expire_at}")
                return False
            
            # Иначе создаем новую подписку
            from src.infrastructure.database.models.dto import SubscriptionDto
            
            subscription = SubscriptionDto(
                plan=promocode.plan,
                is_trial=False,
            )
            await subscription_service.create(user, subscription)
            logger.info(f"Applied subscription from promocode to user '{user.telegram_id}'")
            return True
        
        # Для DURATION, TRAFFIC, DEVICES требуется активная подписка
        if not user.current_subscription:
            logger.warning(
                f"Cannot apply {reward_type} reward to user '{user.telegram_id}': no active subscription"
            )
            return False
        
        if not subscription_service:
            logger.warning(f"Cannot apply {reward_type} reward: subscription_service not available")
            return False
        
        # Получаем свежую подписку из базы данных
        subscription = await subscription_service.get(user.current_subscription.id)
        if not subscription:
            logger.warning(f"Cannot find subscription '{user.current_subscription.id}' for user '{user.telegram_id}'")
            return False
        
        if reward_type == PromocodeRewardType.DURATION:
            # Добавление дней к подписке
            # Если указан target_subscription_id - добавляем дни к конкретной подписке
            if target_subscription_id:
                target_subscription = await subscription_service.get(target_subscription_id)
                if not target_subscription:
                    logger.warning(f"Target subscription '{target_subscription_id}' not found for DURATION promocode")
                    return False
                
                if reward and target_subscription.expire_at:
                    from datetime import timedelta
                    target_subscription.expire_at = target_subscription.expire_at + timedelta(days=reward)
                    await subscription_service.update(target_subscription)
                    logger.info(
                        f"Added {reward} days to subscription '{target_subscription_id}' "
                        f"for user '{user.telegram_id}' from DURATION promocode"
                    )
                    return True
                logger.warning(f"Cannot add days: reward={reward}, expire_at={target_subscription.expire_at}")
                return False
            
            # Иначе добавляем к текущей подписке (для обратной совместимости)
            if reward and subscription.expire_at:
                from datetime import timedelta
                subscription.expire_at = subscription.expire_at + timedelta(days=reward)
                await subscription_service.update(subscription)
                logger.info(f"Added {reward} days to user '{user.telegram_id}' current subscription")
                return True
            return False
        
        if reward_type == PromocodeRewardType.TRAFFIC:
            # Добавление трафика к подписке
            if reward:
                current_limit = subscription.plan.traffic_limit or 0
                # Обновляем traffic_limit в плане подписки
                subscription.plan.traffic_limit = current_limit + reward
                # Также обновляем traffic_limit самой подписки для синхронизации
                subscription.traffic_limit = current_limit + reward
                await subscription_service.update(subscription)
                logger.info(f"Added {reward} GB traffic to user '{user.telegram_id}' subscription")
                return True
            return False
        
        if reward_type == PromocodeRewardType.DEVICES:
            # Добавление устройств к подписке
            if reward:
                current_limit = subscription.plan.device_limit or 0
                # Обновляем device_limit в плане подписки
                subscription.plan.device_limit = current_limit + reward
                # Также обновляем device_limit самой подписки для синхронизации
                subscription.device_limit = current_limit + reward
                await subscription_service.update(subscription)
                logger.info(f"Added {reward} devices to user '{user.telegram_id}' subscription")
                return True
            return False
        
        return False

    def _get_success_message_key(self, reward_type: PromocodeRewardType) -> str:
        """Получение ключа сообщения об успешной активации"""
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
        """Получение количества активаций промокода"""
        promocode = await self.get(promocode_id)
        if promocode:
            return len(promocode.activations)
        return 0

    async def get_user_activations(self, user_telegram_id: int) -> list[PromocodeActivationDto]:
        """Получение всех активаций промокодов пользователем"""
        all_promocodes = await self.get_all()
        user_activations = []
        
        for promocode in all_promocodes:
            for activation in promocode.activations:
                if activation.user_telegram_id == user_telegram_id:
                    user_activations.append(activation)
        
        return user_activations
