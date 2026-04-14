from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from src.core.enums import Locale
from src.infrastructure.database.models.dto import WebAccountDto

from .auth_challenge import ChallengeChannel, ChallengeErrorReason, ChallengePurpose

if TYPE_CHECKING:
    from .email_recovery import EmailRecoveryService


def normalize_username(username: str) -> str:
    return username.strip().lower()


async def forgot_password(
    service: EmailRecoveryService,
    *,
    username: str | None,
    email: str | None,
) -> None:
    if not username and not email:
        return

    normalized_username = service.normalize_username(username) if username else None
    normalized_email = service.normalize_email(email) if email else None

    async with service.uow:
        account = None
        if normalized_email:
            account = await service.uow.repository.web_accounts.get_by_email(normalized_email)
        if account is None and normalized_username:
            account = await service.uow.repository.web_accounts.get_by_username(
                normalized_username
            )

    if not account or not account.email_normalized or account.email_verified_at is None:
        return

    await service._send_password_reset(account=WebAccountDto.from_model(account))


async def request_telegram_password_reset(
    service: EmailRecoveryService,
    *,
    username: str,
) -> None:
    normalized_username = service.normalize_username(username)
    if not normalized_username:
        return

    user_language: Locale | str | None = None
    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_username(normalized_username)
        if account and account.user_telegram_id > 0:
            user = await service.uow.repository.users.get(account.user_telegram_id)
            if user:
                user_language = user.language

    if not account or account.user_telegram_id <= 0:
        return

    challenge = await service.challenge_service.create(
        web_account_id=account.id,
        purpose=ChallengePurpose.PASSWORD_RESET,
        channel=ChallengeChannel.TELEGRAM,
        destination=str(account.user_telegram_id),
        ttl_seconds=service.config.web_app.password_reset_ttl_seconds,
        attempts=service.config.web_app.auth_challenge_attempts,
        include_code=True,
        include_token=False,
        meta={
            "telegram_id": account.user_telegram_id,
            "username": account.username,
        },
    )

    if not challenge.code:
        return
    await service._send_password_reset_telegram_code(
        telegram_id=account.user_telegram_id,
        code=challenge.code,
        language=user_language,
    )


async def reset_password_by_link(
    service: EmailRecoveryService,
    *,
    token: str,
    new_password: str,
) -> None:
    service._validate_new_password(new_password)

    verification = await service.challenge_service.verify_token(
        purpose=ChallengePurpose.PASSWORD_RESET,
        token=token,
    )
    if not verification.ok or not verification.challenge:
        raise ValueError("Invalid or expired reset token")

    await service._update_password(
        web_account_id=verification.challenge.web_account_id,
        new_password=new_password,
    )


async def reset_password_by_code(
    service: EmailRecoveryService,
    *,
    email: str,
    code: str,
    new_password: str,
) -> None:
    service._validate_new_password(new_password)

    normalized_email = service.normalize_email(email)
    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_email(normalized_email)

    if not account or account.email_verified_at is None:
        raise ValueError("Invalid or expired reset code")

    verification = await service.challenge_service.verify_code(
        web_account_id=account.id,
        purpose=ChallengePurpose.PASSWORD_RESET,
        destination=normalized_email,
        code=code.strip(),
    )
    if not verification.ok:
        if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
            raise ValueError("Too many attempts. Request a new reset code.")
        raise ValueError("Invalid or expired reset code")

    await service._update_password(
        web_account_id=account.id,
        new_password=new_password,
    )


async def reset_password_by_telegram_code(
    service: EmailRecoveryService,
    *,
    username: str,
    code: str,
    new_password: str,
) -> None:
    service._validate_new_password(new_password)
    normalized_username = service.normalize_username(username)

    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_username(normalized_username)

    if not account or account.user_telegram_id <= 0:
        raise ValueError("Invalid or expired reset code")

    verification = await service.challenge_service.verify_code(
        web_account_id=account.id,
        purpose=ChallengePurpose.PASSWORD_RESET,
        destination=str(account.user_telegram_id),
        code=code.strip(),
    )
    if not verification.ok:
        if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
            raise ValueError("Too many attempts. Request a new reset code.")
        raise ValueError("Invalid or expired reset code")

    await service._update_password(
        web_account_id=account.id,
        new_password=new_password,
    )


async def send_password_reset(
    service: EmailRecoveryService,
    *,
    account: WebAccountDto | None,
) -> None:
    if not account or not account.email_normalized:
        return

    challenge = await service.challenge_service.create(
        web_account_id=account.id or 0,
        purpose=ChallengePurpose.PASSWORD_RESET,
        channel=ChallengeChannel.EMAIL,
        destination=account.email_normalized,
        ttl_seconds=service.config.web_app.password_reset_ttl_seconds,
        attempts=service.config.web_app.auth_challenge_attempts,
        include_code=True,
        include_token=True,
        meta={"email": account.email_normalized},
    )

    reset_link = service._build_front_url(f"/auth/reset-password?token={challenge.token}")
    project_name = await service._get_branding_project_name()
    subject = f"{project_name} password reset"
    text_body = (
        "Use this code to reset your password:\n"
        f"{challenge.code}\n\n"
        "Or open the reset link:\n"
        f"{reset_link}\n\n"
        "If you did not request this, ignore this message."
    )
    sent = await service.email_sender.send(
        to_email=account.email_normalized,
        subject=subject,
        text_body=text_body,
    )
    if not sent:
        logger.warning(
            "Password reset email was not delivered to '{}'",
            account.email_normalized,
        )


async def send_password_reset_telegram_code(
    service: EmailRecoveryService,
    *,
    telegram_id: int,
    code: str,
    language: Locale | str | None = None,
) -> None:
    project_name = await service._get_branding_project_name()
    fallback_text_body = (
        f"Your {project_name} password reset code:\n"
        f"{code}\n\n"
        "If you did not request this, ignore this message."
    )
    text_body = fallback_text_body
    try:
        branding = await service.settings_service.get_branding_settings()
        template = service.settings_service.resolve_localized_branding_text(
            branding.verification.password_reset_telegram_template,
            language=language,
        )
        text_body = (
            service.settings_service.render_branding_text(
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
            "Failed to render branded Telegram password reset message for '{}': {}",
            telegram_id,
            exc,
        )
        text_body = fallback_text_body

    try:
        await service.bot.send_message(
            chat_id=telegram_id,
            text=text_body,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.warning(
            "Failed to deliver Telegram password reset code to '{}': {}",
            telegram_id,
            exc,
        )
