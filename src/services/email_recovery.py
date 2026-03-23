from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.core.config import AppConfig
from src.core.enums import Locale
from src.core.security.password import hash_password, verify_password
from src.core.utils.branding import resolve_project_name
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import WebAccountDto
from src.infrastructure.database.uow import UnitOfWork

from .auth_challenge import (
    AuthChallengeService,
    ChallengeChannel,
    ChallengeErrorReason,
    ChallengePurpose,
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
        return email.strip().lower()

    @staticmethod
    def normalize_username(username: str) -> str:
        return username.strip().lower()

    async def set_email(self, *, web_account_id: int, email: str) -> WebAccountDto:
        normalized_email = self.normalize_email(email)
        if "@" not in normalized_email:
            raise ValueError("Invalid email format")

        async with self.uow:
            try:
                updated = await self.uow.repository.web_accounts.update(
                    web_account_id,
                    email=email.strip(),
                    email_normalized=normalized_email,
                    email_verified_at=None,
                )
                await self.uow.commit()
            except IntegrityError as exc:
                await self.uow.rollback()
                raise ValueError("Email is already used") from exc

        dto = WebAccountDto.from_model(updated)
        if not dto:
            raise ValueError("Web account not found")
        return dto

    async def request_email_verification(self, *, web_account: WebAccountDto) -> bool:
        destination = web_account.email_normalized
        if not destination:
            raise ValueError("Recovery email is not set")

        challenge = await self.challenge_service.create(
            web_account_id=web_account.id or 0,
            purpose=ChallengePurpose.EMAIL_VERIFY,
            channel=ChallengeChannel.EMAIL,
            destination=destination,
            ttl_seconds=self.config.web_app.email_verify_ttl_seconds,
            attempts=self.config.web_app.auth_challenge_attempts,
            include_code=True,
            include_token=True,
            meta={"email": destination},
        )

        verify_link = self._build_front_url(
            f"/dashboard/settings?email_verify_token={challenge.token}"
        )
        project_name = await self._get_branding_project_name()
        subject = f"{project_name} email verification"
        text_body = (
            "Your verification code:\n"
            f"{challenge.code}\n\n"
            "Or open link:\n"
            f"{verify_link}\n\n"
            "If you did not request this, ignore this message."
        )
        return await self.email_sender.send(
            to_email=destination,
            subject=subject,
            text_body=text_body,
        )

    async def confirm_email(
        self,
        *,
        web_account_id: int,
        code: Optional[str],
        token: Optional[str],
    ) -> WebAccountDto:
        if not code and not token:
            raise ValueError("Provide code or token")

        async with self.uow:
            account = await self.uow.repository.web_accounts.get(web_account_id)
            if not account:
                raise ValueError("Web account not found")
            destination = account.email_normalized

        if not destination:
            raise ValueError("Recovery email is not set")

        if token:
            verification = await self.challenge_service.verify_token(
                purpose=ChallengePurpose.EMAIL_VERIFY,
                token=token,
                web_account_id=web_account_id,
            )
        else:
            verification = await self.challenge_service.verify_code(
                web_account_id=web_account_id,
                purpose=ChallengePurpose.EMAIL_VERIFY,
                destination=destination,
                code=(code or "").strip(),
            )

        if not verification.ok:
            if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
                raise ValueError("Too many attempts. Request a new verification code.")
            raise ValueError("Invalid or expired verification data.")

        async with self.uow:
            updated = await self.uow.repository.web_accounts.update(
                web_account_id,
                email_verified_at=datetime_now(),
            )
            await self.uow.commit()

        dto = WebAccountDto.from_model(updated)
        if not dto:
            raise ValueError("Web account not found")
        return dto

    async def forgot_password(self, *, username: Optional[str], email: Optional[str]) -> None:
        if not username and not email:
            return

        normalized_username = self.normalize_username(username) if username else None
        normalized_email = self.normalize_email(email) if email else None

        async with self.uow:
            account = None
            if normalized_email:
                account = await self.uow.repository.web_accounts.get_by_email(normalized_email)
            if account is None and normalized_username:
                account = await self.uow.repository.web_accounts.get_by_username(
                    normalized_username
                )

        if not account or not account.email_normalized or account.email_verified_at is None:
            return

        await self._send_password_reset(account=WebAccountDto.from_model(account))

    async def request_telegram_password_reset(self, *, username: str) -> None:
        normalized_username = self.normalize_username(username)
        if not normalized_username:
            return

        user_language: Locale | str | None = None
        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_username(normalized_username)
            if account and account.user_telegram_id > 0:
                user = await self.uow.repository.users.get(account.user_telegram_id)
                if user:
                    user_language = user.language

        if not account or account.user_telegram_id <= 0:
            return

        challenge = await self.challenge_service.create(
            web_account_id=account.id,
            purpose=ChallengePurpose.PASSWORD_RESET,
            channel=ChallengeChannel.TELEGRAM,
            destination=str(account.user_telegram_id),
            ttl_seconds=self.config.web_app.password_reset_ttl_seconds,
            attempts=self.config.web_app.auth_challenge_attempts,
            include_code=True,
            include_token=False,
            meta={
                "telegram_id": account.user_telegram_id,
                "username": account.username,
            },
        )

        if not challenge.code:
            return
        await self._send_password_reset_telegram_code(
            telegram_id=account.user_telegram_id,
            code=challenge.code,
            language=user_language,
        )

    async def reset_password_by_link(self, *, token: str, new_password: str) -> None:
        self._validate_new_password(new_password)

        verification = await self.challenge_service.verify_token(
            purpose=ChallengePurpose.PASSWORD_RESET,
            token=token,
        )
        if not verification.ok or not verification.challenge:
            raise ValueError("Invalid or expired reset token")

        await self._update_password(
            web_account_id=verification.challenge.web_account_id,
            new_password=new_password,
        )

    async def reset_password_by_code(self, *, email: str, code: str, new_password: str) -> None:
        self._validate_new_password(new_password)

        normalized_email = self.normalize_email(email)
        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_email(normalized_email)

        if not account or account.email_verified_at is None:
            raise ValueError("Invalid or expired reset code")

        verification = await self.challenge_service.verify_code(
            web_account_id=account.id,
            purpose=ChallengePurpose.PASSWORD_RESET,
            destination=normalized_email,
            code=code.strip(),
        )
        if not verification.ok:
            if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
                raise ValueError("Too many attempts. Request a new reset code.")
            raise ValueError("Invalid or expired reset code")

        await self._update_password(
            web_account_id=account.id,
            new_password=new_password,
        )

    async def reset_password_by_telegram_code(
        self,
        *,
        username: str,
        code: str,
        new_password: str,
    ) -> None:
        self._validate_new_password(new_password)
        normalized_username = self.normalize_username(username)

        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_username(normalized_username)

        if not account or account.user_telegram_id <= 0:
            raise ValueError("Invalid or expired reset code")

        verification = await self.challenge_service.verify_code(
            web_account_id=account.id,
            purpose=ChallengePurpose.PASSWORD_RESET,
            destination=str(account.user_telegram_id),
            code=code.strip(),
        )
        if not verification.ok:
            if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
                raise ValueError("Too many attempts. Request a new reset code.")
            raise ValueError("Invalid or expired reset code")

        await self._update_password(
            web_account_id=account.id,
            new_password=new_password,
        )

    async def change_password(
        self,
        *,
        web_account_id: int,
        current_password: str,
        new_password: str,
    ) -> WebAccountDto:
        self._validate_new_password(new_password)

        async with self.uow:
            account = await self.uow.repository.web_accounts.get(web_account_id)

        if not account:
            raise ValueError("Web account not found")
        if not verify_password(current_password, account.password_hash):
            raise ValueError("Invalid current password")

        return await self._update_password(
            web_account_id=web_account_id,
            new_password=new_password,
        )

    async def issue_temporary_password_for_dev(
        self,
        *,
        target_telegram_id: int,
        ttl_seconds: int,
    ) -> tuple[str, str, datetime]:
        if ttl_seconds <= 0:
            raise ValueError("Invalid temporary password TTL")

        temp_password = f"Tmp{secrets.randbelow(1_000_000):06d}"
        expires_at = datetime_now() + timedelta(seconds=ttl_seconds)

        async with self.uow:
            account = await self.uow.repository.web_accounts.get_by_user_telegram_id(
                target_telegram_id
            )
            if not account:
                raise ValueError("Web account not found")

            updated_account = await self.uow.repository.web_accounts.update(
                account.id,
                password_hash=hash_password(temp_password),
                token_version=account.token_version + 1,
                requires_password_change=True,
                temporary_password_expires_at=expires_at,
            )
            if not updated_account:
                raise ValueError("Web account not found")

            await self.uow.commit()

        return updated_account.username, temp_password, expires_at

    async def _send_password_reset(self, *, account: Optional[WebAccountDto]) -> None:
        if not account or not account.email_normalized:
            return

        challenge = await self.challenge_service.create(
            web_account_id=account.id or 0,
            purpose=ChallengePurpose.PASSWORD_RESET,
            channel=ChallengeChannel.EMAIL,
            destination=account.email_normalized,
            ttl_seconds=self.config.web_app.password_reset_ttl_seconds,
            attempts=self.config.web_app.auth_challenge_attempts,
            include_code=True,
            include_token=True,
            meta={"email": account.email_normalized},
        )

        reset_link = self._build_front_url(f"/auth/reset-password?token={challenge.token}")
        project_name = await self._get_branding_project_name()
        subject = f"{project_name} password reset"
        text_body = (
            "Use this code to reset your password:\n"
            f"{challenge.code}\n\n"
            "Or open the reset link:\n"
            f"{reset_link}\n\n"
            "If you did not request this, ignore this message."
        )
        sent = await self.email_sender.send(
            to_email=account.email_normalized,
            subject=subject,
            text_body=text_body,
        )
        if not sent:
            logger.warning(
                f"Password reset email was not delivered to '{account.email_normalized}'"
            )

    async def _send_password_reset_telegram_code(
        self,
        *,
        telegram_id: int,
        code: str,
        language: Locale | str | None = None,
    ) -> None:
        project_name = await self._get_branding_project_name()
        fallback_text_body = (
            f"Your {project_name} password reset code:\n"
            f"{code}\n\n"
            "If you did not request this, ignore this message."
        )
        text_body = fallback_text_body
        try:
            branding = await self.settings_service.get_branding_settings()
            template = self.settings_service.resolve_localized_branding_text(
                branding.verification.password_reset_telegram_template,
                language=language,
            )
            text_body = (
                self.settings_service.render_branding_text(
                    template,
                    placeholders={
                        "project_name": branding.project_name,
                        "code": code,
                    },
                )
                or fallback_text_body
            )
        except Exception as exc:
            logger.warning(
                f"Failed to render branded Telegram password reset message "
                f"for '{telegram_id}': {exc}"
            )
            text_body = fallback_text_body

        try:
            await self.bot.send_message(
                chat_id=telegram_id,
                text=text_body,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to deliver Telegram password reset code to '{telegram_id}': {exc}"
            )

    @staticmethod
    def _validate_new_password(new_password: str) -> None:
        if len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters")

    async def _update_password(self, *, web_account_id: int, new_password: str) -> WebAccountDto:
        async with self.uow:
            account = await self.uow.repository.web_accounts.get(web_account_id)
            if not account:
                raise ValueError("Web account not found")

            updated_account = await self.uow.repository.web_accounts.update(
                web_account_id,
                password_hash=hash_password(new_password),
                token_version=account.token_version + 1,
                requires_password_change=False,
                temporary_password_expires_at=None,
            )
            if not updated_account:
                raise ValueError("Web account not found")

            await self.uow.commit()

        dto = WebAccountDto.from_model(updated_account)
        if not dto:
            raise ValueError("Web account not found")
        return dto

    async def _get_branding_project_name(self) -> str:
        try:
            branding = await self.settings_service.get_branding_settings()
        except Exception as exc:
            logger.warning(f"Failed to load branding settings for email recovery: {exc}")
            return resolve_project_name(None)

        return resolve_project_name(branding.project_name)

    def _build_front_url(self, path: str) -> str:
        base_url = self.config.web_app.url_str.rstrip("/")
        if not base_url:
            base_url = f"https://{self.config.domain.get_secret_value()}/webapp"
        elif not base_url.endswith("/webapp"):
            base_url = f"{base_url}/webapp"

        if path.startswith("/"):
            return f"{base_url}{path}"
        return f"{base_url}/{path}"
