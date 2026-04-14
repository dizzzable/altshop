from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from aiogram import Bot

from src.infrastructure.database.models.dto import AuthChallengeDto, WebAccountDto
from src.infrastructure.database.models.sql import User, WebAccount
from src.infrastructure.database.uow import UnitOfWork

from .auth_challenge import AuthChallengeService
from .settings import SettingsService
from .telegram_link_binding import (
    assert_merge_allowed as _assert_merge_allowed_impl,
)
from .telegram_link_binding import (
    assert_telegram_not_linked_elsewhere as _assert_telegram_not_linked_elsewhere_impl,
)
from .telegram_link_binding import (
    create_target_user as _create_target_user_impl,
)
from .telegram_link_binding import (
    get_or_create_target_user as _get_or_create_target_user_impl,
)
from .telegram_link_binding import (
    get_source_user_or_error as _get_source_user_or_error_impl,
)
from .telegram_link_binding import (
    get_web_account_or_error as _get_web_account_or_error_impl,
)
from .telegram_link_binding import (
    handle_already_linked_account as _handle_already_linked_account_impl,
)
from .telegram_link_binding import (
    merge_user_values as _merge_user_values_impl,
)
from .telegram_link_binding import (
    safe_auto_link as _safe_auto_link_impl,
)
from .telegram_link_confirmation import (
    bind_existing_account as _bind_existing_account_impl,
)
from .telegram_link_confirmation import confirm_code as _confirm_code_impl
from .telegram_link_confirmation import confirm_token as _confirm_token_impl
from .telegram_link_delivery import (
    build_bot_confirm_deep_link as _build_bot_confirm_deep_link_impl,
)
from .telegram_link_delivery import (
    build_bot_confirm_url as _build_bot_confirm_url_impl,
)
from .telegram_link_delivery import (
    delete_verification_message as _delete_verification_message_impl,
)
from .telegram_link_delivery import (
    request_code as _request_code_impl,
)
from .telegram_link_delivery import (
    save_telegram_message_meta as _save_telegram_message_meta_impl,
)


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


def _build_request_result(
    payload: tuple[bool, int, int, str | None, str | None],
) -> TelegramLinkRequestResult:
    delivered, expires_in_seconds, destination, bot_confirm_url, bot_confirm_deep_link = payload
    return TelegramLinkRequestResult(
        delivered=delivered,
        expires_in_seconds=expires_in_seconds,
        destination=destination,
        bot_confirm_url=bot_confirm_url,
        bot_confirm_deep_link=bot_confirm_deep_link,
    )


def _build_confirm_result(
    payload: tuple[WebAccountDto, int],
) -> TelegramLinkConfirmResult:
    web_account, linked_telegram_id = payload
    return TelegramLinkConfirmResult(
        web_account=web_account,
        linked_telegram_id=linked_telegram_id,
    )


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

    @staticmethod
    def _telegram_link_error(*, code: str, message: str) -> TelegramLinkError:
        return TelegramLinkError(code=code, message=message)

    async def request_code(
        self,
        *,
        web_account: WebAccountDto,
        telegram_id: int,
        ttl_seconds: int,
        attempts: int,
        return_to_miniapp: bool = False,
    ) -> TelegramLinkRequestResult:
        return _build_request_result(
            await _request_code_impl(
                self,
                web_account=web_account,
                telegram_id=telegram_id,
                ttl_seconds=ttl_seconds,
                attempts=attempts,
                return_to_miniapp=return_to_miniapp,
            )
        )

    async def confirm_code(
        self,
        *,
        web_account: WebAccountDto,
        telegram_id: int,
        code: str,
    ) -> TelegramLinkConfirmResult:
        return _build_confirm_result(
            await _confirm_code_impl(
                self,
                web_account=web_account,
                telegram_id=telegram_id,
                code=code,
            )
        )

    async def bind_existing_account(
        self,
        *,
        web_account_id: int,
        telegram_id: int,
    ) -> WebAccountDto:
        return await _bind_existing_account_impl(
            self,
            web_account_id=web_account_id,
            telegram_id=telegram_id,
        )

    async def confirm_token(
        self,
        *,
        telegram_id: int,
        token: str,
    ) -> TelegramLinkConfirmResult:
        return _build_confirm_result(
            await _confirm_token_impl(
                self,
                telegram_id=telegram_id,
                token=token,
            )
        )

    async def _save_telegram_message_meta(
        self,
        *,
        challenge_id: UUID,
        current_meta: Optional[dict[str, object]],
        chat_id: int,
        message_id: int,
    ) -> None:
        await _save_telegram_message_meta_impl(
            self,
            challenge_id=challenge_id,
            current_meta=current_meta,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def _delete_verification_message(
        self,
        *,
        challenge: Optional[AuthChallengeDto],
        fallback_chat_id: int,
    ) -> None:
        await _delete_verification_message_impl(
            self,
            challenge=challenge,
            fallback_chat_id=fallback_chat_id,
        )

    async def _build_bot_confirm_url(
        self,
        token: str | None,
        *,
        return_to_miniapp: bool,
    ) -> str | None:
        return await _build_bot_confirm_url_impl(
            self,
            token,
            return_to_miniapp=return_to_miniapp,
        )

    async def _build_bot_confirm_deep_link(
        self,
        token: str | None,
        *,
        return_to_miniapp: bool,
    ) -> str | None:
        return await _build_bot_confirm_deep_link_impl(
            self,
            token,
            return_to_miniapp=return_to_miniapp,
        )

    async def _safe_auto_link(
        self,
        *,
        web_account_id: int,
        telegram_id: int,
    ) -> WebAccountDto:
        return await _safe_auto_link_impl(
            self,
            web_account_id=web_account_id,
            telegram_id=telegram_id,
        )

    async def _get_web_account_or_error(self, web_account_id: int) -> WebAccount:
        return await _get_web_account_or_error_impl(self, web_account_id)

    async def _handle_already_linked_account(
        self,
        *,
        current_account: WebAccount,
        telegram_id: int,
    ) -> Optional[WebAccountDto]:
        return await _handle_already_linked_account_impl(
            self,
            current_account=current_account,
            telegram_id=telegram_id,
        )

    async def _assert_telegram_not_linked_elsewhere(
        self,
        *,
        current_account_id: int,
        telegram_id: int,
    ) -> None:
        await _assert_telegram_not_linked_elsewhere_impl(
            self,
            current_account_id=current_account_id,
            telegram_id=telegram_id,
        )

    async def _get_source_user_or_error(self, source_telegram_id: int) -> User:
        return await _get_source_user_or_error_impl(self, source_telegram_id)

    async def _get_or_create_target_user(
        self,
        *,
        telegram_id: int,
        source_user: User,
    ) -> User:
        return await _get_or_create_target_user_impl(
            self,
            telegram_id=telegram_id,
            source_user=source_user,
        )

    async def _assert_merge_allowed(
        self,
        *,
        source_user: User,
        target_user: User,
    ) -> bool:
        return await _assert_merge_allowed_impl(
            self,
            source_user=source_user,
            target_user=target_user,
        )

    async def _create_target_user(
        self,
        *,
        telegram_id: int,
        source_user: User,
    ) -> User:
        return await _create_target_user_impl(
            self,
            telegram_id=telegram_id,
            source_user=source_user,
        )

    async def _merge_user_values(
        self,
        *,
        source_user_telegram_id: int,
        target_user_telegram_id: int,
        source_has_data: bool,
    ) -> None:
        await _merge_user_values_impl(
            self,
            source_user_telegram_id=source_user_telegram_id,
            target_user_telegram_id=target_user_telegram_id,
            source_has_data=source_has_data,
        )
