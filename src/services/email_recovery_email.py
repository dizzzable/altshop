from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import WebAccountDto

from .auth_challenge import ChallengeChannel, ChallengeErrorReason, ChallengePurpose

if TYPE_CHECKING:
    from .email_recovery import EmailRecoveryService


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def set_email(
    service: EmailRecoveryService,
    *,
    web_account_id: int,
    email: str,
) -> WebAccountDto:
    normalized_email = normalize_email(email)
    if "@" not in normalized_email:
        raise ValueError("Invalid email format")

    async with service.uow:
        try:
            updated = await service.uow.repository.web_accounts.update(
                web_account_id,
                email=email.strip(),
                email_normalized=normalized_email,
                email_verified_at=None,
            )
            await service.uow.commit()
        except IntegrityError as exc:
            await service.uow.rollback()
            raise ValueError("Email is already used") from exc

    dto = WebAccountDto.from_model(updated)
    if not dto:
        raise ValueError("Web account not found")
    return dto


async def request_email_verification(
    service: EmailRecoveryService,
    *,
    web_account: WebAccountDto,
) -> bool:
    destination = web_account.email_normalized
    if not destination:
        raise ValueError("Recovery email is not set")

    challenge = await service.challenge_service.create(
        web_account_id=web_account.id or 0,
        purpose=ChallengePurpose.EMAIL_VERIFY,
        channel=ChallengeChannel.EMAIL,
        destination=destination,
        ttl_seconds=service.config.web_app.email_verify_ttl_seconds,
        attempts=service.config.web_app.auth_challenge_attempts,
        include_code=True,
        include_token=True,
        meta={"email": destination},
    )

    verify_link = service._build_front_url(
        f"/dashboard/settings?email_verify_token={challenge.token}"
    )
    project_name = await service._get_branding_project_name()
    subject = f"{project_name} email verification"
    text_body = (
        "Your verification code:\n"
        f"{challenge.code}\n\n"
        "Or open link:\n"
        f"{verify_link}\n\n"
        "If you did not request this, ignore this message."
    )
    return await service.email_sender.send(
        to_email=destination,
        subject=subject,
        text_body=text_body,
    )


async def confirm_email(
    service: EmailRecoveryService,
    *,
    web_account_id: int,
    code: str | None,
    token: str | None,
) -> WebAccountDto:
    if not code and not token:
        raise ValueError("Provide code or token")

    async with service.uow:
        account = await service.uow.repository.web_accounts.get(web_account_id)
        if not account:
            raise ValueError("Web account not found")
        destination = account.email_normalized

    if not destination:
        raise ValueError("Recovery email is not set")

    if token:
        verification = await service.challenge_service.verify_token(
            purpose=ChallengePurpose.EMAIL_VERIFY,
            token=token,
            web_account_id=web_account_id,
        )
    else:
        verification = await service.challenge_service.verify_code(
            web_account_id=web_account_id,
            purpose=ChallengePurpose.EMAIL_VERIFY,
            destination=destination,
            code=(code or "").strip(),
        )

    if not verification.ok:
        if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
            raise ValueError("Too many attempts. Request a new verification code.")
        raise ValueError("Invalid or expired verification data.")

    async with service.uow:
        updated = await service.uow.repository.web_accounts.update(
            web_account_id,
            email_verified_at=datetime_now(),
        )
        await service.uow.commit()

    dto = WebAccountDto.from_model(updated)
    if not dto:
        raise ValueError("Web account not found")
    return dto
