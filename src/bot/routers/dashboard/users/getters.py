from typing import Any, cast

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.core.utils.formatters import format_percent
from src.infrastructure.database.models.dto import UserDto
from src.services.referral import ReferralService
from src.services.user import UserService
from src.services.web_account import WebAccountService


def _format_user_row(
    user: UserDto,
    *,
    web_login: str | None,
    i18n: TranslatorRunner,
) -> str:
    base = f"{user.telegram_id} ({user.name})"
    details: list[str] = []

    if user.telegram_id < 0:
        details.append(i18n.get("msg-users-row-web-only"))

    if web_login:
        details.append(i18n.get("msg-users-row-web-login", login=web_login))

    if not details:
        return base

    return f"{base} • " + " • ".join(details)


async def _build_user_rows(
    users: list[UserDto],
    *,
    web_account_service: WebAccountService,
    i18n: TranslatorRunner,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for user in users:
        web_account = await web_account_service.get_by_user_telegram_id(user.telegram_id)
        rows.append(
            {
                "telegram_id": user.telegram_id,
                "display": _format_user_row(
                    user,
                    web_login=web_account.username if web_account else None,
                    i18n=i18n,
                ),
            }
        )
    return rows


@inject
async def search_results_getter(
    dialog_manager: DialogManager,
    web_account_service: FromDishka[WebAccountService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    start_data = cast(dict[str, Any], dialog_manager.start_data)
    found_users_data: list[str] = start_data["found_users"]
    found_users: list[UserDto] = [
        UserDto.model_validate_json(json_string) for json_string in found_users_data
    ]

    return {
        "found_users": await _build_user_rows(
            found_users,
            web_account_service=web_account_service,
            i18n=i18n,
        ),
        "count": len(found_users),
    }


@inject
async def recent_registered_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    users = await user_service.get_recent_registered_users()
    return {
        "recent_registered_users": await _build_user_rows(
            users,
            web_account_service=web_account_service,
            i18n=i18n,
        )
    }


@inject
async def recent_activity_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    users = await user_service.get_recent_activity_users()
    return {
        "recent_activity_users": await _build_user_rows(
            users,
            web_account_service=web_account_service,
            i18n=i18n,
        )
    }


@inject
async def blacklist_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    blocked_users = await user_service.get_blocked_users()
    count_users = await user_service.count()

    return {
        "blocked_users_exists": bool(blocked_users),
        "blocked_users": await _build_user_rows(
            blocked_users,
            web_account_service=web_account_service,
            i18n=i18n,
        ),
        "count_blocked": len(blocked_users),
        "count_users": count_users,
        "percent": format_percent(part=len(blocked_users), whole=count_users),
    }


@inject
async def referrals_getter(
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    referrals, total = await referral_service.get_referrals_page(page=1, limit=50)

    rows: list[dict[str, Any]] = []
    for referral in referrals:
        referred = referral.referred
        referrer = referral.referrer
        source = getattr(referral.invite_source, "value", str(referral.invite_source))
        qualified_channel = (
            getattr(referral.qualified_purchase_channel, "value", "UNKNOWN")
            if referral.qualified_at
            else "—"
        )
        invited_at = referral.created_at.strftime("%d.%m.%Y %H:%M") if referral.created_at else "—"
        rows.append(
            {
                "id": referred.telegram_id,
                "display": (
                    f"{referred.telegram_id} ({referred.name}) <- {referrer.telegram_id} "
                    f"| src:{source} | buy:{qualified_channel} | {invited_at}"
                ),
            }
        )

    return {
        "has_referrals": bool(rows),
        "referrals": rows,
        "count": total,
    }
