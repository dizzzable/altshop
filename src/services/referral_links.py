from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, Optional, cast

import qrcode
from aiogram.types import BufferedInputFile, Message, TelegramObject
from PIL import Image

from src.core.constants import ASSETS_DIR, REFERRAL_PREFIX, T_ME
from src.core.enums import Command, ReferralLevel
from src.infrastructure.database.models.dto import UserDto

if TYPE_CHECKING:
    from .referral import ReferralService


async def get_ref_link(service: ReferralService, referral_payload: str) -> str:
    return f"{await service._get_bot_redirect_url()}?start={REFERRAL_PREFIX}{referral_payload}"


def generate_ref_qr_bytes(_service: ReferralService, url: str) -> bytes:
    qrcode_module = cast(Any, qrcode)
    qr: Any = qrcode_module.QRCode(
        version=1,
        error_correction=qrcode_module.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(url)
    qr.make(fit=True)

    qr_img_raw = qr.make_image(fill_color="black", back_color="white")
    qr_img: Image.Image
    if hasattr(qr_img_raw, "get_image"):
        qr_img = cast(Image.Image, qr_img_raw.get_image())
    else:
        qr_img = cast(Image.Image, qr_img_raw)

    qr_img = qr_img.convert("RGB")

    logo_path = ASSETS_DIR / "logo.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")

        qr_width, qr_height = qr_img.size
        logo_size = int(qr_width * 0.2)
        logo = logo.resize((logo_size, logo_size), resample=Image.Resampling.LANCZOS)

        pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
        qr_img.paste(logo, pos, mask=logo)

    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.getvalue()


def get_ref_qr(service: ReferralService, url: str) -> BufferedInputFile:
    return BufferedInputFile(file=service.generate_ref_qr_bytes(url), filename="ref_qr.png")


async def get_referrer_by_event(
    service: ReferralService,
    event: TelegramObject,
    user_telegram_id: int,
) -> Optional[UserDto]:
    code = service._extract_referral_payload_from_event(event)
    if not code:
        return None

    _, invite_referrer, invite_block_reason = await service.resolve_invite_token(
        code,
        user_telegram_id=user_telegram_id,
    )
    if invite_referrer and invite_block_reason is None:
        return invite_referrer

    return await service.get_partner_referrer_by_code(
        code,
        user_telegram_id=user_telegram_id,
    )


async def get_partner_referrer_by_event(
    service: ReferralService,
    event: TelegramObject,
    user_telegram_id: int,
) -> Optional[UserDto]:
    code = service._extract_referral_payload_from_event(event)
    if not code:
        return None

    return await service.get_partner_referrer_by_code(
        code,
        user_telegram_id=user_telegram_id,
    )


async def is_referral_event(
    service: ReferralService,
    event: TelegramObject,
    user_telegram_id: int,
) -> bool:
    code = service._extract_referral_payload_from_event(event)
    if not code:
        return False

    return await service.is_valid_invite_or_partner_code(
        code,
        user_telegram_id=user_telegram_id,
    )


def _extract_referral_payload_from_event(
    _service: ReferralService,
    event: TelegramObject,
) -> str | None:
    if not isinstance(event, Message) or not event.text:
        return None

    text = event.text
    if not text.startswith(f"/{Command.START.value.command}"):
        return None

    parts = text.split()
    if len(parts) <= 1:
        return None

    code_with_prefix = parts[1]
    if not code_with_prefix.startswith(REFERRAL_PREFIX):
        return None

    return code_with_prefix


def _define_referral_level(
    _service: ReferralService,
    parent_level: ReferralLevel | None,
) -> ReferralLevel:
    if parent_level is None:
        return ReferralLevel.FIRST

    next_level_value = parent_level.value + 1
    max_level_value = max(item.value for item in ReferralLevel)

    if next_level_value > max_level_value:
        return ReferralLevel(parent_level.value)

    return ReferralLevel(next_level_value)


async def _get_bot_redirect_url(service: ReferralService) -> str:
    if service._bot_username is None:
        service._bot_username = (await service.bot.get_me()).username
    return f"{T_ME}{service._bot_username}"
