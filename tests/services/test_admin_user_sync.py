from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from src.bot.routers.dashboard.users.user.getters import (
    _build_give_access_getter_payload,
    _build_partner_settings_getter_payload,
    _build_referral_attach_results_payload,
    _build_subscription_getter_payload,
    _build_subscriptions_getter_payload,
    _build_transaction_getter_payload,
    _build_user_getter_payload,
    _build_web_bind_preview_getter_payload,
    _build_web_cabinet_getter_payload,
    _infer_panel_telegram_id_from_local_subscriptions,
    _resolve_effective_panel_telegram_id,
)
from src.bot.routers.dashboard.users.user.handlers import (
    _get_target_user_subscription_context,
    _resolve_admin_panel_telegram_id,
    _resolve_effective_subscription_owner,
)
from src.core.enums import DeviceType, PlanType, SubscriptionStatus, UserRole
from src.infrastructure.database.models.dto import (
    PlanSnapshotDto,
    SubscriptionDto,
    UserDto,
    WebAccountDto,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def _build_subscription(subscription_id: int) -> SubscriptionDto:
    return SubscriptionDto(
        id=subscription_id,
        user_remna_id=UUID(f"00000000-0000-0000-0000-00000000000{subscription_id}"),
        user_telegram_id=605,
        status=SubscriptionStatus.ACTIVE,
        traffic_limit=100,
        device_limit=1,
        internal_squads=[],
        external_squad=None,
        expire_at=datetime.now(timezone.utc) + timedelta(days=30),
        url=f"https://example.com/{subscription_id}",
        device_type=DeviceType.OTHER,
        plan=PlanSnapshotDto(
            id=1,
            name="StarterPack",
            tag="starter",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=1,
            duration=30,
            internal_squads=[],
            external_squad=None,
        ),
    )


def _build_remna_user(*, telegram_id: str, username: str) -> SimpleNamespace:
    return SimpleNamespace(
        telegram_id=telegram_id,
        username=username,
        active_internal_squads=[],
        subscription_url=f"https://example.com/remna/{username}",
        used_traffic_bytes=256,
        traffic_limit_bytes=1024,
        first_connected=None,
        last_connected_node=None,
        last_connected_node_uuid=None,
    )


def test_resolve_effective_subscription_owner_prefers_panel_identity() -> None:
    target_user = UserDto(telegram_id=8, name="Shadow", role=UserRole.USER)
    owner_user = UserDto(telegram_id=605, name="Linked", role=UserRole.USER)
    dialog_manager = SimpleNamespace(dialog_data={"panel_telegram_id": "605"})

    async def get_user(telegram_id: int):
        if telegram_id == 605:
            return owner_user
        return target_user

    user_service = SimpleNamespace(get=get_user)

    resolved = run_async(
        _resolve_effective_subscription_owner(
            dialog_manager,
            user_service,
            target_user,
        )
    )

    assert resolved.telegram_id == 605


def test_target_user_subscription_context_uses_effective_owner_subscriptions() -> None:
    target_user = UserDto(telegram_id=8, name="Shadow", role=UserRole.USER)
    owner_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=_build_subscription(2),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={"target_telegram_id": 8, "panel_telegram_id": 605},
    )

    async def get_user(telegram_id: int):
        if telegram_id == 8:
            return target_user
        if telegram_id == 605:
            return owner_user
        return None

    async def get_subscriptions(telegram_id: int):
        assert telegram_id == 605
        return [_build_subscription(1), _build_subscription(2)]

    user_service = SimpleNamespace(get=get_user)
    subscription_service = SimpleNamespace(get_all_by_user=get_subscriptions)

    resolved_user, visible_subscriptions, selected_subscription = run_async(
        _get_target_user_subscription_context(
            dialog_manager,
            user_service,
            subscription_service,
        )
    )

    assert resolved_user.telegram_id == 605
    assert len(visible_subscriptions) == 2
    assert selected_subscription.id == 2


def test_effective_panel_telegram_id_prefers_negative_session_override() -> None:
    target_user = UserDto(telegram_id=-12, name="Web only", role=UserRole.USER)
    dialog_manager = SimpleNamespace(dialog_data={"panel_sync_override_telegram_id": "-605"})
    web_account_service = SimpleNamespace(get_by_user_telegram_id=AsyncMock())
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock())
    remnawave_service = SimpleNamespace(get_user=AsyncMock())

    result = run_async(
        _resolve_effective_panel_telegram_id(
            dialog_manager=dialog_manager,
            target_user=target_user,
            web_account_service=web_account_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result == -605
    web_account_service.get_by_user_telegram_id.assert_not_called()
    subscription_service.get_all_by_user.assert_not_called()


def test_effective_panel_telegram_id_infers_from_remnawave_profile() -> None:
    target_user = UserDto(
        telegram_id=-12,
        name="Web only",
        role=UserRole.USER,
        current_subscription=_build_subscription(1),
    )
    dialog_manager = SimpleNamespace(dialog_data={})
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(
            return_value=WebAccountDto(
                id=7,
                user_telegram_id=-12,
                username="alice",
                password_hash="hash",
            )
        )
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=[_build_subscription(1)])
    )
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=SimpleNamespace(telegram_id="605"))
    )

    result = run_async(
        _resolve_effective_panel_telegram_id(
            dialog_manager=dialog_manager,
            target_user=target_user,
            web_account_service=web_account_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result == 605
    subscription_service.get_all_by_user.assert_awaited_once_with(-12)


def test_resolve_admin_panel_telegram_id_prefers_effective_dialog_value() -> None:
    target_user = UserDto(telegram_id=-12, name="Web only", role=UserRole.USER)
    dialog_manager = SimpleNamespace(
        dialog_data={
            "panel_sync_override_telegram_id": -605,
            "effective_panel_telegram_id": 605,
            "panel_telegram_id": -12,
        }
    )

    result = _resolve_admin_panel_telegram_id(dialog_manager, target_user)

    assert result == 605


def test_infer_panel_telegram_id_uses_batched_remna_lookup_after_initial_probe() -> None:
    subscriptions = [_build_subscription(1), _build_subscription(2)]
    target_user = UserDto(
        telegram_id=-12,
        name="Web only",
        role=UserRole.USER,
        current_subscription=subscriptions[1],
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=subscriptions)
    )
    remna_users_by_uuid = {
        subscriptions[0].user_remna_id: _build_remna_user(telegram_id="605", username="alpha"),
        subscriptions[1].user_remna_id: _build_remna_user(telegram_id="605", username="beta"),
    }
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=remna_users_by_uuid[subscriptions[1].user_remna_id]),
        get_users_map_by_telegram_id=AsyncMock(return_value=remna_users_by_uuid),
    )

    result = run_async(
        _infer_panel_telegram_id_from_local_subscriptions(
            target_user=target_user,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result == 605
    remnawave_service.get_user.assert_awaited_once_with(subscriptions[1].user_remna_id)
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(605)


def test_infer_panel_telegram_id_returns_none_for_ambiguous_batched_owner_map() -> None:
    subscriptions = [_build_subscription(1), _build_subscription(2)]
    target_user = UserDto(
        telegram_id=-12,
        name="Web only",
        role=UserRole.USER,
        current_subscription=subscriptions[1],
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=subscriptions)
    )
    remnawave_service = SimpleNamespace(
        get_user=AsyncMock(return_value=_build_remna_user(telegram_id="605", username="beta")),
        get_users_map_by_telegram_id=AsyncMock(
            return_value={
                subscriptions[0].user_remna_id: _build_remna_user(
                    telegram_id="605",
                    username="alpha",
                ),
                subscriptions[1].user_remna_id: _build_remna_user(
                    telegram_id="777",
                    username="beta",
                ),
            }
        ),
    )

    result = run_async(
        _infer_panel_telegram_id_from_local_subscriptions(
            target_user=target_user,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result is None
    remnawave_service.get_user.assert_awaited_once_with(subscriptions[1].user_remna_id)
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(605)


def test_subscription_getter_uses_batched_remna_user_for_selected_subscription() -> None:
    subscriptions = [_build_subscription(1), _build_subscription(2)]
    target_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=subscriptions[1],
    )
    dialog_manager = SimpleNamespace(dialog_data={"target_telegram_id": 605})
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock(return_value=subscriptions))
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(
            return_value={
                subscriptions[0].user_remna_id: _build_remna_user(
                    telegram_id="605",
                    username="alpha",
                ),
                subscriptions[1].user_remna_id: _build_remna_user(
                    telegram_id="605",
                    username="beta",
                ),
            }
        ),
        get_user=AsyncMock(),
    )

    result = run_async(
        _build_subscription_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result["profile_name"] == "beta"
    assert result["subscription_index"] == 2
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(605)
    remnawave_service.get_user.assert_not_called()


def test_subscription_getter_falls_back_to_direct_lookup_when_batch_unavailable() -> None:
    subscriptions = [_build_subscription(1), _build_subscription(2)]
    target_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=subscriptions[1],
    )
    dialog_manager = SimpleNamespace(dialog_data={"target_telegram_id": 605})
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock(return_value=subscriptions))
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(side_effect=RuntimeError("boom")),
        get_user=AsyncMock(return_value=_build_remna_user(telegram_id="605", username="beta")),
    )

    result = run_async(
        _build_subscription_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result["profile_name"] == "beta"
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(605)
    remnawave_service.get_user.assert_awaited_once_with(subscriptions[1].user_remna_id)


def test_subscription_getter_falls_back_to_direct_lookup_when_selected_uuid_missing_from_batch(
) -> None:
    subscriptions = [_build_subscription(1), _build_subscription(2)]
    target_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=subscriptions[1],
    )
    dialog_manager = SimpleNamespace(dialog_data={"target_telegram_id": 605})
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock(return_value=subscriptions))
    remnawave_service = SimpleNamespace(
        get_users_map_by_telegram_id=AsyncMock(
            return_value={
                subscriptions[0].user_remna_id: _build_remna_user(
                    telegram_id="605",
                    username="alpha",
                ),
            }
        ),
        get_user=AsyncMock(return_value=_build_remna_user(telegram_id="605", username="beta")),
    )

    result = run_async(
        _build_subscription_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert result["profile_name"] == "beta"
    remnawave_service.get_users_map_by_telegram_id.assert_awaited_once_with(605)
    remnawave_service.get_user.assert_awaited_once_with(subscriptions[1].user_remna_id)


def test_user_getter_payload_uses_effective_panel_identity_and_owner_subscriptions() -> None:
    actor = UserDto(telegram_id=1, name="Admin", role=UserRole.DEV)
    target_user = UserDto(telegram_id=-12, name="Web only", role=UserRole.USER)
    owner_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=_build_subscription(2),
    )
    dialog_manager = SimpleNamespace(start_data={"target_telegram_id": -12}, dialog_data={})
    web_account = WebAccountDto(
        id=7,
        user_telegram_id=605,
        username="alice",
        password_hash="hash",
    )
    config = SimpleNamespace(bot=SimpleNamespace(dev_id=[1]))
    user_service = SimpleNamespace(
        get=AsyncMock(
            side_effect=lambda telegram_id: (
                target_user
                if telegram_id == -12
                else owner_user
                if telegram_id == 605
                else None
            )
        )
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=[_build_subscription(1), _build_subscription(2)])
    )
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(return_value=web_account)
    )
    remnawave_service = SimpleNamespace(get_user=AsyncMock())
    settings_service = SimpleNamespace(
        get_referral_settings=AsyncMock(return_value=SimpleNamespace())
    )
    referral_service = SimpleNamespace(has_referral_attribution=AsyncMock(return_value=False))
    partner_service = SimpleNamespace(
        get_partner_by_user=AsyncMock(return_value=None),
        has_partner_attribution=AsyncMock(return_value=False),
    )

    payload = run_async(
        _build_user_getter_payload(
            dialog_manager=dialog_manager,
            config=config,
            user=actor,
            user_service=user_service,
            web_account_service=web_account_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
            settings_service=settings_service,
            referral_service=referral_service,
            partner_service=partner_service,
        )
    )

    assert payload["effective_panel_telegram_id"] == "605"
    assert payload["subscriptions_count"] == 2
    assert payload["has_subscription"] is True
    subscription_service.get_all_by_user.assert_awaited_once_with(605)


def test_subscriptions_getter_payload_uses_effective_owner_subscriptions() -> None:
    target_user = UserDto(telegram_id=8, name="Shadow", role=UserRole.USER)
    owner_user = UserDto(
        telegram_id=605,
        name="Linked",
        role=UserRole.USER,
        current_subscription=_build_subscription(2),
    )
    dialog_manager = SimpleNamespace(
        dialog_data={"target_telegram_id": 8, "panel_telegram_id": 605}
    )
    user_service = SimpleNamespace(
        get=AsyncMock(
            side_effect=lambda telegram_id: (
                target_user
                if telegram_id == 8
                else owner_user
                if telegram_id == 605
                else None
            )
        )
    )
    subscription_service = SimpleNamespace(
        get_all_by_user=AsyncMock(return_value=[_build_subscription(1), _build_subscription(2)])
    )
    i18n = SimpleNamespace(get=lambda key, **kwargs: f"{key}:{kwargs}" if kwargs else key)

    payload = run_async(
        _build_subscriptions_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            subscription_service=subscription_service,
            i18n=i18n,
        )
    )

    assert payload["count"] == 2
    assert payload["has_multiple_subscriptions"] is True
    subscription_service.get_all_by_user.assert_awaited_once_with(605)


def test_web_cabinet_getter_payload_exposes_effective_panel_id_and_override_flags() -> None:
    target_user = UserDto(telegram_id=-12, name="Web only", role=UserRole.USER)
    dialog_manager = SimpleNamespace(
        dialog_data={"target_telegram_id": -12, "panel_sync_override_telegram_id": "-777"}
    )
    web_account = WebAccountDto(
        id=7,
        user_telegram_id=605,
        username="alice",
        password_hash="hash",
    )
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(return_value=web_account)
    )
    subscription_service = SimpleNamespace(get_all_by_user=AsyncMock())
    remnawave_service = SimpleNamespace(get_user=AsyncMock())

    payload = run_async(
        _build_web_cabinet_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            web_account_service=web_account_service,
            subscription_service=subscription_service,
            remnawave_service=remnawave_service,
        )
    )

    assert payload["effective_panel_telegram_id"] == "-777"
    assert payload["has_panel_sync_override"] is True
    assert payload["panel_sync_override_telegram_id"] == "-777"
    subscription_service.get_all_by_user.assert_not_called()


def test_referral_attach_results_payload_formats_found_users_with_web_logins() -> None:
    target_user = UserDto(telegram_id=605, name="Target", role=UserRole.USER)
    found_users = [
        UserDto(telegram_id=700, name="Alice", role=UserRole.USER),
        UserDto(telegram_id=701, name="Bob", role=UserRole.USER),
    ]
    dialog_manager = SimpleNamespace(dialog_data={"target_telegram_id": 605})
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    web_account_service = SimpleNamespace(
        get_by_user_telegram_id=AsyncMock(
            side_effect=lambda telegram_id: (
                WebAccountDto(
                    id=telegram_id,
                    user_telegram_id=telegram_id,
                    username=f"user{telegram_id}",
                    password_hash="hash",
                )
                if telegram_id == 700
                else None
            )
        )
    )

    payload = run_async(
        _build_referral_attach_results_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            web_account_service=web_account_service,
            found_users=found_users,
        )
    )

    assert payload["count"] == 2
    assert payload["found_users"][0]["display"] == "700 (Alice) • @user700"
    assert payload["found_users"][1]["display"] == "701 (Bob)"


def test_give_access_getter_payload_marks_allowed_plan_selection() -> None:
    target_user = UserDto(telegram_id=605, name="Target", role=UserRole.USER)
    dialog_manager = SimpleNamespace(dialog_data={"target_telegram_id": 605})
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    plan_service = SimpleNamespace(
        get_allowed_plans=AsyncMock(
            return_value=[
                SimpleNamespace(id=1, name="Starter", allowed_user_ids=[605]),
                SimpleNamespace(id=2, name="Family", allowed_user_ids=[]),
            ]
        )
    )

    payload = run_async(
        _build_give_access_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            plan_service=plan_service,
        )
    )

    assert payload["plans"][0]["selected"] is True
    assert payload["plans"][1]["selected"] is False


def test_transaction_getter_payload_formats_transaction_detail_fields() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={"target_telegram_id": 605, "selected_transaction": "txn-1"}
    )
    transaction = SimpleNamespace(
        is_test=False,
        payment_id="payment-id",
        purchase_type="NEW",
        status="COMPLETED",
        gateway_type="ROBOKASSA",
        pricing=SimpleNamespace(final_amount=10, discount_percent=5, original_amount=12),
        currency=SimpleNamespace(symbol="₽"),
        created_at=datetime.now(timezone.utc),
        plan=SimpleNamespace(
            name="Starter",
            type="BOTH",
            traffic_limit=100,
            device_limit=1,
            duration=30,
        ),
    )
    transaction_service = SimpleNamespace(get=AsyncMock(return_value=transaction))

    payload = run_async(
        _build_transaction_getter_payload(
            dialog_manager=dialog_manager,
            transaction_service=transaction_service,
        )
    )

    assert payload["payment_id"] == "payment-id"
    assert payload["currency"] == "₽"
    assert payload["plan_name"] == "Starter"


def test_partner_settings_getter_payload_prefers_individual_values() -> None:
    target_user = UserDto(telegram_id=605, name="Linked", role=UserRole.USER)
    dialog_manager = SimpleNamespace(dialog_data={"target_telegram_id": 605})
    user_service = SimpleNamespace(get=AsyncMock(return_value=target_user))
    partner = SimpleNamespace(
        individual_settings=SimpleNamespace(
            use_global_settings=False,
            accrual_strategy=SimpleNamespace(value="ON_FIRST_PAYMENT"),
            reward_type=SimpleNamespace(value="FIXED_AMOUNT"),
            level1_percent=11,
            level2_percent=None,
            level3_percent=33,
            level1_fixed_amount=5000,
            level2_fixed_amount=None,
            level3_fixed_amount=9000,
        )
    )
    partner_service = SimpleNamespace(get_partner_by_user=AsyncMock(return_value=partner))
    settings_service = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                partner=SimpleNamespace(
                    level1_percent=5,
                    level2_percent=10,
                    level3_percent=15,
                )
            )
        )
    )

    payload = run_async(
        _build_partner_settings_getter_payload(
            dialog_manager=dialog_manager,
            user_service=user_service,
            partner_service=partner_service,
            settings_service=settings_service,
        )
    )

    assert payload["use_global_settings"] is False
    assert payload["accrual_strategy"] == "ON_FIRST_PAYMENT"
    assert payload["reward_type"] == "FIXED_AMOUNT"
    assert payload["level1_percent"] == 11
    assert payload["level2_percent"] == 10
    assert payload["level3_percent"] == 33
    assert payload["level1_fixed"] == 50
    assert payload["level2_fixed"] == 0
    assert payload["level3_fixed"] == 90


def test_web_bind_preview_getter_payload_formats_rows_and_target_state() -> None:
    dialog_manager = SimpleNamespace(
        dialog_data={
            "web_bind_target_telegram_id": 605,
            "web_bind_source_subscriptions": [
                {
                    "subscription_id": 1,
                    "owner_kind": "WEB",
                    "plan_name": "Starter",
                    "profile_name": "alpha",
                    "status": "ACTIVE",
                }
            ],
            "web_bind_target_subscriptions": [
                {
                    "subscription_id": 2,
                    "owner_kind": "TELEGRAM",
                    "plan_name": "Family",
                    "profile_name": None,
                    "status": "EXPIRED",
                }
            ],
            "web_bind_keep_subscription_ids": [1],
            "web_bind_target_exists": True,
            "web_bind_target_name": "Linked",
            "web_bind_target_web_login": "alice",
            "web_bind_target_web_account_exists": True,
            "web_bind_target_web_account_reclaimable": False,
            "web_bind_target_web_account_bootstrapped": True,
            "web_bind_target_has_material_data": True,
            "web_bind_target_account_will_be_replaced": True,
        }
    )
    i18n = SimpleNamespace(
        get=lambda key, **kwargs: {
            "msg-common-empty-value": "<empty>",
            "msg-user-web-bind-target-occupied-real": "occupied-real",
        }.get(key, key)
    )

    payload = run_async(
        _build_web_bind_preview_getter_payload(
            dialog_manager=dialog_manager,
            i18n=i18n,
        )
    )

    assert payload["target_telegram_id"] == "605"
    assert payload["target_state_summary"] == "occupied-real"
    assert payload["has_source_subscriptions"] is True
    assert payload["has_target_subscriptions"] is True
    assert "[x] WEB | Starter | alpha | ACTIVE" in payload["source_subscriptions"][0]["display"]
    assert "[ ] TG | Family | <empty> | EXPIRED" in payload["target_subscriptions"][0]["display"]
