from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Sequence
from uuid import UUID

from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)

from . import remnawave_sync_crud, remnawave_sync_group, remnawave_sync_plan_resolution

if TYPE_CHECKING:
    from .remnawave import PanelSyncStats


class RemnawaveSyncMixin:
    async def create_user(
        self,
        user: UserDto,
        plan: PlanSnapshotDto,
        subscription_index: int = 0,
    ) -> Any:
        return await remnawave_sync_crud.create_user(
            self,
            user,
            plan,
            subscription_index=subscription_index,
        )

    async def updated_user(
        self,
        user: UserDto,
        uuid: UUID,
        plan: Optional[PlanSnapshotDto] = None,
        subscription: Optional[SubscriptionDto] = None,
        reset_traffic: bool = False,
    ) -> Any:
        return await remnawave_sync_crud.updated_user(
            self,
            user,
            uuid,
            plan=plan,
            subscription=subscription,
            reset_traffic=reset_traffic,
        )

    async def delete_user(self, user: UserDto, uuid: Optional[UUID] = None) -> bool:
        return await remnawave_sync_crud.delete_user(self, user, uuid=uuid)

    async def _resolve_plan_by_tag(
        self,
        plan_tag: Optional[str],
        telegram_id: int,
    ) -> Optional[PlanDto]:
        return await remnawave_sync_plan_resolution._resolve_plan_by_tag(
            self,
            plan_tag,
            telegram_id,
        )

    async def _resolve_plan_by_limits(
        self,
        remna_subscription: RemnaSubscriptionDto,
        telegram_id: int,
    ) -> Optional[PlanDto]:
        return await remnawave_sync_plan_resolution._resolve_plan_by_limits(
            self,
            remna_subscription,
            telegram_id,
        )

    @staticmethod
    def _normalize_squads(value: list[UUID]) -> list[str]:
        return remnawave_sync_plan_resolution._normalize_squads(value)

    def _plan_matches_subscription_limits(
        self,
        plan: PlanDto,
        remna_subscription: RemnaSubscriptionDto,
    ) -> bool:
        return remnawave_sync_plan_resolution._plan_matches_subscription_limits(
            plan,
            remna_subscription,
        )

    @staticmethod
    def _is_imported_tag(plan_tag: Optional[str]) -> bool:
        return remnawave_sync_plan_resolution._is_imported_tag(plan_tag)

    @staticmethod
    def _is_imported_or_unassigned_snapshot(subscription: SubscriptionDto) -> bool:
        return remnawave_sync_plan_resolution._is_imported_or_unassigned_snapshot(subscription)

    @staticmethod
    def _apply_plan_identity(
        subscription: SubscriptionDto,
        matched_plan: Optional[PlanDto],
        telegram_id: int,
    ) -> None:
        remnawave_sync_plan_resolution._apply_plan_identity(
            subscription,
            matched_plan,
            telegram_id,
        )

    async def _get_original_current_subscription_id(
        self,
        *,
        telegram_id: int,
        preserve_current: bool,
        user_before: Optional[UserDto],
    ) -> Optional[int]:
        return await remnawave_sync_group._get_original_current_subscription_id(
            self,
            telegram_id=telegram_id,
            preserve_current=preserve_current,
            user_before=user_before,
        )

    @staticmethod
    def _validate_group_sync_profile_telegram_id(
        *,
        remna_user: Any,
        telegram_id: int,
    ) -> bool:
        return remnawave_sync_group._validate_group_sync_profile_telegram_id(
            remna_user=remna_user,
            telegram_id=telegram_id,
        )

    async def _sync_group_profile(
        self,
        *,
        remna_user: Any,
        telegram_id: int,
        stats: PanelSyncStats,
    ) -> None:
        return await remnawave_sync_group._sync_group_profile(
            self,
            remna_user=remna_user,
            telegram_id=telegram_id,
            stats=stats,
        )

    async def _restore_group_sync_current_subscription(
        self,
        *,
        telegram_id: int,
        original_current_subscription_id: Optional[int],
        preserve_current: bool,
    ) -> None:
        return await remnawave_sync_group._restore_group_sync_current_subscription(
            self,
            telegram_id=telegram_id,
            original_current_subscription_id=original_current_subscription_id,
            preserve_current=preserve_current,
        )

    @staticmethod
    def _pick_group_sync_current_subscription_id(
        subscriptions: Sequence[SubscriptionDto],
    ) -> Optional[int]:
        return remnawave_sync_group._pick_group_sync_current_subscription_id(subscriptions)

    async def _set_group_sync_fallback_current_subscription(self, telegram_id: int) -> None:
        return await remnawave_sync_group._set_group_sync_fallback_current_subscription(
            self,
            telegram_id,
        )

    async def sync_profiles_by_telegram_id(
        self,
        telegram_id: int,
        remna_users: Sequence[Any],
        preserve_current: bool = True,
    ) -> PanelSyncStats:
        return await remnawave_sync_group.sync_profiles_by_telegram_id(
            self,
            telegram_id,
            remna_users,
            preserve_current=preserve_current,
        )

    async def _resolve_matched_plan_for_sync(
        self,
        *,
        remna_subscription: RemnaSubscriptionDto,
        telegram_id: int,
    ) -> Optional[PlanDto]:
        return await remnawave_sync_plan_resolution._resolve_matched_plan_for_sync(
            self,
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
        return await remnawave_sync_group._hydrate_panel_subscription_url(
            self,
            remna_user=remna_user,
            remna_subscription=remna_subscription,
            subscription=subscription,
            telegram_id=telegram_id,
        )

    async def _create_subscription_from_sync(
        self,
        *,
        user: UserDto,
        remna_user: Any,
        remna_subscription: RemnaSubscriptionDto,
        matched_plan: Optional[PlanDto],
    ) -> None:
        return await remnawave_sync_group._create_subscription_from_sync(
            self,
            user=user,
            remna_user=remna_user,
            remna_subscription=remna_subscription,
            matched_plan=matched_plan,
        )

    async def _update_subscription_from_sync(
        self,
        *,
        user: UserDto,
        subscription: SubscriptionDto,
        remna_subscription: RemnaSubscriptionDto,
        matched_plan: Optional[PlanDto],
    ) -> None:
        return await remnawave_sync_group._update_subscription_from_sync(
            self,
            user=user,
            subscription=subscription,
            remna_subscription=remna_subscription,
            matched_plan=matched_plan,
        )

    async def _rebind_subscription_owner_if_needed(
        self,
        *,
        user: UserDto,
        subscription: SubscriptionDto,
    ) -> SubscriptionDto:
        return await remnawave_sync_group._rebind_subscription_owner_if_needed(
            self,
            user=user,
            subscription=subscription,
        )

    async def sync_user(
        self,
        remna_user: Any,
        creating: bool = True,
        *,
        use_current_subscription_fallback: bool = False,
    ) -> None:
        return await remnawave_sync_group.sync_user(
            self,
            remna_user,
            creating=creating,
            use_current_subscription_fallback=use_current_subscription_fallback,
        )
