from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger

from src.core.security.password import hash_password, verify_password
from src.core.utils.branding import resolve_project_name
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto import WebAccountDto

if TYPE_CHECKING:
    from .email_recovery import EmailRecoveryService


async def change_password(
    service: EmailRecoveryService,
    *,
    web_account_id: int,
    current_password: str,
    new_password: str,
) -> WebAccountDto:
    service._validate_new_password(new_password)

    async with service.uow:
        account = await service.uow.repository.web_accounts.get(web_account_id)

    if not account:
        raise ValueError("Web account not found")
    if not verify_password(current_password, account.password_hash):
        raise ValueError("Invalid current password")

    return await service._update_password(
        web_account_id=web_account_id,
        new_password=new_password,
    )


async def issue_temporary_password_for_dev(
    service: EmailRecoveryService,
    *,
    target_telegram_id: int,
    ttl_seconds: int,
) -> tuple[str, str, datetime]:
    if ttl_seconds <= 0:
        raise ValueError("Invalid temporary password TTL")

    temp_password = f"Tmp{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime_now() + timedelta(seconds=ttl_seconds)

    async with service.uow:
        account = await service.uow.repository.web_accounts.get_by_user_telegram_id(
            target_telegram_id
        )
        if not account:
            raise ValueError("Web account not found")

        updated_account = await service.uow.repository.web_accounts.update(
            account.id,
            password_hash=hash_password(temp_password),
            token_version=account.token_version + 1,
            requires_password_change=True,
            temporary_password_expires_at=expires_at,
        )
        if not updated_account:
            raise ValueError("Web account not found")

        await service.uow.commit()

    return updated_account.username, temp_password, expires_at


def validate_new_password(new_password: str) -> None:
    if len(new_password) < 6:
        raise ValueError("Password must be at least 6 characters")


async def update_password(
    service: EmailRecoveryService,
    *,
    web_account_id: int,
    new_password: str,
) -> WebAccountDto:
    async with service.uow:
        account = await service.uow.repository.web_accounts.get(web_account_id)
        if not account:
            raise ValueError("Web account not found")

        updated_account = await service.uow.repository.web_accounts.update(
            web_account_id,
            password_hash=hash_password(new_password),
            token_version=account.token_version + 1,
            requires_password_change=False,
            temporary_password_expires_at=None,
        )
        if not updated_account:
            raise ValueError("Web account not found")

        await service.uow.commit()

    dto = WebAccountDto.from_model(updated_account)
    if not dto:
        raise ValueError("Web account not found")
    return dto


async def get_branding_project_name(service: EmailRecoveryService) -> str:
    try:
        branding = await service.settings_service.get_branding_settings()
    except Exception as exc:
        logger.warning("Failed to load branding settings for email recovery: {}", exc)
        return resolve_project_name(None)

    return resolve_project_name(branding.project_name)


def build_front_url(service: EmailRecoveryService, path: str) -> str:
    base_url = service.config.web_app.url_str.rstrip("/")
    if not base_url:
        base_url = f"https://{service.config.domain.get_secret_value()}/webapp"
    elif not base_url.endswith("/webapp"):
        base_url = f"{base_url}/webapp"

    if path.startswith("/"):
        return f"{base_url}{path}"
    return f"{base_url}/{path}"
