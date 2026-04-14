from __future__ import annotations

from datetime import datetime

from aiogram import Bot

from src.core.config import AppConfig
from src.core.enums import Locale
from src.infrastructure.database.models.dto import WebAccountDto
from src.infrastructure.database.uow import UnitOfWork

from .auth_challenge import AuthChallengeService
from .email_recovery_email import (
    confirm_email as _confirm_email_impl,
)
from .email_recovery_email import (
    normalize_email as _normalize_email_impl,
)
from .email_recovery_email import (
    request_email_verification as _request_email_verification_impl,
)
from .email_recovery_email import (
    set_email as _set_email_impl,
)
from .email_recovery_passwords import (
    build_front_url as _build_front_url_impl,
)
from .email_recovery_passwords import (
    change_password as _change_password_impl,
)
from .email_recovery_passwords import (
    get_branding_project_name as _get_branding_project_name_impl,
)
from .email_recovery_passwords import (
    issue_temporary_password_for_dev as _issue_temporary_password_for_dev_impl,
)
from .email_recovery_passwords import (
    update_password as _update_password_impl,
)
from .email_recovery_passwords import (
    validate_new_password as _validate_new_password_impl,
)
from .email_recovery_reset import (
    forgot_password as _forgot_password_impl,
)
from .email_recovery_reset import (
    normalize_username as _normalize_username_impl,
)
from .email_recovery_reset import (
    request_telegram_password_reset as _request_telegram_password_reset_impl,
)
from .email_recovery_reset import (
    reset_password_by_code as _reset_password_by_code_impl,
)
from .email_recovery_reset import (
    reset_password_by_link as _reset_password_by_link_impl,
)
from .email_recovery_reset import (
    reset_password_by_telegram_code as _reset_password_by_telegram_code_impl,
)
from .email_recovery_reset import (
    send_password_reset as _send_password_reset_impl,
)
from .email_recovery_reset import (
    send_password_reset_telegram_code as _send_password_reset_telegram_code_impl,
)
from .email_sender import EmailSenderService
from .settings import SettingsService


class EmailRecoveryService:
    def __init__(
        self,
        uow: UnitOfWork,
        config: AppConfig,
        challenge_service: AuthChallengeService,
        email_sender: EmailSenderService,
        bot: Bot,
        settings_service: SettingsService,
    ) -> None:
        self.uow = uow
        self.config = config
        self.challenge_service = challenge_service
        self.email_sender = email_sender
        self.bot = bot
        self.settings_service = settings_service

    @staticmethod
    def normalize_email(email: str) -> str:
        return _normalize_email_impl(email)

    @staticmethod
    def normalize_username(username: str) -> str:
        return _normalize_username_impl(username)

    async def set_email(self, *, web_account_id: int, email: str) -> WebAccountDto:
        return await _set_email_impl(
            self,
            web_account_id=web_account_id,
            email=email,
        )

    async def request_email_verification(self, *, web_account: WebAccountDto) -> bool:
        return await _request_email_verification_impl(
            self,
            web_account=web_account,
        )

    async def confirm_email(
        self,
        *,
        web_account_id: int,
        code: str | None,
        token: str | None,
    ) -> WebAccountDto:
        return await _confirm_email_impl(
            self,
            web_account_id=web_account_id,
            code=code,
            token=token,
        )

    async def forgot_password(self, *, username: str | None, email: str | None) -> None:
        await _forgot_password_impl(
            self,
            username=username,
            email=email,
        )

    async def request_telegram_password_reset(self, *, username: str) -> None:
        await _request_telegram_password_reset_impl(
            self,
            username=username,
        )

    async def reset_password_by_link(self, *, token: str, new_password: str) -> None:
        await _reset_password_by_link_impl(
            self,
            token=token,
            new_password=new_password,
        )

    async def reset_password_by_code(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
    ) -> None:
        await _reset_password_by_code_impl(
            self,
            email=email,
            code=code,
            new_password=new_password,
        )

    async def reset_password_by_telegram_code(
        self,
        *,
        username: str,
        code: str,
        new_password: str,
    ) -> None:
        await _reset_password_by_telegram_code_impl(
            self,
            username=username,
            code=code,
            new_password=new_password,
        )

    async def change_password(
        self,
        *,
        web_account_id: int,
        current_password: str,
        new_password: str,
    ) -> WebAccountDto:
        return await _change_password_impl(
            self,
            web_account_id=web_account_id,
            current_password=current_password,
            new_password=new_password,
        )

    async def issue_temporary_password_for_dev(
        self,
        *,
        target_telegram_id: int,
        ttl_seconds: int,
    ) -> tuple[str, str, datetime]:
        return await _issue_temporary_password_for_dev_impl(
            self,
            target_telegram_id=target_telegram_id,
            ttl_seconds=ttl_seconds,
        )

    async def _send_password_reset(self, *, account: WebAccountDto | None) -> None:
        await _send_password_reset_impl(
            self,
            account=account,
        )

    async def _send_password_reset_telegram_code(
        self,
        *,
        telegram_id: int,
        code: str,
        language: Locale | str | None = None,
    ) -> None:
        await _send_password_reset_telegram_code_impl(
            self,
            telegram_id=telegram_id,
            code=code,
            language=language,
        )

    @staticmethod
    def _validate_new_password(new_password: str) -> None:
        _validate_new_password_impl(new_password)

    async def _update_password(
        self,
        *,
        web_account_id: int,
        new_password: str,
    ) -> WebAccountDto:
        return await _update_password_impl(
            self,
            web_account_id=web_account_id,
            new_password=new_password,
        )

    async def _get_branding_project_name(self) -> str:
        return await _get_branding_project_name_impl(self)

    def _build_front_url(self, path: str) -> str:
        return _build_front_url_impl(self, path)
