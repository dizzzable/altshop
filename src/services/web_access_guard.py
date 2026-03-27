from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from fastapi import HTTPException, status
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.constants import T_ME
from src.core.observability import emit_counter
from src.core.storage.key_builder import build_key
from src.infrastructure.database.models.dto import SettingsDto, UserDto, WebAccountDto
from src.infrastructure.redis import RedisRepository
from src.services.access_policy import AccessModePolicyService
from src.services.base import BaseService
from src.services.settings import SettingsService
from src.services.web_account import WebAccountService

WEB_ACCESS_ERROR_CODE = "WEB_ACCESS_REQUIREMENTS_NOT_MET"
WEB_ACCESS_READ_ONLY_CODE = "WEB_ACCESS_READ_ONLY"

RULES_ACCEPTANCE_REQUIRED: Literal["RULES_ACCEPTANCE_REQUIRED"] = "RULES_ACCEPTANCE_REQUIRED"
TELEGRAM_LINK_REQUIRED: Literal["TELEGRAM_LINK_REQUIRED"] = "TELEGRAM_LINK_REQUIRED"
CHANNEL_SUBSCRIPTION_REQUIRED: Literal["CHANNEL_SUBSCRIPTION_REQUIRED"] = (
    "CHANNEL_SUBSCRIPTION_REQUIRED"
)
CHANNEL_VERIFICATION_UNAVAILABLE: Literal["CHANNEL_VERIFICATION_UNAVAILABLE"] = (
    "CHANNEL_VERIFICATION_UNAVAILABLE"
)

UnmetRequirementCode = Literal[
    "RULES_ACCEPTANCE_REQUIRED",
    "TELEGRAM_LINK_REQUIRED",
    "CHANNEL_SUBSCRIPTION_REQUIRED",
    "CHANNEL_VERIFICATION_UNAVAILABLE",
]
AccessLevel = Literal["full", "read_only", "blocked"]
ChannelCheckStatus = Literal["not_required", "verified", "required_unverified", "unavailable"]

_CHANNEL_MEMBER_CACHE_TTL_SECONDS = 300
_CHANNEL_MEMBER_ALLOWED_STATUSES = {
    ChatMemberStatus.CREATOR,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
}


@dataclass(slots=True)
class WebAccessStatus:
    access_mode: str
    rules_required: bool
    channel_required: bool
    requires_telegram_id: bool
    access_level: AccessLevel
    channel_check_status: ChannelCheckStatus
    rules_accepted: bool
    telegram_linked: bool
    channel_verified: bool
    linked_telegram_id: int | None
    rules_link: str | None
    channel_link: str | None
    tg_id_helper_bot_link: str
    verification_bot_link: str | None
    unmet_requirements: list[UnmetRequirementCode]
    can_use_product_features: bool
    can_view_product_screens: bool
    can_mutate_product: bool
    can_purchase: bool
    should_redirect_to_access_screen: bool
    invite_locked: bool


@dataclass(slots=True)
class ChannelMembershipResult:
    verified: bool
    status: ChannelCheckStatus


class WebAccessGuardService(BaseService):
    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        settings_service: SettingsService,
        web_account_service: WebAccountService,
        access_mode_policy_service: AccessModePolicyService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.settings_service = settings_service
        self.web_account_service = web_account_service
        self.access_mode_policy_service = access_mode_policy_service

    async def evaluate_user_access(
        self,
        *,
        user: UserDto,
        force_channel_recheck: bool = False,
    ) -> WebAccessStatus:
        settings = await self.settings_service.get()
        mode_policy = self.access_mode_policy_service.resolve(user=user, settings=settings)
        verification_bot_link = await self.get_verification_bot_link()

        if user.is_privileged:
            return WebAccessStatus(
                access_mode=settings.access_mode.value,
                rules_required=bool(settings.rules_required),
                channel_required=bool(settings.channel_required),
                requires_telegram_id=bool(settings.rules_required or settings.channel_required),
                access_level="full",
                channel_check_status="verified" if settings.channel_required else "not_required",
                rules_accepted=True,
                telegram_linked=True,
                channel_verified=True,
                linked_telegram_id=user.telegram_id if user.telegram_id > 0 else None,
                rules_link=settings.rules_link.get_secret_value()
                if settings.rules_required
                else None,
                channel_link=settings.get_url_channel_link if settings.channel_required else None,
                tg_id_helper_bot_link=f"{T_ME}userinfobot",
                verification_bot_link=verification_bot_link,
                unmet_requirements=[],
                can_use_product_features=True,
                can_view_product_screens=True,
                can_mutate_product=True,
                can_purchase=True,
                should_redirect_to_access_screen=False,
                invite_locked=False,
            )

        web_account = await self.web_account_service.get_by_user_telegram_id(user.telegram_id)
        linked_telegram_id = self._resolve_linked_telegram_id(user=user, web_account=web_account)

        rules_required = bool(settings.rules_required)
        channel_required = bool(settings.channel_required)
        requires_telegram_id = bool(rules_required or channel_required)

        rules_accepted = (not rules_required) or bool(user.is_rules_accepted)
        telegram_linked = (not requires_telegram_id) or linked_telegram_id is not None

        channel_result = ChannelMembershipResult(verified=True, status="not_required")
        if channel_required:
            if linked_telegram_id is None:
                channel_result = ChannelMembershipResult(
                    verified=False, status="required_unverified"
                )
            else:
                channel_result = await self._is_channel_membership_valid(
                    settings=settings,
                    linked_telegram_id=linked_telegram_id,
                    force_recheck=force_channel_recheck,
                )
        channel_verified = channel_result.verified

        unmet_requirements: list[UnmetRequirementCode] = []
        if rules_required and not rules_accepted:
            unmet_requirements.append(RULES_ACCEPTANCE_REQUIRED)
        if requires_telegram_id and not telegram_linked:
            unmet_requirements.append(TELEGRAM_LINK_REQUIRED)
        if channel_required and telegram_linked and channel_result.status == "required_unverified":
            unmet_requirements.append(CHANNEL_SUBSCRIPTION_REQUIRED)
        if channel_required and telegram_linked and channel_result.status == "unavailable":
            unmet_requirements.append(CHANNEL_VERIFICATION_UNAVAILABLE)

        access_level = self._resolve_access_level(
            unmet_requirements=unmet_requirements,
            should_redirect_to_access_screen=mode_policy.should_redirect_to_access_screen,
        )
        can_view_product_screens = (
            mode_policy.can_view_product_screens and access_level != "blocked"
        )
        can_mutate_product = mode_policy.can_mutate_product and access_level == "full"
        can_purchase = mode_policy.can_purchase and access_level == "full"

        return WebAccessStatus(
            access_mode=settings.access_mode.value,
            rules_required=rules_required,
            channel_required=channel_required,
            requires_telegram_id=requires_telegram_id,
            access_level=access_level,
            channel_check_status=channel_result.status,
            rules_accepted=rules_accepted,
            telegram_linked=telegram_linked,
            channel_verified=channel_verified,
            linked_telegram_id=linked_telegram_id,
            rules_link=settings.rules_link.get_secret_value() if rules_required else None,
            channel_link=settings.get_url_channel_link if channel_required else None,
            tg_id_helper_bot_link=f"{T_ME}userinfobot",
            verification_bot_link=verification_bot_link,
            unmet_requirements=unmet_requirements,
            can_use_product_features=access_level == "full",
            can_view_product_screens=can_view_product_screens,
            can_mutate_product=can_mutate_product,
            can_purchase=can_purchase,
            should_redirect_to_access_screen=mode_policy.should_redirect_to_access_screen
            or access_level == "blocked",
            invite_locked=mode_policy.invite_locked,
        )

    @staticmethod
    def _resolve_access_level(
        *,
        unmet_requirements: list[UnmetRequirementCode],
        should_redirect_to_access_screen: bool,
    ) -> AccessLevel:
        if should_redirect_to_access_screen:
            return "blocked"

        if not unmet_requirements:
            return "full"

        return "blocked"

    @staticmethod
    def assert_can_use_product_features(
        access_status: WebAccessStatus,
        *,
        allow_read_only: bool = False,
    ) -> None:
        if access_status.can_use_product_features:
            return
        if allow_read_only and access_status.access_level == "read_only":
            return

        error_code = (
            WEB_ACCESS_READ_ONLY_CODE
            if access_status.access_level == "read_only"
            else WEB_ACCESS_ERROR_CODE
        )
        verification_unavailable = (
            CHANNEL_VERIFICATION_UNAVAILABLE in access_status.unmet_requirements
        )
        message = (
            "Product mutations are temporarily disabled while channel verification is unavailable"
            if access_status.access_level == "read_only"
            else (
                "Channel verification is temporarily unavailable. Access remains blocked "
                "until verification recovers."
            )
            if verification_unavailable
            else "Complete access requirements in settings to continue"
        )
        if access_status.access_level == "read_only":
            emit_counter("web_access_read_only_total")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": error_code,
                "message": message,
                "unmet_requirements": access_status.unmet_requirements,
            },
        )

    async def get_verification_bot_link(self) -> str | None:
        return await self._resolve_verification_bot_link()

    async def _is_channel_membership_valid(
        self,
        *,
        settings: SettingsDto,
        linked_telegram_id: int,
        force_recheck: bool,
    ) -> ChannelMembershipResult:
        channel_chat_id = self._resolve_channel_chat_id(settings)
        if channel_chat_id is None:
            emit_counter("channel_verification_unavailable_total", reason="channel_not_configured")
            logger.warning(
                "Channel requirement is enabled but channel is not configured correctly; "
                "channel check is unavailable."
            )
            return ChannelMembershipResult(verified=False, status="unavailable")

        cache_key = self._build_channel_cache_key(
            linked_telegram_id=linked_telegram_id,
            channel_chat_id=channel_chat_id,
        )
        if not force_recheck:
            cached_value = await self._read_cached_channel_check(cache_key)
            if cached_value is not None:
                return ChannelMembershipResult(
                    verified=cached_value,
                    status="verified" if cached_value else "required_unverified",
                )

        try:
            member = await self.bot.get_chat_member(
                chat_id=channel_chat_id,
                user_id=linked_telegram_id,
            )
            is_member = self._is_channel_member_status_allowed(member.status)
        except Exception as exc:
            emit_counter("channel_verification_unavailable_total", reason="telegram_api_error")
            logger.warning(
                "Failed to check channel membership for tg_id='{}' and channel='{}': {}. "
                "Channel check is unavailable.",
                linked_telegram_id,
                channel_chat_id,
                exc,
            )
            return ChannelMembershipResult(verified=False, status="unavailable")

        await self._write_cached_channel_check(cache_key, is_member)
        return ChannelMembershipResult(
            verified=is_member,
            status="verified" if is_member else "required_unverified",
        )

    @staticmethod
    def _resolve_linked_telegram_id(
        *,
        user: UserDto,
        web_account: Optional[WebAccountDto],
    ) -> int | None:
        if web_account and web_account.user_telegram_id > 0:
            return web_account.user_telegram_id
        if user.telegram_id > 0:
            return user.telegram_id
        return None

    @staticmethod
    def _build_channel_cache_key(*, linked_telegram_id: int, channel_chat_id: str | int) -> str:
        channel_part = str(channel_chat_id).replace(":", "_")
        return build_key("web_access", "channel_member", linked_telegram_id, channel_part)

    async def _read_cached_channel_check(self, cache_key: str) -> bool | None:
        try:
            cached_value = await self.redis_client.get(cache_key)
        except Exception as exc:
            logger.warning(f"Failed to read channel membership cache '{cache_key}': {exc}")
            return None

        if cached_value is None:
            return None

        raw = cached_value.decode("utf-8") if isinstance(cached_value, bytes) else str(cached_value)
        if raw == "1":
            return True
        if raw == "0":
            return False
        return None

    async def _write_cached_channel_check(self, cache_key: str, is_member: bool) -> None:
        value = "1" if is_member else "0"
        try:
            await self.redis_client.setex(
                cache_key,
                _CHANNEL_MEMBER_CACHE_TTL_SECONDS,
                value,
            )
        except Exception as exc:
            logger.warning(f"Failed to write channel membership cache '{cache_key}': {exc}")

    @staticmethod
    def _is_channel_member_status_allowed(status_value: object) -> bool:
        if status_value in _CHANNEL_MEMBER_ALLOWED_STATUSES:
            return True

        raw_value = str(getattr(status_value, "value", status_value) or "").strip().lower()
        return raw_value in {"creator", "administrator", "admin", "member"}

    @staticmethod
    def _resolve_channel_chat_id(settings: SettingsDto) -> str | int | None:
        if settings.channel_id:
            return settings.channel_id

        raw_channel_link = settings.channel_link.get_secret_value().strip()
        if not raw_channel_link:
            return None

        if raw_channel_link.lstrip("-").isdigit():
            return int(raw_channel_link)

        if raw_channel_link.startswith("@"):
            return raw_channel_link

        if raw_channel_link.startswith(("http://", "https://")):
            parsed = urlparse(raw_channel_link)
            channel_slug = parsed.path.strip("/").split("/", maxsplit=1)[0]
            if not channel_slug:
                return None
            return f"@{channel_slug}"

        return None

    async def _resolve_verification_bot_link(self) -> str | None:
        try:
            bot_info = await self.bot.get_me()
        except Exception as exc:
            logger.warning(f"Failed to resolve verification bot link: {exc}")
            return None

        username = (bot_info.username or "").strip().lstrip("@")
        if not username:
            return None
        return f"{T_ME}{username}"
