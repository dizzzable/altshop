from __future__ import annotations

from src.infrastructure.database.models.dto import UserDto, WebAccountDto


def resolve_public_username(
    user: UserDto,
    *,
    web_account: WebAccountDto | None = None,
) -> str:
    if user.username:
        return user.username
    if web_account and web_account.username:
        return web_account.username
    return str(user.telegram_id)
