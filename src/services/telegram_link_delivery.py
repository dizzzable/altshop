from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from loguru import logger

from src.core.constants import T_ME
from src.core.enums import Locale
from src.infrastructure.database.models.dto import AuthChallengeDto, WebAccountDto

from .auth_challenge import ChallengeChannel, ChallengePurpose

if TYPE_CHECKING:
    from .telegram_link import TelegramLinkService


type TelegramLinkRequestPayload = tuple[bool, int, int, str | None, str | None]


async def request_code(
    service: TelegramLinkService,
    *,
    web_account: WebAccountDto,
    telegram_id: int,
    ttl_seconds: int,
    attempts: int,
    return_to_miniapp: bool = False,
) -> TelegramLinkRequestPayload:
    challenge = await service.challenge_service.create(
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
        async with service.uow:
            source_user = await service.uow.repository.users.get(web_account.user_telegram_id)
            if source_user:
                user_language = source_user.language

    branding = await service.settings_service.get_branding_settings()
    template = service.settings_service.resolve_localized_branding_text(
        branding.verification.telegram_template,
        language=user_language,
    )
    message_text = service.settings_service.render_branding_text(
        template,
        placeholders={
            "project_name": branding.project_name,
            "code": code,
        },
    )

    try:
        sent_message = await service.bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        delivered = False
        logger.warning(f"Failed to deliver Telegram link code to '{telegram_id}': {exc}")
    else:
        try:
            await save_telegram_message_meta(
                service,
                challenge_id=challenge.challenge.id,
                current_meta=challenge.challenge.meta,
                chat_id=telegram_id,
                message_id=sent_message.message_id,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to save verification message meta for chat '{telegram_id}': {exc}"
            )

    return (
        delivered,
        ttl_seconds,
        telegram_id,
        await build_bot_confirm_url(
            service,
            challenge.token,
            return_to_miniapp=return_to_miniapp,
        ),
        await build_bot_confirm_deep_link(
            service,
            challenge.token,
            return_to_miniapp=return_to_miniapp,
        ),
    )


async def save_telegram_message_meta(
    service: TelegramLinkService,
    *,
    challenge_id: UUID,
    current_meta: Optional[dict[str, object]],
    chat_id: int,
    message_id: int,
) -> None:
    meta = dict(current_meta or {})
    meta["telegram_chat_id"] = chat_id
    meta["telegram_message_id"] = message_id

    async with service.uow:
        await service.uow.repository.auth_challenges.update(challenge_id, meta=meta)
        await service.uow.commit()


async def delete_verification_message(
    service: TelegramLinkService,
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
        await service.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:
        logger.debug(
            f"Failed to delete verification message '{message_id}' for chat '{chat_id}': {exc}"
        )


async def build_bot_confirm_url(
    service: TelegramLinkService,
    token: str | None,
    *,
    return_to_miniapp: bool,
) -> str | None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None

    try:
        bot_info = await service.bot.get_me()
    except Exception as exc:
        logger.warning(f"Failed to resolve Telegram link bot username: {exc}")
        return None

    username = (bot_info.username or "").strip().lstrip("@")
    if not username:
        return None

    start_prefix = "tglinkapp_" if return_to_miniapp else "tglink_"
    return f"{T_ME}{username}?start={start_prefix}{normalized_token}"


async def build_bot_confirm_deep_link(
    service: TelegramLinkService,
    token: str | None,
    *,
    return_to_miniapp: bool,
) -> str | None:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        return None

    try:
        bot_info = await service.bot.get_me()
    except Exception as exc:
        logger.warning(f"Failed to resolve Telegram link bot username for deep link: {exc}")
        return None

    username = (bot_info.username or "").strip().lstrip("@")
    if not username:
        return None

    start_prefix = "tglinkapp_" if return_to_miniapp else "tglink_"
    return f"tg://resolve?domain={username}&start={start_prefix}{normalized_token}"
