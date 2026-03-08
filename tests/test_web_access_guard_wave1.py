import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from src.core.enums import AccessMode, Locale
from src.infrastructure.database.models.dto import UserDto, WebAccountDto
from src.services.web_access_guard import (
    CHANNEL_VERIFICATION_UNAVAILABLE,
    WEB_ACCESS_READ_ONLY_CODE,
    WebAccessGuardService,
    WebAccessStatus,
)


def _build_user() -> UserDto:
    return UserDto(
        telegram_id=101,
        username="tester",
        referral_code="ref101",
        name="Tester",
        language=Locale.EN,
    )


def _build_web_account() -> WebAccountDto:
    return WebAccountDto(
        id=7,
        user_telegram_id=101,
        username="tester",
        password_hash="hashed",
        token_version=0,
    )


def test_evaluate_user_access_downgrades_channel_outage_to_read_only() -> None:
    settings = SimpleNamespace(
        access_mode=AccessMode.PUBLIC,
        rules_required=False,
        channel_required=True,
        channel_id="@requiredchannel",
        channel_link=SecretStr("https://t.me/requiredchannel"),
        rules_link=SecretStr(""),
        get_url_channel_link="https://t.me/requiredchannel",
    )
    service = WebAccessGuardService(
        config=SimpleNamespace(),
        bot=SimpleNamespace(
            get_me=AsyncMock(return_value=SimpleNamespace(username="verify_bot")),
            get_chat_member=AsyncMock(side_effect=RuntimeError("telegram unavailable")),
        ),
        redis_client=SimpleNamespace(
            get=AsyncMock(return_value=None),
            setex=AsyncMock(),
        ),
        redis_repository=SimpleNamespace(),
        translator_hub=SimpleNamespace(),
        settings_service=SimpleNamespace(get=AsyncMock(return_value=settings)),
        web_account_service=SimpleNamespace(
            get_by_user_telegram_id=AsyncMock(return_value=_build_web_account())
        ),
    )

    access_status = asyncio.run(service.evaluate_user_access(user=_build_user()))

    assert access_status.access_level == "read_only"
    assert access_status.channel_check_status == "unavailable"
    assert access_status.unmet_requirements == [CHANNEL_VERIFICATION_UNAVAILABLE]
    assert access_status.can_use_product_features is False


def test_read_only_access_blocks_mutations_with_specific_error_code() -> None:
    access_status = WebAccessStatus(
        access_mode=AccessMode.PUBLIC.value,
        rules_required=False,
        channel_required=True,
        requires_telegram_id=True,
        access_level="read_only",
        channel_check_status="unavailable",
        rules_accepted=True,
        telegram_linked=True,
        channel_verified=False,
        linked_telegram_id=101,
        rules_link=None,
        channel_link="https://t.me/requiredchannel",
        tg_id_helper_bot_link="https://t.me/userinfobot",
        verification_bot_link="https://t.me/verify_bot",
        unmet_requirements=[CHANNEL_VERIFICATION_UNAVAILABLE],
        can_use_product_features=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        WebAccessGuardService.assert_can_use_product_features(access_status)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == WEB_ACCESS_READ_ONLY_CODE
    assert exc_info.value.detail["unmet_requirements"] == [CHANNEL_VERIFICATION_UNAVAILABLE]
