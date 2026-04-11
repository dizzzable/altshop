from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from loguru import logger
from remnawave.exceptions import NotFoundError

from src.infrastructure.database.models.dto import UserDto, WebAccountDto

from .remnawave import RemnawaveService
from .subscription import SubscriptionService
from .telegram_link import TelegramLinkService
from .user import UserService
from .web_account import WebAccountService


class WebCabinetAdminError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class WebCabinetSubscriptionPreviewItem:
    subscription_id: int
    owner_kind: str
    owner_telegram_id: int
    owner_name: str
    plan_name: str
    profile_name: str | None
    remna_uuid: str
    status: str
    expire_at: str
    is_current: bool


@dataclass(slots=True, frozen=True)
class WebCabinetBindPreview:
    source_user: UserDto
    web_account: WebAccountDto
    target_user: UserDto | None
    source_subscriptions: tuple[WebCabinetSubscriptionPreviewItem, ...]
    target_subscriptions: tuple[WebCabinetSubscriptionPreviewItem, ...]

    @property
    def all_subscription_ids(self) -> tuple[int, ...]:
        return tuple(
            item.subscription_id
            for item in (*self.source_subscriptions, *self.target_subscriptions)
        )


@dataclass(slots=True, frozen=True)
class WebCabinetBindApplyResult:
    web_account: WebAccountDto
    target_user: UserDto
    kept_subscription_ids: tuple[int, ...]
    deleted_subscription_ids: tuple[int, ...]


class WebCabinetAdminService:
    def __init__(
        self,
        user_service: UserService,
        web_account_service: WebAccountService,
        subscription_service: SubscriptionService,
        remnawave_service: RemnawaveService,
        telegram_link_service: TelegramLinkService,
    ) -> None:
        self.user_service = user_service
        self.web_account_service = web_account_service
        self.subscription_service = subscription_service
        self.remnawave_service = remnawave_service
        self.telegram_link_service = telegram_link_service

    async def build_bind_preview(
        self,
        *,
        source_user_telegram_id: int,
        target_telegram_id: int,
    ) -> WebCabinetBindPreview:
        source_user = await self.user_service.get(source_user_telegram_id)
        if source_user is None:
            raise WebCabinetAdminError("Source user not found")

        web_account = await self.web_account_service.get_by_user_telegram_id(
            source_user.telegram_id
        )
        if web_account is None:
            raise WebCabinetAdminError("User has no web account")

        if target_telegram_id == source_user.telegram_id:
            raise WebCabinetAdminError("Web account is already bound to this Telegram ID")

        target_user = await self.user_service.get(target_telegram_id)
        source_subscriptions = await self._build_subscription_preview_items(
            owner=source_user,
            owner_kind="WEB",
        )
        target_subscriptions = await self._build_subscription_preview_items(
            owner=target_user,
            owner_kind="TELEGRAM",
        )
        return WebCabinetBindPreview(
            source_user=source_user,
            web_account=web_account,
            target_user=target_user,
            source_subscriptions=tuple(source_subscriptions),
            target_subscriptions=tuple(target_subscriptions),
        )

    async def apply_bind_merge(  # noqa: C901
        self,
        *,
        source_user_telegram_id: int,
        target_telegram_id: int,
        kept_subscription_ids: Sequence[int],
    ) -> WebCabinetBindApplyResult:
        preview = await self.build_bind_preview(
            source_user_telegram_id=source_user_telegram_id,
            target_telegram_id=target_telegram_id,
        )
        keep_ids = {int(subscription_id) for subscription_id in kept_subscription_ids}
        known_ids = set(preview.all_subscription_ids)
        invalid_ids = sorted(keep_ids - known_ids)
        if invalid_ids:
            raise WebCabinetAdminError(f"Unknown subscriptions selected: {invalid_ids}")

        source_user = preview.source_user
        target_user = preview.target_user
        if target_user is None:
            target_user = await self.user_service.create_placeholder_user(
                telegram_id=target_telegram_id
            )

        all_subscriptions = await self.subscription_service.get_by_ids(list(known_ids))
        subscriptions_by_id = {
            subscription.id: subscription
            for subscription in all_subscriptions
            if subscription.id is not None and subscription.status.value != "DELETED"
        }

        deleted_ids: list[int] = []
        for subscription_id in sorted(known_ids - keep_ids):
            subscription = subscriptions_by_id.get(subscription_id)
            if subscription is None:
                continue
            owner_user = (
                source_user
                if subscription.user_telegram_id == source_user.telegram_id
                else target_user
            )
            if subscription.user_remna_id:
                try:
                    await self.remnawave_service.delete_user(
                        owner_user, uuid=subscription.user_remna_id
                    )
                except NotFoundError:
                    logger.info(
                        "Remnawave profile '{}' already missing during DEV web bind cleanup",
                        subscription.user_remna_id,
                    )
            await self.subscription_service.delete_subscription(subscription_id)
            deleted_ids.append(subscription_id)

        updated_account = await self.telegram_link_service.bind_existing_account(
            web_account_id=preview.web_account.id or 0,
            telegram_id=target_user.telegram_id,
        )
        rebound_subscriptions = await self.subscription_service.get_by_ids(list(keep_ids))
        for subscription in rebound_subscriptions:
            if subscription.id is None or subscription.status.value == "DELETED":
                continue
            if subscription.user_remna_id:
                await self.remnawave_service.updated_user(
                    user=target_user,
                    uuid=subscription.user_remna_id,
                    subscription=subscription,
                    reset_traffic=False,
                )

        refreshed_target_user = await self.user_service.get(target_user.telegram_id)
        if refreshed_target_user is None:
            raise WebCabinetAdminError("Failed to reload target user after merge")

        retained_subscriptions = [
            subscription
            for subscription in await self.subscription_service.get_all_by_user(
                refreshed_target_user.telegram_id
            )
            if subscription.status.value != "DELETED"
        ]
        preferred_ids = [
            subscription_id
            for subscription_id in (
                refreshed_target_user.current_subscription.id
                if refreshed_target_user.current_subscription
                else None,
                source_user.current_subscription.id if source_user.current_subscription else None,
            )
            if subscription_id is not None and subscription_id in keep_ids
        ]
        current_subscription_id = next(iter(preferred_ids), None)
        if current_subscription_id is None:
            current_subscription_id = RemnawaveService._pick_group_sync_current_subscription_id(
                retained_subscriptions
            )

        if current_subscription_id is None:
            await self.user_service.delete_current_subscription(refreshed_target_user.telegram_id)
        else:
            await self.user_service.set_current_subscription(
                refreshed_target_user.telegram_id,
                current_subscription_id,
            )

        return WebCabinetBindApplyResult(
            web_account=updated_account,
            target_user=refreshed_target_user,
            kept_subscription_ids=tuple(sorted(keep_ids)),
            deleted_subscription_ids=tuple(sorted(deleted_ids)),
        )

    async def rename_web_login(
        self,
        *,
        user_telegram_id: int,
        username: str,
    ) -> WebAccountDto:
        return await self.web_account_service.rename_login(
            user_telegram_id=user_telegram_id,
            username=username,
        )

    async def _build_subscription_preview_items(
        self,
        *,
        owner: UserDto | None,
        owner_kind: str,
    ) -> list[WebCabinetSubscriptionPreviewItem]:
        if owner is None:
            return []

        subscriptions = [
            subscription
            for subscription in await self.subscription_service.get_all_by_user(owner.telegram_id)
            if subscription.id is not None and subscription.status.value != "DELETED"
        ]
        items: list[WebCabinetSubscriptionPreviewItem] = []
        current_subscription_id = (
            owner.current_subscription.id if owner.current_subscription else None
        )
        for subscription in subscriptions:
            profile_name = None
            try:
                remna_user = await self.remnawave_service.get_user(subscription.user_remna_id)
            except Exception:
                remna_user = None
            if remna_user is not None:
                raw_username = getattr(remna_user, "username", None)
                if raw_username:
                    profile_name = str(raw_username)
            items.append(
                WebCabinetSubscriptionPreviewItem(
                    subscription_id=subscription.id or 0,
                    owner_kind=owner_kind,
                    owner_telegram_id=owner.telegram_id,
                    owner_name=owner.name or str(owner.telegram_id),
                    plan_name=subscription.plan.name,
                    profile_name=profile_name,
                    remna_uuid=str(subscription.user_remna_id),
                    status=subscription.status.value,
                    expire_at=subscription.expire_at.isoformat(),
                    is_current=current_subscription_id == subscription.id,
                )
            )
        return items
