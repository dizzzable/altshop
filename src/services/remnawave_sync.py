# mypy: ignore-errors
# ruff: noqa: E501

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Sequence, cast
from uuid import UUID

from loguru import logger
from remnawave.enums.users import TrafficLimitStrategy
from remnawave.exceptions import ConflictError
from remnawave.models import (
    CreateUserRequestDto,
    DeleteUserResponseDto,
    UpdateUserRequestDto,
)

from src.core.constants import IMPORTED_TAG, MAX_SUBSCRIPTIONS_PER_USER
from src.core.enums import DeviceType, SubscriptionStatus
from src.core.utils.formatters import (
    format_days_to_datetime,
    format_device_count,
    format_gb_to_bytes,
    format_limits_to_plan_type,
)
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)

if TYPE_CHECKING:
    from .remnawave import PanelSyncStats


class RemnawaveSyncMixin:
    async def create_user(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        subscription_index: int = 0,
    ):
        existing_subscriptions = await self.subscription_service.get_all_by_user(user.telegram_id)
        active_subscriptions_count = len(
            [s for s in existing_subscriptions if s.status != SubscriptionStatus.DELETED]
        )

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

                from remnawave.models import UserResponseDto  # noqa: PLC0415

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
    ):
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

        from remnawave.models import UserResponseDto  # noqa: PLC0415

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
                users_result = await self.remnawave.users.get_users_by_telegram_id(
                    telegram_id=str(user.telegram_id)
                )

                from remnawave.models import TelegramUserResponseDto  # noqa: PLC0415

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
        remna_user: Any,
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
        remna_user: Any,
        telegram_id: int,
        stats: "PanelSyncStats",
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
        remna_users: Sequence[Any],
        preserve_current: bool = True,
    ) -> "PanelSyncStats":
        from .remnawave import PanelSyncStats  # noqa: PLC0415

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
        remna_user: Any,
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
        remna_user: Any,
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

    async def _rebind_subscription_owner_if_needed(
        self,
        *,
        user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionDto:
        if subscription.user_telegram_id == user.telegram_id:
            return subscription

        if subscription.id is None:
            raise ValueError("Subscription ID is required for ownership rebind")

        logger.info(
            "Rebinding subscription '{}' from user '{}' to '{}'",
            subscription.id,
            subscription.user_telegram_id,
            user.telegram_id,
        )
        rebound_subscription = await self.subscription_service.rebind_user(
            subscription_id=subscription.id,
            user_telegram_id=user.telegram_id,
            previous_user_telegram_id=subscription.user_telegram_id,
            auto_commit=False,
        )
        if rebound_subscription is None:
            raise ValueError(
                f"Failed to rebind subscription '{subscription.id}' "
                f"to user '{user.telegram_id}'"
            )
        return rebound_subscription

    async def sync_user(
        self,
        remna_user: Any,
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
        if subscription:
            subscription = await self._rebind_subscription_owner_if_needed(
                user=user,
                subscription=subscription,
            )
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
