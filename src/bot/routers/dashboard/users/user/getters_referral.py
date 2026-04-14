from __future__ import annotations

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.infrastructure.database.models.dto import UserDto
from src.services.partner import PartnerService
from src.services.referral import ReferralService
from src.services.settings import SettingsService
from src.services.user import UserService
from src.services.web_account import WebAccountService


async def _build_attach_candidate_rows(
    users: list[UserDto],
    *,
    web_account_service: WebAccountService,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in users:
        web_account = await web_account_service.get_by_user_telegram_id(candidate.telegram_id)
        display = f"{candidate.telegram_id} ({candidate.name})"
        if web_account and web_account.username:
            display = f"{display} • @{web_account.username}"

        rows.append(
            {
                "telegram_id": candidate.telegram_id,
                "display": display,
            }
        )

    return rows


@inject
async def referral_attach_search_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_referral_attach_search_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
    )


async def _build_referral_attach_search_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    return {
        "target_name": target_user.name,
        "target_telegram_id": target_user.telegram_id,
    }


@inject
async def referral_attach_results_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    **kwargs: Any,
) -> dict[str, Any]:
    found_users_data = dialog_manager.dialog_data.get("referral_attach_found_users", [])
    found_users = [UserDto.model_validate_json(json_string) for json_string in found_users_data]
    return await _build_referral_attach_results_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        web_account_service=web_account_service,
        found_users=found_users,
    )


async def _build_referral_attach_results_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    web_account_service: WebAccountService,
    found_users: list[UserDto],
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    return {
        "target_name": target_user.name,
        "target_telegram_id": target_user.telegram_id,
        "count": len(found_users),
        "found_users": await _build_attach_candidate_rows(
            found_users,
            web_account_service=web_account_service,
        ),
    }


@inject
async def referral_attach_confirm_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    partner_service: FromDishka[PartnerService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_referral_attach_confirm_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        web_account_service=web_account_service,
        partner_service=partner_service,
    )


async def _build_referral_attach_confirm_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    web_account_service: WebAccountService,
    partner_service: PartnerService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    selected_referrer_telegram_id = dialog_manager.dialog_data.get(
        "referral_attach_selected_referrer_telegram_id"
    )

    target_user = await user_service.get(telegram_id=target_telegram_id)
    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    if selected_referrer_telegram_id is None:
        raise ValueError("Selected referrer is missing")

    referrer = await user_service.get(telegram_id=int(selected_referrer_telegram_id))
    if not referrer:
        raise ValueError(f"Referrer '{selected_referrer_telegram_id}' not found")

    referrer_web_account = await web_account_service.get_by_user_telegram_id(referrer.telegram_id)
    return {
        "target_name": target_user.name,
        "target_telegram_id": target_user.telegram_id,
        "referrer_name": referrer.name,
        "referrer_telegram_id": referrer.telegram_id,
        "referrer_web_login": (referrer_web_account.username if referrer_web_account else False),
        "referrer_is_partner": await partner_service.is_partner(referrer.telegram_id),
    }


@inject
async def referrals_getter(
    dialog_manager: DialogManager,
    referral_service: FromDishka[ReferralService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_referrals_getter_payload(
        dialog_manager=dialog_manager,
        referral_service=referral_service,
    )


async def _build_referrals_getter_payload(
    *,
    dialog_manager: DialogManager,
    referral_service: ReferralService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    referrals, total = await referral_service.get_referrals_page_by_referrer(
        target_telegram_id,
        page=1,
        limit=50,
    )

    rows: list[dict[str, Any]] = []
    for referral in referrals:
        referred = referral.referred
        source = getattr(referral.invite_source, "value", str(referral.invite_source))
        qualified_channel = (
            getattr(referral.qualified_purchase_channel, "value", "UNKNOWN")
            if referral.qualified_at
            else "—"
        )
        invited_at = (
            referral.created_at.strftime("%d.%m.%Y %H:%M") if referral.created_at else "—"
        )
        rows.append(
            {
                "id": referred.telegram_id,
                "display": (
                    f"{referred.telegram_id} ({referred.name}) | src:{source} "
                    f"| buy:{qualified_channel} | {invited_at}"
                ),
            }
        )

    return {
        "has_referrals": bool(rows),
        "referrals": rows,
        "count": total,
    }


@inject
async def referral_invite_settings_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    settings_service: FromDishka[SettingsService],
    referral_service: FromDishka[ReferralService],
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_referral_invite_settings_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        settings_service=settings_service,
        referral_service=referral_service,
        i18n=i18n,
    )


async def _build_referral_invite_settings_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    settings_service: SettingsService,
    referral_service: ReferralService,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)

    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    global_settings = await settings_service.get_referral_settings()
    effective = await referral_service.get_effective_invite_limits(target_user)
    individual = target_user.referral_invite_settings

    def _display(value: int | None) -> str:
        return str(value) if value is not None else i18n.get("msg-referral-invite-unset")

    return {
        "use_global_settings": individual.use_global_settings,
        "use_global": individual.use_global_settings,
        "ttl_enabled": individual.link_ttl_enabled,
        "slots_enabled": individual.slots_enabled,
        "ttl_value": _display(individual.link_ttl_seconds),
        "initial_slots": _display(individual.initial_slots),
        "refill_threshold": _display(individual.refill_threshold_qualified),
        "refill_amount": _display(individual.refill_amount),
        "effective_ttl_enabled": effective.link_ttl_enabled,
        "effective_slots_enabled": effective.slots_enabled,
        "effective_ttl_status": i18n.get(
            "msg-referral-invite-enabled-status",
            enabled=effective.link_ttl_enabled,
        ),
        "effective_slots_status": i18n.get(
            "msg-referral-invite-enabled-status",
            enabled=effective.slots_enabled,
        ),
        "effective_ttl_value": _display(effective.link_ttl_seconds),
        "effective_initial_slots": _display(effective.initial_slots),
        "effective_refill_threshold": _display(effective.refill_threshold_qualified),
        "effective_refill_amount": _display(effective.refill_amount),
        "global_ttl_enabled": global_settings.invite_limits.link_ttl_enabled,
        "global_slots_enabled": global_settings.invite_limits.slots_enabled,
    }
