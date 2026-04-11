from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from aiogram import Bot
from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.constants import T_ME
from src.core.enums import Locale, UserRole
from src.infrastructure.database.models.dto import AuthChallengeDto, WebAccountDto
from src.infrastructure.database.models.sql import User, WebAccount
from src.infrastructure.database.uow import UnitOfWork

from .auth_challenge import (
    AuthChallengeService,
    ChallengeChannel,
    ChallengeErrorReason,
    ChallengePurpose,
)
from .settings import SettingsService


class TelegramLinkError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class TelegramLinkRequestResult:
    delivered: bool
    expires_in_seconds: int
    destination: int
    bot_confirm_url: str | None = None
    bot_confirm_deep_link: str | None = None


@dataclass
class TelegramLinkConfirmResult:
    web_account: WebAccountDto
    linked_telegram_id: int


class TelegramLinkService:
    def __init__(
        self,
        uow: UnitOfWork,
        challenge_service: AuthChallengeService,
        bot: Bot,
        settings_service: SettingsService,
    ) -> None:
        self.uow = uow
        self.challenge_service = challenge_service
        self.bot = bot
        self.settings_service = settings_service

    async def request_code(
        self,
        *,
        web_account: WebAccountDto,
        telegram_id: int,
        ttl_seconds: int,
        attempts: int,
        return_to_miniapp: bool = False,
    ) -> TelegramLinkRequestResult:
        challenge = await self.challenge_service.create(
            web_account_id=web_account.id or 0,
            purpose=ChallengePurpose.TG_LINK,
            channel=ChallengeChannel.TELEGRAM,
            destination=str(telegram_id),
            ttl_seconds=ttl_seconds,
            attempts=attempts,
            include_code=True,
            include_token=True,
            meta={
                "telegram_id": telegram_id,
                "return_to_miniapp": return_to_miniapp,
            },
        )

        delivered = True
        code = challenge.code or ""
        user_language: str | Locale | None = None
        if web_account.user_telegram_id is not None:
            async with self.uow:
                source_user = await self.uow.repository.users.get(web_account.user_telegram_id)
                if source_user:
                    user_language = source_user.language

        branding = await self.settings_service.get_branding_settings()
        template = self.settings_service.resolve_localized_branding_text(
            branding.verification.telegram_template,
            language=user_language,
        )
        message_text = self.settings_service.render_branding_text(
            template,
            placeholders={
                "project_name": branding.project_name,
                "code": code,
            },
        )

        try:
            sent_message = await self.bot.send_message(
                chat_id=telegram_id,
                text=message_text,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            delivered = False
            logger.warning(f"Failed to deliver Telegram link code to '{telegram_id}': {exc}")
        else:
            try:
                await self._save_telegram_message_meta(
                    challenge_id=challenge.challenge.id,
                    current_meta=challenge.challenge.meta,
                    chat_id=telegram_id,
                    message_id=sent_message.message_id,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to save verification message meta for chat '{telegram_id}': {exc}"
                )

        return TelegramLinkRequestResult(
            delivered=delivered,
            expires_in_seconds=ttl_seconds,
            destination=telegram_id,
            bot_confirm_url=await self._build_bot_confirm_url(
                challenge.token,
                return_to_miniapp=return_to_miniapp,
            ),
            bot_confirm_deep_link=await self._build_bot_confirm_deep_link(
                challenge.token,
                return_to_miniapp=return_to_miniapp,
            ),
        )

    async def confirm_code(
        self,
        *,
        web_account: WebAccountDto,
        telegram_id: int,
        code: str,
    ) -> TelegramLinkConfirmResult:
        verification = await self.challenge_service.verify_code(
            web_account_id=web_account.id or 0,
            purpose=ChallengePurpose.TG_LINK,
            destination=str(telegram_id),
            code=code.strip(),
        )
        if not verification.ok:
            if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
                raise TelegramLinkError(
                    code="TOO_MANY_ATTEMPTS",
                    message="Too many attempts. Request a new code.",
                )
            raise TelegramLinkError(
                code="INVALID_OR_EXPIRED_CODE",
                message="Invalid or expired code.",
            )

        account = await self._safe_auto_link(
            web_account_id=web_account.id or 0,
            telegram_id=telegram_id,
        )
        await self._delete_verification_message(
            challenge=verification.challenge,
            fallback_chat_id=telegram_id,
        )
        return TelegramLinkConfirmResult(
            web_account=account,
            linked_telegram_id=telegram_id,
        )


    async def bind_existing_account(
        self,
        *,
        web_account_id: int,
        telegram_id: int,
    ) -> WebAccountDto:
        return await self._safe_auto_link(
            web_account_id=web_account_id,
            telegram_id=telegram_id,
        )

    async def confirm_token(
        self,
        *,
        telegram_id: int,
        token: str,
    ) -> TelegramLinkConfirmResult:
        verification = await self.challenge_service.verify_token(
            purpose=ChallengePurpose.TG_LINK,
            token=token.strip(),
            destination=str(telegram_id),
        )
        if not verification.ok or verification.challenge is None:
            raise TelegramLinkError(
                code="INVALID_OR_EXPIRED_CODE",
                message="Invalid or expired code.",
            )

        account = await self._safe_auto_link(
            web_account_id=verification.challenge.web_account_id,
            telegram_id=telegram_id,
        )
        await self._delete_verification_message(
            challenge=verification.challenge,
            fallback_chat_id=telegram_id,
        )
        return TelegramLinkConfirmResult(
            web_account=account,
            linked_telegram_id=telegram_id,
        )

    async def _save_telegram_message_meta(
        self,
        *,
        challenge_id: UUID,
        current_meta: Optional[dict[str, object]],
        chat_id: int,
        message_id: int,
    ) -> None:
        meta = dict(current_meta or {})
        meta["telegram_chat_id"] = chat_id
        meta["telegram_message_id"] = message_id

        async with self.uow:
            await self.uow.repository.auth_challenges.update(challenge_id, meta=meta)
            await self.uow.commit()

    async def _delete_verification_message(
        self,
        *,
        challenge: Optional[AuthChallengeDto],
        fallback_chat_id: int,
    ) -> None:
        if not challenge:
            return

        meta = challenge.meta or {}
        raw_message_id = meta.get("telegram_message_id")
        raw_chat_id: object = meta.get("telegram_chat_id", fallback_chat_id)

        if not isinstance(raw_message_id, (str, int)) or not isinstance(raw_chat_id, (str, int)):
            return

        try:
            message_id = int(raw_message_id)
            chat_id = int(raw_chat_id)
        except (TypeError, ValueError):
            return

        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as exc:
            logger.debug(
                f"Failed to delete verification message '{message_id}' for chat '{chat_id}': {exc}"
            )

    async def _build_bot_confirm_url(
        self,
        token: str | None,
        *,
        return_to_miniapp: bool,
    ) -> str | None:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            return None

        try:
            bot_info = await self.bot.get_me()
        except Exception as exc:
            logger.warning(f"Failed to resolve Telegram link bot username: {exc}")
            return None

        username = (bot_info.username or "").strip().lstrip("@")
        if not username:
            return None

        start_prefix = "tglinkapp_" if return_to_miniapp else "tglink_"
        return f"{T_ME}{username}?start={start_prefix}{normalized_token}"

    async def _build_bot_confirm_deep_link(
        self,
        token: str | None,
        *,
        return_to_miniapp: bool,
    ) -> str | None:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            return None

        try:
            bot_info = await self.bot.get_me()
        except Exception as exc:
            logger.warning(f"Failed to resolve Telegram link bot username for deep link: {exc}")
            return None

        username = (bot_info.username or "").strip().lstrip("@")
        if not username:
            return None

        start_prefix = "tglinkapp_" if return_to_miniapp else "tglink_"
        return f"tg://resolve?domain={username}&start={start_prefix}{normalized_token}"

    async def _safe_auto_link(
        self,
        *,
        web_account_id: int,
        telegram_id: int,
    ) -> WebAccountDto:
        async with self.uow:
            current_account = await self._get_web_account_or_error(web_account_id)
            already_linked = await self._handle_already_linked_account(
                current_account=current_account,
                telegram_id=telegram_id,
            )
            if already_linked:
                return already_linked

            await self._assert_telegram_not_linked_elsewhere(
                current_account_id=current_account.id,
                telegram_id=telegram_id,
            )
            source_user = await self._get_source_user_or_error(current_account.user_telegram_id)
            target_user = await self._get_or_create_target_user(
                telegram_id=telegram_id,
                source_user=source_user,
            )
            source_has_data = await self._assert_merge_allowed(
                source_user=source_user,
                target_user=target_user,
            )

            if source_user.telegram_id != target_user.telegram_id and source_has_data:
                try:
                    await self.uow.repository.users.reassign_telegram_id_references(
                        source_telegram_id=source_user.telegram_id,
                        target_telegram_id=target_user.telegram_id,
                    )
                except IntegrityError as exception:
                    logger.warning(
                        "Automatic Telegram link merge failed for source='{}' target='{}': {}",
                        source_user.telegram_id,
                        target_user.telegram_id,
                        exception,
                    )
                    raise TelegramLinkError(
                        code="MANUAL_MERGE_REQUIRED",
                        message=(
                            "Automatic merge failed because referral attribution already exists."
                        ),
                    ) from exception

            await self._merge_user_values(
                source_user_telegram_id=source_user.telegram_id,
                target_user_telegram_id=target_user.telegram_id,
                source_has_data=source_has_data,
            )

            updated_account = await self.uow.repository.web_accounts.update(
                current_account.id,
                user_telegram_id=target_user.telegram_id,
                token_version=current_account.token_version + 1,
                link_prompt_snooze_until=None,
            )
            if not updated_account:
                raise TelegramLinkError(
                    code="LINK_UPDATE_FAILED",
                    message="Failed to link Telegram account.",
                )

            if source_user.telegram_id < 0 and source_user.telegram_id != target_user.telegram_id:
                await self.uow.repository.users.delete(source_user.telegram_id)

            await self.uow.commit()

        account_dto = WebAccountDto.from_model(updated_account)
        if not account_dto:
            raise TelegramLinkError(
                code="LINK_UPDATE_FAILED",
                message="Failed to link Telegram account.",
            )
        return account_dto

    async def _get_web_account_or_error(self, web_account_id: int) -> WebAccount:
        account = await self.uow.repository.web_accounts.get(web_account_id)
        if not account:
            raise TelegramLinkError(
                code="WEB_ACCOUNT_NOT_FOUND",
                message="Web account not found.",
            )
        return account

    async def _handle_already_linked_account(
        self,
        *,
        current_account: WebAccount,
        telegram_id: int,
    ) -> Optional[WebAccountDto]:
        if current_account.user_telegram_id != telegram_id:
            return None

        updated = await self.uow.repository.web_accounts.update(
            current_account.id,
            link_prompt_snooze_until=None,
        )
        await self.uow.commit()
        account_dto = WebAccountDto.from_model(updated)
        if not account_dto:
            raise TelegramLinkError(
                code="WEB_ACCOUNT_NOT_FOUND",
                message="Web account not found.",
            )
        return account_dto

    async def _assert_telegram_not_linked_elsewhere(
        self,
        *,
        current_account_id: int,
        telegram_id: int,
    ) -> None:
        other_account = await self.uow.repository.web_accounts.get_by_user_telegram_id(telegram_id)
        if other_account and other_account.id != current_account_id:
            raise TelegramLinkError(
                code="TELEGRAM_ALREADY_LINKED",
                message="Telegram ID is already linked to another account.",
            )

    async def _get_source_user_or_error(self, source_telegram_id: int) -> User:
        source_user = await self.uow.repository.users.get(source_telegram_id)
        if not source_user:
            raise TelegramLinkError(
                code="SOURCE_USER_NOT_FOUND",
                message="Source profile not found.",
            )
        return source_user

    async def _get_or_create_target_user(self, *, telegram_id: int, source_user: User) -> User:
        target_user = await self.uow.repository.users.get(telegram_id)
        if target_user:
            return target_user
        return await self._create_target_user(telegram_id=telegram_id, source_user=source_user)

    async def _assert_merge_allowed(self, *, source_user: User, target_user: User) -> bool:
        source_has_data = await self.uow.repository.users.has_material_data(
            source_user.telegram_id,
            include_referrals=True,
        )
        source_has_conflicting_data = await self.uow.repository.users.has_material_data(
            source_user.telegram_id,
            include_referrals=False,
        )
        target_has_conflicting_data = await self.uow.repository.users.has_material_data(
            target_user.telegram_id,
            include_referrals=False,
        )
        is_source_provisional = source_user.telegram_id < 0

        if (
            source_has_conflicting_data
            and target_has_conflicting_data
            and not is_source_provisional
        ):
            raise TelegramLinkError(
                code="MANUAL_MERGE_REQUIRED",
                message="Both profiles contain material data. Manual merge is required.",
            )

        return source_has_data

    async def _create_target_user(self, *, telegram_id: int, source_user: User) -> User:
        referral_code = await self.uow.repository.users.generate_unique_referral_code()
        target = User(
            telegram_id=telegram_id,
            username=source_user.username,
            referral_code=referral_code,
            name=source_user.name or str(telegram_id),
            role=source_user.role or UserRole.USER,
            language=source_user.language or Locale.EN,
            personal_discount=0,
            purchase_discount=0,
            points=0,
            is_blocked=False,
            is_bot_blocked=False,
            is_rules_accepted=True,
        )
        try:
            return await self.uow.repository.users.create(target)
        except IntegrityError:
            existing = await self.uow.repository.users.get(telegram_id)
            if not existing:
                raise
            return existing

    async def _merge_user_values(
        self,
        *,
        source_user_telegram_id: int,
        target_user_telegram_id: int,
        source_has_data: bool,
    ) -> None:
        source_user = await self.uow.repository.users.get(source_user_telegram_id)
        target_user = await self.uow.repository.users.get(target_user_telegram_id)
        if not source_user or not target_user:
            return

        update_data: dict[str, object] = {}
        if not target_user.username and source_user.username:
            update_data["username"] = source_user.username

        if (
            not target_user.name or target_user.name.strip() == str(target_user.telegram_id)
        ) and source_user.name:
            update_data["name"] = source_user.name

        if source_has_data:
            update_data["points"] = max(target_user.points, source_user.points)
            update_data["personal_discount"] = max(
                target_user.personal_discount,
                source_user.personal_discount,
            )
            update_data["purchase_discount"] = max(
                target_user.purchase_discount,
                source_user.purchase_discount,
            )

        if update_data:
            await self.uow.repository.users.update(target_user.telegram_id, **update_data)
