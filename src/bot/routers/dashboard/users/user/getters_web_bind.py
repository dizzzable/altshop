from __future__ import annotations

from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from fluentogram import TranslatorRunner

from src.services.user import UserService
from src.services.web_account import WebAccountService


@inject
async def web_bind_target_getter(
    dialog_manager: DialogManager,
    user_service: FromDishka[UserService],
    web_account_service: FromDishka[WebAccountService],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_web_bind_target_getter_payload(
        dialog_manager=dialog_manager,
        user_service=user_service,
        web_account_service=web_account_service,
    )


async def _build_web_bind_target_getter_payload(
    *,
    dialog_manager: DialogManager,
    user_service: UserService,
    web_account_service: WebAccountService,
) -> dict[str, Any]:
    target_telegram_id = dialog_manager.dialog_data["target_telegram_id"]
    target_user = await user_service.get(telegram_id=target_telegram_id)
    if not target_user:
        raise ValueError(f"User '{target_telegram_id}' not found")

    web_account = await web_account_service.get_by_user_telegram_id(target_telegram_id)
    return {
        "target_name": target_user.name,
        "target_telegram_id": str(target_user.telegram_id),
        "web_login": web_account.username if web_account else False,
        "has_web_account": bool(web_account),
        "web_account_provisional": bool(
            web_account and web_account.credentials_bootstrapped_at is None
        ),
    }


@inject
async def web_bind_preview_getter(
    dialog_manager: DialogManager,
    i18n: FromDishka[TranslatorRunner],
    **kwargs: Any,
) -> dict[str, Any]:
    return await _build_web_bind_preview_getter_payload(
        dialog_manager=dialog_manager,
        i18n=i18n,
    )


async def _build_web_bind_preview_getter_payload(
    *,
    dialog_manager: DialogManager,
    i18n: TranslatorRunner,
) -> dict[str, Any]:
    target_tg_id = dialog_manager.dialog_data.get("web_bind_target_telegram_id")
    source_items = list(dialog_manager.dialog_data.get("web_bind_source_subscriptions", []))
    target_items = list(dialog_manager.dialog_data.get("web_bind_target_subscriptions", []))
    kept_ids = {
        int(subscription_id)
        for subscription_id in dialog_manager.dialog_data.get("web_bind_keep_subscription_ids", [])
    }

    def _row(item: dict[str, Any]) -> dict[str, Any]:
        subscription_id = int(item["subscription_id"])
        profile_name = item.get("profile_name") or i18n.get("msg-common-empty-value")
        owner_label = "WEB" if item.get("owner_kind") == "WEB" else "TG"
        return {
            **item,
            "subscription_id": subscription_id,
            "display": (
                f"{'[x]' if subscription_id in kept_ids else '[ ]'} "
                f"{owner_label} | {item.get('plan_name', '-')} | "
                f"{profile_name} | {item.get('status', '-')}"
            ),
        }

    source_rows = [_row(item) for item in source_items]
    target_rows = [_row(item) for item in target_items]
    target_exists = bool(dialog_manager.dialog_data.get("web_bind_target_exists"))
    target_name = dialog_manager.dialog_data.get("web_bind_target_name") or False
    target_web_login = dialog_manager.dialog_data.get("web_bind_target_web_login") or False
    target_web_account_exists = bool(
        dialog_manager.dialog_data.get("web_bind_target_web_account_exists")
    )
    target_web_account_reclaimable = bool(
        dialog_manager.dialog_data.get("web_bind_target_web_account_reclaimable")
    )
    target_web_account_bootstrapped = bool(
        dialog_manager.dialog_data.get("web_bind_target_web_account_bootstrapped")
    )
    target_has_material_data = bool(
        dialog_manager.dialog_data.get("web_bind_target_has_material_data")
    )
    target_account_will_be_replaced = bool(
        dialog_manager.dialog_data.get("web_bind_target_account_will_be_replaced")
    )

    if target_web_account_reclaimable:
        target_state_summary = i18n.get("msg-user-web-bind-target-occupied-provisional")
    elif target_account_will_be_replaced:
        target_state_summary = i18n.get("msg-user-web-bind-target-occupied-real")
    elif target_exists:
        target_state_summary = i18n.get("msg-user-web-bind-target-existing")
    else:
        target_state_summary = i18n.get("msg-user-web-bind-target-missing")

    return {
        "target_telegram_id": str(target_tg_id) if target_tg_id is not None else False,
        "target_exists": target_exists,
        "target_name": target_name,
        "target_web_login": target_web_login,
        "target_web_account_exists": target_web_account_exists,
        "target_web_account_reclaimable": target_web_account_reclaimable,
        "target_web_account_bootstrapped": target_web_account_bootstrapped,
        "target_has_material_data": target_has_material_data,
        "target_account_will_be_replaced": target_account_will_be_replaced,
        "target_state_summary": target_state_summary,
        "source_subscriptions": source_rows,
        "target_subscriptions": target_rows,
        "has_source_subscriptions": bool(source_rows),
        "has_target_subscriptions": bool(target_rows),
    }
