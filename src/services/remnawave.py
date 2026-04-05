from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional, Sequence, cast
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from httpx import AsyncClient, Timeout
from loguru import logger
from pydantic import ValidationError
from redis.asyncio import Redis
from remnawave import RemnawaveSDK
from remnawave.exceptions import NotFoundError
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserHwidDeviceResponseDto,
    DeleteUserResponseDto,
    GetExternalSquadsResponseDto,
    GetStatsResponseDto,
    GetUserHwidDevicesResponseDto,
    HWIDDeleteRequest,
    HwidUserDeviceDto,
    TelegramUserResponseDto,
    UpdateUserRequestDto,
    UserResponseDto,
)
from remnawave.models.hwid import HwidDeviceDto
from remnawave.models.webhook import NodeDto

from src.bot.keyboards import get_user_keyboard
from src.core.config import AppConfig
from src.core.constants import DATETIME_FORMAT, IMPORTED_TAG, MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import (
    DeviceType,
    RemnaNodeEvent,
    RemnaUserEvent,
    RemnaUserHwidDevicesEvent,
    SubscriptionStatus,
    SystemNotificationType,
    UserNotificationType,
)
from src.core.i18n.keys import ByteUnitKey
from src.core.utils.formatters import (
    format_country_code,
    format_days_to_datetime,
    format_device_count,
    format_gb_to_bytes,
    format_limits_to_plan_type,
    i18n_format_bytes_to_unit,
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from src.core.utils.message_payload import MessagePayload
from src.core.utils.time import datetime_now
from src.core.utils.types import RemnaUserDto
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.redis import RedisRepository
from src.infrastructure.taskiq.tasks.notifications import (
    send_subscription_expire_notification_task,
    send_subscription_limited_notification_task,
    send_system_notification_task,
)
from src.services.plan import PlanService
from src.services.settings import SettingsService
from src.services.subscription import SubscriptionService
from src.services.user import UserService

from .base import BaseService


@dataclass(slots=True)
class PanelSyncStats:
    user_created: bool = False
    subscriptions_created: int = 0
    subscriptions_updated: int = 0
    errors: int = 0


class RemnawaveService(BaseService):
    remnawave: RemnawaveSDK
    user_service: UserService
    subscription_service: SubscriptionService
    plan_service: PlanService
    settings_service: SettingsService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        remnawave: RemnawaveSDK,
        user_service: UserService,
        subscription_service: SubscriptionService,
        plan_service: PlanService,
        settings_service: SettingsService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.remnawave = remnawave
        self.user_service = user_service
        self.subscription_service = subscription_service
        self.plan_service = plan_service
        self.settings_service = settings_service

    async def try_connection(self) -> None:
        try:
            response = await self.remnawave.system.get_stats()
        except ValidationError as exception:
            logger.warning(
                "Remnawave SDK validation failed for /system/stats, "
                "falling back to raw health check: {}",
                exception,
            )
            await self._try_connection_raw()
            return

        if not isinstance(response, GetStatsResponseDto):
            if isinstance(response, (bytes, bytearray)):
                response = response.decode(errors="ignore")
            logger.warning(
                "Unexpected Remnawave /system/stats response type '{}', "
                "falling back to raw health check",
                type(response).__name__,
            )
            await self._try_connection_raw()

    def _build_raw_api_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.config.remnawave.token.get_secret_value()}",
            "X-Api-Key": self.config.remnawave.caddy_token.get_secret_value(),
        }

        if not self.config.remnawave.is_external:
            headers["x-forwarded-proto"] = "https"
            headers["x-forwarded-for"] = "127.0.0.1"

        return headers

    def _build_raw_api_base_url(self) -> str:
        return f"{self.config.remnawave.url.get_secret_value()}/api"

    async def _try_connection_raw(self) -> None:
        async with AsyncClient(
            base_url=self._build_raw_api_base_url(),
            headers=self._build_raw_api_headers(),
            cookies=self.config.remnawave.cookies,
            timeout=Timeout(15.0, connect=5.0),
        ) as client:
            response = await client.get("/system/stats")
            response.raise_for_status()

    @staticmethod
    def _normalize_platform_to_device_type(platform: str | None) -> DeviceType:
        platform_upper = (platform or "").upper()

        if "ANDROID" in platform_upper:
            return DeviceType.ANDROID
        if "IPHONE" in platform_upper or "IOS" in platform_upper:
            return DeviceType.IPHONE
        if "WINDOWS" in platform_upper:
            return DeviceType.WINDOWS
        if any(marker in platform_upper for marker in ("MAC", "MACOS", "OS X", "OSX", "DARWIN")):
            return DeviceType.MAC

        return DeviceType.OTHER

    async def get_external_squads_safe(self) -> list[dict[str, Any]]:
        """Get external squads in a way that survives SDK DTO validation issues.

        Why:
        - Remnawave Panel may return `subscriptionSettings` without some optional fields
        - `remnawave==2.3.2` SDK marks several `subscriptionSettings.*` fields as required
          and raises `ValidationError` on `/external-squads` response parsing.

        This helper tries the SDK first (best-effort typed DTO), then falls back
        to a raw HTTP request and extracts only `uuid` and `name`.
        """

        try:
            response = await self.remnawave.external_squads.get_external_squads()
            if isinstance(response, GetExternalSquadsResponseDto):
                return [{"uuid": s.uuid, "name": s.name} for s in response.external_squads]
        except ValidationError as exc:
            logger.warning(
                "Remnawave SDK validation error for /external-squads, falling back to raw HTTP: "
                f"{exc}"
            )
        except Exception as exc:
            logger.warning(
                f"Failed to fetch /external-squads via SDK, falling back to raw HTTP: {exc}"
            )

        return await self._get_external_squads_raw()

    async def _get_external_squads_raw(self) -> list[dict[str, Any]]:
        config = self.config

        headers: dict[str, str] = {
            "Authorization": f"Bearer {config.remnawave.token.get_secret_value()}",
            "X-Api-Key": config.remnawave.caddy_token.get_secret_value(),
        }

        if not config.remnawave.is_external:
            headers["x-forwarded-proto"] = "https"
            headers["x-forwarded-for"] = "127.0.0.1"

        async with AsyncClient(
            base_url=f"{config.remnawave.url.get_secret_value()}/api",
            headers=headers,
            cookies=config.remnawave.cookies,
            verify=True,
            timeout=Timeout(connect=15.0, read=25.0, write=10.0, pool=5.0),
        ) as client:
            response = await client.get("/external-squads")
            response.raise_for_status()
            data = response.json()

        return self._parse_external_squads_payload(data)

    @staticmethod
    def _parse_external_squads_payload(data: Any) -> list[dict[str, Any]]:
        if not isinstance(data, dict):
            return []

        response = data.get("response")
        if response is None:
            response = data

        if not isinstance(response, dict):
            return []

        squads = response.get("externalSquads") or response.get("external_squads")
        if not isinstance(squads, list):
            return []

        parsed: list[dict[str, Any]] = []
        for item in squads:
            if not isinstance(item, dict):
                continue
            raw_uuid = item.get("uuid")
            name = item.get("name")
            if not raw_uuid or not name:
                continue
            try:
                squad_uuid = UUID(str(raw_uuid))
            except Exception:
                continue
            parsed.append({"uuid": squad_uuid, "name": str(name)})

        return parsed

    async def create_user(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        subscription_index: int = 0,
    ) -> UserResponseDto:
        from remnawave.exceptions import ConflictError  # noqa: PLC0415

        # Get existing subscriptions count to generate unique username
        existing_subscriptions = await self.subscription_service.get_all_by_user(user.telegram_id)
        # Filter out deleted subscriptions
        active_subscriptions_count = len(
            [s for s in existing_subscriptions if s.status != SubscriptionStatus.DELETED]
        )

        # Check effective business limit from settings (with user override support).
        effective_max_subscriptions = await self.settings_service.get_max_subscriptions_for_user(
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

        # Hard safety guardrail.
        if total_after_creation > MAX_SUBSCRIPTIONS_PER_USER:
            raise ValueError(
                f"User '{user.telegram_id}' would exceed hard ceiling "
                f"({MAX_SUBSCRIPTIONS_PER_USER}). Current: {active_subscriptions_count}, "
                f"Requested index: {subscription_index}"
            )

        # Generate unique username for multiple subscriptions
        # Format: remna_name_sub, remna_name_sub1, remna_name_sub2, etc.
        base_index = active_subscriptions_count + subscription_index

        # Try to create user with retry on conflict (username already exists)
        max_retries = 10
        for retry in range(max_retries):
            current_index = base_index + retry
            if current_index == 0:
                username = f"{user.remna_name}_sub"
            else:
                username = f"{user.remna_name}_sub{current_index}"

            logger.info(
                f"Creating RemnaUser '{username}' for plan '{plan.name}' "
                f"(index: {current_index}, retry: {retry})"
            )

            try:
                created_user = await self.remnawave.users.create_user(
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

                if not isinstance(created_user, UserResponseDto):
                    raise ValueError("Failed to create RemnaUser: unexpected response")

                logger.info(
                    f"RemnaUser '{created_user.telegram_id}' created successfully "
                    f"with username '{username}'"
                )
                return created_user

            except ConflictError as e:
                if "username already exists" in str(e).lower():
                    logger.warning(
                        f"Username '{username}' already exists on panel, trying next index..."
                    )
                    continue
                raise

        raise ValueError(
            f"Failed to create RemnaUser for '{user.telegram_id}' after {max_retries} retries - "
            f"all usernames are taken"
        )

    async def updated_user(
        self,
        user: UserDto,
        uuid: UUID,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
        reset_traffic: bool = False,
    ) -> UserResponseDto:
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

        updated_user = await self.remnawave.users.update_user(
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
            await self.remnawave.users.reset_user_traffic(str(uuid))
            logger.info(f"Traffic reset for RemnaUser '{user.telegram_id}'")

        if not isinstance(updated_user, UserResponseDto):
            raise ValueError("Failed to update RemnaUser: unexpected response")

        logger.info(f"RemnaUser '{user.telegram_id}' updated successfully")
        return updated_user

    async def delete_user(self, user: UserDto, uuid: Optional[UUID] = None) -> bool:
        logger.info(f"Deleting RemnaUser '{user.telegram_id}'")

        target_uuid: Optional[UUID] = uuid

        if target_uuid is None:
            if user.current_subscription:
                target_uuid = user.current_subscription.user_remna_id
            else:
                # In multi-subscription mode panel may still have users
                # even without current_subscription.
                users_result = await self.remnawave.users.get_users_by_telegram_id(
                    telegram_id=str(user.telegram_id)
                )

                if not isinstance(users_result, TelegramUserResponseDto) or not users_result:
                    logger.warning(f"No RemnaUser found in panel for '{user.telegram_id}'")
                    return False

                target_uuid = users_result[0].uuid

        result = await self.remnawave.users.delete_user(uuid=str(target_uuid))

        if not isinstance(result, DeleteUserResponseDto):
            raise ValueError("Failed to delete RemnaUser: unexpected response")

        if result.is_deleted:
            logger.info(f"RemnaUser '{user.telegram_id}' deleted successfully")
        else:
            logger.warning(f"RemnaUser '{user.telegram_id}' deletion failed")

        return result.is_deleted

    async def get_devices_by_subscription_uuid(self, user_remna_id: UUID) -> list[HwidDeviceDto]:
        logger.info(f"Fetching devices for Remna subscription '{user_remna_id}'")

        result = await self.remnawave.hwid.get_hwid_user(uuid=str(user_remna_id))

        if not isinstance(result, GetUserHwidDevicesResponseDto):
            raise ValueError("Unexpected response fetching devices")

        if result.total:
            logger.info(
                f"Found '{result.total}' device(s) for Remna subscription '{user_remna_id}'"
            )
            return result.devices

        logger.info(f"No devices found for Remna subscription '{user_remna_id}'")
        return []

    async def get_devices_user(self, user: UserDto) -> list[HwidDeviceDto]:
        logger.info(f"Fetching devices for RemnaUser '{user.telegram_id}'")

        if not user.current_subscription:
            logger.warning(f"No subscription found for user '{user.telegram_id}'")
            return []

        return await self.get_devices_by_subscription_uuid(user.current_subscription.user_remna_id)

    async def delete_device_by_subscription_uuid(
        self,
        user_remna_id: UUID,
        hwid: str,
    ) -> Optional[int]:
        logger.info(f"Deleting device '{hwid}' for Remna subscription '{user_remna_id}'")

        result = await self.remnawave.hwid.delete_hwid_to_user(
            HWIDDeleteRequest(
                user_uuid=str(user_remna_id),
                hwid=hwid,
            )
        )

        if not isinstance(result, DeleteUserHwidDeviceResponseDto):
            raise ValueError("Unexpected response deleting device")

        logger.info(f"Deleted device '{hwid}' for Remna subscription '{user_remna_id}'")
        return result.total

    async def delete_device(self, user: UserDto, hwid: str) -> Optional[int]:
        logger.info(f"Deleting device '{hwid}' for RemnaUser '{user.telegram_id}'")

        if not user.current_subscription:
            logger.warning(f"No subscription found for user '{user.telegram_id}'")
            return None

        return await self.delete_device_by_subscription_uuid(
            user_remna_id=user.current_subscription.user_remna_id,
            hwid=hwid,
        )

    async def get_user(self, uuid: UUID) -> Optional[UserResponseDto]:
        logger.info(f"Fetching RemnaUser '{uuid}'")
        try:
            remna_user = await self.remnawave.users.get_user_by_uuid(str(uuid))
        except NotFoundError:
            logger.warning(f"RemnaUser '{uuid}' not found (NotFoundError)")
            return None

        if not isinstance(remna_user, UserResponseDto):
            logger.warning(f"RemnaUser '{uuid}' not found")
            return None

        logger.info(f"RemnaUser '{remna_user.telegram_id}' fetched successfully")
        return remna_user

    async def get_users_by_telegram_id(self, telegram_id: int) -> list[UserResponseDto]:
        logger.info(f"Fetching RemnaUsers by telegram_id '{telegram_id}'")
        users_result = await self.remnawave.users.get_users_by_telegram_id(
            telegram_id=str(telegram_id)
        )

        if not isinstance(users_result, TelegramUserResponseDto):
            raise ValueError("Unexpected response fetching users by telegram_id")

        users = list(users_result.root)
        logger.info(
            f"Fetched '{len(users)}' RemnaUser(s) by telegram_id '{telegram_id}' successfully"
        )
        return users

    async def get_subscription_url(self, uuid: UUID) -> Optional[str]:
        remna_user = await self.get_user(uuid)

        if remna_user is None:
            logger.warning(f"RemnaUser '{uuid}' has not subscription url")
            return None

        return remna_user.subscription_url

    async def _resolve_plan_by_tag(
        self,
        plan_tag: Optional[str],
        telegram_id: int,
    ) -> Optional[PlanDto]:
        if not plan_tag:
            logger.debug(
                f"No tag in panel data, using imported snapshot metadata for user '{telegram_id}'"
            )
            return None

        try:
            plan = await self.plan_service.get_by_tag(plan_tag)
        except Exception as exception:
            logger.exception(
                f"Error getting plan by tag '{plan_tag}' for user '{telegram_id}': {exception}"
            )
            return None

        if plan:
            logger.info(f"Found plan '{plan.name}' by tag '{plan_tag}' for user '{telegram_id}'")
            return plan

        logger.debug(
            f"Plan with tag '{plan_tag}' not found, using imported snapshot metadata for "
            f"user '{telegram_id}'"
        )
        return None

    async def _resolve_plan_by_limits(
        self,
        remna_subscription: RemnaSubscriptionDto,
        telegram_id: int,
    ) -> Optional[PlanDto]:
        try:
            plans = await self.plan_service.get_all()
        except Exception as exception:
            logger.exception(
                f"Error loading plans for limits-based sync match for user '{telegram_id}': "
                f"{exception}"
            )
            return None

        active_plans = [plan for plan in plans if plan.is_active]
        matches = [
            plan
            for plan in active_plans
            if self._plan_matches_subscription_limits(plan, remna_subscription)
        ]

        if not matches:
            logger.debug(
                f"No limits-based plan match for user '{telegram_id}' "
                f"(traffic={remna_subscription.traffic_limit}, "
                f"devices={remna_subscription.device_limit})"
            )
            return None

        if remna_subscription.tag:
            for plan in matches:
                if plan.tag == remna_subscription.tag:
                    logger.info(
                        f"Matched plan '{plan.name}' by tag within limits candidates "
                        f"for user '{telegram_id}'"
                    )
                    return plan

        matches.sort(key=lambda plan: (plan.order_index, plan.id or 0))
        selected = matches[0]
        logger.info(
            f"Matched plan '{selected.name}' by limits for user '{telegram_id}' "
            f"({len(matches)} candidate(s))"
        )
        return selected

    @staticmethod
    def _normalize_squads(value: list[UUID]) -> list[str]:
        return sorted(str(item) for item in value)

    def _plan_matches_subscription_limits(
        self,
        plan: PlanDto,
        remna_subscription: RemnaSubscriptionDto,
    ) -> bool:
        if plan.traffic_limit != remna_subscription.traffic_limit:
            return False
        if plan.device_limit != remna_subscription.device_limit:
            return False

        if (
            remna_subscription.traffic_limit_strategy is not None
            and plan.traffic_limit_strategy != remna_subscription.traffic_limit_strategy
        ):
            return False

        if self._normalize_squads(plan.internal_squads) != self._normalize_squads(
            remna_subscription.internal_squads
        ):
            return False

        return plan.external_squad == remna_subscription.external_squad

    @staticmethod
    def _is_imported_tag(plan_tag: Optional[str]) -> bool:
        return bool(plan_tag and str(plan_tag).upper() == IMPORTED_TAG)

    @staticmethod
    def _is_imported_or_unassigned_snapshot(subscription: SubscriptionDto) -> bool:
        plan = subscription.plan
        if plan.id is None or plan.id <= 0:
            return True

        plan_tag = (plan.tag or "").upper()
        plan_name = (plan.name or "").upper()
        return plan_tag == IMPORTED_TAG or plan_name == IMPORTED_TAG

    @staticmethod
    def _apply_plan_identity(
        subscription: SubscriptionDto,
        matched_plan: Optional[PlanDto],
        telegram_id: int,
    ) -> None:
        if not matched_plan or matched_plan.id is None:
            return

        plan = subscription.plan
        if plan.id != matched_plan.id:
            logger.info(
                f"Updating snapshot plan.id for user '{telegram_id}': "
                f"{plan.id} -> {matched_plan.id}"
            )
            plan.id = matched_plan.id

        if plan.tag != matched_plan.tag:
            plan.tag = matched_plan.tag

        if plan.name != matched_plan.name:
            plan.name = matched_plan.name

    async def _get_original_current_subscription_id(
        self,
        *,
        telegram_id: int,
        preserve_current: bool,
        user_before: Optional[UserDto],
    ) -> Optional[int]:
        if not preserve_current or not user_before:
            return None

        current_subscription = await self.subscription_service.get_current(telegram_id)
        if (
            current_subscription
            and current_subscription.id
            and current_subscription.status != SubscriptionStatus.DELETED
        ):
            return current_subscription.id

        return None

    @staticmethod
    def _validate_group_sync_profile_telegram_id(
        *,
        remna_user: RemnaUserDto,
        telegram_id: int,
    ) -> bool:
        if not remna_user.telegram_id:
            logger.warning(
                f"Skipping profile '{remna_user.uuid}' during grouped sync: missing telegram_id"
            )
            return False

        try:
            profile_tg_id = int(remna_user.telegram_id)
        except (TypeError, ValueError):
            logger.warning(
                f"Skipping profile '{remna_user.uuid}' during grouped sync: "
                f"invalid telegram_id '{remna_user.telegram_id}'"
            )
            return False

        if profile_tg_id != telegram_id:
            logger.warning(
                f"Skipping profile '{remna_user.uuid}' during grouped sync: "
                f"telegram_id mismatch ({profile_tg_id} != {telegram_id})"
            )
            return False

        return True

    async def _sync_group_profile(
        self,
        *,
        remna_user: RemnaUserDto,
        telegram_id: int,
        stats: PanelSyncStats,
    ) -> None:
        try:
            existing_subscription = await self.subscription_service.get_by_remna_id(remna_user.uuid)
            await self.sync_user(remna_user, creating=True)

            if existing_subscription:
                stats.subscriptions_updated += 1
            else:
                stats.subscriptions_created += 1
        except Exception as exception:
            logger.exception(
                f"Failed to sync profile '{remna_user.uuid}' for telegram_id='{telegram_id}': "
                f"{exception}"
            )
            stats.errors += 1

    async def _restore_group_sync_current_subscription(
        self,
        *,
        telegram_id: int,
        original_current_subscription_id: Optional[int],
        preserve_current: bool,
    ) -> None:
        if not preserve_current:
            return

        if not original_current_subscription_id:
            await self._set_group_sync_fallback_current_subscription(telegram_id)
            return

        original_subscription = await self.subscription_service.get(
            original_current_subscription_id
        )
        if (
            original_subscription
            and original_subscription.status != SubscriptionStatus.DELETED
            and original_subscription.user_telegram_id == telegram_id
        ):
            await self.user_service.set_current_subscription(
                telegram_id=telegram_id,
                subscription_id=original_current_subscription_id,
            )
            logger.info(
                f"Restored current subscription '{original_current_subscription_id}' "
                f"for user '{telegram_id}' after grouped sync"
            )
            return

        logger.debug(
            f"Original current subscription '{original_current_subscription_id}' for "
            f"user '{telegram_id}' is no longer valid, skip restore"
        )
        await self._set_group_sync_fallback_current_subscription(telegram_id)

    @staticmethod
    def _pick_group_sync_current_subscription_id(
        subscriptions: Sequence[SubscriptionDto],
    ) -> Optional[int]:
        candidates = [
            subscription
            for subscription in subscriptions
            if subscription.id is not None and subscription.status != SubscriptionStatus.DELETED
        ]
        if not candidates:
            return None

        status_priority = {
            SubscriptionStatus.ACTIVE: 0,
            SubscriptionStatus.LIMITED: 1,
            SubscriptionStatus.EXPIRED: 2,
            SubscriptionStatus.DISABLED: 3,
        }
        candidates.sort(
            key=lambda subscription: (
                status_priority.get(subscription.status, 99),
                -subscription.expire_at.timestamp(),
                subscription.id or 0,
            )
        )
        return candidates[0].id

    async def _set_group_sync_fallback_current_subscription(self, telegram_id: int) -> None:
        subscriptions = await self.subscription_service.get_all_by_user(telegram_id)
        fallback_subscription_id = self._pick_group_sync_current_subscription_id(subscriptions)
        if fallback_subscription_id is None:
            await self.user_service.delete_current_subscription(telegram_id)
            logger.debug(
                f"No fallback current subscription remains for user '{telegram_id}' "
                "after grouped sync"
            )
            return

        await self.user_service.set_current_subscription(
            telegram_id=telegram_id,
            subscription_id=fallback_subscription_id,
        )
        logger.info(
            f"Selected fallback current subscription '{fallback_subscription_id}' "
            f"for user '{telegram_id}' after grouped sync"
        )

    async def sync_profiles_by_telegram_id(
        self,
        telegram_id: int,
        remna_users: Sequence[RemnaUserDto],
        preserve_current: bool = True,
    ) -> PanelSyncStats:
        stats = PanelSyncStats()
        if not remna_users:
            return stats

        user_before = await self.user_service.get(telegram_id=telegram_id)
        original_current_subscription_id = await self._get_original_current_subscription_id(
            telegram_id=telegram_id,
            preserve_current=preserve_current,
            user_before=user_before,
        )

        logger.info(
            f"Starting grouped sync for telegram_id='{telegram_id}' "
            f"with '{len(remna_users)}' profile(s)"
        )

        for remna_user in remna_users:
            if not self._validate_group_sync_profile_telegram_id(
                remna_user=remna_user,
                telegram_id=telegram_id,
            ):
                continue

            await self._sync_group_profile(
                remna_user=remna_user,
                telegram_id=telegram_id,
                stats=stats,
            )

        await self._restore_group_sync_current_subscription(
            telegram_id=telegram_id,
            original_current_subscription_id=original_current_subscription_id,
            preserve_current=preserve_current,
        )

        user_after = await self.user_service.get(telegram_id=telegram_id)
        stats.user_created = user_before is None and user_after is not None

        logger.info(
            f"Grouped sync summary for user '{telegram_id}': "
            f"user_created={stats.user_created}, "
            f"created={stats.subscriptions_created}, "
            f"updated={stats.subscriptions_updated}, "
            f"errors={stats.errors}"
        )
        return stats

    async def _resolve_matched_plan_for_sync(
        self,
        *,
        remna_subscription: RemnaSubscriptionDto,
        telegram_id: int,
    ) -> Optional[PlanDto]:
        matched_plan = await self._resolve_plan_by_tag(
            plan_tag=remna_subscription.tag,
            telegram_id=telegram_id,
        )
        if matched_plan:
            return matched_plan

        return await self._resolve_plan_by_limits(
            remna_subscription=remna_subscription,
            telegram_id=telegram_id,
        )

    async def _hydrate_panel_subscription_url(
        self,
        *,
        remna_user: RemnaUserDto,
        remna_subscription: RemnaSubscriptionDto,
        subscription: Optional[SubscriptionDto],
        telegram_id: int,
    ) -> None:
        panel_subscription_url = remna_subscription.url.strip() if remna_subscription.url else ""
        if panel_subscription_url:
            return

        refreshed_subscription_url = await self.get_subscription_url(remna_user.uuid)
        if refreshed_subscription_url:
            remna_subscription.url = refreshed_subscription_url
            return

        if subscription and subscription.url:
            remna_subscription.url = subscription.url

        if not remna_subscription.url:
            logger.warning(
                f"Subscription URL is empty for RemnaUser '{remna_user.uuid}' "
                f"(telegram_id='{telegram_id}')"
            )

    async def _create_subscription_from_sync(
        self,
        *,
        user: UserDto,
        remna_user: RemnaUserDto,
        remna_subscription: RemnaSubscriptionDto,
        matched_plan: Optional[PlanDto],
    ) -> None:
        plan_tag = remna_subscription.tag
        plan_name = IMPORTED_TAG
        plan_id = -1

        if matched_plan and matched_plan.id is not None:
            plan_name = matched_plan.name
            plan_id = matched_plan.id
            plan_tag = matched_plan.tag

        internal_squads = remna_subscription.internal_squads
        if not isinstance(internal_squads, list):
            logger.warning(
                f"internal_squads is not a list for user '{user.telegram_id}', using empty list"
            )
            internal_squads = []

        from remnawave.enums.users import TrafficLimitStrategy  # noqa: PLC0415

        traffic_limit_strategy = remna_subscription.traffic_limit_strategy
        if traffic_limit_strategy is None:
            traffic_limit_strategy = TrafficLimitStrategy.NO_RESET

        temp_plan = PlanSnapshotDto(
            id=plan_id,
            name=plan_name,
            tag=plan_tag,
            type=format_limits_to_plan_type(
                remna_subscription.traffic_limit,
                remna_subscription.device_limit,
            ),
            traffic_limit=remna_subscription.traffic_limit,
            device_limit=remna_subscription.device_limit,
            duration=-1,
            traffic_limit_strategy=traffic_limit_strategy,
            internal_squads=internal_squads,
            external_squad=remna_subscription.external_squad,
        )

        expired = remna_user.expire_at and remna_user.expire_at < datetime_now()
        status = SubscriptionStatus.EXPIRED if expired else remna_user.status
        subscription = SubscriptionDto(
            user_remna_id=remna_user.uuid,
            status=status,
            traffic_limit=temp_plan.traffic_limit,
            device_limit=temp_plan.device_limit,
            internal_squads=internal_squads,
            external_squad=remna_subscription.external_squad,
            expire_at=remna_user.expire_at,
            url=remna_subscription.url,
            plan=temp_plan,
            device_type=DeviceType.OTHER,
        )
        await self.subscription_service.create(user, subscription)
        logger.info(f"Subscription created for '{user.telegram_id}'")

    async def _update_subscription_from_sync(
        self,
        *,
        user: UserDto,
        subscription: SubscriptionDto,
        remna_subscription: RemnaSubscriptionDto,
        matched_plan: Optional[PlanDto],
    ) -> None:
        logger.info(f"Synchronizing subscription '{subscription.id}' for '{user.telegram_id}'")
        subscription = subscription.apply_sync(remna_subscription)

        auto_plan_assignment = self._is_imported_or_unassigned_snapshot(subscription)
        if auto_plan_assignment:
            self._apply_plan_identity(
                subscription=subscription,
                matched_plan=matched_plan,
                telegram_id=user.telegram_id,
            )
        else:
            logger.debug(
                f"Preserving manually assigned plan snapshot for subscription "
                f"'{subscription.id}' (user '{user.telegram_id}')"
            )

        if subscription.device_type is None and auto_plan_assignment:
            subscription.device_type = DeviceType.OTHER

        await self.subscription_service.update(subscription)
        logger.info(f"Subscription '{subscription.id}' updated for '{user.telegram_id}'")

    async def sync_user(
        self,
        remna_user: RemnaUserDto,
        creating: bool = True,
        *,
        use_current_subscription_fallback: bool = False,
    ) -> None:
        if not remna_user.telegram_id:
            logger.warning(f"Skipping sync for '{remna_user.username}', missing 'telegram_id'")
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)
        if not user and creating:
            logger.debug(f"User '{remna_user.telegram_id}' not found in bot, creating new user")
            user = await self.user_service.create_from_panel(remna_user)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        user = cast(UserDto, user)
        subscription = await self.subscription_service.get_by_remna_id(remna_user.uuid)
        if not subscription and creating and use_current_subscription_fallback:
            subscription = await self.subscription_service.get_current(telegram_id=user.telegram_id)
            if subscription:
                logger.debug(
                    f"Subscription not found by remna_id '{remna_user.uuid}', "
                    f"using current subscription '{subscription.id}' for user '{user.telegram_id}'"
                )

        remna_subscription = RemnaSubscriptionDto.from_remna_user(remna_user.model_dump())
        matched_plan = await self._resolve_matched_plan_for_sync(
            remna_subscription=remna_subscription,
            telegram_id=user.telegram_id,
        )
        await self._hydrate_panel_subscription_url(
            remna_user=remna_user,
            remna_subscription=remna_subscription,
            subscription=subscription,
            telegram_id=user.telegram_id,
        )

        if not subscription:
            if not creating:
                logger.debug(
                    f"No subscription found for remna_id '{remna_user.uuid}' "
                    f"and creating=False, skipping sync for user '{user.telegram_id}'"
                )
                return

            logger.info(f"No subscription found for '{user.telegram_id}', creating")
            await self._create_subscription_from_sync(
                user=user,
                remna_user=remna_user,
                remna_subscription=remna_subscription,
                matched_plan=matched_plan,
            )
        else:
            await self._update_subscription_from_sync(
                user=user,
                subscription=subscription,
                remna_subscription=remna_subscription,
                matched_plan=matched_plan,
            )

        logger.info(f"Sync completed for user '{remna_user.telegram_id}'")

    #

    @staticmethod
    def _build_user_event_i18n_kwargs(user: UserDto, remna_user: RemnaUserDto) -> dict[str, Any]:
        return {
            "is_trial": False,
            "user_id": str(user.telegram_id),
            "user_name": user.name,
            "username": user.username or False,
            "subscription_id": str(remna_user.uuid),
            "subscription_status": remna_user.status,
            "traffic_used": i18n_format_bytes_to_unit(
                remna_user.used_traffic_bytes,
                min_unit=ByteUnitKey.MEGABYTE,
            ),
            "traffic_limit": (
                i18n_format_bytes_to_unit(remna_user.traffic_limit_bytes)
                if remna_user.traffic_limit_bytes > 0
                else i18n_format_traffic_limit(-1)
            ),
            "device_limit": (
                i18n_format_device_limit(remna_user.hwid_device_limit)
                if remna_user.hwid_device_limit
                else i18n_format_device_limit(-1)
            ),
            "expire_time": i18n_format_expire_time(remna_user.expire_at),
        }

    async def _handle_created_user_event(self, remna_user: RemnaUserDto) -> None:
        if remna_user.tag != IMPORTED_TAG:
            logger.debug(
                f"Created RemnaUser '{remna_user.telegram_id}' "
                f"is not tagged as '{IMPORTED_TAG}', skipping sync"
            )
            return

        await self.sync_user(remna_user)

    @staticmethod
    def _is_expired_imported_user(remna_user: RemnaUserDto, user: UserDto) -> bool:
        if not remna_user.expire_at:
            return False

        if remna_user.expire_at + timedelta(days=2) >= datetime_now():
            return False

        logger.debug(
            f"Subscription for RemnaUser '{user.telegram_id}' expired more than 2 days ago, "
            "skipping РІР‚вЂќ most likely an imported user"
        )
        return True

    async def _handle_status_change_user_event(
        self,
        *,
        event: str,
        remna_user: RemnaUserDto,
        i18n_kwargs: dict[str, Any],
        update_status_current_subscription_task: Any,
    ) -> None:
        logger.debug(
            f"RemnaUser '{remna_user.telegram_id}' status changed to '{remna_user.status}'"
        )
        await update_status_current_subscription_task.kiq(
            user_telegram_id=remna_user.telegram_id,
            status=SubscriptionStatus(remna_user.status),
            user_remna_id=remna_user.uuid,
        )
        if event == RemnaUserEvent.LIMITED:
            await send_subscription_limited_notification_task.kiq(
                remna_user=remna_user,
                i18n_kwargs=i18n_kwargs,
            )
            return

        if event == RemnaUserEvent.EXPIRED:
            await send_subscription_expire_notification_task.kiq(
                remna_user=remna_user,
                ntf_type=UserNotificationType.EXPIRED,
                i18n_kwargs=i18n_kwargs,
            )

    async def _handle_expiration_user_event(
        self,
        *,
        event: str,
        remna_user: RemnaUserDto,
        i18n_kwargs: dict[str, Any],
    ) -> None:
        logger.debug(f"Sending expiration notification for RemnaUser '{remna_user.telegram_id}'")
        expire_map = {
            RemnaUserEvent.EXPIRES_IN_72_HOURS: UserNotificationType.EXPIRES_IN_3_DAYS,
            RemnaUserEvent.EXPIRES_IN_48_HOURS: UserNotificationType.EXPIRES_IN_2_DAYS,
            RemnaUserEvent.EXPIRES_IN_24_HOURS: UserNotificationType.EXPIRES_IN_1_DAYS,
            RemnaUserEvent.EXPIRED_24_HOURS_AGO: UserNotificationType.EXPIRED_1_DAY_AGO,
        }
        await send_subscription_expire_notification_task.kiq(
            remna_user=remna_user,
            ntf_type=expire_map[RemnaUserEvent(event)],
            i18n_kwargs=i18n_kwargs,
        )

    async def handle_user_event(self, event: str, remna_user: RemnaUserDto) -> None:
        from src.infrastructure.taskiq.tasks.subscriptions import (  # noqa: PLC0415
            delete_current_subscription_task,
            update_status_current_subscription_task,
        )

        logger.info(f"Received event '{event}' for RemnaUser '{remna_user.telegram_id}'")

        if not remna_user.telegram_id:
            logger.debug(f"Skipping RemnaUser '{remna_user.username}': telegram_id is empty")
            return

        if event == RemnaUserEvent.CREATED:
            await self._handle_created_user_event(remna_user)
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        i18n_kwargs = self._build_user_event_i18n_kwargs(user, remna_user)

        if event == RemnaUserEvent.MODIFIED:
            logger.debug(f"RemnaUser '{remna_user.telegram_id}' modified")
            await self.sync_user(remna_user, creating=False)
            return

        if event == RemnaUserEvent.DELETED:
            logger.debug(f"RemnaUser '{remna_user.telegram_id}' deleted")
            await delete_current_subscription_task.kiq(
                user_telegram_id=remna_user.telegram_id,
                user_remna_id=remna_user.uuid,
            )
            return

        if self._is_expired_imported_user(remna_user, user):
            logger.debug(
                f"Subscription for RemnaUser '{user.telegram_id}' expired more than 2 days ago, "
                "skipping вЂ” most likely an imported user"
            )
            return

        if event in {
            RemnaUserEvent.REVOKED,
            RemnaUserEvent.ENABLED,
            RemnaUserEvent.DISABLED,
            RemnaUserEvent.LIMITED,
            RemnaUserEvent.EXPIRED,
        }:
            await self._handle_status_change_user_event(
                event=event,
                remna_user=remna_user,
                i18n_kwargs=i18n_kwargs,
                update_status_current_subscription_task=update_status_current_subscription_task,
            )
            return

        if event == RemnaUserEvent.FIRST_CONNECTED:
            logger.debug(f"RemnaUser '{remna_user.telegram_id}' connected for the first time")
            await send_system_notification_task.kiq(
                ntf_type=SystemNotificationType.USER_FIRST_CONNECTED,
                payload=MessagePayload.not_deleted(
                    i18n_key="ntf-event-user-first-connected",
                    i18n_kwargs=i18n_kwargs,
                    reply_markup=get_user_keyboard(user.telegram_id),
                ),
            )
            return

        if event in {
            RemnaUserEvent.EXPIRES_IN_72_HOURS,
            RemnaUserEvent.EXPIRES_IN_48_HOURS,
            RemnaUserEvent.EXPIRES_IN_24_HOURS,
            RemnaUserEvent.EXPIRED_24_HOURS_AGO,
        }:
            await self._handle_expiration_user_event(
                event=event,
                remna_user=remna_user,
                i18n_kwargs=i18n_kwargs,
            )
            return

        logger.warning(f"Unhandled user event '{event}' for '{remna_user.telegram_id}'")

    async def handle_device_event(
        self,
        event: str,
        remna_user: RemnaUserDto,
        device: HwidUserDeviceDto,
    ) -> None:
        logger.info(f"Received device event '{event}' for RemnaUser '{remna_user.telegram_id}'")

        if not remna_user.telegram_id:
            logger.debug(f"Skipping RemnaUser '{remna_user.username}': telegram_id is empty")
            return

        user = await self.user_service.get(telegram_id=remna_user.telegram_id)

        if not user:
            logger.warning(f"No local user found for telegram_id '{remna_user.telegram_id}'")
            return

        if event == RemnaUserHwidDevicesEvent.ADDED:
            logger.debug(f"Device '{device.hwid}' added for RemnaUser '{remna_user.telegram_id}'")
            i18n_key = "ntf-event-user-hwid-added"
            detected_device_type = self._normalize_platform_to_device_type(device.platform)

            try:
                subscription = await self.subscription_service.get_by_remna_id(remna_user.uuid)
            except Exception as exception:
                logger.warning(
                    f"Failed to load subscription by remna_id '{remna_user.uuid}' "
                    f"for HWID event '{event}': {exception}"
                )
                subscription = None

            if subscription:
                current_device_type = subscription.device_type
                should_update_device_type = detected_device_type != DeviceType.OTHER and (
                    current_device_type is None or current_device_type == DeviceType.OTHER
                )
                if should_update_device_type:
                    subscription.device_type = detected_device_type
                    updated = await self.subscription_service.update(subscription)
                    if updated:
                        logger.info(
                            f"Auto-assigned device_type '{detected_device_type.value}' "
                            f"for subscription '{subscription.id}' "
                            f"from platform '{device.platform}'"
                        )
            else:
                logger.debug(
                    f"Subscription with remna_id '{remna_user.uuid}' "
                    f"not found for HWID event '{event}'"
                )

        elif event == RemnaUserHwidDevicesEvent.DELETED:
            logger.debug(f"Device '{device.hwid}' deleted for RemnaUser '{remna_user.telegram_id}'")
            i18n_key = "ntf-event-user-hwid-deleted"

        else:
            logger.warning(
                f"Unhandled device event '{event}' for RemnaUser '{remna_user.telegram_id}'"
            )
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.USER_HWID,
            payload=MessagePayload.not_deleted(
                i18n_key=i18n_key,
                i18n_kwargs={
                    "user_id": str(user.telegram_id),
                    "user_name": user.name,
                    "username": user.username or False,
                    "hwid": device.hwid,
                    "platform": device.platform,
                    "device_model": device.device_model,
                    "os_version": device.os_version,
                    "user_agent": device.user_agent,
                },
                reply_markup=get_user_keyboard(user.telegram_id),
            ),
        )

    async def handle_node_event(self, event: str, node: NodeDto) -> None:
        logger.info(f"Received node event '{event}' for node '{node.name}'")

        if event == RemnaNodeEvent.CONNECTION_LOST:
            logger.warning(f"Connection lost for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-lost"

        elif event == RemnaNodeEvent.CONNECTION_RESTORED:
            logger.info(f"Connection restored for node '{node.name}'")
            i18n_key = "ntf-event-node-connection-restored"

        elif event == RemnaNodeEvent.TRAFFIC_NOTIFY:
            # TODO: Temporarily shutting down the node (and plans?) before the traffic is reset
            logger.debug(f"Traffic threshold reached on node '{node.name}'")
            i18n_key = "ntf-event-node-traffic"

        else:
            logger.warning(f"Unhandled node event '{event}' for node '{node.name}'")
            return

        await send_system_notification_task.kiq(
            ntf_type=SystemNotificationType.NODE_STATUS,
            payload=MessagePayload.not_deleted(
                i18n_key=i18n_key,
                i18n_kwargs={
                    "country": format_country_code(code=node.country_code),
                    "name": node.name,
                    "address": node.address,
                    "port": str(node.port),
                    "traffic_used": i18n_format_bytes_to_unit(node.traffic_used_bytes),
                    "traffic_limit": i18n_format_bytes_to_unit(node.traffic_limit_bytes),
                    "last_status_message": node.last_status_message or "None",
                    "last_status_change": node.last_status_change.strftime(DATETIME_FORMAT)
                    if node.last_status_change
                    else "None",
                },
            ),
        )
