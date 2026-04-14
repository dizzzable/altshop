from __future__ import annotations

from typing import TYPE_CHECKING

from src.infrastructure.database.models.dto import WebAccountDto

from .auth_challenge import ChallengeErrorReason, ChallengePurpose

if TYPE_CHECKING:
    from .telegram_link import TelegramLinkService


type TelegramLinkConfirmPayload = tuple[WebAccountDto, int]


async def confirm_code(
    service: TelegramLinkService,
    *,
    web_account: WebAccountDto,
    telegram_id: int,
    code: str,
) -> TelegramLinkConfirmPayload:
    verification = await service.challenge_service.verify_code(
        web_account_id=web_account.id or 0,
        purpose=ChallengePurpose.TG_LINK,
        destination=str(telegram_id),
        code=code.strip(),
    )
    if not verification.ok:
        if verification.reason == ChallengeErrorReason.TOO_MANY_ATTEMPTS:
            raise service._telegram_link_error(
                code="TOO_MANY_ATTEMPTS",
                message="Too many attempts. Request a new code.",
            )
        raise service._telegram_link_error(
            code="INVALID_OR_EXPIRED_CODE",
            message="Invalid or expired code.",
        )

    account = await service._safe_auto_link(
        web_account_id=web_account.id or 0,
        telegram_id=telegram_id,
    )
    await service._delete_verification_message(
        challenge=verification.challenge,
        fallback_chat_id=telegram_id,
    )
    return account, telegram_id


async def bind_existing_account(
    service: TelegramLinkService,
    *,
    web_account_id: int,
    telegram_id: int,
) -> WebAccountDto:
    return await service._safe_auto_link(
        web_account_id=web_account_id,
        telegram_id=telegram_id,
    )


async def confirm_token(
    service: TelegramLinkService,
    *,
    telegram_id: int,
    token: str,
) -> TelegramLinkConfirmPayload:
    verification = await service.challenge_service.verify_token(
        purpose=ChallengePurpose.TG_LINK,
        token=token.strip(),
        destination=str(telegram_id),
    )
    if not verification.ok or verification.challenge is None:
        raise service._telegram_link_error(
            code="INVALID_OR_EXPIRED_CODE",
            message="Invalid or expired code.",
        )

    account = await service._safe_auto_link(
        web_account_id=verification.challenge.web_account_id,
        telegram_id=telegram_id,
    )
    await service._delete_verification_message(
        challenge=verification.challenge,
        fallback_chat_id=telegram_id,
    )
    return account, telegram_id
